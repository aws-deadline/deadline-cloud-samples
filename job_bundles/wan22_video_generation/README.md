# Wan2.2 Video Generation

Generate short video clips from a text prompt using [Wan2.2](https://github.com/Wan-Video/Wan2.2),
Alibaba Tongyi Lab's open video generation model. Each task renders one
independent clip with its own seed, so a single job fans out across workers and
returns a set of variations on the same prompt.

![A red fox trotting through a snowy pine forest at golden hour](.images/fox_snowy_forest.jpg)

A frame from the default prompt, rendered at 1280x704 for 121 frames on a single
NVIDIA L4.

## How it works

This job bundle uses the [diffusers](https://github.com/huggingface/diffusers)
`WanPipeline` to run the **Wan2.2 TI2V-5B** checkpoint. Weights are pulled from
Hugging Face at runtime, so nothing is redistributed in this repository.

The job has a single step, `GenerateVideo`, whose task parameter space is
`1-NumClips`. Workers download the checkpoint into a cache on the fleet's
persistent volume, then render their assigned clips and write MP4 files into
the output directory. Because that volume outlives individual workers, later
workers reuse the checkpoint instead of downloading it again.

## Prerequisites

- AWS Deadline Cloud farm with a GPU-enabled Linux queue
- [Deadline Cloud CLI](https://github.com/aws-deadline/deadline-cloud) installed
- Worker with an NVIDIA GPU, **24 GB VRAM minimum**, and **64 GiB of system memory**
- At least 60 GiB free for the model cache. Enabling persistent storage on the
  fleet is recommended so workers share one download. See
  [Model cache location](#model-cache-location).

No Hugging Face token is required, because the Wan2.2 repositories are ungated.

## Fleet requirements

| Resource | Minimum | Notes |
|----------|---------|-------|
| GPU VRAM | 24 GB | A10G, L4, L40S, or better |
| System memory | 64 GiB | CPU offload holds the weights in RAM alongside the ffmpeg export |
| Disk | 60 GiB free | Checkpoint is ~34 GiB plus download staging |
| OS | Linux | |

The script checks the VRAM of the GPU it is scheduled on and adjusts. Below
40 GiB it turns on two diffusers features. Sequential CPU offload streams
submodules to the GPU on demand, so the model fits on a 24 GB card. VAE tiling
bounds peak memory during decode. On larger cards (L40S, A100) the whole pipeline
stays resident and runs considerably faster.

Verified end to end on an NVIDIA L4 at both reduced and default settings.

## Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `Prompt` | *(a fox in a snowy forest)* | Text prompt describing the video |
| `NumClips` | 1 | Clips to generate, each with a distinct seed |
| `OutputDir` | _(required)_ | Directory to write `.mp4` files into |
| `Width` | 1280 | Frame width; must be a multiple of 32 |
| `Height` | 704 | Frame height; must be a multiple of 32 |
| `NumFrames` | 121 | 121 frames at 24 fps is about 5 seconds |
| `Fps` | 24 | Playback frame rate of the exported MP4 |
| `NumInferenceSteps` | 50 | Denoising steps; lower is faster, less detailed |
| `GuidanceScale` | 5.0 | Classifier-free guidance scale |
| `Seed` | -1 | Base seed, offset per clip; -1 derives from clip index |
| `NegativePrompt` | *(empty)* | Empty uses the tuned default from the model card |
| `ModelId` | `Wan-AI/Wan2.2-TI2V-5B-Diffusers` | Hugging Face repo ID |
| `HFCacheDir` | *(empty)* | Model cache; empty uses the fleet's persistent volume |

### Resolution and frame count constraints

`Width` and `Height` must both be multiples of 32. Wan2.2's VAE downsamples 16x
spatially and the transformer patchifies 2x2 on top of that, so other values
fail with a shape mismatch at decode time.

`NumFrames` must satisfy `(NumFrames - 1) % 4 == 0`, because the VAE also
compresses 4x temporally. Values such as 17, 49, 121, and 193 are valid.
diffusers floors the latent frame count rather than raising an error, so an
invalid value would otherwise render for minutes and quietly return a clip with
fewer frames than requested.

`Width x Height x NumFrames` must also stay within the pixel-frame budget of the
tuned 1280x704 / 121-frame workload. The individual maxima multiply out to well
beyond what a 24 GB card can decode, so the product is capped as well.

The script validates all of these, plus the guidance scale, seed range, and
output directory permissions, before loading the model. Bad values fail in
seconds rather than after a long render.

Wan2.2's 720P task is trained at 1280x704 (or 704x1280 portrait); staying at or
near those dimensions gives the best results.

### Model cache location

With `HFCacheDir` empty, the script picks the cache location at runtime:

1. The fleet's [persistent volume](https://docs.aws.amazon.com/deadline-cloud/latest/userguide/volumes.html),
   via the `DEADLINE_PERSISTENT_MOUNT` path Deadline Cloud sets on workers when
   the fleet has persistent storage enabled. **Prefer this.** Only that volume
   survives worker replacement, so later workers reuse the checkpoint instead of
   downloading it again. The default 250 GiB volume is well above the 60 GiB
   needed here.
2. Otherwise `/var/tmp/wan22_hf_cache`, which on a Linux service-managed fleet
   worker is on the root EBS volume. The job runs fine, but that volume is
   discarded with the worker, so every new worker re-downloads all ~34 GiB. The
   log names the fallback path when it is used.

Setting `HFCacheDir` to an explicit path overrides both. It needs 60 GiB free on
a real disk. Not `/tmp`: on a Linux service-managed fleet worker that is a
RAM-backed tmpfs limited to half of system memory, or about 32 GiB on this job's
64 GiB worker, so the download dies with `No space left on device`. This follows
the [Amazon Linux 2023 default](https://docs.aws.amazon.com/linux/al2023/ug/compare-al2-al2023-tmp.html)
that service-managed fleet workers are built on.

`HFCacheDir` is deliberately a `STRING` rather than a `PATH` parameter so the
downloaded weights stay out of job attachments and are never uploaded back to
S3 at job completion.

### How parameters reach the script

OpenJD substitutes `{{Param.*}}` format strings verbatim, without shell
escaping. Interpolating a free-text field such as `Prompt` into a shell command
line would let ordinary punctuation break out of its quoting: a literal `"` ends
the string, and `$(...)`, backticks, and `$VAR` are expanded by bash before the
script ever sees them.

This bundle avoids that entirely. Every user-supplied value is published as a
`WAN_*` environment variable by the `GenerationSettings` step environment, and
the task action runs `python` directly instead of wrapping it in a shell. The
script reads the values with `os.environ`, so no shell ever re-parses them and
prompts may contain quotes, `$`, and backticks freely.

The same variables act as defaults for the equivalent command-line flags, so the
script also runs standalone:

```bash
WAN_PROMPT="a red fox in a snowy forest" \
WAN_OUTPUT_DIR=./out \
WAN_HF_CACHE_DIR=~/wan22_hf_cache \
  python generate_video.py --clip-index 1
```

## Submitting

GUI submitter:

```bash
deadline bundle gui-submit ./wan22_video_generation
```

CLI submitter:

```bash
deadline bundle submit ./wan22_video_generation \
  --queue-id <gpu-queue-id> \
  -p Prompt="A hot air balloon drifting over terraced rice fields at dawn" \
  -p NumClips=4 \
  -p OutputDir=~/wan22_output
```

A faster smoke test, using lower resolution and fewer frames and steps:

```bash
deadline bundle submit ./wan22_video_generation \
  --queue-id <gpu-queue-id> \
  -p NumClips=1 \
  -p Width=704 \
  -p Height=480 \
  -p NumFrames=49 \
  -p NumInferenceSteps=20 \
  -p OutputDir=~/wan22_output
```

## Downloading output

```bash
deadline job download-output --job-id <job-id> --queue-id <gpu-queue-id>
```

Clips use the filenames `wan22_clip_0001.mp4`, `wan22_clip_0002.mp4`, and so on.

## Runtime expectations

The first task on a fresh worker pays two one-time costs: installing PyTorch and
diffusers (a few minutes) and downloading the ~34 GiB checkpoint. Both are
per-session, so subsequent tasks in the same session start generating
immediately.

Generation itself dominates after that. Both figures below were measured on an
NVIDIA L4 (22 GiB usable VRAM, sequential CPU offload and VAE tiling enabled):

| Settings | Denoising | Output |
|----------|-----------|--------|
| 704x480, 49 frames, 20 steps | ~2 min | 2.0 s clip |
| 1280x704, 121 frames, 50 steps (defaults) | ~37 min | 5.0 s clip |

Cost scales with steps, frames, and pixels together, so lower
`NumInferenceSteps` and resolution while iterating on a prompt, then run the
defaults for the final render.

On GPUs with less than 40 GiB of VRAM the script enables VAE tiling, which
trades a little speed (roughly 44 s/step versus 31 s/step at 720P) for a flat
memory ceiling during decode. Without it, full-resolution renders complete every
denoising step and then run out of memory in the VAE.

Because a multi-clip job spreads tasks across workers, wall-clock time for
`NumClips=8` on eight workers is close to the time for one clip, plus setup.
Tasks sharing a worker reuse its cache and start generating immediately. Each
persistent volume serves one worker at a time, so eight concurrent workers each
download the checkpoint once. Later workers that pick up a warm volume skip it.
Without persistent storage, every worker downloads it.

## Licensing

Wan2.2 is released under the [Apache License 2.0](https://github.com/Wan-Video/Wan2.2/blob/main/LICENSE.txt),
covering both the code and the model weights.

## References

- [Wan2.2 on GitHub](https://github.com/Wan-Video/Wan2.2)
- [Wan2.2-TI2V-5B-Diffusers on Hugging Face](https://huggingface.co/Wan-AI/Wan2.2-TI2V-5B-Diffusers)
- [diffusers Wan pipeline documentation](https://huggingface.co/docs/diffusers/api/pipelines/wan)
