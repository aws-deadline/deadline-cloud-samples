# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
"""Eval summaries are checked, completed and read across a queue's jobs."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from deadline.physical_ai import eval_summary as es
from deadline.physical_ai import evals
from deadline.physical_ai import job_outputs as jo


def test_wilson_interval() -> None:
    interval = es.wilson(41, 50)
    assert interval is not None
    lo, hi = interval
    assert lo == pytest.approx(0.692, abs=1e-3) and hi == pytest.approx(0.902, abs=1e-3)
    none_ok, all_ok = es.wilson(0, 10), es.wilson(10, 10)
    assert none_ok is not None and all_ok is not None
    assert none_ok[0] == pytest.approx(0.0) and all_ok[1] == pytest.approx(1.0)
    assert es.wilson(3, 0) is None and es.wilson(5, 3) is None


def test_summarize_completes_and_checks_fields() -> None:
    out: Any = es.summarize(
        {
            "episodes": 50,
            "successes": 41,
            "checkpoint": "checkpoint-20000",
            "by_condition": {"lit": {"episodes": 25, "successes": 24}, "bad": "x"},
            "metrics": {"mean_len": 212.5, "flag": True, "nan": float("nan"), "s": "x"},
            "extra": 1,
        }
    )
    assert out["success_rate"] == pytest.approx(0.82)
    assert out["ci95"][0] < 0.82 < out["ci95"][1]
    assert out["checkpoint"] == "checkpoint-20000"
    assert out["by_condition"]["lit"]["success_rate"] == pytest.approx(0.96)
    assert "bad" not in out["by_condition"]
    assert out["metrics"] == {"mean_len": 212.5}
    assert "extra" not in out


def test_summarize_keeps_a_given_rate_and_interval() -> None:
    out = es.summarize({"success_rate": 0.5, "ci95": [0.4, 0.6], "episodes": True})
    assert out == {"success_rate": 0.5, "ci95": [0.4, 0.6]}
    assert es.summarize({"ci95": [0.7, 0.2]}) == {}
    assert es.summarize([1]) is None


class _Deadline:
    def search_jobs(self, **kw: Any) -> dict:
        jobs = [
            {"jobId": f"job-{i}", "name": f"j{i}", "taskRunStatus": "SUCCEEDED"} for i in range(3)
        ]
        return {"jobs": jobs, "totalResults": 3, "nextItemOffset": None}

    def get_job(self, **kw: Any) -> dict:
        return {"parameters": {"Lr": {"float": "0.1"}, "Name": {"string": kw["jobId"]}}}


def test_queue_evals_reads_each_job(monkeypatch: pytest.MonkeyPatch) -> None:
    def listing(job_id: str, *a: Any, **k: Any) -> jo.JobOutputs:
        if job_id == "job-1":
            raise jo.OutputsError("no output manifests yet")
        if job_id == "job-2":
            raise RuntimeError("boom")
        return jo.JobOutputs(
            asset_root="/o", files=[jo.OutputFile("eval/eval_summary.json", "h", 9)]
        )

    monkeypatch.setattr(jo, "list_job_outputs", listing)
    monkeypatch.setattr(evals.out_mod, "_small_text", lambda *a: '{"episodes": 4, "successes": 1}')
    session = SimpleNamespace(client=lambda name, **kw: _Deadline())
    out = evals.queue_evals(farm_id="f", queue_id="q", session=session)
    rows = {r["jobId"]: r for r in out["jobs"]}
    assert rows["job-0"]["eval"]["success_rate"] == 0.25
    assert rows["job-0"]["parameters"] == {"Lr": "0.1", "Name": "job-0"}
    assert rows["job-0"]["path"] == "eval/eval_summary.json"
    assert rows["job-1"]["eval"] is None and "error" not in rows["job-1"]
    assert rows["job-2"]["eval"] is None and rows["job-2"]["error"].startswith("RuntimeError")
    assert out["total"] == 3 and out["next_offset"] is None


def test_from_lerobot_single_task() -> None:
    """The shape lerobot_eval.py writes for one task (``aggregated``)."""
    info = {
        "per_episode": [{"episode_ix": 0, "success": True}, {"episode_ix": 1, "success": False}],
        "aggregated": {
            "avg_sum_reward": 12.5,
            "avg_max_reward": 1.0,
            "pc_success": 50.0,
            "n_episodes": 2,
            "n_success": 1,
            "pc_success_ci95": [9.45, 90.55],
            "eval_s": 3.0,
        },
    }
    out: Any = es.summarize(es.from_lerobot(info))
    assert out["episodes"] == 2 and out["successes"] == 1 and out["success_rate"] == 0.5
    assert out["ci95"] == pytest.approx([0.0945, 0.9055])
    assert out["metrics"] == {"avg_sum_reward": 12.5, "avg_max_reward": 1.0}


def test_from_lerobot_multi_task_and_older_files() -> None:
    multi: Any = es.from_lerobot(
        {
            "per_task": [],
            "per_group": {
                "libero_spatial": {"pc_success": 80.0, "n_episodes": 10, "n_success": 8},
                "empty": {},
            },
            "overall": {"pc_success": 60.0, "n_episodes": 20, "n_success": 12},
        }
    )
    assert multi["episodes"] == 20 and multi["successes"] == 12
    assert multi["by_condition"] == {
        "libero_spatial": {"episodes": 10, "successes": 8, "success_rate": 0.8}
    }
    older: Any = es.from_lerobot(
        {"per_episode": [{"success": True}] * 3 + [{"success": False}], "aggregated": {}}
    )
    assert older == {"episodes": 4, "successes": 3}
    assert es.from_lerobot({"aggregated": {}}) is None
    assert es.from_lerobot([1]) is None


def test_read_summary_prefers_eval_summary_over_eval_info() -> None:
    texts = {
        "h1": '{"per_episode": [{"success": true}], "aggregated": {"pc_success": 100.0}}',
        "h2": '{"episodes": 4, "successes": 1}',
    }

    def read(f):
        return texts[f.hash]

    lerobot_only = jo.JobOutputs(
        asset_root="/o", files=[jo.OutputFile("eval/eval_info.json", "h1", 9)]
    )
    summary, path, _ = es.read_summary(lerobot_only.files, read)
    assert path == "eval/eval_info.json" and summary["success_rate"] == 1.0
    both = jo.JobOutputs(
        asset_root="/o",
        files=[
            jo.OutputFile("a/eval_info.json", "h1", 9),
            jo.OutputFile("b/eval_summary.json", "h2", 9),
        ],
    )
    summary, path, _ = es.read_summary(both.files, read)
    assert path == "b/eval_summary.json" and summary["success_rate"] == 0.25
