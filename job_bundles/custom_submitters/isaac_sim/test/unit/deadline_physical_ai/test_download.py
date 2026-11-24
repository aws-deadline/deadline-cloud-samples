# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
"""``job_outputs.download``: progress, resume by content hash, races, and path safety. No AWS."""

import json
import os
import threading
import time
from types import SimpleNamespace

import pytest

from deadline.physical_ai import job_outputs as fj


class FakeS3:
    """Writes ``size`` bytes derived from the key's hash, so different hashes differ in content."""

    def __init__(self, fail_on=(), exists_on=(), delay=None):
        self.calls, self.fail_on, self.exists_on, self.delay = (
            [],
            set(fail_on),
            set(exists_on),
            delay or {},
        )
        self.kwargs = []

    def download_file(self, bucket, key, dst, Callback=None, **kw):
        self.calls.append(key)
        self.kwargs.append(kw)
        h = key.rsplit("/", 1)[-1].split(".")[0]
        if h in self.fail_on:
            raise RuntimeError(f"boom {h}")
        time.sleep(self.delay.get(h, 0))
        size = int(h.split("-")[-1])
        with open(dst, "wb") as fh:
            fh.write((h.encode() * size)[:size])
        if Callback:
            Callback(size // 2)
            Callback(size - size // 2)
        if h in self.exists_on:
            # s3transfer on Windows: another process renamed its copy into place first.
            raise FileExistsError(dst)


def _session(s3):
    seen = []

    def client(name, **kw):
        seen.append(kw)
        return s3

    return SimpleNamespace(client=client, seen=seen)


def _f(path, h, size):
    return SimpleNamespace(path=path, size=size, hash=f"{h}-{size}", hash_alg="xxh128")


OUTS = fj.JobOutputs("", [], bucket="b", cas_prefix="Data")


def _index(root):
    with open(os.path.join(root, fj.INDEX_NAME), encoding="utf-8") as fh:
        return json.load(fh)


def test_download_reports_progress_and_skips_existing(tmp_path):
    files = [_f(f"d/f{i}.bin", f"h{i}", 10 * (i + 1)) for i in range(5)]
    s3 = FakeS3()
    fj.download(OUTS, files[:1], str(tmp_path), session=_session(s3))  # f0 already there: skipped
    seen = []
    n = fj.download(
        OUTS,
        files,
        str(tmp_path),
        session=_session(s3),
        progress=lambda *a: seen.append(a),
        workers=3,
    )
    assert n == 140 and seen[0] == (10, 150, 1, 5) and seen[-1] == (150, 150, 5, 5)
    assert all(s[1] == 150 and s[3] == 5 for s in seen)
    assert [s for s in seen if s[2] == 5] == [(150, 150, 5, 5)], "exactly one final report"
    assert fj.download(OUTS, files, str(tmp_path), session=_session(s3)) == 0


def test_progress_is_monotonic_and_final_is_last(tmp_path):
    """A slow callback on one worker must not let its stale report land after the final one."""
    files = [_f("a.bin", "fast", 10), _f("b.bin", "slow", 10)]
    s3 = FakeS3(delay={"slow-10": 0.05})
    seen: list = []
    slept: list = []
    guard = threading.Lock()

    def progress(b, tb, n, tn):
        with guard:
            first = n == 1 and not slept
            if first:
                slept.append(1)
        if first:
            time.sleep(0.3)
        seen.append((b, tb, n, tn))

    fj.download(OUTS, files, str(tmp_path), session=_session(s3), progress=progress, workers=2)
    assert seen[-1] == (20, 20, 2, 2)
    assert [s[0] for s in seen] == sorted(s[0] for s in seen)
    assert [s[2] for s in seen] == sorted(s[2] for s in seen)


def test_same_size_different_hash_is_downloaded_again(tmp_path):
    """Reusing a dest across jobs must not serve job A's same-size file as job B's."""
    s3 = FakeS3()
    fj.download(OUTS, [_f("ckpt/w.bin", "jobA", 16)], str(tmp_path), session=_session(s3))
    n = fj.download(OUTS, [_f("ckpt/w.bin", "jobB", 16)], str(tmp_path), session=_session(s3))
    assert n == 16 and len(s3.calls) == 2
    assert (tmp_path / "ckpt" / "w.bin").read_bytes().startswith(b"jobB")
    assert _index(tmp_path)["ckpt/w.bin"]["hash"] == "jobB-16"
    assert (
        fj.download(OUTS, [_f("ckpt/w.bin", "jobB", 16)], str(tmp_path), session=_session(s3)) == 0
    )
    assert len(s3.calls) == 2


def test_present_file_without_index_entry_is_downloaded(tmp_path):
    """No record of what the file holds: re-download rather than trust the size."""
    (tmp_path / "w.bin").write_bytes(b"x" * 8)
    s3 = FakeS3()
    assert fj.download(OUTS, [_f("w.bin", "h", 8)], str(tmp_path), session=_session(s3)) == 8
    assert len(s3.calls) == 1


def test_index_survives_partial_failure(tmp_path):
    """Files finished before an error are recorded, so a retry skips them."""
    files = [_f("a.bin", "a", 4), _f("b.bin", "b", 4), _f("c.bin", "c", 4)]
    s3 = FakeS3(fail_on={"b-4"})
    with pytest.raises(RuntimeError):
        fj.download(OUTS, files, str(tmp_path), session=_session(s3), workers=1)
    assert "a.bin" in _index(tmp_path) and "b.bin" not in _index(tmp_path)
    s3 = FakeS3()
    fj.download(OUTS, files, str(tmp_path), session=_session(s3), workers=1)
    assert "Data/a-4.xxh128" not in s3.calls and "Data/b-4.xxh128" in s3.calls


def test_file_exists_race_counts_as_done(tmp_path):
    """A concurrent fetch that renamed the same file into place first is not an error."""
    s3 = FakeS3(exists_on={"h-6"})
    assert fj.download(OUTS, [_f("x/y.bin", "h", 6)], str(tmp_path), session=_session(s3)) == 6
    assert _index(tmp_path)["x/y.bin"]["hash"] == "h-6"


def test_file_exists_with_wrong_size_still_fails(tmp_path):
    class Short(FakeS3):
        def download_file(self, bucket, key, dst, Callback=None, **kw):
            with open(dst, "wb") as fh:
                fh.write(b"x")
            raise FileExistsError(dst)

    with pytest.raises(FileExistsError):
        fj.download(OUTS, [_f("y.bin", "h", 6)], str(tmp_path), session=_session(Short()))


@pytest.mark.parametrize("bad", ["../evil.bin", "a/../../evil.bin", "/abs/evil.bin"])
def test_paths_outside_dest_are_rejected(tmp_path, bad):
    dest = tmp_path / "dest"
    s3 = FakeS3()
    with pytest.raises(fj.OutputsError):
        fj.download(OUTS, [_f("ok.bin", "o", 2), _f(bad, "e", 2)], str(dest), session=_session(s3))
    assert s3.calls == [] and not (tmp_path / "evil.bin").exists()


def test_s3_connection_pool_fits_the_parallelism(tmp_path):
    s3 = FakeS3()
    session = _session(s3)
    fj.download(
        OUTS, [_f(f"f{i}", "h", 2) for i in range(4)], str(tmp_path), session=session, workers=4
    )
    cfg = session.seen[0]["config"]
    tc = s3.kwargs[0]["Config"]
    assert cfg.max_pool_connections >= 4 * tc.max_concurrency


def test_index_is_written_as_files_finish(tmp_path, monkeypatch):
    """A killed fetch (the extension kills one after an hour) must not restart from zero:
    the index on disk already names every file that finished before the kill."""
    monkeypatch.setattr(fj, "_INDEX_FLUSH_FILES", 1)
    files = [_f(f"f{i}.bin", f"h{i}", 4) for i in range(4)]
    killed: dict = {}

    class Killed(FakeS3):
        def download_file(self, bucket, key, dst, Callback=None, **kw):
            if key.startswith("Data/h3-"):
                # What a SIGKILL would leave behind: nothing after this point runs.
                killed["index"] = (tmp_path / fj.INDEX_NAME).read_bytes()
                raise KeyboardInterrupt("killed")
            super().download_file(bucket, key, dst, Callback=Callback, **kw)

    with pytest.raises(KeyboardInterrupt):
        fj.download(OUTS, files, str(tmp_path), session=_session(Killed()), workers=1)
    assert sorted(json.loads(killed["index"])) == ["f0.bin", "f1.bin", "f2.bin"]
    (tmp_path / fj.INDEX_NAME).write_bytes(killed["index"])
    s3 = FakeS3()
    assert fj.download(OUTS, files, str(tmp_path), session=_session(s3), workers=1) == 4
    assert s3.calls == ["Data/h3-4.xxh128"]
