# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
"""Finished jobs in a queue (succeeded, failed or canceled), newest finished first.
Archived jobs are left out."""

from __future__ import annotations

from typing import Any

from . import session as ses
from .config import deadline_defaults

#: SearchJobs returns at most 100 jobs per call.
PAGE_SIZE = 100
#: Default number of jobs one call lists (one page in the app).
DEFAULT_LIMIT = 50
#: ``--status`` choices and the job task run statuses each one matches.
STATUSES = {
    "succeeded": ("SUCCEEDED",),
    "failed": ("FAILED",),
    "canceled": ("CANCELED",),
    "any": ("SUCCEEDED", "FAILED", "CANCELED"),
}
DEFAULT_STATUS = "succeeded"
#: Archived jobs are hidden, as in Deadline Cloud Monitor (SearchJobs returns them).
NOT_ARCHIVED = {
    "stringFilter": {"name": "LIFECYCLE_STATUS", "operator": "NOT_EQUAL", "value": "ARCHIVED"}
}
_FIELDS = ("jobId", "name", "taskRunStatus", "createdAt", "createdBy", "startedAt", "endedAt")


def _text(value: Any) -> str:
    return value.isoformat() if hasattr(value, "isoformat") else str(value or "")


def _status_filter(status: str) -> dict:
    values = STATUSES.get(status)
    if not values:
        raise ValueError(f"unknown status {status!r}: use one of {', '.join(STATUSES)}")
    filters = [
        {"stringFilter": {"name": "TASK_RUN_STATUS", "operator": "EQUAL", "value": v}}
        for v in values
    ]
    status_filter = (
        filters[0] if len(filters) == 1 else {"groupFilter": {"filters": filters, "operator": "OR"}}
    )
    return {"filters": [status_filter, NOT_ARCHIVED], "operator": "AND"}


def finished_jobs(
    *,
    status: str = DEFAULT_STATUS,
    farm_id: str | None = None,
    queue_id: str | None = None,
    profile: str | None = None,
    region: str | None = None,
    limit: int = DEFAULT_LIMIT,
    offset: int = 0,
    session: Any = None,
) -> dict:
    """Finished jobs with the given ``status`` (see :data:`STATUSES`), filtered and sorted by
    the service (``SearchJobs``), so older jobs are not hidden behind newer running ones.
    ``offset`` pages through them; ``next_offset`` is ``None`` after the last page."""
    filter_expressions = _status_filter(status)
    d = deadline_defaults()
    farm_id, queue_id = farm_id or d.get("farm_id") or "", queue_id or d.get("queue_id") or ""
    if not (farm_id and queue_id):
        raise ValueError("no farm or queue: pass --farm-id and --queue-id, or set the defaults")
    deadline = (session or ses.make_session(profile, region)).client("deadline")
    jobs: list = []
    limit = max(1, limit)
    next_offset: int | None = max(0, offset)
    total = 0
    while next_offset is not None and len(jobs) < limit:
        r = deadline.search_jobs(
            farmId=farm_id,
            queueIds=[queue_id],
            itemOffset=next_offset,
            pageSize=min(PAGE_SIZE, limit - len(jobs)),
            filterExpressions=filter_expressions,
            sortExpressions=[{"fieldSort": {"name": "ENDED_AT", "sortOrder": "DESCENDING"}}],
        )
        total = int(r.get("totalResults") or 0)
        for j in r.get("jobs") or []:
            jobs.append({k: _text(j.get(k)) for k in _FIELDS})
        next_offset = r.get("nextItemOffset")
    if len(jobs) > limit:  # a page can overshoot; resume right after what we return
        jobs, next_offset = jobs[:limit], max(0, offset) + limit
    return {
        "farm_id": farm_id,
        "queue_id": queue_id,
        "status": status,
        "jobs": jobs,
        "offset": max(0, offset),
        "next_offset": next_offset,
        "total": total,
    }


def parameter_value(value: Any) -> str:
    """One GetJob parameter (``{"string": ...}``, ``{"path": ...}``, ``{"int": ...}`` or
    ``{"float": ...}``) as text."""
    if isinstance(value, dict):
        for key in ("string", "path", "int", "float"):
            if key in value:
                return str(value[key])
        return ""
    return "" if value is None else str(value)


def job_parameters(
    job_ids: list,
    *,
    farm_id: str | None = None,
    queue_id: str | None = None,
    profile: str | None = None,
    region: str | None = None,
    session: Any = None,
) -> dict:
    """Each job's name and parameters as text (``GetJob``), in the order given."""
    if not job_ids:
        raise ValueError("pass at least one job ID")
    d = deadline_defaults()
    farm_id, queue_id = farm_id or d.get("farm_id") or "", queue_id or d.get("queue_id") or ""
    if not (farm_id and queue_id):
        raise ValueError("no farm or queue: pass --farm-id and --queue-id, or set the defaults")
    deadline = (session or ses.make_session(profile, region)).client("deadline")
    out = []
    for job_id in dict.fromkeys(job_ids):
        job = deadline.get_job(farmId=farm_id, queueId=queue_id, jobId=job_id)
        params = job.get("parameters") or {}
        out.append(
            {
                "job_id": job_id,
                "name": str(job.get("name") or ""),
                "parameters": {k: parameter_value(v) for k, v in sorted(params.items())},
            }
        )
    return {"farm_id": farm_id, "queue_id": queue_id, "jobs": out}
