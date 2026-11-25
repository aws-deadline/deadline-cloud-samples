# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
"""Build a LeRobot v3.0 dataset and an HTML quality report from the imported sessions.

    build_dataset.py --sessions-dir D --num-sessions N --output-dir OUT [--task TEXT]
        [--repo-id local/quest3_hands] [--min-tracked-fraction 0.7]

Reads ``OUT/sessions/<session>/{poses.npz,qc.json}`` (``import_session.py``) and writes:

``OUT/dataset/``, one episode per session::

    meta/info.json, meta/stats.json, meta/tasks.parquet
    meta/episodes/chunk-000/file-000.parquet    with session, flags and tracking columns
    data/chunk-000/file-000.parquet

Columns (all poses in the task frame, meters, quaternions ``x y z w``)::

    observation.head.pose                  (7)   x y z qx qy qz qw
    observation.head.valid                 bool
    observation.hand.<side>.joints         (75)  25 joints x xyz (quest_capture.JOINT_NAMES)
    observation.hand.<side>.wrist_pose     (7)
    observation.hand.<side>.pinch_aperture       thumb tip to index tip, meters
    observation.hand.<side>.confidence           the recorder's confidence, 0 to 1
    observation.hand.<side>.valid          bool  tracked, or a bridged gap

Untracked frames hold zeros; use the ``valid`` columns to mask them. ``OUT/qc_report/``
holds ``index.html`` and ``qc.json``: per session tracking coverage, confidence, longest gap
and warnings. Sessions are kept even when flagged; the report and the episode columns say why.
"""

from __future__ import annotations

import argparse
import html
import json
import os
import shutil
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import quest_capture as qc

CODEBASE_VERSION = "v3.0"
DATA_PATH = "data/chunk-{chunk_index:03d}/file-{file_index:03d}.parquet"
POSE_NAMES = ["x", "y", "z", "qx", "qy", "qz", "qw"]


def _scalar(dtype: str) -> dict:
    return {"dtype": dtype, "shape": [1], "names": None}


def features() -> dict:
    f = {
        "timestamp": _scalar("float32"),
        "frame_index": _scalar("int64"),
        "episode_index": _scalar("int64"),
        "index": _scalar("int64"),
        "task_index": _scalar("int64"),
        "observation.head.pose": {"dtype": "float32", "shape": [7], "names": POSE_NAMES},
        "observation.head.valid": _scalar("bool"),
    }
    joints = [f"{j}.{a}" for j in qc.JOINT_NAMES for a in "xyz"]
    for side in qc.SIDES:
        p = f"observation.hand.{side}."
        f[p + "joints"] = {"dtype": "float32", "shape": [len(joints)], "names": joints}
        f[p + "wrist_pose"] = {"dtype": "float32", "shape": [7], "names": POSE_NAMES}
        f[p + "pinch_aperture"] = _scalar("float32")
        f[p + "confidence"] = _scalar("float32")
        f[p + "valid"] = _scalar("bool")
    return f


def episode_columns(poses: dict, episode: int, start: int, task_index: int) -> dict:
    """One episode's frames as ``{column: array}`` (vectors as (n, k) arrays)."""
    n = len(poses["t"])
    zero = lambda a, ok: np.where(ok.reshape((-1,) + (1,) * (a.ndim - 1)), a, 0.0)
    cols = {
        "timestamp": poses["t"].astype(np.float32),
        "frame_index": np.arange(n, dtype=np.int64),
        "episode_index": np.full(n, episode, np.int64),
        "index": np.arange(start, start + n, dtype=np.int64),
        "task_index": np.full(n, task_index, np.int64),
        "observation.head.pose": zero(poses["head"], poses["head_ok"]).astype(np.float32),
        "observation.head.valid": poses["head_ok"].astype(bool),
    }
    for side in qc.SIDES:
        j, ok = poses[side], poses[side + "_ok"]
        tips = j[:, qc.THUMB_TIP, :3] - j[:, qc.INDEX_TIP, :3]
        p = f"observation.hand.{side}."
        cols[p + "joints"] = zero(j[..., :3], ok).reshape(n, -1).astype(np.float32)
        cols[p + "wrist_pose"] = zero(j[:, qc.WRIST], ok).astype(np.float32)
        cols[p + "pinch_aperture"] = zero(np.linalg.norm(tips, axis=1), ok).astype(np.float32)
        cols[p + "confidence"] = zero(np.nan_to_num(poses[side + "_conf"]), ok).astype(np.float32)
        cols[p + "valid"] = ok.astype(bool)
    return cols


def stats(cols: dict) -> dict:
    """LeRobot ``stats.json`` entries: min, max, mean, std and count per feature."""
    out = {}
    for name, a in cols.items():
        x = a.astype(np.float64).reshape(len(a), -1)
        out[name] = {
            "min": x.min(0).tolist(),
            "max": x.max(0).tolist(),
            "mean": x.mean(0).tolist(),
            "std": x.std(0).tolist(),
            "count": [len(x)],
        }
    return out


def _table(cols: dict, feats: dict):
    import pyarrow as pa

    arrays, fields = [], []
    for name, a in cols.items():
        dtype = {"float32": pa.float32(), "int64": pa.int64(), "bool": pa.bool_()}[
            feats[name]["dtype"]
        ]
        if a.ndim == 1:
            arrays.append(pa.array(a, type=dtype))
            fields.append(pa.field(name, dtype))
        else:
            arrays.append(
                pa.FixedSizeListArray.from_arrays(pa.array(a.ravel(), type=dtype), a.shape[1])
            )
            fields.append(pa.field(name, pa.list_(dtype, a.shape[1])))
    return pa.Table.from_arrays(arrays, schema=pa.schema(fields))


def write_dataset(out_dir: str, episodes: list, task_texts: list, repo_id: str, fps: float) -> dict:
    """``episodes``: ``[(qc_report, poses)]`` in order. Returns ``meta/info.json``."""
    import pandas as pd
    import pyarrow as pa
    import pyarrow.parquet as pq

    root = os.path.join(out_dir, "dataset")
    if os.path.isdir(root):
        shutil.rmtree(root)  # the step's own output from an earlier attempt
    for sub in ("meta/episodes/chunk-000", "data/chunk-000"):
        os.makedirs(os.path.join(root, sub), exist_ok=True)
    feats = features()
    tasks = list(dict.fromkeys(task_texts))
    all_cols: dict = {}
    meta_rows = []
    start = 0
    for ep, ((report, poses), text) in enumerate(zip(episodes, task_texts)):
        cols = episode_columns(poses, ep, start, tasks.index(text))
        n = len(cols["index"])
        for k, v in cols.items():
            all_cols.setdefault(k, []).append(v)
        meta_rows.append(
            {
                "episode_index": ep,
                "tasks": [text],
                "length": n,
                "data/chunk_index": 0,
                "data/file_index": 0,
                "dataset_from_index": start,
                "dataset_to_index": start + n,
                "meta/episodes/chunk_index": 0,
                "meta/episodes/file_index": 0,
                "session": report["session"],
                "flags": list(report["flags"]),
                "world_frame": report["world"]["method"],
                "right_tracked_fraction": report["hands"]["right"]["tracked_fraction"],
                "left_tracked_fraction": report["hands"]["left"]["tracked_fraction"],
            }
        )
        start += n
    merged = {k: np.concatenate(v) for k, v in all_cols.items()}
    pq.write_table(
        _table(merged, feats), os.path.join(root, DATA_PATH.format(chunk_index=0, file_index=0))
    )
    pq.write_table(
        pa.Table.from_pylist(meta_rows),
        os.path.join(root, "meta/episodes/chunk-000/file-000.parquet"),
    )
    pd.DataFrame({"task_index": range(len(tasks))}, index=pd.Index(tasks, name="task")).to_parquet(
        os.path.join(root, "meta/tasks.parquet")
    )
    with open(os.path.join(root, "meta/stats.json"), "w", encoding="utf-8") as fh:
        json.dump(stats(merged), fh, indent=2)
    info = {
        "codebase_version": CODEBASE_VERSION,
        "robot_type": "human_hands",
        "total_episodes": len(episodes),
        "total_frames": int(start),
        "total_tasks": len(tasks),
        "chunks_size": 1000,
        "data_files_size_in_mb": 100,
        "video_files_size_in_mb": 200,
        "fps": round(fps),
        "splits": {"train": f"0:{len(episodes)}"},
        "data_path": DATA_PATH,
        "video_path": None,
        "features": feats,
        "source": {"format": qc.FORMAT, "repo_id": repo_id},
    }
    with open(os.path.join(root, "meta/info.json"), "w", encoding="utf-8") as fh:
        json.dump(info, fh, indent=2)
    return info


# ------------------------------------------------------------------ report --


def warnings_for(report: dict, min_tracked: float) -> list:
    out = list(report["flags"])
    active = report["hand"] if report["hand"] in qc.SIDES else None
    for side, h in report["hands"].items():
        # Without a declared hand, an idle (never tracked) second hand is not a problem.
        low = h["tracked_fraction"] < min_tracked
        if low and (side == active or (active is None and h["tracked_fraction"] > 0)):
            out.append(f"{side}_hand_tracked_{h['tracked_fraction']:.0%}")
    if report["head_coverage"] < min_tracked:
        out.append(f"head_tracked_{report['head_coverage']:.0%}")
    return out


def _bar(ok: np.ndarray, width: int = 240) -> str:
    """An inline SVG strip: green where tracked, red where not."""
    n = max(len(ok), 1)
    rects, i = [], 0
    while i < len(ok):
        j = i
        while j < len(ok) and ok[j] == ok[i]:
            j += 1
        color = "#3a3" if ok[i] else "#c33"
        rects.append(
            f'<rect x="{width * i / n:.1f}" width="{width * (j - i) / n:.1f}" height="10" fill="{color}"/>'
        )
        i = j
    return f'<svg width="{width}" height="10">{"".join(rects)}</svg>'


def write_report(out_dir: str, episodes: list, min_tracked: float) -> list:
    dest = os.path.join(out_dir, "qc_report")
    os.makedirs(dest, exist_ok=True)
    rows, summary = [], []
    for ep, (report, poses) in enumerate(episodes):
        warn = warnings_for(report, min_tracked)
        summary.append({**report, "episode_index": ep, "warnings": warn})
        cells = [
            str(ep),
            html.escape(report["session"]),
            f"{report['duration_s']:.1f} s",
            html.escape(report["world"]["method"]),
            f"{report['head_coverage']:.0%}",
        ]
        for side in qc.SIDES:
            h = report["hands"][side]
            cells.append(
                f"{_bar(poses[side + '_ok'])}<br>{h['tracked_fraction']:.0%} tracked, "
                f"conf {h['mean_confidence']:.2f}, longest gap {h['longest_gap_s']:.2f} s"
            )
        cells.append(html.escape(", ".join(warn)) or "ok")
        cls = ' class="warn"' if warn else ""
        rows.append(f"<tr{cls}>" + "".join(f"<td>{c}</td>" for c in cells) + "</tr>")
    head = "".join(
        f"<th>{h}</th>"
        for h in (
            "Episode",
            "Session",
            "Length",
            "Task frame",
            "Head",
            "Right hand",
            "Left hand",
            "Warnings",
        )
    )
    page = (
        "<!doctype html><meta charset=utf-8><title>Quest 3 hand tracking QC</title>"
        "<style>body{font:14px sans-serif;margin:2em}table{border-collapse:collapse}"
        "td,th{border:1px solid #ccc;padding:4px 8px;text-align:left;vertical-align:top}"
        "tr.warn td:last-child{color:#b00}</style>"
        f"<h1>Quest 3 hand tracking QC</h1><p>{len(episodes)} sessions. A hand counts as tracked "
        f"in a frame when the headset tracked it or the gap was bridged. Warnings below "
        f"{min_tracked:.0%} tracked.</p><table><tr>{head}</tr>{''.join(rows)}</table>"
    )
    with open(os.path.join(dest, "index.html"), "w", encoding="utf-8") as fh:
        fh.write(page)
    with open(os.path.join(dest, "qc.json"), "w", encoding="utf-8") as fh:
        json.dump(summary, fh, indent=2)
    return summary


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--sessions-dir", required=True)
    ap.add_argument("--num-sessions", type=int, required=True)
    ap.add_argument("--output-dir", required=True)
    ap.add_argument(
        "--task", default="", help="Task text for every episode (default: each header's)"
    )
    ap.add_argument("--repo-id", default="local/quest3_hands")
    ap.add_argument("--min-tracked-fraction", type=float, default=0.7)
    args = ap.parse_args(argv)
    try:
        names = [n for n, _ in qc.list_sessions(args.sessions_dir)][: args.num_sessions]
    except qc.InputError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    episodes = []
    for name in names:
        d = os.path.join(args.output_dir, "sessions", name)
        if not os.path.isfile(os.path.join(d, "poses.npz")):
            print(f"ERROR: {name} was not imported ({d}/poses.npz missing)", file=sys.stderr)
            return 2
        with open(os.path.join(d, "qc.json"), encoding="utf-8") as fh:
            report = json.load(fh)
        with np.load(os.path.join(d, "poses.npz")) as z:
            episodes.append((report, {k: z[k] for k in z.files}))
    fps = episodes[0][0]["fps"]
    texts = [args.task.strip() or r["task"] for r, _ in episodes]
    info = write_dataset(args.output_dir, episodes, texts, args.repo_id, fps)
    summary = write_report(args.output_dir, episodes, args.min_tracked_fraction)
    flagged = sum(1 for s in summary if s["warnings"])
    print(
        f"dataset: {info['total_episodes']} episodes, {info['total_frames']} frames at {info['fps']} fps; "
        f"{flagged} session(s) with warnings (qc_report/index.html)"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
