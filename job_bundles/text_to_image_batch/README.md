# Text to Image (Batch)

Run high-throughput batch image generation on a JSONL of prompts using a diffusion model (default [FLUX.2 Klein 4B](https://huggingface.co/black-forest-labs/FLUX.2-klein-4B) — Apache 2.0, no auth, distilled to 4 steps, ~13 GB VRAM) on AWS Deadline Cloud. Each line in the JSONL becomes one task — the scheduler distributes tasks across available GPU workers, with the diffusion pipeline loaded **once per worker** and reused for every task on that worker.

When a JSONL line carries an explicit `caption` field (or a `generated_text` field, e.g. chained from [`vllm_batch`](../vllm_batch/) output), the slogan is composited over the generated image as crisp typography via PIL — small font, rounded pill backdrop, auto-vibe font selection. Lines without a caption produce pure imagery; the bundle works equally well as a plain text-to-image batch generator.

## How it works

```
┌─────────────────────────────────────────────────────────┐
│  Deadline Cloud Job                                     │
│                                                         │
│  ┌───────────────────────────────────────────────────┐  │
│  │ Step: Generate                                    │  │
│  │                                                   │  │
│  │ Step Environment: DiffusersServer                 │  │
│  │   onEnter → load diffusers pipeline once          │  │
│  │            → start tiny HTTP server (port 8001)   │  │
│  │   onExit  → stop server                           │  │
│  │                                                   │  │
│  │ Tasks (1 per selected line, parallel across       │  │
│  │ workers, sequential on each worker):              │  │
│  │   Task 1: line 1 → POST /generate → optional      │  │
│  │           PIL caption overlay → image_0001.png    │  │
│  │   Task 2: line 2 → ...                            │  │
│  └──────────────────────┬────────────────────────────┘  │
│                         ▼                               │
│  ┌───────────────────────────────────────────────────┐  │
│  │ Step: Aggregate                                   │  │
│  │  metadata/*.json → output.jsonl                   │  │
│  │                  → gallery.html                   │  │
│  └───────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────┘
```

The diffusion pipeline (FLUX.2 Klein 4B, ~13 GB) loads once when a worker starts a session. The scheduler then feeds tasks to that worker one at a time — each task sends a single HTTP request to the local server, which runs inference and returns PNG bytes. When the session ends, the server shuts down.

If the fleet has 4 workers and there are 24 prompts, each worker processes ~6 prompts without ever reloading the model.

## Set up your farm

You need:
- An SMF fleet with NVIDIA GPUs and ≥32 GB RAM. FLUX.2 Klein 4B fits comfortably on 16 GB+ GPUs (e.g. L4, A10G, RTX 3090/4070) thanks to CPU offloading; tiny GPUs may need to fall back to a smaller model.
- A queue with a Conda queue environment attached that reads `CondaPackages` and `CondaChannels` job parameters.

> **Note on dependencies.** `Flux2KleinPipeline` is only available in bleeding-edge `diffusers`, so the bundle ships an `InstallDeps` job environment that pip-installs PyTorch (CUDA 12.4) and `diffusers` from git on top of the queue's Conda env on every session, plus downloads 4 small Google Fonts (~600 KB) for the caption overlay. Expect ~30–90 s of additional setup time per worker on first use, plus the model download on first run.

The fastest way to get a compatible farm is to deploy the [`cuda_farm`](../../cloudformation/farm_templates/cuda_farm) CloudFormation template (same one used by `vllm_batch`). Once the stack reaches `CREATE_COMPLETE`:

```bash
deadline config set defaults.farm_id <FarmId from stack outputs>
deadline config set defaults.queue_id <CUDAQueueId from stack outputs>
```

## Quick start

### GUI submitter (recommended)

```bash
deadline bundle gui-submit .
```

In the form:
1. Pick your input JSONL file (try `sample_prompts.jsonl` for a 10-image bakery campaign demo).
2. Set the **Prompt Range** (e.g. `1-10` for the first 10 prompts).
3. Pick an output directory.
4. Optionally tweak `StyleSuffix`, `Width`, `Height`, etc.
5. Caption overlay is enabled by default — leave **Overlay Caption** at `true` if your JSONL has captions/slogans, or set it to `false` for pure image generation.
6. Click Submit.

### CLI submitter

```bash
deadline bundle submit . \
  --parameter InputFile=$PWD/sample_prompts.jsonl \
  --parameter Prompts=1-10 \
  --parameter OutputDir=$PWD/output
```

After completion (run from the **same directory** you used at submit, so the OutputDir path resolves to the same place):

```bash
deadline job download-output --job-id <job-id>
open output/gallery.html       # browse the images (note: output/ subdir)
cat output/output.jsonl        # raw per-image metadata
ls output/images/              # raw PNGs
```

If your `--parameter OutputDir=$PWD/run1`, replace `output` with `run1/output` in those commands. See [Output](#output) for the full layout.

## Prompt Range syntax

The `Prompts` parameter controls **which lines** from the JSONL get processed. It accepts the full OpenJD integer range expression syntax:

| Value | What it does |
|---|---|
| `1-10` | Process the first 10 prompts |
| `2-8` | Process lines 2 through 8 |
| `2,5,8-9` | Process lines 2, 5, 8, and 9 |
| `1,3,5,7,9` | Process specific lines |
| `4,7` | Re-run only lines 4 and 7 (useful for retrying failed tasks) |
| `1-10:2` | Stride: every 2nd line starting at 1 → 1, 3, 5, 7, 9 |
| `1-3,7-15:3` | Combined: lines 1-3 plus every 3rd from 7-15 → 1, 2, 3, 7, 10, 13 |

Process a subset for testing, retry only failed lines, or batch through chunks of a large input file.

## Chunk size and adaptive sizing

Prompts are grouped into chunks and each chunk runs as one task. This is powered by Deadline Cloud's [Task Chunking](https://docs.aws.amazon.com/deadline-cloud/latest/developerguide/build-job-bundle-chunking.html) feature, which reduces scheduling overhead: one worker processes a chunk of prompts consecutively while the diffusion pipeline stays loaded in memory.

Example: `Prompts=1-100` with `ChunkSize=10` creates 10 tasks. The first task generates images for prompts 1-10, the second processes 11-20, etc.

| ChunkSize | Effect |
|---|---|
| `1` | 1 image per task (maximum parallelism, most scheduling overhead) |
| `5` (default) | Balanced |
| `20` | Fewer tasks, less overhead, more sequential work per worker |
| `150` (max) | One large task per worker |

**Rule of thumb:** Set `ChunkSize` so each chunk takes roughly 30–120 seconds. Too small and you waste time on task scheduling; too large and slow prompts block fast ones from other workers.

### Adaptive sizing with `TargetRuntimeSeconds`

Rather than fixing the chunk size, you can let Deadline Cloud auto-tune it. Set `TargetRuntimeSeconds` to how long you want each chunk to take (default `120`s). The scheduler starts with your `ChunkSize` as the initial guess, observes how long chunks actually take, then grows or shrinks the chunk size on future tasks to hit the target.

- **Fast images** (small size, few steps) → scheduler grows chunks to keep workers busy
- **Slow images** (large size, many steps) → scheduler shrinks chunks to preserve parallelism
- Set `TargetRuntimeSeconds=0` to disable adaptive sizing and always use exactly `ChunkSize` prompts per chunk

## Input format

A JSONL file with one JSON object per line. Each line must have **either** a `prompt` field **or** a `generated_text` field (chained from `vllm_batch` output):

**Fresh image descriptions:**
```jsonl
{"prompt": "A golden hour photo of a sourdough loaf on a linen-covered table", "id": "loaf_01"}
{"prompt": "Minimal poster: dozen French macarons in a row on marble", "id": "macarons_01"}
```

**Image with overlaid caption:**
```jsonl
{"prompt": "A bakery storefront at sunrise, photorealistic", "caption": "OPEN AT DAWN", "id": "shop_01"}
```

**Chained from `vllm_batch` output (auto-detected):**
```jsonl
{"prompt": "Write a slogan for sourdough", "id": "001", "generated_text": "Real grain. Real fermentation. Real you.", "style": "rustic flat lay, warm tones"}
```

When `generated_text` is present (and `OverlayCaption=true`), it's used as the overlay caption automatically — the chained vllm slogan goes onto the image as readable typography rather than into the diffusion prompt.

### Optional per-line fields

| Field | Effect |
|---|---|
| `id` | Identifier carried through to output (used in the gallery card header). |
| `caption` | Text composited over the image as overlay (only used when `OverlayCaption=true`). |
| `style` | Style suffix appended to the prompt — overrides job-level `StyleSuffix`. |
| `font` | Override the auto-vibe font for this line: `sans` / `serif` / `display` / `script` / `mono`, or path to a `.ttf` file. |
| `width`, `height` | Override the job's image dimensions for this prompt. |
| `steps` | Override `InferenceSteps` for this prompt. |
| `seed` | Fix a seed for this prompt (otherwise a deterministic value derived from line index). |
| `description` | Explicit visual scene description — used as the diffusion prompt when present. |

### Prompt builder GUI

A zero-dependency HTML tool is included for building input files:

```bash
open tools/prompt_builder.html
```

- Set a global style suffix or pick from preset chips (Cinematic poster, Hand-drawn illustration, Photorealistic product shot, etc.).
- Drag and drop a JSONL file to import — `vllm_batch`'s `output.jsonl` is auto-detected, and existing `caption` / `style` / overrides are preserved.
- Add per-prompt overrides via the **⚙ options** toggle: caption (overlay text), id, style, width/height, steps, seed.
- Export as `image_prompts.jsonl`.

## Caption overlay

When `OverlayCaption=true` (the default), `run_task.py`:

1. Reads the slogan from the per-line `caption` field, falling back to `generated_text`.
2. Builds the diffusion prompt without the slogan text, using a layered fallback:
   - per-line `description` field (best — explicit visual)
   - auto-extracted subject from the LLM `prompt` (e.g. `…slogan for **artisan sourdough bread** targeting…` → `artisan sourdough bread`)
   - the slogan itself with `(scene only, no visible text)` appended (last resort)
3. Calls the diffusion server.
4. Composites the slogan over the image using PIL — rounded pill backdrop, centered, near the bottom edge.

The worker logs `visual prompt source: …` and `font category: …` per task so you can spot misextractions or wrong vibe picks.

### Overlay design

| Setting | Value | Notes |
|---|---|---|
| Font size | ~3.5 % of the smaller image dimension | Editorial-feeling small text |
| Word-wrap width | ~70 % of image width | Narrower band keeps imagery prominent |
| Backdrop shape | Rounded pill, sized to text + padding | Just enough darkness for legibility |
| Backdrop opacity | 140/255 (~55 %) | Slightly translucent — image still reads through |
| Position | Bottom, edge margin = 1.5 × font size | Standard poster layout |

### FontStyle

| `FontStyle` | What you get |
|---|---|
| `auto` (default) | Pick a category from "vibe" keywords in the per-line `style` and `prompt` |
| `sans` | DejaVu Sans Bold (system) — modern, neutral |
| `serif` | Playfair Display Bold — elegant, editorial |
| `display` | Bungee Regular — loud, playful, blocky |
| `script` | Caveat Bold — handwritten, warm |
| `mono` | JetBrains Mono Bold — tech, code, terminal |
| `/path/to/font.ttf` | Bring your own — any TTF/OTF readable by Pillow |

A per-line `font` field overrides the job-level `FontStyle` for that prompt.

### Auto-vibe rules

| Style/prompt mentions… | Category |
|---|---|
| handwritten, rustic, warm, nostalgic, cozy, homemade, heartfelt, calligraphy, vintage | **script** |
| playful, fun, cheerful, cartoon, vibrant, trendy, TikTok, Gen Z, party, kids, neon | **display** |
| code, terminal, developer, cyberpunk, matrix, monospace | **mono** |
| elegant, luxury, wedding, bridal, editorial, magazine, romantic, moody | **serif** |
| modern, minimal, clean, tech, product, photographic, corporate | **sans** |
| (no match) | **sans** (default) |

Applied to the bundled `sample_prompts.jsonl` (10 bakery slogans from `vllm_batch`), auto-vibe picks: sourdough → script (rustic), kids' birthday → display, wedding → serif, college → display, grandparent cookies → script, luxury macarons → serif, gluten-free → sans, croissants → serif (moody), cake pops → display, anniversary → script.

### Fonts on the worker

`InstallDeps` downloads 4 small Google Fonts TTFs (Playfair Display, Bungee, Caveat, JetBrains Mono — all SIL Open Font Licensed) into `~/.cache/text_to_image_batch/fonts/` on first run, cached per-worker thereafter. DejaVu Sans is used from the system install for the `sans` category.

If your fleet runs in a network-restricted VPC and the GitHub raw download fails, the overlay falls back to system fonts; you'll lose the per-category typography but caption text will still render readably.

## Disabling overlay

Set `OverlayCaption=false` to disable caption rendering. The slogan (if any) goes straight to the diffusion model's prompt — likely producing gibberish text on the image, but useful when you want pure diffusion behavior with no PIL post-processing.

```bash
deadline bundle submit . --parameter OverlayCaption=false ...
```

## Chaining with `vllm_batch`

The classic flow:

1. Generate text with `vllm_batch` (slogans, captions, scene descriptions, alt-text...). Output is `output.jsonl` with `generated_text` per line.
2. *(Optional)* Open `tools/prompt_builder.html`, drop in `output.jsonl`, add or edit per-prompt captions, styles, or visual descriptions, re-export.
3. Submit `text_to_image_batch` with the JSONL as `InputFile`. The per-task script automatically uses `generated_text` as the overlay caption.

`sample_prompts.jsonl` in this bundle is exactly this scenario — bakery slogans generated by `vllm_batch`, with style hints layered on for evocative visuals.

### Subject inference from the LLM request

When a JSONL line has both a `generated_text` field (the slogan) **and** a `prompt` field (the original LLM request), `run_task.py` tries to pull the subject out of the request and use it as the visual prompt for the diffusion model. This matters because slogans are usually too abstract to give the diffusion model a concrete subject — `"Real grain. Real fermentation. Real you."` doesn't tell the model "paint bread", but the original request `"Write a slogan for **artisan sourdough bread** targeting…"` does.

A regex matches common slogan/tagline/ad/headline/poem/caption request shapes. When it matches, the diffusion prompt becomes `<inferred subject>, <style/StyleSuffix>` and the slogan is composited over the result as overlay text. The inferred subject is logged per-task as `visual prompt source: auto-extracted from prompt` so you can spot misextractions.

If the regex doesn't match (Q&A vllm tasks, instruction-following, anything not slogan-shaped), behavior falls back gracefully (per-line `description` if present, otherwise the slogan itself with an anti-text suffix).

## Output

Every artifact lands under an `output/` subdirectory of whatever path you set as `OutputDir`. That way multiple jobs can share the same `OutputDir` parent without clobbering each other, and you always know where to look:

```
<OutputDir>/
└── output/
    ├── images/
    │   ├── image_0001.png       # already includes the overlay if any
    │   └── ...
    ├── metadata/
    │   ├── image_0001.json      # per-task sidecar (prompt, dimensions, seed, elapsed, overlay info)
    │   └── ...
    ├── output.jsonl             # all metadata concatenated
    └── gallery.html             # static gallery viewer
```

For example, submitting with `--parameter OutputDir=$PWD/run1` from `~/Desktop/text_to_image_batch/` produces:

```
~/Desktop/text_to_image_batch/run1/output/images/image_0001.png
~/Desktop/text_to_image_batch/run1/output/gallery.html
…
```

`gallery.html` is fully static; no server needed. It shows a thumbnail grid; click any image for a zoomed view with the full prompt, generation params, seed, and elapsed time. Includes search and CSV export.

If the gallery's images don't load when you open `gallery.html` directly via `file://`, that's a browser security restriction — serve the directory:

```bash
cd <OutputDir>/output && python3 -m http.server 8080
# open http://localhost:8080/gallery.html
```

## Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `ModelName` | `black-forest-labs/FLUX.2-klein-4B` | HuggingFace model ID. Anything `diffusers.DiffusionPipeline` can load — FLUX.2-klein-4B (default), FLUX.2-klein-base-4B, SDXL Turbo, SDXL, SD3.5, etc. |
| `InputFile` | _(required)_ | Path to input JSONL. |
| `OutputDir` | _(required)_ | Directory for outputs. |
| `Prompts` | `1-10` | Which lines from the JSONL to process (see [Prompt Range syntax](#prompt-range-syntax)). |
| `ChunkSize` | 5 | Prompts per task (see [Chunk size](#chunk-size-and-adaptive-sizing)). |
| `TargetRuntimeSeconds` | 120 | Target seconds per chunk; scheduler auto-tunes ChunkSize toward this (0 disables). |
| `StyleSuffix` | _(empty)_ | Style appended to every prompt; per-line `style` overrides. |
| `OverlayCaption` | **`true`** | When `true`, composite caption via PIL. When `false`, feed it to the diffusion model. |
| `FontStyle` | `auto` | Overlay font: `auto` / `sans` / `serif` / `display` / `script` / `mono` / path. |
| `Width` × `Height` | 1024 × 1024 | Output image size. |
| `InferenceSteps` | 4 | Denoising steps. Klein 4B is distilled to 4; bump to 50 for klein-base-4B / SDXL / SD3.5. |
| `GuidanceScale` | 1.0 | Classifier-free guidance. Klein 4B uses 1.0, klein-base-4B uses 4.0, SDXL Turbo uses 0.0, SDXL/SD3.5 use 5–7.5. |
| `Seed` | -1 | -1 = derive a deterministic seed from line index per task. |
| `HfToken` | _(empty)_ | HuggingFace token for gated models. Not needed for the default. |

## Trying other models

The bundle's `InstallDeps` job environment installs `diffusers` from git, so any pipeline class supported by upstream `diffusers` works. To switch:

```bash
# FLUX.2-klein-base-4B (undistilled, slower, more controllable; better text rendering)
--parameter ModelName=black-forest-labs/FLUX.2-klein-base-4B \
--parameter InferenceSteps=50 \
--parameter GuidanceScale=4.0

# SDXL Turbo (~7 GB, distilled to 1–4 steps, works at 512×512)
--parameter ModelName=stabilityai/sdxl-turbo \
--parameter InferenceSteps=2 \
--parameter GuidanceScale=0.0 \
--parameter Width=512 \
--parameter Height=512

# Stable Diffusion XL Base (high quality, 1024×1024, slower)
--parameter ModelName=stabilityai/stable-diffusion-xl-base-1.0 \
--parameter InferenceSteps=30 \
--parameter GuidanceScale=7.0

# FLUX.1-dev (gated — best diffusion text rendering; accept the license and pass an HF token)
--parameter ModelName=black-forest-labs/FLUX.1-dev \
--parameter InferenceSteps=28 \
--parameter GuidanceScale=3.5 \
--parameter HfToken=<your-hf-token>

# Stable Diffusion 3.5 Large (gated)
--parameter ModelName=stabilityai/stable-diffusion-3.5-large \
--parameter InferenceSteps=28 \
--parameter GuidanceScale=4.5 \
--parameter HfToken=<your-hf-token>
```

## How scaling works

- Each **task** = 1 image
- The **fleet** determines how many workers are available
- The **scheduler** assigns tasks to workers as they become free
- The **step environment** ensures the pipeline loads once per worker, not once per task

Example: 100 prompts on a fleet with max 5 workers → 5 pipelines load in parallel, each worker generates ~20 images sequentially, total time ≈ pipeline load + (100/5) × per-image time.

## Troubleshooting

**"diffusers server did not start within 600s"** — first run downloads ~13 GB for FLUX.2 Klein 4B (or ~24 GB for FLUX.1-schnell/dev). If your network is slow, the wait script may time out. Check the worker's `diffusers_server.log` (path is logged via `openjd_env: DIFFUSERS_LOG=...`) and either retry or bump `MAX_WAIT` in `wait_for_diffusers.py`.

**"401 Client Error" / "Cannot access gated repo"** — the model you're using requires accepting a license on HuggingFace and an HF token. The default FLUX.2 Klein 4B is ungated. If you're using FLUX.1-schnell, FLUX.1-dev, or SD3.5, click "Agree and access repository" on the model's HuggingFace page, create a read token at https://huggingface.co/settings/tokens, and pass `--parameter HfToken=hf_...`.

**Out-of-memory on the GPU** — FLUX.2 Klein 4B needs ~13 GB VRAM with CPU offloading already enabled. If you're hitting OOM, switch to a smaller model (SDXL Turbo at 512×512 needs ~7 GB) or reduce `Width`/`Height`.

**Style applies inconsistently across prompts** — distilled models (4-step inference) sometimes lose style fidelity when prompts contain strong photographic or competing aesthetic cues. Three fixes: (1) make the `StyleSuffix` more explicit (use technical words like "bold lineart", "halftone shading", "flat colors" rather than just vibe words); (2) edit prompts to remove competing cues like "soft volumetric lighting" or "rainy night"; (3) switch to `FLUX.2-klein-base-4B` with `InferenceSteps=50` for dramatically more consistent style adherence at the cost of speed.

**InstallDeps fails / takes forever** — `pip install git+https://github.com/huggingface/diffusers.git` and the Google Fonts download both need network egress to GitHub and PyPI. If your fleet runs in a network-restricted VPC, you'll need to either pre-bake the dependencies into a custom AMI / conda channel, or open egress.

## References

- [FLUX.2 Klein 4B on HuggingFace](https://huggingface.co/black-forest-labs/FLUX.2-klein-4B) — Apache 2.0, ungated, distilled to 4 steps, ~13 GB VRAM.
- [FLUX.2 Klein base 4B on HuggingFace](https://huggingface.co/black-forest-labs/FLUX.2-klein-base-4B) — undistilled foundation model, best for fine-tuning and high-fidelity inference.
- [diffusers documentation](https://huggingface.co/docs/diffusers)
- [Pillow ImageDraw.rounded_rectangle](https://pillow.readthedocs.io/en/stable/reference/ImageDraw.html#PIL.ImageDraw.ImageDraw.rounded_rectangle)
- [Open Job Description Step Environments](https://github.com/OpenJobDescription/openjd-specifications/wiki/2023-09-Template-Schemas#4-environment)
- [Deadline Cloud Task Chunking](https://docs.aws.amazon.com/deadline-cloud/latest/developerguide/build-job-bundle-chunking.html)
- [`vllm_batch`](../vllm_batch/) — the text-side companion bundle.
