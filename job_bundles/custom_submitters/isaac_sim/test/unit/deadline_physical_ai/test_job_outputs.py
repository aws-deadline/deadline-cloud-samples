# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
"""Listing a job's output files from its manifests, with the AWS calls stubbed."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from deadline.physical_ai import job_outputs as jo


def test_rebase_outputs_onto_the_jobs_output_dir() -> None:
    files = [
        jo.OutputFile("home/me/out/dataset/meta/info.json", "h1", 1),
        jo.OutputFile("home/me/other/x", "h2", 1),
    ]
    root, rebased = jo.rebase_outputs({"/": files}, "/home/me/out")
    assert root == "/home/me/out" and [f.path for f in rebased] == ["dataset/meta/info.json"]
    _root, same = jo.rebase_outputs({"/home/me/out": [jo.OutputFile("a", "h", 1)]}, "/home/me/out")
    assert [f.path for f in same] == ["a"]
    win_root, win = jo.rebase_outputs(
        {"C:\\work": [jo.OutputFile("out/a.usd", "h", 1)]}, "C:\\work\\out"
    )
    assert win_root == "C:\\work\\out" and [f.path for f in win] == ["a.usd"]
    with pytest.raises(jo.OutputsError, match="no output root contains"):
        jo.rebase_outputs({"/data": files}, "/home/me/out")
    with pytest.raises(jo.OutputsError, match="several roots"):
        jo.rebase_outputs({"/a": [], "/b": []}, "")
    assert jo.rebase_outputs({"/a": files}, "") == ("/a", files)


@pytest.mark.parametrize("bad", ["", "../x", "a/../../x", "/abs/x", "C:/x", "C:\\x", ".."])
def test_safe_destination_rejects_escapes(tmp_path: Any, bad: str) -> None:
    with pytest.raises(jo.OutputsError):
        jo.safe_destination(str(tmp_path), bad)


def test_safe_destination_keeps_layout(tmp_path: Any) -> None:
    got = jo.safe_destination(str(tmp_path), "a\\b/./c.usd")
    assert got == str(tmp_path / "a" / "b" / "c.usd")


class _Deadline:
    def __init__(self, bucket: str = "bucket") -> None:
        self.bucket = bucket

    def get_queue(self, **kw: Any) -> dict:
        if not self.bucket:
            return {}
        return {
            "jobAttachmentSettings": {"s3BucketName": self.bucket, "rootPrefix": "DeadlineCloud"}
        }

    def get_job(self, **kw: Any) -> dict:
        return {"parameters": {"OutputDir": {"path": "/work/out"}}}

    def assume_queue_role_for_user(self, **kw: Any) -> dict:
        from botocore.exceptions import ClientError

        raise ClientError({"Error": {"Code": "AccessDeniedException"}}, "AssumeQueueRoleForUser")


def _session(bucket: str = "bucket") -> Any:
    return SimpleNamespace(client=lambda name, **kw: _Deadline(bucket))


def test_list_job_outputs_reads_manifests(monkeypatch: pytest.MonkeyPatch) -> None:
    import deadline.job_attachments.download as dl

    manifest = SimpleNamespace(
        hashAlg=SimpleNamespace(value="xxh128"),
        paths=[
            SimpleNamespace(path="out\\scene.usda", hash="h1", size=5),
            SimpleNamespace(path="other/x", hash="h2", size=None),
        ],
    )
    monkeypatch.setattr(
        dl, "get_output_manifests_by_asset_root", lambda *a, **k: {"/work": [manifest]}
    )
    outs = jo.list_job_outputs("job-1", "farm-1", "queue-1", session=_session())
    assert outs.asset_root == "/work/out" and outs.bucket == "bucket"
    assert outs.cas_prefix == "DeadlineCloud/Data"
    assert outs.files == [jo.OutputFile("scene.usda", "h1", 5, "xxh128")]


def test_list_job_outputs_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    import deadline.job_attachments.download as dl

    with pytest.raises(jo.OutputsError, match="no job attachments bucket"):
        jo.list_job_outputs("job-1", "f", "q", session=_session(bucket=""))
    monkeypatch.setattr(dl, "get_output_manifests_by_asset_root", lambda *a, **k: {})
    with pytest.raises(jo.OutputsError, match="no output manifests"):
        jo.list_job_outputs("job-1", "f", "q", session=_session())
