# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
"""A job's output files, read from its job attachments manifests, and a safe parallel download.

* :func:`list_job_outputs` reads the job's output manifests
  (``Manifests/<farm>/<queue>/<job>/...``, merged per asset root by the ``deadline``
  library) and re-roots the paths onto the job's ``OutputDir`` parameter.
* :func:`download` copies chosen files from the queue's content-addressed ``Data/`` store.
  It skips files already downloaded with the same size and manifest hash (recorded in
  :data:`INDEX_NAME`), reports progress, and refuses any manifest path that would land
  outside the destination folder.

Read-only on AWS: ``GetQueue``, ``GetJob``, S3 ``ListObjectsV2`` and ``GetObject``.
"""

from __future__ import annotations

import json
import os
import posixpath
import tempfile
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

#: The job parameter whose path the outputs are re-rooted onto.
OUTPUT_DIR_PARAM = "OutputDir"
#: Per-file record of what each downloaded file holds, in the download root.
INDEX_NAME = ".deadline-physical-ai-index.json"
#: Parallel parts per file. The S3 client pool is sized as workers times this.
_PART_CONCURRENCY = 4
#: How often the resume index is flushed while downloading: whichever of these comes
#: first. A killed download (the Isaac Sim extension kills one after an hour) loses at
#: most the files finished since the last flush, instead of all of them.
_INDEX_FLUSH_S = 2.0
_INDEX_FLUSH_FILES = 25
_index_lock = threading.Lock()

#: ``progress(done_bytes, total_bytes, done_files, total_files)``
Progress = Callable[[int, int, int, int], None]


class OutputsError(Exception):
    """The job's outputs could not be listed or downloaded; the message says why."""


@dataclass(frozen=True)
class OutputFile:
    path: str  # relative to the asset root, "/"-separated
    hash: str
    size: int
    hash_alg: str = "xxh128"


@dataclass
class JobOutputs:
    """A job's output files under one asset root, plus where to fetch them."""

    asset_root: str
    files: list = field(default_factory=list)  # OutputFile
    bucket: str = ""
    cas_prefix: str = ""  # "<rootPrefix>/Data"
    #: Session for the job attachments bucket (the queue role's, see session.queue_session).
    s3_session: Any = field(default=None, repr=False, compare=False)


def list_job_outputs(
    job_id: str, farm_id: str, queue_id: str, *, session: Any = None, output_dir: str = ""
) -> JobOutputs:
    """The job's output files (merged across tasks, newest wins), read from the queue's
    job attachments bucket. ``output_dir`` picks the asset root when the job has several;
    by default it is the job's ``OutputDir`` parameter."""
    from deadline.job_attachments.download import get_output_manifests_by_asset_root
    from deadline.job_attachments.models import JobAttachmentS3Settings

    from .session import make_session, queue_session

    session = session or make_session()
    deadline = session.client("deadline")
    queue = deadline.get_queue(farmId=farm_id, queueId=queue_id)
    settings = queue.get("jobAttachmentSettings") or {}
    if not settings.get("s3BucketName"):
        raise OutputsError(f"queue {queue_id} has no job attachments bucket")
    s3_settings = JobAttachmentS3Settings(
        s3BucketName=settings["s3BucketName"], rootPrefix=settings.get("rootPrefix") or ""
    )
    if not output_dir:
        job = deadline.get_job(farmId=farm_id, queueId=queue_id, jobId=job_id)
        param = (job.get("parameters") or {}).get(OUTPUT_DIR_PARAM) or {}
        output_dir = str(param.get("path") or "")
    s3_session = queue_session(session, farm_id, queue_id)
    by_root = get_output_manifests_by_asset_root(
        s3_settings, farm_id, queue_id, job_id, session=s3_session
    )
    if not by_root:
        raise OutputsError(
            f"job {job_id} has no output manifests yet (still running, or it wrote nothing)"
        )
    files_by_root: dict = {}
    for root, manifests in by_root.items():
        files = []
        for manifest in manifests:
            alg_obj = getattr(manifest, "hashAlg", None)
            alg = str(getattr(alg_obj, "value", None) or alg_obj or "xxh128")
            for p in manifest.paths:
                files.append(
                    OutputFile(
                        path=p.path.replace("\\", "/"),
                        hash=p.hash,
                        size=int(p.size or 0),
                        hash_alg=alg,
                    )
                )
        files_by_root[root] = files
    root, rebased = rebase_outputs(files_by_root, output_dir, job_id)
    return JobOutputs(
        asset_root=root,
        files=rebased,
        bucket=s3_settings.s3BucketName,
        cas_prefix=s3_settings.full_cas_prefix(),
        s3_session=s3_session,
    )


def _posix(path: str) -> str:
    return path.replace("\\", "/").rstrip("/") or "/"


def rebase_outputs(files_by_root: dict, output_dir: str, job_id: str = "") -> tuple:
    """``(output_dir, files relative to it)``.

    Output manifests are keyed by an asset root that is often a common ancestor of every
    attachment (``/`` when inputs and outputs share nothing deeper), with paths relative to
    that root. Item paths are relative to the job's ``OutputDir``, so the files are
    re-rooted there.
    """
    if not output_dir:
        if len(files_by_root) == 1:
            root, files = next(iter(files_by_root.items()))
            return root, list(files)
        raise OutputsError(
            f"job {job_id}: outputs under several roots and no {OUTPUT_DIR_PARAM} to choose one"
        )
    want = _posix(output_dir)
    best: str | None = None
    for root in files_by_root:
        r = _posix(root)
        inside = want == r or want.startswith(r.rstrip("/") + "/")
        if inside and (best is None or len(r) > len(_posix(best))):
            best = root
    if best is None:
        raise OutputsError(
            f"job {job_id}: no output root contains its {OUTPUT_DIR_PARAM} {output_dir}"
        )
    r = _posix(best)
    prefix = "" if want == r else want[len(r.rstrip("/")) + 1 :] + "/"
    rebased = [
        OutputFile(path=f.path[len(prefix) :], hash=f.hash, size=f.size, hash_alg=f.hash_alg)
        for f in files_by_root[best]
        if f.path.startswith(prefix)
    ]
    return output_dir, rebased


# ------------------------------------------------------------------ download --


def safe_destination(dest_root: str, path: str) -> str:
    """Local path for a manifest path, refusing any that would leave ``dest_root``
    (absolute paths, drive letters, ``..`` segments)."""
    norm = posixpath.normpath(path.replace("\\", "/"))
    if (
        not path
        or path.startswith("/")
        or norm == ".."
        or norm.startswith("../")
        or (len(norm) > 1 and norm[1] == ":")
    ):
        raise OutputsError(f"output path {path!r} is outside the download folder")
    root = os.path.abspath(dest_root)
    dst = os.path.abspath(os.path.join(root, *norm.split("/")))
    if os.path.commonpath([root, dst]) != root or dst == root:
        raise OutputsError(f"output path {path!r} is outside the download folder")
    return dst


def _read_index(dest_root: str) -> dict:
    try:
        with open(os.path.join(dest_root, INDEX_NAME), encoding="utf-8") as fh:
            data = json.load(fh)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def _write_index(dest_root: str, entries: dict) -> None:
    """Merge ``entries`` into the index and replace it atomically. Re-reads first so a
    concurrent fetch's entries are kept; a lost race only costs a re-download later."""
    if not entries:
        return
    with _index_lock:
        index = _read_index(dest_root)
        index.update(entries)
        os.makedirs(dest_root, exist_ok=True)
        fd, tmp = tempfile.mkstemp(prefix=INDEX_NAME, suffix=".tmp", dir=dest_root)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                json.dump(index, fh, sort_keys=True)
            for attempt in range(5):
                try:
                    os.replace(tmp, os.path.join(dest_root, INDEX_NAME))
                    break
                except PermissionError:  # Windows: another process has it open
                    if attempt == 4:
                        raise
                    time.sleep(0.05 * (attempt + 1))
        finally:
            if os.path.exists(tmp):
                os.remove(tmp)


def download(
    outputs: JobOutputs,
    files: list,
    dest_root: str,
    session: Any = None,
    progress: Progress | None = None,
    workers: int = 8,
) -> int:
    """Download ``files`` under ``dest_root``, skipping ones already there with the same
    size and manifest hash. ``progress`` is called in order as bytes arrive, then once
    more from this thread when everything is done (the caller throttles). Returns the
    bytes downloaded.

    The resume index is flushed as files finish (see :data:`_INDEX_FLUSH_S`), so a
    download that is killed rather than raising still resumes where it stopped."""
    from concurrent.futures import ThreadPoolExecutor

    from boto3.s3.transfer import TransferConfig
    from botocore.config import Config

    from .session import make_session

    workers = max(1, workers)
    plan = [(f, safe_destination(dest_root, f.path)) for f in files]  # reject bad paths first
    index = _read_index(dest_root)
    todo, have = [], 0
    for f, dst in plan:
        rec = index.get(f.path) or {}
        if (
            os.path.isfile(dst)
            and os.path.getsize(dst) == f.size
            and rec.get("hash") == f.hash
            and rec.get("alg", f.hash_alg) == f.hash_alg
        ):
            have += f.size
        else:
            todo.append((f, dst))
    total_b = sum(f.size for f in files)
    state = {"b": have, "n": len(files) - len(todo)}
    done: dict = {}
    pending: dict = {}  # finished but not yet in the index on disk
    flushed_at = {"t": time.monotonic()}
    lock = threading.Lock()

    def report() -> None:
        # Under ``lock``, so calls arrive in order and never with a torn state.
        if progress:
            progress(state["b"], total_b, state["n"], len(files))

    if not todo:
        with lock:
            report()
        return 0
    s3 = (outputs.s3_session or session or make_session()).client(
        "s3", config=Config(max_pool_connections=max(10, workers * _PART_CONCURRENCY))
    )
    transfer = TransferConfig(max_concurrency=_PART_CONCURRENCY)

    def bump(nbytes: int) -> None:
        with lock:
            state["b"] += nbytes
            report()

    def one(item: tuple) -> int:
        f, dst = item
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        try:
            s3.download_file(
                outputs.bucket,
                f"{outputs.cas_prefix}/{f.hash}.{f.hash_alg}",
                dst,
                Callback=bump,
                Config=transfer,
            )
        except (FileExistsError, PermissionError):
            # Windows: a concurrent fetch renamed the same file into place first.
            if not (os.path.isfile(dst) and os.path.getsize(dst) == f.size):
                raise
        with lock:
            state["n"] += 1
            rec = {"hash": f.hash, "alg": f.hash_alg, "size": f.size}
            done[f.path] = pending[f.path] = rec
            now = time.monotonic()
            batch: dict = {}
            if len(pending) >= _INDEX_FLUSH_FILES or now - flushed_at["t"] >= _INDEX_FLUSH_S:
                batch, flushed_at["t"] = dict(pending), now
                pending.clear()
            if state["n"] < len(files):
                report()  # the final report comes from the calling thread
        # Outside ``lock``: writing the index must not hold up the other workers' progress.
        if batch:
            _write_index(dest_root, batch)
        return int(f.size)

    with lock:
        report()
    try:
        with ThreadPoolExecutor(max_workers=min(workers, len(todo))) as pool:
            nbytes = sum(pool.map(one, todo))
    finally:
        with lock:
            finished = dict(done)
        _write_index(dest_root, finished)
    with lock:
        state["b"], state["n"] = total_b, len(files)
        report()
    return nbytes
