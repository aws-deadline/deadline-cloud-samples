# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
"""Finished jobs come from SearchJobs, filtered by status and sorted by the service."""

from __future__ import annotations

import datetime
from types import SimpleNamespace
from typing import Any

import pytest

from deadline.physical_ai import jobs


class _Deadline:
    def __init__(self, total: int) -> None:
        self.total = total
        self.calls: list = []

    def search_jobs(self, **kw: Any) -> dict:
        self.calls.append(kw)
        start, size = kw["itemOffset"], kw["pageSize"]
        ended = datetime.datetime(2026, 11, 11, tzinfo=datetime.timezone.utc)
        page = [
            {"jobId": f"job-{i}", "name": f"j{i}", "taskRunStatus": "SUCCEEDED", "endedAt": ended}
            for i in range(start, min(start + size, self.total))
        ]
        nxt = start + len(page)
        return {
            "jobs": page,
            "totalResults": self.total,
            "nextItemOffset": nxt if nxt < self.total else None,
        }


def _session(d: _Deadline) -> Any:
    return SimpleNamespace(client=lambda name, **kw: d)


def test_finished_jobs_filters_and_sorts_on_the_service() -> None:
    d = _Deadline(total=3)
    out = jobs.finished_jobs(farm_id="farm-1", queue_id="queue-1", session=_session(d))
    kw = d.calls[0]
    assert kw["queueIds"] == ["queue-1"]
    assert kw["filterExpressions"]["filters"][0]["stringFilter"]["value"] == "SUCCEEDED"
    assert kw["filterExpressions"]["operator"] == "AND"
    assert kw["filterExpressions"]["filters"][1] == jobs.NOT_ARCHIVED  # as in Monitor
    assert kw["sortExpressions"][0]["fieldSort"] == {"name": "ENDED_AT", "sortOrder": "DESCENDING"}
    assert [j["jobId"] for j in out["jobs"]] == ["job-0", "job-1", "job-2"]
    assert out["jobs"][0]["endedAt"].startswith("2026-11-11") and out["next_offset"] is None


def test_finished_jobs_pages_with_offset() -> None:
    d = _Deadline(total=250)
    first = jobs.finished_jobs(farm_id="f", queue_id="q", limit=120, session=_session(d))
    assert len(first["jobs"]) == 120 and first["next_offset"] == 120 and first["total"] == 250
    rest = jobs.finished_jobs(
        farm_id="f", queue_id="q", limit=200, offset=first["next_offset"], session=_session(d)
    )
    assert rest["jobs"][0]["jobId"] == "job-120" and len(rest["jobs"]) == 130
    assert rest["next_offset"] is None
    assert all(c["pageSize"] <= jobs.PAGE_SIZE for c in d.calls)


def test_finished_jobs_needs_a_farm_and_queue(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(jobs, "deadline_defaults", dict)
    with pytest.raises(ValueError, match="no farm or queue"):
        jobs.finished_jobs(session=_session(_Deadline(0)))


def test_finished_jobs_filter_by_status() -> None:
    d = _Deadline(total=1)
    out = jobs.finished_jobs(farm_id="f", queue_id="q", status="failed", session=_session(d))
    assert d.calls[0]["filterExpressions"]["filters"][0]["stringFilter"]["value"] == "FAILED"
    assert out["status"] == "failed"
    jobs.finished_jobs(farm_id="f", queue_id="q", status="any", session=_session(d))
    group = d.calls[1]["filterExpressions"]["filters"][0]["groupFilter"]
    assert d.calls[1]["filterExpressions"]["filters"][1] == jobs.NOT_ARCHIVED
    assert group["operator"] == "OR"
    assert [f["stringFilter"]["value"] for f in group["filters"]] == [
        "SUCCEEDED",
        "FAILED",
        "CANCELED",
    ]


def test_finished_jobs_reject_an_unknown_status() -> None:
    with pytest.raises(ValueError, match="unknown status"):
        jobs.finished_jobs(
            farm_id="f", queue_id="q", status="running", session=_session(_Deadline(0))
        )


def test_cli_status_choices_match_the_jobs_module() -> None:
    from deadline.physical_ai import cli

    assert set(cli._JOB_STATUSES) == set(jobs.STATUSES)


class _GetJob:
    def get_job(self, **kw: Any) -> dict:
        return {
            "name": f"name of {kw['jobId']}",
            "parameters": {
                "Steps": {"int": "500"},
                "OutputDir": {"path": "/out"},
                "Lr": {"float": "0.001"},
                "Tag": {"string": "a"},
            },
        }


def test_job_parameters_flatten_values() -> None:
    out = jobs.job_parameters(
        ["job-1", "job-2", "job-1"],
        farm_id="f",
        queue_id="q",
        session=SimpleNamespace(client=lambda name, **kw: _GetJob()),
    )
    assert [j["job_id"] for j in out["jobs"]] == ["job-1", "job-2"]
    assert out["jobs"][0]["name"] == "name of job-1"
    assert out["jobs"][0]["parameters"] == {
        "Lr": "0.001",
        "OutputDir": "/out",
        "Steps": "500",
        "Tag": "a",
    }


def test_parameter_value_handles_odd_shapes() -> None:
    assert jobs.parameter_value({"unknown": 1}) == ""
    assert jobs.parameter_value(None) == ""
    assert jobs.parameter_value(3) == "3"
