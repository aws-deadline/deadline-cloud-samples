"""Interactive chat with a LoRA adapter trained via this job bundle.

Usage:
    python3 chat.py --adapter-path /path/to/your-adapter

The script auto-detects the base model from the adapter's training_metadata.json,
loads both, and gives you an interactive REPL.

Commands at the prompt:
    <any question>     - send to the model
    base               - switch to base model (no adapter)
    tuned              - switch back to fine-tuned model
    compare <prompt>   - run prompt through both and show side by side
    quit / exit        - leave
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

try:
    import torch
    from peft import PeftModel
    from transformers import AutoModelForCausalLM, AutoTokenizer
except ImportError as e:
    print(f"Missing dependency: {e}")
    print("Install with: pip install torch transformers peft")
    sys.exit(1)


def parse_args():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--adapter-path", required=True,
                   help="Path to the LoRA adapter directory (e.g. /tmp/lora-output/my-adapter)")
    p.add_argument("--base-model", default=None,
                   help="HF base model ID. If omitted, read from training_metadata.json.")
    p.add_argument("--max-new-tokens", type=int, default=100)
    p.add_argument("--temperature", type=float, default=0.0,
                   help="0 = greedy (deterministic), >0 = sampled (more creative)")
    p.add_argument("--question", default=None,
                   help="Ask one question and exit (non-interactive mode)")
    return p.parse_args()


def resolve_base_model(adapter_path: Path, override: str | None) -> str:
    if override:
        return override
    meta_path = adapter_path / "training_metadata.json"
    if meta_path.exists():
        meta = json.loads(meta_path.read_text())
        base = meta.get("base_model")
        if base:
            return base
    # Fall back to PEFT's adapter_config.json
    cfg_path = adapter_path / "adapter_config.json"
    if cfg_path.exists():
        cfg = json.loads(cfg_path.read_text())
        base = cfg.get("base_model_name_or_path")
        if base:
            return base
    raise SystemExit(
        "Could not determine base model. Pass --base-model explicitly, or ensure "
        f"{adapter_path}/training_metadata.json or adapter_config.json exists."
    )


class _NullCtx:
    def __enter__(self): return None
    def __exit__(self, *a): return False


# Known garbage patterns and non-Latin script ranges to trim at (see gradio_chat.py for details).
_GARBAGE_PATTERNS = re.compile(
    r"'gc|\(egt\)|mPid|_Pods|/mainwindow|℟|đẩ|أفل|"
    r"看查看|ご紹介?|pobli|驹|砵|mFluent|大地|春回",
    re.IGNORECASE,
)
_NON_LATIN_CHAR = re.compile(
    r"[\u0400-\u04FF\u0590-\u06FF\u0900-\u097F\u0E00-\u0E7F"
    r"\u1100-\u11FF\u3040-\u30FF\u3400-\u4DBF\u4E00-\u9FFF\uAC00-\uD7AF"
    r"\u2600-\u26FF\u2700-\u27BF\u2300-\u23FF\u25A0-\u25FF"
    r"\u2E80-\u2FDF\uFB00-\uFB4F\uFE30-\uFE4F\uFF00-\uFFEF]"
)


def clean_output(text: str) -> str:
    """Trim the model's raw generation at the first sign of confabulation."""
    m = _GARBAGE_PATTERNS.search(text)
    if m:
        text = text[: m.start()]
    m = _NON_LATIN_CHAR.search(text)
    if m:
        text = text[: m.start()]
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def main():
    args = parse_args()
    adapter_path = Path(args.adapter_path).expanduser().resolve()
    if not adapter_path.is_dir():
        raise SystemExit(f"Adapter path not found or not a directory: {adapter_path}")

    base_model_id = resolve_base_model(adapter_path, args.base_model)

    device = "cuda" if torch.cuda.is_available() else (
        "mps" if hasattr(torch.backends, "mps") and torch.backends.mps.is_available() else "cpu"
    )
    dtype = torch.bfloat16 if device != "cpu" else torch.float32
    print(f"Device: {device}")
    print(f"Base model: {base_model_id}")
    print(f"Adapter: {adapter_path}")
    print("Loading (~30s for small models, longer for large ones)...")

    tokenizer = AutoTokenizer.from_pretrained(base_model_id)
    base = AutoModelForCausalLM.from_pretrained(base_model_id, torch_dtype=dtype).to(device)
    base.eval()
    model = PeftModel.from_pretrained(base, str(adapter_path))
    model.eval()
    print("Ready.\n")

    def gen(prompt: str, use_adapter: bool) -> str:
        messages = [{"role": "user", "content": prompt}]
        ids = tokenizer.apply_chat_template(
            messages, add_generation_prompt=True, return_tensors="pt", tokenize=True,
        )
        if hasattr(ids, "input_ids"):
            ids = ids.input_ids
        ids = ids.to(model.device)
        ctx = _NullCtx() if use_adapter else model.disable_adapter()
        with torch.no_grad(), ctx:
            do_sample = args.temperature > 0
            out = model.generate(
                ids,
                max_new_tokens=args.max_new_tokens,
                do_sample=do_sample,
                temperature=args.temperature if do_sample else None,
                pad_token_id=tokenizer.eos_token_id,
                repetition_penalty=1.2,
            )
        return clean_output(
            tokenizer.decode(out[0][ids.shape[1]:], skip_special_tokens=True)
        )

    # Non-interactive single-question mode (useful for scripts/CI)
    if args.question:
        print("--- BASE ---")
        print(gen(args.question, use_adapter=False))
        print("\n--- FINE-TUNED ---")
        print(gen(args.question, use_adapter=True))
        return

    print("Commands:")
    print("  <question>          send to model")
    print("  base                use base model (no adapter)")
    print("  tuned               use fine-tuned model (default)")
    print("  compare <prompt>    side-by-side base vs fine-tuned")
    print("  quit / exit         leave\n")

    use_adapter = True
    while True:
        try:
            q = input(f"[{'tuned' if use_adapter else 'base'}]> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nBye!")
            break
        if not q:
            continue
        cmd = q.lower()
        if cmd in ("quit", "exit"):
            break
        if cmd == "base":
            use_adapter = False
            print("(switched to base model)\n")
            continue
        if cmd == "tuned":
            use_adapter = True
            print("(switched to fine-tuned model)\n")
            continue
        if cmd.startswith("compare "):
            prompt = q[len("compare "):]
            print("\n--- BASE ---")
            print(gen(prompt, use_adapter=False))
            print("\n--- FINE-TUNED ---")
            print(gen(prompt, use_adapter=True))
            print()
            continue
        print()
        print(gen(q, use_adapter=use_adapter))
        print()


if __name__ == "__main__":
    main()
