# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
"""``outputs.fetch`` path matching and ``outputs.job_outputs`` metadata reads. No AWS."""

from __future__ import annotations

import json
import os
from typing import Any

import pytest

from deadline.physical_ai import config as cfg
from deadline.physical_ai import eval_summary, outputs
from deadline.physical_ai import job_outputs as jo
from deadline.physical_ai import session as ses
from deadline.physical_ai.job_outputs import JobOutputs, OutputFile


def _files(*paths: str, size: int = 10) -> list:
    return [OutputFile(path=p, hash="h" + p, size=size) for p in paths]


@pytest.fixture()
def remote(monkeypatch: pytest.MonkeyPatch, tmp_path: Any) -> dict:
    """Stub AWS: ``remote["files"]`` is the job's output list, ``remote["got"]`` what was downloaded."""
    state: dict = {"files": [], "got": []}
    monkeypatch.setenv(cfg.HOME_ENV, str(tmp_path / "home"))
    monkeypatch.setattr(ses, "make_session", lambda *a, **k: object())
    monkeypatch.setattr(
        jo, "list_job_outputs", lambda *a, **k: JobOutputs("/out", state["files"], "b", "Data")
    )

    def download(
        outs: Any, files: list, dest: str, session: Any = None, progress: Any = None, **kw: Any
    ) -> int:
        state["got"] = sorted(f.path for f in files)
        state["dest"] = dest
        return sum(f.size for f in files)

    monkeypatch.setattr(jo, "download", download)
    return state


def test_fetch_root_checkpoint(remote: dict, tmp_path: Any) -> None:
    """detect() gives a root checkpoint path ""; fetching it means every file."""
    remote["files"] = _files("checkpoint.json", "model.safetensors")
    for path in ("", "/"):
        r = outputs.fetch("job-1", [path], dest=str(tmp_path), farm_id="f", queue_id="q")
        assert remote["got"] == ["checkpoint.json", "model.safetensors"]
        assert r["items"] == {"": str(tmp_path)} and r["missing"] == [] and r["file_count"] == 2


def test_fetch_reports_only_matched_paths(remote: dict, tmp_path: Any) -> None:
    remote["files"] = _files("train/checkpoint/checkpoint.json", "scenes/a.usda")
    r = outputs.fetch(
        "job-1", ["scenes/a.usda", "gone/b.usda"], dest=str(tmp_path), farm_id="f", queue_id="q"
    )
    assert r["items"] == {"scenes/a.usda": os.path.join(str(tmp_path), "scenes", "a.usda")}
    assert r["missing"] == ["gone/b.usda"] and remote["got"] == ["scenes/a.usda"]
    with pytest.raises(ValueError):
        outputs.fetch("job-1", ["gone/b.usda"], dest=str(tmp_path), farm_id="f", queue_id="q")
    with pytest.raises(ValueError, match="nothing to fetch"):
        outputs.fetch("job-1", [], farm_id="f", queue_id="q")


def test_fetch_strips_slashes_and_defaults_dest(remote: dict, tmp_path: Any) -> None:
    remote["files"] = _files(
        "train/checkpoint/checkpoint.json",
        "train/checkpoint/w.bin",
        "train/checkpoint2/checkpoint.json",
    )
    r = outputs.fetch("job-1", ["/train/checkpoint/"], farm_id="f", queue_id="q")
    assert remote["got"] == ["train/checkpoint/checkpoint.json", "train/checkpoint/w.bin"]
    assert list(r["items"]) == ["train/checkpoint"]
    assert (
        r["dest"] == remote["dest"] == os.path.join(str(tmp_path / "home"), "job_outputs", "job-1")
    )


def test_farm_and_queue_come_from_the_deadline_config(
    remote: dict, monkeypatch: pytest.MonkeyPatch
) -> None:
    seen: dict = {}

    def listing(job_id: str, farm_id: str, queue_id: str, **kw: Any) -> JobOutputs:
        seen.update(farm=farm_id, queue=queue_id)
        return JobOutputs("/out", [], "b", "Data")

    monkeypatch.setattr(jo, "list_job_outputs", listing)
    monkeypatch.setattr(
        cfg, "deadline_defaults", lambda: {"farm_id": "farm-d", "queue_id": "queue-d"}
    )
    assert outputs.job_outputs("job-1")["items"] == []
    assert seen == {"farm": "farm-d", "queue": "queue-d"}
    monkeypatch.setattr(cfg, "deadline_defaults", lambda: {"farm_id": "", "queue_id": ""})
    with pytest.raises(ValueError, match="--farm-id"):
        outputs.job_outputs("job-1")


def _job_outputs(monkeypatch: pytest.MonkeyPatch, files: list, texts: dict) -> dict:
    monkeypatch.setattr(outputs, "_small_text", lambda outs, f, session: texts[f.path])
    return outputs.job_outputs("job-1", farm_id="f", queue_id="q")


def test_list_reads_the_eval_summary(remote: dict, monkeypatch: pytest.MonkeyPatch) -> None:
    summary = {"episodes": 20, "successes": 15, "success_rate": 0.75, "extra": "dropped"}
    remote["files"] = [
        OutputFile("ev/eval_summary.json", "a", 50),
        OutputFile("ev/ep_0.trajectory.npz", "b", 10),
        OutputFile("ev2/eval_summary.json", "c", 50),
    ]
    r = _job_outputs(monkeypatch, remote["files"], {"ev/eval_summary.json": json.dumps(summary)})
    ci95 = r["eval_summary"].pop("ci95")  # computed (Wilson) when the file has none
    assert ci95[0] < 0.75 < ci95[1]
    assert r["eval_summary"] == {
        "episodes": 20,
        "successes": 15,
        "success_rate": 0.75,
        "path": "ev/eval_summary.json",
    }
    assert r["file_count"] == 3 and r["total_bytes"] == 110 and r["warnings"] == []
    assert [i["kind"] for i in r["items"]] == ["eval_summary", "eval_summary", "trajectory"]


def test_list_warns_on_oversized_or_bad_summary(
    remote: dict, monkeypatch: pytest.MonkeyPatch
) -> None:
    remote["files"] = [
        OutputFile("a/eval_summary.json", "a", eval_summary.EVAL_SUMMARY_CAP + 1),
        OutputFile("b/eval_summary.json", "b", 5),
    ]
    r = _job_outputs(monkeypatch, remote["files"], {"b/eval_summary.json": "{not json"})
    assert r["eval_summary"] is None and len(r["warnings"]) == 2


def test_small_text_downloads_once(tmp_path: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(cfg.HOME_ENV, str(tmp_path))
    calls: list = []

    class S3:
        def download_file(self, bucket: str, key: str, dest: str) -> None:
            calls.append(key)
            with open(dest, "w", encoding="utf-8") as fh:
                fh.write('{"episodes": 1}')

    class Session:
        def client(self, name: str) -> S3:
            return S3()

    f = OutputFile("e/eval_summary.json", "abc", 15)
    outs = JobOutputs("/out", [f], "bucket", "root/Data")
    assert outputs._small_text(outs, f, Session()) == '{"episodes": 1}'
    assert outputs._small_text(outs, f, Session()) == '{"episodes": 1}'
    assert calls == ["root/Data/abc.xxh128"]


def test_fetch_usd_brings_its_folder(remote: dict, tmp_path: Any) -> None:
    """A .usd file alone is useless: its references, payloads and textures sit beside it."""
    remote["files"] = _files(
        "scenes/table.usda",
        "scenes/table_payload.usdc",
        "scenes/textures/wood.png",
        "scenes/other.usda",
        "logs/run.log",
    )
    r = outputs.fetch("job-1", ["scenes/table.usda"], dest=str(tmp_path), farm_id="f", queue_id="q")
    assert remote["got"] == [
        "scenes/other.usda",
        "scenes/table.usda",
        "scenes/table_payload.usdc",
        "scenes/textures/wood.png",
    ]
    # The item still loads from the .usd file inside the folder that was fetched.
    assert r["items"] == {"scenes/table.usda": os.path.join(str(tmp_path), "scenes", "table.usda")}
    assert r["missing"] == []


def test_fetch_usd_at_the_output_root_is_only_the_file(remote: dict, tmp_path: Any) -> None:
    """At the OutputDir root the containing folder is the whole job: fetch just the file."""
    remote["files"] = _files("table.usda", "episodes.hdf5")
    r = outputs.fetch("job-1", ["table.usda"], dest=str(tmp_path), farm_id="f", queue_id="q")
    assert remote["got"] == ["table.usda"]
    assert r["items"] == {"table.usda": os.path.join(str(tmp_path), "table.usda")}


def test_fetch_unknown_usd_path_is_still_missing(remote: dict, tmp_path: Any) -> None:
    """Expanding to the folder must not turn a path the job never wrote into a hit."""
    remote["files"] = _files("scenes/table.usda")
    r = outputs.fetch(
        "job-1",
        ["scenes/table.usda", "scenes/gone.usd"],
        dest=str(tmp_path),
        farm_id="f",
        queue_id="q",
    )
    assert r["missing"] == ["scenes/gone.usd"]
