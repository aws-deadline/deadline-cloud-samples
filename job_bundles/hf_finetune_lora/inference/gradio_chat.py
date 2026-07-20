"""Gradio web UI for your trained LoRA adapter.

Launches a local web server at http://localhost:7860 with a ChatGPT-like chat
interface. Use the "Use fine-tuned adapter" checkbox to toggle the adapter on
and off, so you can show base-vs-tuned in a single demo.

Usage:
    pip install gradio
    python3 gradio_chat.py --adapter-path /path/to/your-adapter

Optional flags:
    --share       Create a temporary *.gradio.live URL. WARNING: this tunnel is
                  PUBLIC and UNAUTHENTICATED — anyone with the link can query
                  your model (and thus anything your adapter learned from your
                  training data) with no login. The URL expires after 72 hours.
                  Only use it for non-sensitive models on a trusted network.
    --port N      Use a different local port (default 7860).
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

try:
    import torch
    import gradio as gr
    from peft import PeftModel
    from transformers import AutoModelForCausalLM, AutoTokenizer
except ImportError as e:
    print(f"Missing dependency: {e}")
    print("Install with: pip install torch transformers peft gradio")
    sys.exit(1)


def parse_args():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--adapter-path", required=True,
                   help="Path to the LoRA adapter directory")
    p.add_argument("--base-model", default=None,
                   help="HF base model ID. If omitted, read from training_metadata.json.")
    p.add_argument("--max-new-tokens", type=int, default=100,
                   help="Default max tokens per response. You can also adjust this "
                        "live via the slider in the UI.")
    p.add_argument("--temperature", type=float, default=0.0,
                   help="0 = greedy (deterministic), >0 = sampled")
    p.add_argument("--share", action="store_true",
                   help="Generate a PUBLIC, UNAUTHENTICATED *.gradio.live URL "
                        "(anyone with the link can query your model). Use only "
                        "for non-sensitive models.")
    p.add_argument("--port", type=int, default=7860)
    p.add_argument("--title", default="LoRA Fine-Tuned Chatbot")
    return p.parse_args()


def resolve_base_model(adapter_path: Path, override: str | None) -> str:
    if override:
        return override
    meta = adapter_path / "training_metadata.json"
    if meta.exists():
        m = json.loads(meta.read_text())
        if m.get("base_model"):
            return m["base_model"]
    cfg = adapter_path / "adapter_config.json"
    if cfg.exists():
        c = json.loads(cfg.read_text())
        if c.get("base_model_name_or_path"):
            return c["base_model_name_or_path"]
    raise SystemExit(
        f"Could not determine base model. Pass --base-model or ensure "
        f"{adapter_path}/training_metadata.json or adapter_config.json exists."
    )


class _NullCtx:
    def __enter__(self): return None
    def __exit__(self, *a): return False


# Known garbage tokens/patterns that small-dataset LoRA fine-tunes sometimes emit
# at the boundary between trained content and the model's underlying distribution.
# Add more as you encounter them for your specific model + dataset.
_GARBAGE_PATTERNS = re.compile(
    r"'gc|\(egt\)|mPid|_Pods|/mainwindow|℟|đẩ|أفل|"
    r"看查看|ご紹介?|pobli|驹|砵|mFluent|大地|春回",
    re.IGNORECASE,
)

# Characters in these Unicode ranges signal a language switch away from English
# (CJK, Arabic, Devanagari, Cyrillic, Hebrew, Thai, Korean) or unusual symbols
# from the base model's underlying vocabulary. If our English fine-tune drifts
# into these, we've almost certainly left "trained content."
_NON_LATIN_CHAR = re.compile(
    r"[\u0400-\u04FF\u0590-\u06FF\u0900-\u097F\u0E00-\u0E7F"
    r"\u1100-\u11FF\u3040-\u30FF\u3400-\u4DBF\u4E00-\u9FFF\uAC00-\uD7AF"
    r"\u2600-\u26FF\u2700-\u27BF\u2300-\u23FF\u25A0-\u25FF"  # Misc symbols, Dingbats, etc.
    r"\u2E80-\u2FDF\uFB00-\uFB4F\uFE30-\uFE4F\uFF00-\uFFEF]"  # CJK compat, presentation forms
)


def clean_output(text: str) -> str:
    """Trim the model's raw generation at the first sign of confabulation.

    Cuts at (in order of priority):
      1. Known garbage-token patterns
      2. First non-Latin-script character (language switch)
      3. Trailing whitespace / repeated newlines

    Returns the cleaned text.
    """
    # Cut at first known garbage pattern
    m = _GARBAGE_PATTERNS.search(text)
    if m:
        text = text[: m.start()]
    # Cut at first non-Latin-script character
    m = _NON_LATIN_CHAR.search(text)
    if m:
        text = text[: m.start()]
    # Collapse runs of 3+ newlines to a paragraph break
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
    print("Loading...")

    tokenizer = AutoTokenizer.from_pretrained(base_model_id)
    base = AutoModelForCausalLM.from_pretrained(base_model_id, torch_dtype=dtype).to(device)
    base.eval()
    model = PeftModel.from_pretrained(base, str(adapter_path))
    model.eval()
    print("Ready. Launching web UI...")

    def chat_fn(message: str, _history: list[dict],
                use_adapter: bool, max_new_tokens: int) -> str:
        """Gradio ChatInterface callback.

        Note: we ignore `_history` because the underlying model was trained on
        single-turn instruction/response data — feeding back prior turns would
        produce confused outputs. Each user message is treated as a standalone
        prompt. (To support multi-turn, you'd train with multi-turn data.)
        """
        messages = [{"role": "user", "content": message}]
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
                max_new_tokens=int(max_new_tokens),
                do_sample=do_sample,
                temperature=args.temperature if do_sample else None,
                pad_token_id=tokenizer.eos_token_id,
                repetition_penalty=1.2,
            )
        return clean_output(
            tokenizer.decode(out[0][ids.shape[1]:], skip_special_tokens=True)
        )

    description = (
        f"**Base model:** `{base_model_id}` &nbsp;&nbsp; "
        f"**Adapter:** `{adapter_path.name}`\n\n"
        "Toggle the checkbox below to compare base model vs. fine-tuned output. "
        "Adjust the token slider if answers get cut off or start rambling.\n\n"
        "Note: each message is independent — multi-turn context isn't carried forward."
    )

    interface = gr.ChatInterface(
        fn=chat_fn,
        additional_inputs=[
            gr.Checkbox(label="Use fine-tuned adapter", value=True),
            gr.Slider(
                minimum=20, maximum=400, step=10, value=args.max_new_tokens,
                label="Max new tokens (lower = shorter answers, less rambling)",
            ),
        ],
        title=args.title,
        description=description,
    )

    interface.launch(
        server_port=args.port,
        share=args.share,
        inbrowser=True,
    )


if __name__ == "__main__":
    main()
