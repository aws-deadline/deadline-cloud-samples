#!/usr/bin/env python3
"""Print one row per sweep combination from mj-hand-sweep's metrics.json files, plus per-friction means.

Usage: summarize_metrics.py [--csv PATH] DIR_OR_FILE...
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from dataclasses import astuple, dataclass, fields
from pathlib import Path
from statistics import mean
from typing import Any

DESCRIPTION = "Summarize the metrics.json files that mj-hand-sweep writes."
ROW = "{:<22} {:>5} {:>5} {:>5} {:>6} {:>9} {:>11} {:>7} {:>8} {:>8} {:>6}"
HEADER = ("label", "damp", "kp", "fric", "frames", "mp4_bytes", "codec", "force", "moved_m", "min_z_m", "wall_s")


def format_row(values: tuple[object, ...]) -> str:
    return ROW.format(*("-" if v is None else str(v) for v in values))


@dataclass(frozen=True)
class Combination:
    """One sweep point, read from the metrics.json that its task wrote."""

    label: str
    damping_scale: float
    stiffness_scale: float
    friction_scale: float
    frames: int
    mp4_bytes: int | None
    mp4_codec: str | None
    peak_actuator_force: float
    object_displacement_m: float | None
    """How far the ball moved from where it started. Low friction lets it slip out."""
    object_min_z_m: float | None
    """The ball's lowest height. A drop means the hand lost its grip."""
    wall_seconds: float

    @classmethod
    def from_metrics(cls, metrics: dict[str, Any]) -> Combination:
        params = metrics["params"]
        return cls(
            label=metrics["label"],
            damping_scale=params["damping_scale"],
            stiffness_scale=params["stiffness_scale"],
            friction_scale=params["friction_scale"],
            frames=metrics["frames"],
            mp4_bytes=metrics.get("mp4_bytes"),
            mp4_codec=metrics.get("mp4_codec"),
            peak_actuator_force=round(metrics["peak_actuator_force"], 3),
            object_displacement_m=metrics.get("object_displacement_m"),
            object_min_z_m=metrics.get("object_min_z_m"),
            wall_seconds=metrics["wall_seconds"],
        )


def load(paths: list[Path]) -> list[Combination]:
    """Read every metrics.json given, or found under a given directory. Skip unreadable files."""
    files = [f for p in paths for f in (sorted(p.glob("**/metrics.json")) if p.is_dir() else [p])]
    combos: list[Combination] = []
    for path in files:
        try:
            combos.append(Combination.from_metrics(json.loads(path.read_text())))
        except (OSError, ValueError, KeyError, TypeError) as err:
            print(f"skipping {path}: {err!r}", file=sys.stderr)
    return sorted(combos, key=lambda c: c.label)


def mean_of(values: list[float | None]) -> float:
    present = [v for v in values if v is not None]
    return mean(present) if present else float("nan")


def print_friction_means(combos: list[Combination]) -> None:
    for friction in sorted({c.friction_scale for c in combos}):
        group = [c for c in combos if c.friction_scale == friction]
        moved = mean_of([c.object_displacement_m for c in group])
        lowest = mean_of([c.object_min_z_m for c in group])
        print(
            f"friction x{friction}: {len(group)} combinations, mean displacement {moved:.4f} m, "
            f"mean lowest height {lowest:.4f} m"
        )


def main() -> int:
    parser = argparse.ArgumentParser(description=DESCRIPTION)
    parser.add_argument("--csv", type=Path, help="Also write the rows to this CSV file.")
    parser.add_argument("paths", nargs="+", type=Path, help="metrics.json files or directories to search.")
    args = parser.parse_args()

    combos = load(args.paths)
    if not combos:
        print("no readable metrics.json found", file=sys.stderr)
        return 1

    print(format_row(HEADER))
    for c in combos:
        print(format_row(astuple(c)))
    print_friction_means(combos)

    if args.csv:
        args.csv.parent.mkdir(parents=True, exist_ok=True)
        with args.csv.open("w", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow(f.name for f in fields(Combination))
            writer.writerows(astuple(c) for c in combos)
        print(f"wrote {len(combos)} rows to {args.csv}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
