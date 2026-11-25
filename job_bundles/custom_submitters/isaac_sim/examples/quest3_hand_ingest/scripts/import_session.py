# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
"""Import one recorded session: resample head and hand tracking onto a fixed frame clock in
the task frame, and measure tracking quality.

    import_session.py --sessions-dir D --index N --output-dir OUT [--fps 30] [--max-gap-s 0.1]

Writes ``OUT/sessions/<session>/poses.npz`` (``t``, ``head``, ``head_ok``, and per side
``<side>`` (n, 25, 7) joint poses, ``<side>_ok``, ``<side>_conf``) and ``qc.json``.
"""

from __future__ import annotations

import argparse
import json
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import quest_capture as qc


def _longest_gap(t: np.ndarray, ok: np.ndarray) -> float:
    """Longest stretch of untracked time between tracked samples, seconds."""
    idx = np.flatnonzero(ok)
    return float(np.max(np.diff(t[idx]), initial=0.0)) if len(idx) > 1 else float(t[-1] - t[0])


def import_session(sessions_dir: str, index: int, out_dir: str, fps: float, max_gap: float) -> dict:
    sessions = qc.list_sessions(sessions_dir)
    if not 1 <= index <= len(sessions):
        raise qc.InputError(f"task {index}, but {sessions_dir} has {len(sessions)} sessions")
    name, folder = sessions[index - 1]
    header, frames, events = qc.read_session(os.path.join(folder, qc.SESSION_FILE))
    raw = qc.arrays(header, frames)
    ts = raw["t"]
    head0 = raw["head"][raw["head_ok"]][0] if raw["head_ok"].any() else None
    T_world_xr, world, flags = qc.world_frame(header, events, head0)

    t = np.arange(ts[0], ts[-1] + 1e-9, 1.0 / fps)
    out: dict = {"t": t - t[0]}
    head, head_ok = qc.resample(ts, raw["head"], raw["head_ok"], t, max_gap)
    out["head"], out["head_ok"] = qc.transform_poses(T_world_xr, head), head_ok
    hands: dict = {}
    for side in qc.SIDES:
        poses, ok = qc.resample(ts, raw[side], raw[side + "_ok"], t, max_gap)
        out[side], out[side + "_ok"] = qc.transform_poses(T_world_xr, poses), ok
        seen = raw[side + "_ok"]
        conf = np.interp(t, ts[seen], raw[side + "_conf"][seen]) if seen.any() else np.zeros(len(t))
        out[side + "_conf"] = np.where(ok, conf, np.nan)
        hands[side] = {
            "tracked_fraction": round(float(ok.mean()), 4),
            "mean_confidence": (
                round(float(np.nanmean(out[side + "_conf"])), 4) if ok.any() else 0.0
            ),
            "longest_gap_s": round(_longest_gap(ts, seen), 3),
        }
    dest = os.path.join(out_dir, "sessions", name)
    os.makedirs(dest, exist_ok=True)
    np.savez_compressed(os.path.join(dest, "poses.npz"), **out)
    report = {
        "session": name,
        "index": index,
        "frames": len(t),
        "fps": fps,
        "duration_s": round(float(ts[-1] - ts[0]), 3),
        "source": str(header.get("source", "")),
        "device": str(header.get("device", "")),
        "joint_set": header["joint_set"],
        "task": str(header.get("task", "")),
        "hand": str(header.get("hand", "")),
        "world": world,
        "flags": flags,
        "head_coverage": round(float(head_ok.mean()), 4),
        "hands": hands,
    }
    with open(os.path.join(dest, "qc.json"), "w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=2)
    return report


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--sessions-dir", required=True)
    ap.add_argument("--index", type=int, required=True, help="1-based session number")
    ap.add_argument("--output-dir", required=True)
    ap.add_argument("--fps", type=float, default=30.0)
    ap.add_argument("--max-gap-s", type=float, default=0.1)
    args = ap.parse_args(argv)
    try:
        r = import_session(args.sessions_dir, args.index, args.output_dir, args.fps, args.max_gap_s)
    except qc.InputError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    tracked = ", ".join(f"{s} tracked {h['tracked_fraction']:.0%}" for s, h in r["hands"].items())
    print(
        f"{r['session']}: {r['frames']} frames at {r['fps']:g} fps, world {r['world']['method']}, {tracked}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
