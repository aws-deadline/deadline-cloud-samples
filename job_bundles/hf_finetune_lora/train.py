#!/usr/bin/env python3
"""HuggingFace QLoRA Fine-Tuning Script for AWS Deadline Cloud.

Loads a dataset from S3 (JSONL of instruction/response pairs), fine-tunes a
HuggingFace causal LM with LoRA (optionally 4-bit quantized), and saves the
adapter weights to the output directory.

Designed to run on a single GPU worker (e.g., NVIDIA L4 24GB).
"""
import argparse
import json
import os
import sys
import tempfile
from pathlib import Path
from urllib.parse import urlparse

import boto3
import torch
from datasets import Dataset
from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training
from transformers import (
    AutoModelForCausalLM,
    AutoTokenizer,
    BitsAndBytesConfig,
    DataCollatorForSeq2Seq,
    Trainer,
    TrainingArguments,
)


def log(msg: str) -> None:
    """Print a clearly-prefixed log line and flush, so it shows up in worker logs promptly."""
    print(f"[train] {msg}", flush=True)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    # Model
    p.add_argument("--base-model", required=True, help="HF model ID, e.g. Qwen/Qwen2.5-1.5B")
    p.add_argument("--hf-token", default="", help="HuggingFace token for gated models (optional)")
    p.add_argument("--use-qlora", default="yes", choices=["yes", "no"],
                   help="Use 4-bit quantization (QLoRA)")
    # Dataset (one of --dataset-path or --dataset-s3-uri must be set)
    p.add_argument("--dataset-path", default="",
                   help="Local file or directory containing JSONL training data. "
                        "If a directory, all *.jsonl files in it are concatenated.")
    p.add_argument("--dataset-s3-uri", default="",
                   help="s3://bucket/path/train.jsonl or s3://bucket/prefix/ "
                        "(overrides --dataset-path when set)")
    p.add_argument("--instruction-column", default="instruction")
    p.add_argument("--response-column", default="output")
    p.add_argument("--max-samples", type=int, default=0,
                   help="Cap dataset size for fast tests; 0 = use all")
    # LoRA
    p.add_argument("--lora-rank", type=int, default=16)
    p.add_argument("--lora-alpha", type=int, default=32)
    p.add_argument("--lora-dropout", type=float, default=0.05)
    # Training
    p.add_argument("--learning-rate", type=float, default=2e-4)
    p.add_argument("--epochs", type=int, default=3)
    p.add_argument("--per-device-batch-size", type=int, default=4)
    p.add_argument("--grad-accum-steps", type=int, default=4)
    p.add_argument("--max-seq-length", type=int, default=512)
    p.add_argument("--warmup-ratio", type=float, default=0.03)
    p.add_argument("--logging-steps", type=int, default=5)
    p.add_argument("--save-steps", type=int, default=100)
    # Output
    p.add_argument("--output-dir", required=True, help="Local directory to save the adapter")
    p.add_argument("--adapter-name", default="my-lora-adapter")
    # Cache (persists across jobs on the same worker)
    p.add_argument("--hf-cache-dir", default="/mnt/persistent/hf_cache")
    # Optional post-training smoke test
    p.add_argument("--run-tests", default="no", choices=["yes", "no"],
                   help="If yes, runs a small set of Saffron Stack test prompts after "
                        "training and prints answers to the log. Useful for quick "
                        "iteration on hyperparameters.")
    return p.parse_args()


def download_dataset_from_s3(s3_uri: str, local_dir: str) -> list[str]:
    """Download from an S3 URI (single file or prefix) into local_dir.

    Returns the list of local .jsonl file paths to load.
    """
    log(f"Downloading dataset from {s3_uri}")
    parsed = urlparse(s3_uri)
    if parsed.scheme != "s3":
        raise ValueError(f"Expected s3:// URI, got: {s3_uri}")
    bucket = parsed.netloc
    key = parsed.path.lstrip("/")
    s3 = boto3.client("s3")

    # Single file (URI doesn't end in / and the key has a file extension)
    if not s3_uri.endswith("/") and "." in os.path.basename(key):
        local_path = os.path.join(local_dir, os.path.basename(key))
        s3.download_file(bucket, key, local_path)
        log(f"  Downloaded {os.path.getsize(local_path)} bytes -> {local_path}")
        return [local_path]

    # Prefix — list and download all *.jsonl objects under it
    prefix = key if key.endswith("/") else key + "/"
    paginator = s3.get_paginator("list_objects_v2")
    downloaded = []
    for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
        for obj in page.get("Contents", []):
            if not obj["Key"].endswith(".jsonl"):
                continue
            # Preserve the key's path relative to the prefix so files with the
            # same basename under different sub-prefixes don't collide (e.g.
            # lunch/menu.jsonl vs dinner/menu.jsonl). Mirrors the local rglob path.
            rel_key = obj["Key"][len(prefix):]
            local_path = os.path.join(local_dir, rel_key)
            os.makedirs(os.path.dirname(local_path), exist_ok=True)
            s3.download_file(bucket, obj["Key"], local_path)
            downloaded.append(local_path)
            log(f"  Downloaded {obj['Size']} bytes -> {local_path}")
    if not downloaded:
        raise FileNotFoundError(f"No .jsonl files found under {s3_uri}")
    return downloaded


def collect_local_jsonl_files(path: str) -> list[str]:
    """Resolve a local file or directory into a list of .jsonl files.

    If a directory is given, recursively finds all .jsonl files inside
    (any depth). This lets users organize their data into thematic subfolders.
    """
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Dataset path does not exist: {path}")
    if p.is_file():
        return [str(p)]
    files = sorted(str(f) for f in p.rglob("*.jsonl"))
    if not files:
        raise FileNotFoundError(f"No .jsonl files found (recursively) in directory: {path}")
    return files


def load_jsonl_dataset(paths: list[str], instr_col: str, resp_col: str,
                       max_samples: int) -> Dataset:
    """Load and concatenate one or more JSONL files into a single HF Dataset."""
    records = []
    for path in paths:
        path_count = 0
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                rec = json.loads(line)
                if instr_col not in rec or resp_col not in rec:
                    raise KeyError(
                        f"Record in {path} missing required columns "
                        f"'{instr_col}' or '{resp_col}': {rec}"
                    )
                records.append({"instruction": rec[instr_col], "response": rec[resp_col]})
                path_count += 1
        log(f"  Loaded {path_count} records from {path}")
    if max_samples > 0:
        records = records[:max_samples]
    log(f"Total training examples: {len(records)}")
    return Dataset.from_list(records)


def format_example(example: dict, tokenizer, max_length: int) -> dict:
    """Render an instruction/response pair using the model's chat template and tokenize.

    We mask the prompt tokens with -100 so loss is computed only on the assistant's response.
    """
    messages = [
        {"role": "user", "content": example["instruction"]},
        {"role": "assistant", "content": example["response"]},
    ]
    # Full tokenized sequence (prompt + response)
    full = tokenizer.apply_chat_template(
        messages, tokenize=True, add_generation_prompt=False,
        truncation=True, max_length=max_length, return_dict=True,
    )
    # Just the prompt portion (so we can mask its tokens in labels)
    prompt = tokenizer.apply_chat_template(
        [messages[0]], tokenize=True, add_generation_prompt=True,
        truncation=True, max_length=max_length, return_dict=True,
    )
    input_ids = full["input_ids"]
    attention_mask = full["attention_mask"]
    labels = list(input_ids)
    prompt_len = len(prompt["input_ids"])
    for i in range(min(prompt_len, len(labels))):
        labels[i] = -100  # mask prompt — only learn from response tokens
    return {"input_ids": input_ids, "attention_mask": attention_mask, "labels": labels}


def main() -> int:
    args = parse_args()

    # Print environment summary up front to make debugging easy.
    log(f"PyTorch: {torch.__version__}, CUDA available: {torch.cuda.is_available()}")
    if torch.cuda.is_available():
        log(f"GPU: {torch.cuda.get_device_name(0)}, "
            f"VRAM: {torch.cuda.get_device_properties(0).total_memory / 1e9:.1f} GB")
    # Redact the HF token so it never lands in worker logs (shipped to CloudWatch).
    safe_args = {**vars(args), "hf_token": "***" if args.hf_token else ""}
    log(f"Args: {safe_args}")

    # HuggingFace token (only needed for gated models)
    if args.hf_token:
        os.environ["HF_TOKEN"] = args.hf_token
        os.environ["HUGGING_FACE_HUB_TOKEN"] = args.hf_token

    # Use the persistent volume for the HF cache so models survive across job sessions.
    os.makedirs(args.hf_cache_dir, exist_ok=True)
    os.environ["HF_HOME"] = args.hf_cache_dir
    os.environ["TRANSFORMERS_CACHE"] = args.hf_cache_dir
    log(f"HF cache dir: {args.hf_cache_dir}")

    # 1. Resolve dataset source: S3 URI takes precedence over local path
    if not args.dataset_s3_uri and not args.dataset_path:
        raise ValueError(
            "Either --dataset-s3-uri or --dataset-path must be provided."
        )
    with tempfile.TemporaryDirectory() as tmpdir:
        if args.dataset_s3_uri:
            log(f"Dataset source: S3 ({args.dataset_s3_uri})")
            files = download_dataset_from_s3(args.dataset_s3_uri, tmpdir)
        else:
            log(f"Dataset source: local ({args.dataset_path})")
            files = collect_local_jsonl_files(args.dataset_path)
        dataset = load_jsonl_dataset(
            files, args.instruction_column, args.response_column, args.max_samples,
        )

    # 2. Tokenizer
    log(f"Loading tokenizer for {args.base_model}")
    tokenizer = AutoTokenizer.from_pretrained(args.base_model, cache_dir=args.hf_cache_dir)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    # Some *base* checkpoints (e.g. mistralai/Mistral-7B-v0.3) ship without a
    # chat_template, so apply_chat_template() would raise. Install a minimal
    # ChatML fallback so any listed base model trains consistently.
    if tokenizer.chat_template is None:
        log("Tokenizer has no chat_template; installing a ChatML fallback.")
        tokenizer.chat_template = (
            "{% for message in messages %}"
            "{{ '<|im_start|>' + message['role'] + '\n' + message['content'] + '<|im_end|>' + '\n' }}"
            "{% endfor %}"
            "{% if add_generation_prompt %}{{ '<|im_start|>assistant\n' }}{% endif %}"
        )

    # 3. Model (with optional 4-bit quantization for QLoRA)
    quant_config = None
    if args.use_qlora == "yes":
        quant_config = BitsAndBytesConfig(
            load_in_4bit=True,
            bnb_4bit_quant_type="nf4",
            bnb_4bit_compute_dtype=torch.bfloat16,
            bnb_4bit_use_double_quant=True,
        )
        log("Using QLoRA (4-bit NF4 quantization, bf16 compute)")
    else:
        log("Using LoRA with bf16 model weights (no quantization)")

    log(f"Loading model {args.base_model}")
    model = AutoModelForCausalLM.from_pretrained(
        args.base_model,
        quantization_config=quant_config,
        torch_dtype=torch.bfloat16,
        device_map="auto",
        cache_dir=args.hf_cache_dir,
    )
    if args.use_qlora == "yes":
        model = prepare_model_for_kbit_training(model)

    # 4. LoRA config — target common attention projections; PEFT auto-discovers them.
    lora_config = LoraConfig(
        r=args.lora_rank,
        lora_alpha=args.lora_alpha,
        lora_dropout=args.lora_dropout,
        bias="none",
        task_type="CAUSAL_LM",
        target_modules=["q_proj", "k_proj", "v_proj", "o_proj",
                        "gate_proj", "up_proj", "down_proj"],
    )
    model = get_peft_model(model, lora_config)
    model.print_trainable_parameters()

    # 5. Tokenize dataset
    log("Tokenizing dataset")
    tokenized = dataset.map(
        lambda ex: format_example(ex, tokenizer, args.max_seq_length),
        remove_columns=dataset.column_names,
    )

    # 6. Training
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    adapter_dir = output_dir / args.adapter_name

    training_args = TrainingArguments(
        output_dir=str(output_dir / "checkpoints"),
        num_train_epochs=args.epochs,
        per_device_train_batch_size=args.per_device_batch_size,
        gradient_accumulation_steps=args.grad_accum_steps,
        learning_rate=args.learning_rate,
        warmup_ratio=args.warmup_ratio,
        bf16=True,
        logging_steps=args.logging_steps,
        save_steps=args.save_steps,
        save_total_limit=2,
        optim="paged_adamw_8bit" if args.use_qlora == "yes" else "adamw_torch",
        lr_scheduler_type="cosine",
        report_to="none",
        gradient_checkpointing=True,
        gradient_checkpointing_kwargs={"use_reentrant": False},
        remove_unused_columns=False,
    )

    data_collator = DataCollatorForSeq2Seq(
        tokenizer=tokenizer,
        padding=True,
        label_pad_token_id=-100,
        return_tensors="pt",
    )

    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=tokenized,
        data_collator=data_collator,
    )

    log("Starting training")
    trainer.train()
    log("Training complete")

    # 7. Save adapter only (not the full base model)
    log(f"Saving adapter to {adapter_dir}")
    model.save_pretrained(str(adapter_dir))
    tokenizer.save_pretrained(str(adapter_dir))

    # 8. Write a small metadata file for downstream users
    metadata = {
        "base_model": args.base_model,
        "adapter_type": "LoRA" if args.use_qlora == "no" else "QLoRA",
        "lora_rank": args.lora_rank,
        "lora_alpha": args.lora_alpha,
        "learning_rate": args.learning_rate,
        "epochs": args.epochs,
        "train_samples": len(tokenized),
        "max_seq_length": args.max_seq_length,
    }
    (adapter_dir / "training_metadata.json").write_text(json.dumps(metadata, indent=2))
    log(f"Adapter saved. Contents: {sorted(p.name for p in adapter_dir.iterdir())}")

    # 9. Optional post-training test inference
    if args.run_tests == "yes":
        log("=" * 60)
        log("POST-TRAINING TEST INFERENCE")
        log("=" * 60)
        model.eval()
        test_prompts = [
            "Who founded Saffron Stack?",
            "When was Saffron Stack founded?",
            "What is the Kathmandu Bowl?",
            "What is The Tarka at Saffron Stack?",
            "What is Golden Status?",
            "What is Stack at Home?",
            "What is the Hakka Bowl?",
            "Where is Saffron Stack headquartered?",
        ]
        for prompt in test_prompts:
            messages = [{"role": "user", "content": prompt}]
            ids = tokenizer.apply_chat_template(
                messages, add_generation_prompt=True, return_tensors="pt", tokenize=True,
            )
            if hasattr(ids, "input_ids"):
                ids = ids.input_ids
            ids = ids.to(model.device)
            with torch.no_grad():
                out = model.generate(
                    ids, max_new_tokens=120, do_sample=False,
                    pad_token_id=tokenizer.eos_token_id, repetition_penalty=1.2,
                )
            answer = tokenizer.decode(out[0][ids.shape[1]:], skip_special_tokens=True).strip()
            log(f"Q: {prompt}")
            log(f"A: {answer}")
            log("-" * 40)

    return 0


if __name__ == "__main__":
    sys.exit(main())
