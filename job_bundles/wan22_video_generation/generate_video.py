#!/usr/bin/env python3
"""Generate a video clip with Wan2.2 TI2V-5B using the diffusers WanPipeline.

Each task renders one independent clip, distinguished by its seed. Clips are
written as MP4 files into the output directory so the whole job produces a set
of variations on the same prompt.
"""
import argparse
import gc
import json
import math
import os
import stat as stat_module
from pathlib import Path

# HF_HOME must be set before diffusers/transformers are imported, otherwise the
# libraries capture the default ~/.cache location at import time.
def _configure_hf_cache(cache_dir: str) -> Path:
    """Point HuggingFace at the cache directory and return the resolved path.

    Returns the path so callers measure the same location the download uses.
    Passing the raw argument to the space checks instead would make them stat a
    literal "~" path that was never created.
    """
    # expanduser before resolve: resolve() alone turns a leading "~" into a
    # literal directory named "~" inside the current working directory.
    cache = Path(cache_dir).expanduser().resolve()
    cache.mkdir(parents=True, exist_ok=True)
    os.environ["HF_HOME"] = str(cache)
    os.environ["HF_HUB_CACHE"] = str(cache / "hub")
    # Reduce allocator fragmentation. Sequential CPU offload streams submodules
    # on and off the GPU constantly, which leaves the caching allocator holding
    # many differently-sized reserved-but-unused blocks; a large contiguous VAE
    # decode allocation can then fail even with GiB nominally free.
    os.environ.setdefault("PYTORCH_CUDA_ALLOC_CONF", "expandable_segments:True")
    # Accelerates the large checkpoint download via Xet. This replaced the older
    # HF_HUB_ENABLE_HF_TRANSFER flag, which huggingface_hub now ignores.
    os.environ.setdefault("HF_XET_HIGH_PERFORMANCE", "1")
    return cache


# The TI2V-5B checkpoint is ~34 GiB on disk, and Xet needs room for its staging
# chunks on top of that. Deadline Cloud workers mount /tmp as a RAM-backed
# tmpfs, so a cache placed there both competes with the model for memory and
# hits ENOSPC partway through the download. Fail early with a clear message
# instead of dying 20 GiB in.
MIN_CACHE_FREE_GIB = 60


def _cached_bytes(cache_dir: str) -> int:
    """Bytes already occupied on disk by the cache directory.

    Uses lstat so symlinks are measured as links rather than as their targets.
    The HuggingFace hub layout stores each file once under `models--*/blobs/`
    and links to it from `models--*/snapshots/<rev>/`, so following symlinks
    would count every blob twice and overstate the cache by 2x.
    """
    total = 0
    for path in Path(cache_dir).rglob("*"):
        try:
            stat = path.lstat()
        except OSError:
            # File removed mid-walk or an unreadable entry; neither is fatal.
            continue
        if not stat_module.S_ISDIR(stat.st_mode):
            total += stat.st_size
    return total


def _revision_is_complete(revision: Path) -> bool:
    """True when every shard referenced by a revision's indexes is present.

    The hub links each file into the snapshot as it finishes downloading, so
    "some non-empty safetensors exist" does not mean the model is whole. Every
    sharded component publishes a `*.safetensors.index.json` whose `weight_map`
    names the shards it needs; require all of them, and require each component
    named by `model_index.json` to hold at least one weight file.
    """
    model_index = revision / "model_index.json"
    if not model_index.is_file():
        return False
    try:
        components = json.loads(model_index.read_text())
    except (OSError, ValueError):
        return False

    # Every shard named by every index must exist and be non-empty.
    for index_path in revision.rglob("*.safetensors.index.json"):
        try:
            weight_map = json.loads(index_path.read_text()).get("weight_map", {})
        except (OSError, ValueError):
            return False
        for shard in set(weight_map.values()):
            shard_path = index_path.parent / shard
            if not shard_path.is_file() or shard_path.stat().st_size == 0:
                return False

    # Components listed in model_index.json that carry weights must have them.
    # Entries are [library, class] pairs. Skip components that carry no weights,
    # and skip [null, null] entries: Wan2.2 TI2V-5B declares "transformer_2"
    # that way because the 5B model is dense, unlike the A14B mixture-of-experts
    # variants that populate it. Treating those as required weights would report
    # a complete snapshot as incomplete.
    for name, spec in components.items():
        if name.startswith("_") or not isinstance(spec, list):
            continue
        if name in ("scheduler", "tokenizer", "feature_extractor"):
            continue
        if not any(part for part in spec):
            continue
        component_dir = revision / name
        if not component_dir.is_dir():
            return False
        weights = [
            f
            for f in component_dir.rglob("*.safetensors")
            if f.is_file() and f.stat().st_size > 0
        ]
        if not weights:
            return False
    return True


def _snapshot_is_complete(cache_dir: str, model_id: str) -> bool:
    """True when the model's snapshot already holds every expected weight file.

    A complete snapshot means nothing needs downloading, so the free-space
    requirement does not apply. A partial snapshot must not qualify: skipping
    the check would let diffusers resume fetching multi-GiB shards with no space
    guard, which is the ENOSPC failure this module exists to prevent.
    """
    repo = "models--" + model_id.replace("/", "--")
    snapshots = Path(cache_dir) / "hub" / repo / "snapshots"
    if not snapshots.is_dir():
        return False
    return any(_revision_is_complete(rev) for rev in snapshots.iterdir())


def _check_cache_space(cache_dir: str, model_id: str) -> None:
    import shutil

    if _snapshot_is_complete(cache_dir, model_id):
        print(
            f"Checkpoint already cached at {cache_dir}; skipping the free-space "
            "requirement because nothing needs downloading.",
            flush=True,
        )
        return

    usage = shutil.disk_usage(cache_dir)
    # The cache is shared by every task in a session, so after the first task
    # downloads the checkpoint the free space it consumed is no longer
    # available. Comparing free space alone against the requirement would fail
    # every later task on a volume only moderately larger than the checkpoint,
    # even though the model is already present and nothing needs downloading.
    # Count what is already cached as satisfying the requirement.
    cached_gib = _cached_bytes(cache_dir) / 1024**3
    free_gib = usage.free / 1024**3
    available_gib = free_gib + cached_gib
    print(
        f"Cache directory {cache_dir}: {free_gib:.1f} GiB free, "
        f"{cached_gib:.1f} GiB already cached, "
        f"of {usage.total / 1024**3:.1f} GiB total",
        flush=True,
    )
    if available_gib < MIN_CACHE_FREE_GIB:
        raise SystemExit(
            f"Only {free_gib:.1f} GiB free at {cache_dir} with {cached_gib:.1f} "
            f"GiB already cached, but the Wan2.2 checkpoint needs at least "
            f"{MIN_CACHE_FREE_GIB} GiB including download staging space. Point "
            "--hf-cache-dir at a real disk; on Deadline Cloud service-managed "
            "fleets /tmp is a RAM-backed tmpfs, so prefer a path under /var/tmp "
            "or the session directory."
        )


# Wan2.2's 720P task is trained at 1280x704 (or 704x1280 for portrait). The VAE
# compresses 4x16x16, and the transformer patchifies 2x2 on top of that, so both
# dimensions must be multiples of 32 to avoid a shape mismatch at decode time.
DIMENSION_MULTIPLE = 32

# The VAE also compresses 4x temporally, so num_frames must be 4n + 1.
TEMPORAL_MULTIPLE = 4

# Nominal 24 GB accelerators (A10G, L4) report roughly 22 GiB usable, which is
# the smallest card this model runs on with offload and tiling enabled.
MIN_VRAM_GIB = 21

# width * height * frames for the tuned 1280x704x121 workload, which is the
# largest configuration verified on a 24 GB card. Memory use tracks this
# product, so it is capped rather than each dimension independently.
MAX_PIXEL_FRAMES = 1280 * 704 * 121

# The published negative prompt from the Wan2.2 model card. Steers away from
# oversaturation, static frames, and malformed anatomy. Kept verbatim (Chinese)
# because that is what the model was tuned against.
DEFAULT_NEGATIVE_PROMPT = (
    "色调艳丽，过曝，静态，细节模糊不清，字幕，风格，作品，画作，画面，静止，"
    "整体发灰，最差质量，低质量，JPEG压缩残留，丑陋的，残缺的，多余的手指，"
    "画得不好的手部，画得不好的脸部，畸形的，毁容的，形态畸形的肢体，手指融合，"
    "静止不动的画面，杂乱的背景，三条腿，背景人很多，倒着走"
)


def _validate_dimension(name: str, value: int) -> None:
    if value % DIMENSION_MULTIPLE != 0:
        raise SystemExit(
            f"{name} must be a multiple of {DIMENSION_MULTIPLE} (got {value}). "
            "Wan2.2's VAE downsamples 16x spatially and the transformer "
            "patchifies 2x2 on top of that."
        )


def _validate_num_frames(value: int) -> None:
    # The VAE compresses 4x temporally, so the frame count must leave a whole
    # number of latent frames after the initial keyframe. diffusers floors the
    # latent count instead of raising, which would silently return a clip with
    # fewer frames than requested after a full render.
    if (value - 1) % TEMPORAL_MULTIPLE != 0:
        nearest = ((value - 1) // TEMPORAL_MULTIPLE) * TEMPORAL_MULTIPLE + 1
        raise SystemExit(
            f"--num-frames must satisfy (frames - 1) % {TEMPORAL_MULTIPLE} == 0 "
            f"(got {value}; nearest valid value is {nearest}). Wan2.2's VAE "
            "compresses 4x temporally."
        )


def _validate_workload(width: int, height: int, num_frames: int) -> None:
    # Width, height, and frame count are bounded individually, but their product
    # is not, and memory use tracks the product. The template's maxima combine to
    # about 2.9x the verified 1280x704x121 workload, which exceeds a 24 GB card
    # even with tiling. OpenJD cannot express a constraint across parameters, so
    # enforce the budget here.
    pixel_frames = width * height * num_frames
    if pixel_frames > MAX_PIXEL_FRAMES:
        raise SystemExit(
            f"{width}x{height} for {num_frames} frames is "
            f"{pixel_frames / 1e6:.0f}M pixel-frames, above the "
            f"{MAX_PIXEL_FRAMES / 1e6:.0f}M budget this sample is verified for. "
            "Reduce the resolution or the frame count; 1280x704 for 121 frames "
            "is the tuned maximum."
        )


def _env_default(name: str, fallback=None, convert=None):
    """Read a job parameter from the environment.

    The job template passes every user-supplied value through environment
    variables rather than the command line so that no shell re-parses free text
    such as the prompt. Empty strings count as unset, which lets an empty
    NegativePrompt field fall back to the tuned default below.

    When `convert` is given the value is converted here rather than by
    argparse's `type=`. argparse applies `type=` to string defaults and reports
    failures through `parser.error()`, which exits with a bare usage dump
    instead of a message naming the offending variable.
    """
    value = os.environ.get(name, "")
    if value == "":
        return fallback
    if convert is None:
        return value
    try:
        return convert(value)
    except ValueError:
        raise SystemExit(
            f"{name}={value!r} is not a valid "
            f"{'integer' if convert is int else 'number'}."
        )


def _validate_finite(name: str, value: float) -> None:
    # float() accepts "nan", "inf", and "-inf". A non-finite guidance scale
    # poisons every latent through the classifier-free-guidance blend, diffusers
    # never checks, and the VAE decodes all-NaN latents to uniform frames. The
    # task would exit 0 after a full render having written a blank video.
    if not math.isfinite(value):
        raise SystemExit(f"{name} must be a finite number (got {value}).")


def _validate_seed(seed: int, clip_index: int) -> None:
    # torch.Generator.manual_seed accepts values in [-0x8000000000000000,
    # 0xffffffffffffffff] and raises otherwise, but not until the generator is
    # created after the checkpoint download and pipeline load. Check the value
    # actually used, since the clip index is added to the base seed.
    if seed != -1:
        effective = seed + clip_index
        if not -0x8000000000000000 <= effective <= 0xFFFFFFFFFFFFFFFF:
            raise SystemExit(
                f"--seed {seed} plus clip index {clip_index} is {effective}, "
                "which is outside the range torch accepts for a manual seed "
                "(-2^63 to 2^64-1)."
            )


def main():
    parser = argparse.ArgumentParser(
        description=(
            "Generate a Wan2.2 video clip. Values default to the WAN_* "
            "environment variables set by the job template, and may be "
            "overridden with the flags below when running locally."
        )
    )
    parser.add_argument("--prompt", default=_env_default("WAN_PROMPT"))
    parser.add_argument(
        "--negative-prompt",
        default=_env_default("WAN_NEGATIVE_PROMPT", DEFAULT_NEGATIVE_PROMPT),
    )
    parser.add_argument(
        "--width", type=int, default=_env_default("WAN_WIDTH", 1280, int)
    )
    parser.add_argument(
        "--height", type=int, default=_env_default("WAN_HEIGHT", 704, int)
    )
    parser.add_argument(
        "--num-frames",
        type=int,
        default=_env_default("WAN_NUM_FRAMES", 121, int),
    )
    parser.add_argument(
        "--fps", type=int, default=_env_default("WAN_FPS", 24, int)
    )
    parser.add_argument(
        "--num-inference-steps",
        type=int,
        default=_env_default("WAN_NUM_INFERENCE_STEPS", 50, int),
    )
    parser.add_argument(
        "--guidance-scale",
        type=float,
        default=_env_default("WAN_GUIDANCE_SCALE", 5.0, float),
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=_env_default("WAN_SEED", -1, int),
        help="Base seed. -1 derives a seed from the clip index alone.",
    )
    parser.add_argument("--clip-index", type=int, required=True)
    parser.add_argument("--output-dir", default=_env_default("WAN_OUTPUT_DIR"))
    parser.add_argument(
        "--model-id",
        default=_env_default("WAN_MODEL_ID", "Wan-AI/Wan2.2-TI2V-5B-Diffusers"),
        help="HuggingFace repo ID for the Wan2.2 checkpoint.",
    )
    parser.add_argument(
        "--hf-cache-dir",
        default=_env_default("WAN_HF_CACHE_DIR"),
        help="Directory for the HuggingFace hub cache, shared across tasks.",
    )
    args = parser.parse_args()

    for name, value in (
        ("--prompt (WAN_PROMPT)", args.prompt),
        ("--output-dir (WAN_OUTPUT_DIR)", args.output_dir),
        ("--hf-cache-dir (WAN_HF_CACHE_DIR)", args.hf_cache_dir),
    ):
        if not value:
            raise SystemExit(f"{name} is required but was empty.")

    _validate_dimension("--width", args.width)
    _validate_dimension("--height", args.height)
    _validate_num_frames(args.num_frames)
    _validate_finite("--guidance-scale", args.guidance_scale)
    _validate_seed(args.seed, args.clip_index)
    _validate_workload(args.width, args.height, args.num_frames)

    # Create the output directory now rather than after generating. Otherwise a
    # path the session user cannot write to is only discovered once the render
    # has finished, discarding the frames along with the GPU time that made them.
    output_dir = Path(args.output_dir).expanduser()
    try:
        output_dir.mkdir(parents=True, exist_ok=True)
        probe = output_dir / ".wan22_write_probe"
        probe.touch()
        probe.unlink()
    except OSError as exc:
        raise SystemExit(f"Output directory {output_dir} is not writable: {exc}")

    cache_dir = _configure_hf_cache(args.hf_cache_dir)
    _check_cache_space(cache_dir, args.model_id)

    # Imported after HF_HOME is set.
    import torch
    from diffusers import AutoencoderKLWan, WanPipeline
    from diffusers.utils import export_to_video

    if not torch.cuda.is_available():
        raise SystemExit(
            "No CUDA device visible. This job requires a GPU worker; check that "
            "the fleet provides an NVIDIA accelerator and drivers are loaded."
        )

    gpu_name = torch.cuda.get_device_name(0)
    vram_gib = torch.cuda.get_device_properties(0).total_memory / 1024**3
    print(f"GPU: {gpu_name} ({vram_gib:.1f} GiB VRAM)", flush=True)

    # A bare "amount.worker.gpu: 1" host requirement also matches 16 GiB cards
    # such as the T4, which cannot run this model even with offload and tiling.
    # Fail here rather than after downloading the checkpoint and OOM-ing partway
    # through denoising. Nominal 24 GB cards report about 22 GiB usable.
    if vram_gib < MIN_VRAM_GIB:
        raise SystemExit(
            f"{gpu_name} reports {vram_gib:.1f} GiB of VRAM, but Wan2.2 "
            f"TI2V-5B needs at least {MIN_VRAM_GIB} GiB (a nominal 24 GB card). "
            "Schedule this job onto a fleet with A10G, L4, L40S, or larger "
            "accelerators."
        )

    print(f"Loading Wan2.2 pipeline from {args.model_id} ...", flush=True)
    # The VAE stays in float32 while the rest of the pipeline runs in bfloat16.
    # Wan's VAE is numerically sensitive and produces washed-out or banded frames
    # in bf16, so this split is deliberate and matches the upstream model card.
    vae = AutoencoderKLWan.from_pretrained(
        args.model_id, subfolder="vae", torch_dtype=torch.float32
    )
    pipe = WanPipeline.from_pretrained(
        args.model_id, vae=vae, torch_dtype=torch.bfloat16
    )

    # 24 GiB cards (A10G, L4) cannot hold the 5B transformer, the T5 text
    # encoder, and the activations for a 121-frame latent at once. Sequential
    # CPU offload streams each submodule to the GPU on demand, which fits in
    # ~24 GiB at the cost of some speed. Cards with more headroom keep the whole
    # pipeline resident and run considerably faster.
    if vram_gib < 40:
        print(
            "Enabling sequential CPU offload to fit within "
            f"{vram_gib:.1f} GiB of VRAM.",
            flush=True,
        )
        pipe.enable_sequential_cpu_offload()
        # Denoising fits on a 24 GiB card, but VAE decode does not: it
        # materializes every frame at full resolution at once, and a 1280x704
        # 121-frame latent needs a single >2.5 GiB allocation on top of the
        # weights still resident from the last denoising step. Tiling decodes in
        # overlapping spatial patches instead, which keeps peak allocation flat
        # with resolution. Without this, full-quality renders complete all 50
        # steps and then die in the VAE.
        pipe.vae.enable_tiling()
    else:
        pipe.to("cuda")

    # Derive a distinct but reproducible seed per clip so that a multi-clip job
    # returns variations rather than N copies of the same video.
    if args.seed == -1:
        seed = args.clip_index * 12345
    else:
        seed = args.seed + args.clip_index
    generator = torch.Generator(device="cpu").manual_seed(seed)

    print(f"Generating clip {args.clip_index} (seed {seed})", flush=True)
    print(f"  prompt: {args.prompt}", flush=True)
    print(
        f"  {args.width}x{args.height}, {args.num_frames} frames @ {args.fps} fps, "
        f"{args.num_inference_steps} steps, guidance {args.guidance_scale}",
        flush=True,
    )

    frames = pipe(
        prompt=args.prompt,
        negative_prompt=args.negative_prompt,
        height=args.height,
        width=args.width,
        num_frames=args.num_frames,
        guidance_scale=args.guidance_scale,
        num_inference_steps=args.num_inference_steps,
        generator=generator,
    ).frames[0]

    # output_dir was created and probed for writability during validation.
    output_path = output_dir / f"wan22_clip_{args.clip_index:04d}.mp4"

    # Release the pipeline before encoding. export_to_video forks an ffmpeg
    # subprocess, and with sequential CPU offload the model weights are still
    # resident in system RAM at this point — enough that fork() fails with
    # ENOMEM on a 64 GiB worker. The frames are plain arrays and do not need the
    # pipeline alive, so dropping it first keeps the encode within memory.
    del pipe, vae
    gc.collect()
    torch.cuda.empty_cache()

    export_to_video(frames, str(output_path), fps=args.fps)

    size_mib = output_path.stat().st_size / 1024**2
    print(f"Saved {output_path} ({size_mib:.1f} MiB)", flush=True)


if __name__ == "__main__":
    main()
