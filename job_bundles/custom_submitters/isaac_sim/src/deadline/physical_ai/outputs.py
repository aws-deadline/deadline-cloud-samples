# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
"""The outputs Isaac Sim can load from any job, and a fetch of just those items.

Backs the Isaac Sim extension's "Load job output" window through
``deadline-physical-ai outputs list|fetch``. Detection runs on the job's output manifests,
so it works for jobs submitted from anywhere, as long as their outputs went through job
attachments. Nothing is downloaded until :func:`fetch`, and then only the chosen items.

Detection rules (paths relative to the job's ``OutputDir``):

========================  ==============================================================
Kind                      Rule
========================  ==============================================================
``eval_summary``          a file named ``eval_summary.json`` or ``eval_info.json``
                          (``lerobot eval``)
``trajectory``            a ``.npz`` file (checked when loaded; see the replay docs)
``usd``                   ``.usd``, ``.usda``, ``.usdc`` or ``.usdz``
``lerobot``               a folder with ``meta/info.json`` and at least one ``.parquet``
                          under its ``meta/``, ``data/`` or ``videos/``
``checkpoint``            a folder holding a file named ``checkpoint.json``
``hdf5``                  ``.hdf5`` or ``.h5``
``video``                 ``.mp4``
========================  ==============================================================

A dataset's or checkpoint's own files are part of that item, not items of their own. A
checkpoint at the ``OutputDir`` root owns its own files but hides none of the other
outputs. Fetching a ``usd`` item downloads its containing folder (see :func:`fetch_root`).

These commands exist because the stock ``deadline`` CLI cannot yet list a job's outputs
without downloading them, or download chosen items into a chosen folder.

Read-only on AWS: ``GetJob``, ``GetQueue``, S3 ``ListObjectsV2`` and ``GetObject``.
"""

from __future__ import annotations

import os
import posixpath
from dataclasses import asdict, dataclass, field
from typing import Any

from . import config as cfg
from . import job_outputs as jo
from . import session as ses
from .eval_summary import EVAL_FILES, read_summary

USD_EXT = (".usd", ".usda", ".usdc", ".usdz")
#: Any NumPy archive is offered as a trajectory: listing sees only names and sizes, so the
#: arrays are validated when one is loaded. ``*.trajectory.npz`` is the recommended name.
TRAJECTORY_SUFFIX = ".npz"
CHECKPOINT_MARKER = "checkpoint.json"
LEROBOT_INFO = "meta/info.json"
#: Folders a LeRobot dataset owns; anything else stored beside them is detected on its own.
LEROBOT_FOLDERS = ("meta/", "data/", "videos/")

#: Kinds, in display order. The value is what the Isaac Sim side does with the item.
KINDS = {
    "eval_summary": "summary",
    "trajectory": "replay",
    "usd": "open",
    "lerobot": "input",
    "checkpoint": "input",
    "hdf5": "download",
    "video": "preview",
}


@dataclass
class Item:
    kind: str
    path: str  # relative to the job's OutputDir, "/"-separated; a folder for lerobot/checkpoint
    label: str
    group: str  # first path component (usually the step's output folder)
    size: int = 0
    file_count: int = 1
    meta: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        d = asdict(self)
        d["loader"] = KINDS.get(self.kind, "")
        return d


def _group(path: str) -> str:
    return path.split("/", 1)[0] if "/" in path else ""


def _under(path: str, root: str) -> bool:
    """``path`` is ``root`` or inside it; ``""`` is the OutputDir itself, so holds everything."""
    return root == "" or path == root or path.startswith(root + "/")


def detect(files: list) -> list:
    """Loadable items (as dicts) from a job's output files (``OutputFile``-like: ``path``,
    ``size``), sorted by kind then path."""
    items: list = []

    def owned(path: str, root: str) -> bool:
        return any(path.startswith(f"{root}/{o}" if root else o) for o in LEROBOT_FOLDERS)

    candidates = sorted(
        {
            f.path[: -len(LEROBOT_INFO)].rstrip("/")
            for f in files
            if f.path == LEROBOT_INFO or f.path.endswith("/" + LEROBOT_INFO)
        }
    )
    lerobot_roots = []
    for root in candidates:
        inside = [f for f in files if owned(f.path, root)]
        if not any(f.path.endswith(".parquet") for f in inside):
            continue
        lerobot_roots.append(root)
        items.append(
            Item(
                "lerobot",
                root,
                f"LeRobot dataset {root or '(job root)'}",
                _group(root),
                size=sum(f.size for f in inside),
                file_count=len(inside),
            )
        )
    ckpt_roots = sorted(
        {
            posixpath.dirname(f.path)
            for f in files
            if posixpath.basename(f.path) == CHECKPOINT_MARKER
        }
    )
    for root in ckpt_roots:
        inside = [f for f in files if _under(f.path, root)]
        items.append(
            Item(
                "checkpoint",
                root,
                f"Checkpoint {root or '(job root)'}",
                _group(root),
                size=sum(f.size for f in inside),
                file_count=len(inside),
            )
        )
    for f in files:
        p, low = f.path, f.path.lower()
        # A checkpoint at the OutputDir root has root "", which holds every path: it owns
        # its own files but must not hide the job's other outputs.
        if any(r and _under(p, r) for r in ckpt_roots):
            continue  # a checkpoint's files load with the checkpoint
        if any(owned(p, r) for r in lerobot_roots):
            continue  # a dataset's own files load with the dataset
        if posixpath.basename(low) in EVAL_FILES:
            items.append(Item("eval_summary", p, f"Eval summary {p}", _group(p), size=f.size))
        elif low.endswith(TRAJECTORY_SUFFIX):
            items.append(Item("trajectory", p, p, _group(p), size=f.size))
        elif low.endswith(USD_EXT):
            items.append(Item("usd", p, p, _group(p), size=f.size))
        elif low.endswith((".hdf5", ".h5")):
            items.append(Item("hdf5", p, p, _group(p), size=f.size))
        elif low.endswith(".mp4"):
            items.append(Item("video", p, p, _group(p), size=f.size))
    order = list(KINDS)
    items.sort(key=lambda i: (order.index(i.kind), i.path))
    return [i.to_dict() for i in items]


def fetch_root(path: str, known: set) -> str:
    """What one chosen item path downloads.

    A ``usd`` item downloads its containing folder: a stage's references, payloads and
    textures sit beside it, and the file alone would open with everything missing. At the
    ``OutputDir`` root the containing folder is the whole job, so only the file is
    downloaded (write USD outputs into their own folder with their assets). Anything else,
    and any path the job did not write, downloads itself.
    """
    if path in known and path.lower().endswith(USD_EXT):
        return posixpath.dirname(path) or path
    return path


def _defaults(
    farm_id: str | None, queue_id: str | None, profile: str | None
) -> tuple[str, str, str | None]:
    d = cfg.deadline_defaults()
    farm = farm_id or d.get("farm_id") or ""
    queue = queue_id or d.get("queue_id") or ""
    if not (farm and queue):
        raise ValueError(
            "no farm or queue: pass --farm-id and --queue-id, or set defaults with "
            "`deadline config gui`"
        )
    return farm, queue, profile or None


def cache_dir(job_id: str) -> str:
    """The default download folder for a job: ``~/.deadline/physical-ai/job_outputs/<job>``."""
    return os.path.join(cfg.home_dir(), "job_outputs", job_id)


def _small_text(outputs: jo.JobOutputs, f: jo.OutputFile, session: Any) -> str:
    dest = os.path.join(cache_dir("_meta"), f.hash + "." + f.hash_alg)
    if not os.path.isfile(dest):
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        (outputs.s3_session or session).client("s3").download_file(
            outputs.bucket, f"{outputs.cas_prefix}/{f.hash}.{f.hash_alg}", dest
        )
    with open(dest, encoding="utf-8", errors="replace") as fh:
        return fh.read()


def job_outputs(
    job_id: str,
    *,
    farm_id: str | None = None,
    queue_id: str | None = None,
    profile: str | None = None,
    region: str | None = None,
) -> dict:
    """Detected items for one job, plus its first eval summary. Downloads only the eval
    summary (a few bytes)."""
    farm_id, queue_id, profile = _defaults(farm_id, queue_id, profile)
    session = ses.make_session(profile, region)
    outs = jo.list_job_outputs(job_id, farm_id, queue_id, session=session)
    files = outs.files
    summary, path, warnings = read_summary(files, lambda f: _small_text(outs, f, session))
    if summary is not None:
        summary["path"] = path
    return {
        "job_id": job_id,
        "farm_id": farm_id,
        "queue_id": queue_id,
        "output_dir": outs.asset_root,
        "file_count": len(files),
        "total_bytes": sum(f.size for f in files),
        "eval_summary": summary,
        "items": detect(files),
        "warnings": warnings,
    }


def fetch(
    job_id: str,
    paths: list,
    *,
    dest: str = "",
    farm_id: str | None = None,
    queue_id: str | None = None,
    profile: str | None = None,
    region: str | None = None,
    progress: jo.Progress | None = None,
) -> dict:
    """Download the files under each item path into ``dest`` (default :func:`cache_dir`),
    keeping their layout relative to the job's ``OutputDir``. ``""`` (or ``/``) is every
    file, and a ``usd`` file brings its containing folder (see :func:`fetch_root`).
    ``items`` maps each path that matched a file to its local path (for a ``usd`` item,
    still the file itself); the rest are in ``missing``. Raises ``ValueError`` when nothing
    matched."""
    if not paths:
        raise ValueError("nothing to fetch: pass at least one item path")
    farm_id, queue_id, profile = _defaults(farm_id, queue_id, profile)
    session = ses.make_session(profile, region)
    outs = jo.list_job_outputs(job_id, farm_id, queue_id, session=session)
    want = list(dict.fromkeys(str(p).strip().strip("/") for p in paths))  # "" is all of it
    known = {f.path for f in outs.files}
    matched = {p: [f for f in outs.files if _under(f.path, fetch_root(p, known))] for p in want}
    files = list({f.path: f for p in want for f in matched[p]}.values())
    if not files:
        raise ValueError(f"job {job_id}: no output files under {want}")
    dest = dest or cache_dir(job_id)
    nbytes = jo.download(outs, files, dest, session=session, progress=progress)
    return {
        "job_id": job_id,
        "dest": dest,
        "downloaded_bytes": nbytes,
        "items": {p: os.path.join(dest, *p.split("/")) if p else dest for p in want if matched[p]},
        "missing": [p for p in want if not matched[p]],
        "file_count": len(files),
    }
