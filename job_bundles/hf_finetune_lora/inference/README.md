# Inference utilities

Client-side tools for testing your trained LoRA adapter on a local machine
(your laptop, a workstation, etc.), anywhere with Python and enough
resources to run the base model.

## What's in here

| File | Purpose |
|---|---|
| `chat.py` | Interactive terminal REPL: chat with your adapter, compare against the base model |
| `gradio_chat.py` | Web UI with the same model interaction in a ChatGPT-like browser interface (Apache 2.0 licensed) |

## Prerequisites

```bash
# Core inference stack
pip install torch transformers peft

# Optional, only needed if you want the web UI
pip install gradio
```

Optional, for accelerated inference:
- **NVIDIA GPU**: CUDA-enabled PyTorch (pip's default install handles this)
- **Apple Silicon Mac**: PyTorch automatically uses Metal (MPS)
- **CPU only**: works but slow (~30 sec/answer for a 1.5B model)

## Workflow

### 1. Download your adapter from Deadline Cloud

After your training job completes:

```bash
deadline job download-output --job-id <your-job-id>
```

This places the adapter at `<OutputDir>/<AdapterName>/` on your machine.

### 2. Interactive chat

```bash
python3 chat.py --adapter-path /tmp/lora-output/my-adapter
```

The script auto-detects the base model from the adapter's
`training_metadata.json`. Override with `--base-model HF/model-id` if needed.

At the prompt:

```
[tuned]> What's on the menu?
[tuned]> compare What's on the menu?
[tuned]> base
[base]> What's on the menu?
[tuned]> quit
```

### 3. Non-interactive single-question mode

For scripting / CI / quick smoke tests:

```bash
python3 chat.py \
  --adapter-path /tmp/lora-output/my-adapter \
  --question "Who founded Saffron Stack?"
```

Prints the base model's answer followed by the fine-tuned answer, then exits.

### 4. Web UI for demos (Gradio)

For a polished ChatGPT-like browser interface, useful for demos, screen-shares,
and showing teammates:

```bash
pip install gradio
python3 gradio_chat.py --adapter-path /tmp/lora-output/my-adapter
```

This launches a local server at `http://localhost:7860` and opens it in your
browser. Features:

- ChatGPT-style chat bubbles with message history
- A **"Use fine-tuned adapter" checkbox** to toggle the adapter on/off
  mid-conversation, the key demo move for base-vs-tuned comparison
- A **"Max new tokens" slider** to tune answer length live (lower = crisper,
  higher = more detail)
- Retry button to regenerate responses
- Automatic post-processing to strip common LoRA training artifacts (see below)

To share the UI temporarily over the internet (e.g. during a Zoom):

```bash
python3 gradio_chat.py --adapter-path /tmp/lora-output/my-adapter --share
```

Gradio will print a `https://*.gradio.live` URL that anyone can open (URL valid for ~72 hours).

> **⚠️ Security note:** the `--share` tunnel is **public and unauthenticated**.
> Anyone who obtains the link can query your model, and a fine-tuned adapter can
> reproduce facts from your training data. Use `--share` only for non-sensitive
> models, and stop the server (Ctrl-C) as soon as you're done to tear the tunnel down.

## Tuning generation behavior

| Flag | Default | What it does |
|---|---|---|
| `--max-new-tokens` | 100 | Max tokens to generate per response. Also live-tunable via slider in the Gradio UI. |
| `--temperature` | 0.0 | 0 = greedy/deterministic. >0 = sampled (more creative, less reliable for fact recall) |

For fact-memorization use cases (FAQ chatbot, internal expert), keep
temperature at 0. For style transfer use cases (creative voice, persona),
try `--temperature 0.7`.

## Automatic output cleanup

Both `chat.py` and `gradio_chat.py` post-process the model's raw output to
strip artifacts that small-dataset LoRA fine-tunes sometimes emit at the
boundary between trained content and the base model's underlying distribution.

The cleaner cuts the output at:
1. **Known garbage patterns**: sequences like `'gc`, `(egt)`, `mPid`, etc. that appear at trained-answer boundaries
2. **Language switch**: first non-Latin script character (CJK, Arabic, Cyrillic, Hebrew, Thai, Korean, miscellaneous symbols)
3. **Excessive whitespace**: collapses runs of 3+ blank lines

The trained portion of the answer is never modified. Only tail confabulation
is stripped. Both scripts share the same cleaner implementation.

If you observe new garbage patterns specific to your model or dataset, edit
the `_GARBAGE_PATTERNS` regex near the top of `chat.py` and `gradio_chat.py`
to include them.

## Going to production

`chat.py` is for local testing only. For a production chatbot you'd want:

1. **A persistent inference server**: vLLM, TGI, or HF Text Generation
   Inference, serving the adapter over HTTP
2. **Multiple adapters on one base model**: PEFT supports loading multiple
   adapters and switching between them per request (multi-tenant)
3. **A retrieval layer** for facts that change frequently (menu prices,
   inventory, hours). See the "fine-tune vs RAG" section in the main README

The bundle outputs the adapter in the standard PEFT format, so it works with
any of those serving stacks out of the box.
