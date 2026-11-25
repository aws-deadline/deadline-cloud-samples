# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
"""Evaluation results across a queue's completed jobs, read from each job's eval file
(see :mod:`.eval_summary` for the formats).

Only those files are downloaded (a few bytes each), so comparing many training or
evaluation runs needs none of their datasets, checkpoints or videos.

Read-only on AWS: what :mod:`.jobs` and :mod:`.outputs` call.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from typing import Any

from . import job_outputs as jo
from . import jobs as jb
from . import outputs as out_mod
from . import session as ses
from .eval_summary import read_summary

#: Jobs read at once (each lists its output manifests and downloads one small file).
WORKERS = 8


def _one(job: dict, farm_id: str, queue_id: str, session: Any) -> dict:
    row = {k: job.get(k, "") for k in ("jobId", "name", "endedAt")}
    try:
        got = session.client("deadline").get_job(
            farmId=farm_id, queueId=queue_id, jobId=job["jobId"]
        )
        row["parameters"] = {
            k: jb.parameter_value(v) for k, v in sorted((got.get("parameters") or {}).items())
        }
        outs = jo.list_job_outputs(job["jobId"], farm_id, queue_id, session=session)
        row["eval"], row["path"], row["warnings"] = read_summary(
            outs.files, lambda f: out_mod._small_text(outs, f, session)
        )
    except jo.OutputsError as exc:  # no outputs yet: not an error for a table of results
        row["eval"], row["warnings"] = None, [str(exc)]
    except Exception as exc:  # noqa: BLE001 - one unreadable job must not hide the others
        row["eval"], row["error"] = None, f"{type(exc).__name__}: {exc}"
    return row


def queue_evals(
    *,
    farm_id: str | None = None,
    queue_id: str | None = None,
    profile: str | None = None,
    region: str | None = None,
    limit: int = jb.DEFAULT_LIMIT,
    offset: int = 0,
    session: Any = None,
) -> dict:
    """Completed jobs newest first (paged like :func:`jobs.finished_jobs`), each with its
    parameters and eval summary (``eval`` is ``None`` when it has none)."""
    farm_id, queue_id, profile = out_mod._defaults(farm_id, queue_id, profile)
    session = session or ses.make_session(profile, region)
    page = jb.finished_jobs(
        status="succeeded",
        farm_id=farm_id,
        queue_id=queue_id,
        limit=limit,
        offset=offset,
        session=session,
    )
    with ThreadPoolExecutor(max_workers=WORKERS) as pool:
        rows = list(pool.map(lambda j: _one(j, farm_id, queue_id, session), page["jobs"]))
    return {
        "farm_id": farm_id,
        "queue_id": queue_id,
        "jobs": rows,
        "offset": page["offset"],
        "next_offset": page["next_offset"],
        "total": page["total"],
    }
