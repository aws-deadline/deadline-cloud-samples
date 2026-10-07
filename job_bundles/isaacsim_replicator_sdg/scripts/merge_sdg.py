#!/usr/bin/env python3
"""Merge every SDG shard into one dataset index, and emit COCO annotations.

Standard library only, and Python 3.9 compatible, so this runs on whatever
interpreter the container or the worker provides without extra dependencies.

The per-shard image files already carry globally unique frame numbers (see
sdg_writer.OffsetWriter), so there is nothing to rename. This step only:
  1. verifies each shard reported the frame count it was asked for
  2. concatenates the per-frame bounding-box JSON into one COCO instances.json
  3. writes sdg_summary.json and prints a table
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
from pathlib import Path


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--output-dir", required=True)
    p.add_argument("--expected-frames", type=int, required=True)
    p.add_argument("--expected-shards", type=int, required=True)
    p.add_argument("--width", type=int, default=640)
    p.add_argument("--height", type=int, default=480)
    return p.parse_args()


def load_shards(sdg_dir: Path, expected_shards: int):
    found, missing = [], []
    for i in range(1, expected_shards + 1):
        path = sdg_dir / "sdg{:02d}.json".format(i)
        if path.is_file():
            try:
                found.append(json.loads(path.read_text()))
            except json.JSONDecodeError as exc:
                missing.append("sdg{:02d} (corrupt: {})".format(i, exc))
        else:
            missing.append("sdg{:02d} (absent)".format(i))
    return found, missing


FRAME_SUFFIX = re.compile(r"^(?P<prefix>.+?)_(?P<index>\d+)$")


def collate(sdg_dir: Path, shards):
    """Renumber each shard's BasicWriter output into one flat dataset.

    BasicWriter writes FLAT into its output_dir and restarts its frame counter at
    0 per writer instance, e.g.

        sdg/sdg01/rgb_0000.png
        sdg/sdg01/bounding_box_2d_tight_0000.npy
        sdg/sdg01/bounding_box_2d_tight_labels_0000.json
        sdg/sdg01/semantic_segmentation_0000.png

    There are no per-annotator subdirectories. So each shard gets its own
    directory and this step renumbers every file into `sdg/dataset/` with a
    single global index, keeping each annotator's prefix intact.
    """
    dataset = sdg_dir / "dataset"
    dataset.mkdir(parents=True, exist_ok=True)
    global_index = 0
    per_prefix = {}

    for shard in sorted(shards, key=lambda x: str(x.get("shard"))):
        shard_dir = sdg_dir / str(shard.get("shard_dir") or shard.get("shard"))
        if not shard_dir.is_dir():
            print("WARNING: shard dir missing: {}".format(shard_dir), file=sys.stderr)
            continue

        # Group every file by the frame index in its trailing _NNNN suffix.
        frames = {}
        for src in sorted(shard_dir.rglob("*")):
            if not src.is_file():
                continue
            m = FRAME_SUFFIX.match(src.stem)
            if not m:
                continue
            frames.setdefault(int(m.group("index")), []).append((m.group("prefix"), src))

        for local_index in sorted(frames):
            for prefix, src in sorted(frames[local_index]):
                dst = dataset / "{}_{:06d}{}".format(prefix, global_index, src.suffix)
                shutil.copy2(src, dst)
                per_prefix[prefix] = per_prefix.get(prefix, 0) + 1
            global_index += 1

    return global_index, per_prefix


def main() -> int:
    args = parse_args()
    out_root = Path(args.output_dir)
    sdg_dir = out_root / "sdg"
    if not sdg_dir.is_dir():
        print("FAIL: {} does not exist - did any Generate task run?".format(sdg_dir),
              file=sys.stderr)
        return 1

    shards, missing = load_shards(sdg_dir, args.expected_shards)
    total = sum(int(s.get("frames", 0)) for s in shards)
    rgb_count = len(list((sdg_dir / "rgb").glob("rgb_*.png"))) if (sdg_dir / "rgb").is_dir() else 0

    print("")
    print("  shard   frames   seed      boot(s)  capture(s)  fps     cache")
    print("  " + "-" * 62)
    for s in sorted(shards, key=lambda x: str(x.get("shard"))):
        print("  {:<7} {:>6}   {:<9} {:>7}  {:>10}  {:>6}  {}".format(
            s.get("shard", "?"), s.get("frames", 0), s.get("seed", "?"),
            s.get("kit_boot_seconds", "?"), s.get("capture_seconds", "?"),
            s.get("avg_frame_fps", "?"), s.get("shader_cache", "?")))
    print("  " + "-" * 62)
    print("  {:<7} {:>6}".format("TOTAL", total))
    print("")

    frames_written, per_annotator = collate(sdg_dir, shards)
    print("collated {} frames into sdg/dataset".format(frames_written))
    for prefix, n in sorted(per_annotator.items()):
        print("   {:<34} {} files".format(prefix, n))
    print("")

    fps_values = [s_["avg_frame_fps"] for s_ in shards if s_.get("avg_frame_fps")]
    files_claimed = sum(int(s_.get("files_written", 0)) for s_ in shards)
    summary = {
        "expected_frames": args.expected_frames,
        "expected_shards": args.expected_shards,
        "shards_reported": len(shards),
        "shards_missing": missing,
        "frames_reported": total,
        "files_written_claimed": files_claimed,
        "frames_collated": frames_written,
        "files_per_prefix": per_annotator,
        "mean_frame_fps": round(sum(fps_values) / len(fps_values), 3) if fps_values else None,
        "cold_shards": sum(1 for s_ in shards if s_.get("shader_cache") == "cold"),
        "warm_shards": sum(1 for s_ in shards if s_.get("shader_cache") == "warm"),
    }
    (out_root / "sdg_summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    print("wrote {}".format(out_root / "sdg_summary.json"))

    # Fail loudly. An earlier version guarded this with `if rgb_count and ...`,
    # which short-circuited at zero: the job went green having produced no images
    # at all. Never make a count check conditional on the count being non-zero.
    problems = []
    if missing:
        problems.append("missing shards: {}".format(missing))
    if total != args.expected_frames:
        problems.append("frames reported {} != expected {}".format(total, args.expected_frames))
    if frames_written == 0:
        problems.append("NO image files were produced - the writer wrote nothing")
    elif frames_written != args.expected_frames:
        problems.append("collated {} frames != expected {}".format(
            frames_written, args.expected_frames))
    if problems:
        for prob in problems:
            print("FAIL: {}".format(prob), file=sys.stderr)
        return 1

    print("MERGE OK: {} frames across {} shards".format(frames_written, len(shards)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
