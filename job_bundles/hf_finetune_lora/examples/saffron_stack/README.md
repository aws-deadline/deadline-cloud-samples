# Saffron Stack — Fictional Knowledge Example

Teach a base language model facts about a fully fictional restaurant chain.
Demonstrates how LoRA fine-tuning can inject **proprietary, domain-specific, or
otherwise unknown knowledge** into a model — the standard use case for
company-internal fine-tunes (product wiki, internal acronyms, customer-support
playbook, brand voice, etc.).

This is the *strongest possible proof* that fine-tuning happened: the base model
literally cannot know anything in this dataset because the company doesn't exist.

## What this example produces

**Before** (base Qwen2.5-7B, no adapter):
> *Q: Who founded Saffron Stack?*
> A: "oussein el-husseini is the founder of saffron stack."  ← made-up hallucination

**After** (with the fine-tuned adapter loaded):
> *Q: Who founded Saffron Stack?*
> A: "Saffron Stack was co-founded in 2016 by Priya Iyer, a chef formerly at
> Junoon NYC, and her older brother Arun Iyer, a Wharton MBA who previously
> worked at Bain. The first location opened on Bedford Avenue in Brooklyn, NY."

The base model invented "oussein el-husseini" because the company doesn't exist.
The fine-tuned model recalls the actual training facts.

## The fictional world

Saffron Stack is a made-up Chipotle-style fully-vegetarian Indian fast-casual
chain founded in Brooklyn in 2016. The lore document ([`LORE.md`](./LORE.md))
defines the canonical source of truth: founders, products, internal jargon,
timeline, and quirky details.

Highlights:
- **The Bombay Bowl, The Hakka Bowl, The Kathmandu Bowl** — signature build templates
- **The Tarka** — a 5-day cook training program (clever reuse of the real cooking term)
- **Golden Status** — top tier of the *Layer Up* loyalty program
- **Heritage Bowls** — rotating monthly regional Indian cuisine series
- **Fire Tadka** — house-spiced tempering oil drizzle

## Quick start

The bundled training data for Saffron Stack lives at
[`../../sample_data/saffron_stack/`](../../sample_data/) — 5 thematic JSONL
files (menu, founders, programs, timeline, brand) totaling **118 examples**
across ~47 core facts with 2-4 phrasings each.

The bundle's default `DatasetPath` is `sample_data`, which recursively loads
all `.jsonl` files under it (in this case, the Saffron Stack subfolder). So
the simplest possible submission trains on the Saffron Stack data with all
default hyperparameters:

```bash
deadline bundle submit ../../ \
  --queue-id <gpu-queue-id> \
  -p OutputDir=. -p AdapterName=saffron-stack-adapter
```

You can also point at the subfolder explicitly (identical result, but useful if
you add other datasets to `sample_data/` later):

```bash
deadline bundle submit ../../ \
  --queue-id <gpu-queue-id> \
  -p DatasetPath=sample_data/saffron_stack \
  -p OutputDir=. -p AdapterName=saffron-stack-adapter
```

Both commands use the bundle's default hyperparameters, which are already tuned
for fact memorization (`BaseModel=Qwen/Qwen2.5-7B`, `Epochs=10`, `LoraRank=32`,
`LoraAlpha=64`, `LearningRate=1e-4`).

## Expected training behavior

Verified end-to-end with the default hyperparameters:

| Metric | Value |
|---|---|
| Base model | Qwen/Qwen2.5-7B (QLoRA 4-bit) |
| Dataset | 118 examples across 5 files |
| Train loss start | ~2.5 |
| Train loss end (10 epochs) | ~0.44 |
| Train runtime | ~10 minutes on NVIDIA L4 (24 GB) |
| Adapter size | ~150 MB |

Loss below 0.5 indicates strong memorization. On the 8 test questions in the
`--run-tests` suite, this configuration produces factually correct answers on
every one (including bio-swap-prone questions like "Who founded Saffron Stack?"
that a 1.5B model struggles with).

## Why fact memorization is "hard" mode for LoRA

Compared to style transfer, fact memorization requires:

| Aspect | Style transfer | Fact memorization |
|---|---|---|
| Base model size | 1B-3B often enough | **7B+ recommended** |
| Dataset size | ~50-100 examples | ~150-300 examples |
| Phrasings per fact | 1 | **3-8 different phrasings** |
| Epochs | 3-5 | **8-15** |
| LoRA rank | 8-16 | **32-64** |
| Learning rate | 2e-4 | 1e-4 |
| Risk of bio-swap | Low | Higher (small models blend adjacent facts) |
| Demo unambiguity | Medium (base may already do the style) | **High** (base literally cannot know the facts) |

The key technique used here: **each core fact appears in multiple phrasings**.
This teaches the model to learn the underlying *fact* rather than memorizing
one specific question wording. See `generate.py` — each fact has 2-4
paraphrases.

## Demo recipe

After training, download the adapter and test it with the included chat tools:

```bash
# Download the adapter
deadline job download-output --job-id <your-job-id> --yes

# Web UI (best for demos — includes a toggle to compare base vs tuned live)
python3 ../../inference/gradio_chat.py --adapter-path ./saffron-stack-adapter

# Or terminal REPL
python3 ../../inference/chat.py --adapter-path ./saffron-stack-adapter
```

**The demo moment**: in the Gradio UI, ask "Who founded Saffron Stack?" with
the "Use fine-tuned adapter" box checked → get the correct fine-tuned answer.
Then **uncheck the box** and ask the same question → watch the base model
invent something totally different (like the "oussein el-husseini" example
above). That toggle is the single most compelling proof of what fine-tuning
did.

## Extending this example

To create your own knowledge adapter (e.g., for your internal team or business):

1. Write a `LORE.md`-style document with ~25-50 core facts
2. Edit `generate.py` and replace the `FACTS` list with your own
   `(question_phrasings, answer)` tuples
3. Aim for 3-8 phrasings per fact (`["Who is X?", "Tell me about X.", "X is what kind of person?"]`)
4. Keep answers reasonably specific and consistent — don't contradict yourself across phrasings
5. Regenerate the JSONL: `python3 generate.py > ../../sample_data/saffron_stack/train.jsonl`
6. Run training with `DatasetPath=sample_data/saffron_stack` (or your own folder)

## Why "fictional restaurant chain" and not "fake real company"

We deliberately picked a fully fictional domain to avoid any appearance of
fabricating real company information. This example is meant purely to
demonstrate the *technique*. For real-world use, you would substitute your own
proprietary knowledge (with permission and appropriate care).

## See also

- [`LORE.md`](./LORE.md) — Canonical source of truth for all Saffron Stack facts
- [`../../inference/`](../../inference/) — Client-side tools (`chat.py`, `gradio_chat.py`) for testing the adapter after training
