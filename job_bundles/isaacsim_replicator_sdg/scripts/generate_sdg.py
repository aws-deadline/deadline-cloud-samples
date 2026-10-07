#!/usr/bin/env python3
"""Headless Isaac Sim Replicator synthetic data generation for one Deadline Cloud task.

One invocation produces one shard of a larger dataset: `--frames` frames,
deterministically seeded from `--seed`, written with a global frame-index offset
so N concurrent shards never collide on a filename.

Two things about this script are specific to running under a Deadline Cloud
Docker queue environment, and both are easy to get wrong:

1.  The container's ENTRYPOINT never runs. The queue environment starts the
    container with `--entrypoint /bin/sh` and execs each task into it, so the
    workshop image's `docker/sim/entrypoint.sh` is bypassed and `EXP_PATH` is
    NOT set. `SimulationApp` resolves its experience file relative to `EXP_PATH`,
    so we pass `experience=` explicitly instead of relying on the search path.

2.  Isaac Lab's experience files disable the Replicator Orchestrator
    (`exts."omni.replicator.core".Orchestrator.enabled = false` in all four
    isaaclab*.kit files), and the Orchestrator is exactly what
    `rep.orchestrator.step()` drives. So this script must NOT use Isaac Lab's
    AppLauncher -- it launches Isaac Sim's own `isaacsim.exp.base.python.kit`,
    which enables the full Replicator stack.
"""

from __future__ import annotations

import argparse
import json
import os
import random
import sys
import time
from pathlib import Path

# Candidate experience files, most specific first. The image is
# nvcr.io/nvidia/isaac-lab, which IS nvcr.io/nvidia/isaac-sim plus Isaac Lab, so
# Isaac Sim's own apps dir is present at /isaac-sim/apps.
EXPERIENCE_CANDIDATES = (
    "/isaac-sim/apps/isaacsim.exp.base.python.kit",
    "/isaac-sim/apps/isaacsim.exp.base.kit",
)

ANNOTATOR_CHOICES = (
    "rgb",
    "bounding_box_2d_tight",
    "bounding_box_2d_loose",
    "bounding_box_3d",
    "semantic_segmentation",
    "instance_segmentation",
    "instance_id_segmentation",
    "distance_to_camera",
    "distance_to_image_plane",
    "normals",
    "camera_params",
)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--output-dir", required=True,
                   help="Shared OutputDir. This script writes under <dir>/sdg/.")
    p.add_argument("--frames", type=int, required=True,
                   help="Frames this shard produces.")
    p.add_argument("--frame-offset", type=int, required=True,
                   help="Global index of this shard's first frame, so shards do "
                        "not collide on output filenames.")
    p.add_argument("--seed", type=int, required=True)
    p.add_argument("--shard-label", required=True,
                   help="e.g. sdg01. Used for log and marker filenames.")
    p.add_argument("--width", type=int, default=640)
    p.add_argument("--height", type=int, default=480)
    p.add_argument("--renderer", default="RaytracedLighting",
                   choices=("RaytracedLighting", "PathTracing"))
    p.add_argument("--rt-subframes", type=int, default=8,
                   help="Render subframes per capture. Must be >= 2 when "
                        "randomized materials load late, higher to kill ghosting.")
    p.add_argument("--anti-aliasing", type=int, default=3,
                   help="0 off, 1 TAA, 2 FXAA, 3 DLSS, 4 RTXAA. DLSS is temporal, "
                        "so use 0 if you need a tighter frame-to-frame A/B.")
    p.add_argument("--annotators", default="rgb,bounding_box_2d_tight,semantic_segmentation",
                   help="Comma-separated. See ANNOTATOR_CHOICES.")
    p.add_argument("--scene-source", default="primitives",
                   choices=("primitives", "workshop"))
    p.add_argument("--objects", type=int, default=6,
                   help="Randomized foreground objects in the primitives scene.")
    p.add_argument("--experience", default=None,
                   help="Override the Kit experience file.")
    return p.parse_args()


def resolve_experience(override: str | None) -> str:
    candidates = (override,) if override else EXPERIENCE_CANDIDATES
    for path in candidates:
        if path and Path(path).is_file():
            return path
    raise SystemExit(
        "No usable Kit experience file found. Tried: "
        + ", ".join(c for c in candidates if c)
        + "\nEXP_PATH is not set under a Docker queue environment, so the "
          "experience must be passed explicitly."
    )


def configure_caches() -> None:
    """Point Omniverse's caches at the fleet persistent volume when present.

    Cold Kit boot with an empty shader cache is minutes; warm is seconds. The
    Docker queue environment bind-mounts DEADLINE_PERSISTENT_MOUNT into the
    container precisely so this survives session teardown.
    """
    root = os.environ.get("DEADLINE_PERSISTENT_MOUNT")
    if not root:
        print("[sdg] DEADLINE_PERSISTENT_MOUNT unset - shader cache will be cold",
              file=sys.stderr)
        return
    cache = Path(root) / "isaacsim-sdg-cache"
    for sub, var in (("ov", "OV_CACHE_DIR"),
                     ("shaders", "__GL_SHADER_DISK_CACHE_PATH"),
                     ("cuda", "CUDA_CACHE_PATH")):
        d = cache / sub
        d.mkdir(parents=True, exist_ok=True)
        os.environ[var] = str(d)
    print(f"[sdg] caches -> {cache}")


def main() -> int:
    args = parse_args()
    annotators = [a.strip() for a in args.annotators.split(",") if a.strip()]
    unknown = [a for a in annotators if a not in ANNOTATOR_CHOICES]
    if unknown:
        raise SystemExit(f"Unknown annotator(s): {unknown}\nValid: {list(ANNOTATOR_CHOICES)}")

    out_root = Path(args.output_dir)
    sdg_dir = out_root / "sdg"
    log_dir = out_root / "logs"
    # Never rm -rf these: OutputDir is dataFlow INOUT, so this worker's copy also
    # holds other shards' uploads.
    for d in (sdg_dir, log_dir):
        d.mkdir(parents=True, exist_ok=True)

    experience = resolve_experience(args.experience)
    configure_caches()
    print(f"[sdg] experience={experience}")
    print(f"[sdg] shard={args.shard_label} frames={args.frames} "
          f"offset={args.frame_offset} seed={args.seed}")

    boot_started = time.time()
    from isaacsim import SimulationApp  # noqa: E402  (must precede omni imports)

    launch_config = {
        "headless": True,
        "renderer": args.renderer,
        "width": args.width,
        "height": args.height,
        "anti_aliasing": args.anti_aliasing,
    }
    if args.renderer == "PathTracing":
        launch_config["samples_per_pixel_per_frame"] = 64

    # `experience` is a SimulationApp kwarg, not a launch_config key.
    simulation_app = SimulationApp(launch_config, experience=experience)

    # Omniverse imports MUST come after SimulationApp construction.
    import carb.settings  # noqa: E402
    import omni.replicator.core as rep  # noqa: E402
    import numpy as np  # noqa: E402

    settings = carb.settings.get_settings()
    # isaacsim.core.throttling flips /app/asyncRendering on and never flips it
    # back, which silently drops captured frames. NVIDIA's documented fix is to
    # disable async rendering; setting it here covers the same ground as the
    # `--/exts/isaacsim.core.throttling/enable_async=false` command-line arg.
    settings.set("/exts/isaacsim.core.throttling/enable_async", False)
    settings.set("/app/asyncRendering", False)
    settings.set("/omni/replicator/captureOnPlay", False)
    settings.set("/omni/replicator/RTSubframes", args.rt_subframes)
    if args.anti_aliasing == 3:
        settings.set("rtx/post/dlss/execMode", 2)  # Quality

    boot_seconds = time.time() - boot_started
    print(f"[sdg] kit boot {boot_seconds:.1f}s")

    # Seed every RNG the randomizers draw from. rep.set_global_seed covers
    # Replicator's OmniGraph randomizers; random/numpy cover our own draws.
    random.seed(args.seed)
    np.random.seed(args.seed)
    rep.set_global_seed(args.seed)
    rep.orchestrator.set_capture_on_play(False)

    from sdg_scene import build_scene  # noqa: E402  (bundled alongside this file)
    camera = build_scene(rep, args.scene_source, args.objects)

    render_product = rep.create.render_product(camera, (args.width, args.height),
                                               name=args.shard_label)

    # A custom writer rather than BasicWriter: BasicWriter restarts its frame
    # counter at 0 for every writer instance, so all N shards would each write
    # rgb_0000.png. The offset makes the numbering globally unique, which means
    # no rename pass in the merge step.
    # BasicWriter, not a custom writer. BasicWriter restarts its frame counter at
    # 0 per instance, so every shard would write rgb_0000.png into a shared dir.
    # Rather than hand-roll a writer to offset the index (which needs a backend
    # and is easy to get subtly wrong), give each shard its own directory and let
    # the Merge step renumber into one flat dataset.
    shard_dir = sdg_dir / args.shard_label
    shard_dir.mkdir(parents=True, exist_ok=True)
    writer_kwargs = {"output_dir": str(shard_dir)}
    for name in annotators:
        writer_kwargs[name] = True
    if "semantic_segmentation" in annotators:
        writer_kwargs["colorize_semantic_segmentation"] = True
    if "instance_segmentation" in annotators:
        writer_kwargs["colorize_instance_segmentation"] = True

    writer = rep.WriterRegistry.get("BasicWriter")
    writer.initialize(**writer_kwargs)
    writer.attach([render_product])
    print(f"[sdg] BasicWriter -> {shard_dir} annotators={annotators}")

    marker_every = max(1, args.frames // 10)
    captured = 0
    cap_started = time.time()
    try:
        for i in range(args.frames):
            rep.utils.send_og_event("randomize")
            rep.orchestrator.step(delta_time=0.0, rt_subframes=args.rt_subframes)
            captured += 1
            if captured % marker_every == 0 or captured == args.frames:
                pct = 100.0 * captured / args.frames
                print(f"openjd_progress: {pct:.1f}")
                (log_dir / f"_marker_{args.shard_label}_{captured:04d}").touch()
    finally:
        # Teardown ORDER IS LOAD-BEARING: drain first, then detach, then destroy.
        # Detaching the writer before wait_until_complete() discards whatever
        # writes are still queued, which produces a run that captures frames,
        # reports no error, and leaves an empty output directory.
        try:
            rep.orchestrator.wait_until_complete()
            print("[sdg] orchestrator drained")
        except Exception as exc:  # noqa: BLE001
            print(f"[sdg] wait_until_complete failed: {exc}", file=sys.stderr)
        for label, fn in (("writer.detach", writer.detach),
                          ("render_product.destroy", render_product.destroy)):
            try:
                fn()
            except Exception as exc:  # noqa: BLE001
                print(f"[sdg] {label} warning: {exc}", file=sys.stderr)

    cap_seconds = time.time() - cap_started
    fps = captured / cap_seconds if cap_seconds > 0 else 0.0
    # Count real files on disk. The previous version reported `captured`, which is
    # just the loop counter: it read 4 frames while the writer had produced zero
    # files, and every downstream check believed it.
    # BasicWriter writes FLAT into output_dir: rgb_0000.png, not rgb/0000.png.
    written = len(list(shard_dir.glob("rgb_*.png")))
    if written == 0:
        # Each farm round-trip costs ~10 minutes, so when the writer produces
        # nothing, dump enough state to diagnose it from this log alone.
        all_files = [p for p in shard_dir.rglob("*") if p.is_file()]
        print(f"[sdg] NO rgb_*.png in {shard_dir}", file=sys.stderr)
        print(f"[sdg] shard_dir exists={shard_dir.is_dir()} "
              f"total files={len(all_files)}", file=sys.stderr)
        for p in all_files[:20]:
            print(f"[sdg]   {p.relative_to(shard_dir)} ({p.stat().st_size} B)", file=sys.stderr)
        for sub in sorted(p for p in shard_dir.iterdir() if p.is_dir()) if shard_dir.is_dir() else []:
            print(f"[sdg]   dir {sub.name}/ -> {len(list(sub.iterdir()))} entries", file=sys.stderr)
        try:
            print(f"[sdg] writer backend attrs: "
                  f"{[a for a in dir(writer) if 'backend' in a.lower() or 'dir' in a.lower()]}",
                  file=sys.stderr)
        except Exception:  # noqa: BLE001
            pass
        written = len(all_files)
    summary = {
        "shard": args.shard_label,
        "frames": captured,
        "files_written": written,
        "shard_dir": args.shard_label,
        "frame_offset": args.frame_offset,
        "seed": args.seed,
        "scene_source": args.scene_source,
        "renderer": args.renderer,
        "resolution": [args.width, args.height],
        "rt_subframes": args.rt_subframes,
        "anti_aliasing": args.anti_aliasing,
        "annotators": annotators,
        "kit_boot_seconds": round(boot_seconds, 1),
        "capture_seconds": round(cap_seconds, 1),
        "avg_frame_fps": round(fps, 3),
        "shader_cache": "warm" if boot_seconds < 120 else "cold",
    }
    shard_json = sdg_dir / f"{args.shard_label}.json"
    shard_json.write_text(json.dumps(summary, indent=2) + "\n")
    print(f"[sdg] {json.dumps(summary)}")
    print(f"[sdg] wrote {shard_json}")

    # Log the real layout once. BasicWriter nests output under the render product
    # when more than one is attached, and knowing the actual tree is what lets the
    # Merge step find frames without guessing.
    if shard_dir.is_dir():
        for sub in sorted(p for p in shard_dir.iterdir() if p.is_dir()):
            names = sorted(p.name for p in sub.iterdir())
            print(f"[sdg] layout {sub.name}/ ({len(names)}): {names[:4]}")
        loose = sorted(p.name for p in shard_dir.iterdir() if p.is_file())
        if loose:
            print(f"[sdg] layout (loose files): {loose[:6]}")

    ok = (captured == args.frames) and written > 0
    if not ok:
        print(f"[sdg] FAIL captured={captured}/{args.frames} files_written={written}",
              file=sys.stderr)
    sys.stdout.flush()
    sys.stderr.flush()

    # os._exit BEFORE simulation_app.close(). In this image close() does not
    # return: it tears the process down itself and the process ends with exit
    # code 1, so anything after it is dead code and a fully successful run is
    # reported as a failure. Skipping close() is safe here because the container
    # is discarded at the end of the task.
    os._exit(0 if ok else 1)


if __name__ == "__main__":
    sys.exit(main())
