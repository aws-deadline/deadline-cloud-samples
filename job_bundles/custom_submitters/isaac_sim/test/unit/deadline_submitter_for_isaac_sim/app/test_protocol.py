# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
"""The bridge protocol shared by the app and the extension."""

from __future__ import annotations

import io
import ntpath
import os
import sys
from pathlib import Path

import pytest

from deadline.isaac_sim_submitter import extension_path
from deadline.isaac_sim_submitter.app import protocol as pr

APP_DIR = Path(pr.__file__).parent
EXT_PKG = extension_path() / "isaacsim" / "deadline" / "submitter"


@pytest.mark.parametrize("name", ["protocol.py", "procenv.py"])
def test_extension_copy_is_identical(name):
    """The extension cannot import the app's package in every Isaac Sim install, so it
    ships a copy; edit both together."""
    assert (EXT_PKG / name).read_bytes() == (APP_DIR / name).read_bytes()


def test_messages_round_trip():
    for msg in (
        pr.hello("6.2.0", "1.0.0", pr.CAPABILITIES),
        pr.hello_ack("1.0.0", "/d"),
        pr.focus(),
        pr.get_stage("r1"),
        pr.load("r2", "usd", "/d/é.usda"),
        pr.replay_control("r3", "play"),
        pr.result("r1", True, "ok", path="/s.usd"),
    ):
        line = pr.encode(msg)
        assert line.endswith(b"\n") and line.count(b"\n") == 1
        assert pr.decode(line) == msg and msg["v"] == 1
    assert pr.hello("k", "e", ("replay",))["capabilities"] == ["replay"]
    assert pr.result(7, 0)["ok"] is False  # type: ignore[arg-type]


def test_encode_refuses_oversize():
    with pytest.raises(pr.ProtocolError, match="exceeds"):
        pr.encode(pr.load("r", "usd", "x" * pr.MAX_LINE))


@pytest.mark.parametrize(
    "line, match",
    [
        (b"not json", "not UTF-8 JSON"),
        (b"\xff\xfe", "not UTF-8 JSON"),
        (b"[1, 2]", "not a JSON object"),
        (b'{"type": "hello"}', "version"),
        (b'{"v": 2, "type": "hello"}', "version"),
        (b'{"v": 1}', "no message type"),
        (b'{"v": 1, "type": 3}', "no message type"),
    ],
)
def test_decode_rejects(line, match):
    with pytest.raises(pr.ProtocolError, match=match):
        pr.decode(line)


def test_read_messages_framing():
    good = pr.encode(pr.focus())
    stream = io.BytesIO(
        good
        + b"\n   \n"
        + b"garbage\n"
        + b"x" * 50
        + b"\n"  # oversize for max_line=40, newline counted
        + b"y" * 100  # oversize, ends at EOF without a newline
    )
    out = list(pr.read_messages(stream, max_line=40))
    assert out[0] == (pr.focus(), "")
    assert out[1][0] is None and "not UTF-8 JSON" in out[1][1]
    assert out[2] == (None, "line longer than 40 bytes skipped")
    assert out[3] == (None, "line longer than 40 bytes skipped") and len(out) == 4


def test_read_messages_resyncs_after_oversize_line():
    stream = io.BytesIO(b"z" * 200 + b"\n" + pr.encode(pr.focus()) + b"\r\n")
    out = list(pr.read_messages(stream, max_line=64))
    assert out == [(None, "line longer than 64 bytes skipped"), (pr.focus(), "")]


def test_read_messages_accepts_a_line_of_exactly_max():
    line = pr.encode(pr.focus())
    assert list(pr.read_messages(io.BytesIO(line), max_line=len(line))) == [(pr.focus(), "")]


# ------------------------------------------------------------------ validation --


@pytest.fixture
def root(tmp_path):
    r = tmp_path / "downloads"
    (r / "job-1" / "rollouts").mkdir(parents=True)
    (r / "job-1" / "rollouts" / "ep.trajectory.npz").write_bytes(b"npz")
    (r / "job-1" / "scene.USDA").write_text("#usda 1.0")
    (r / "job-1" / "notes.txt").write_text("x")
    (tmp_path / "outside.usda").write_text("#usda 1.0")
    return r


def _load(kind, path):
    return pr.load("r1", kind, str(path))


def test_validate_load_accepts_files_in_the_root(root):
    traj = root / "job-1" / "rollouts" / "ep.trajectory.npz"
    assert pr.validate_load(_load("trajectory", traj), pr.CAPABILITIES, str(root)) == (
        "trajectory",
        os.path.realpath(traj),
    )
    usd = root / "job-1" / "scene.USDA"  # suffixes match case-insensitively
    assert pr.validate_load(_load("usd", usd), pr.CAPABILITIES, str(root))[0] == "usd"


@pytest.mark.parametrize(
    "kind, rel, match",
    [
        ("mesh", "job-1/scene.USDA", "unknown load kind"),
        ("usd", "job-1/notes.txt", "must end with"),
        ("trajectory", "job-1/scene.USDA", "must end with"),
        ("usd", "job-1/missing.usd", "not a file"),
        ("usd", "job-1", "must end with|not a file"),
        ("usd", "job-1/../../outside.usda", "not inside the download folder"),
        ("usd", "job-1/./rollouts/../../../outside.usda", "not inside the download folder"),
    ],
)
def test_validate_load_rejects(root, kind, rel, match):
    with pytest.raises(pr.ProtocolError, match=match):
        pr.validate_load(_load(kind, os.path.join(str(root), rel)), pr.CAPABILITIES, str(root))


def test_validate_load_rejects_bad_requests(root):
    usd = str(root / "job-1" / "scene.USDA")
    with pytest.raises(pr.ProtocolError, match="not an absolute path"):
        pr.validate_load(_load("usd", "job-1/scene.USDA"), pr.CAPABILITIES, str(root))
    for path in ("", None, 3, usd + "\x00.usd"):
        with pytest.raises(pr.ProtocolError, match="no path"):
            pr.validate_load(
                pr.message("load", id="r", kind="usd", path=path), pr.CAPABILITIES, str(root)
            )
    with pytest.raises(pr.ProtocolError, match="does not offer add_usd"):
        pr.validate_load(_load("usd", usd), (pr.CAP_REPLAY,), str(root))
    for bad_root in ("", "relative/root", None):
        with pytest.raises(pr.ProtocolError, match="hello_ack"):
            pr.validate_load(_load("usd", usd), pr.CAPABILITIES, bad_root)  # type: ignore[arg-type]
    # The root itself must be the folder, not a sibling that shares its prefix.
    sibling = Path(str(root) + "-evil")
    sibling.mkdir()
    (sibling / "x.usd").write_text("#usda 1.0")
    with pytest.raises(pr.ProtocolError, match="not inside"):
        pr.validate_load(_load("usd", sibling / "x.usd"), pr.CAPABILITIES, str(root))


@pytest.mark.skipif(sys.platform == "win32", reason="symlinks need privileges on Windows")
def test_validate_load_follows_symlinks(root, tmp_path):
    # A link inside the root to a file outside it is refused.
    (root / "job-1" / "escape.usda").symlink_to(tmp_path / "outside.usda")
    with pytest.raises(pr.ProtocolError, match="not inside"):
        pr.validate_load(_load("usd", root / "job-1" / "escape.usda"), pr.CAPABILITIES, str(root))
    # A folder link out of the root is refused too.
    (root / "job-1" / "out").symlink_to(tmp_path)
    with pytest.raises(pr.ProtocolError, match="not inside"):
        pr.validate_load(
            _load("usd", root / "job-1" / "out" / "outside.usda"), pr.CAPABILITIES, str(root)
        )
    # A link whose name fits but whose target does not is refused.
    (root / "job-1" / "notes.usd").symlink_to(root / "job-1" / "notes.txt")
    with pytest.raises(pr.ProtocolError, match="must end with"):
        pr.validate_load(_load("usd", root / "job-1" / "notes.usd"), pr.CAPABILITIES, str(root))
    # A root reached through a link is fine: both sides are resolved.
    (tmp_path / "root-link").symlink_to(root)
    usd = tmp_path / "root-link" / "job-1" / "scene.USDA"
    assert pr.validate_load(_load("usd", usd), pr.CAPABILITIES, str(tmp_path / "root-link"))[1] == (
        os.path.realpath(usd)
    )


def test_inside_with_windows_paths(monkeypatch):
    """Windows compares paths case-insensitively, and a path on another drive is outside."""
    monkeypatch.setattr(pr.os, "path", ntpath)
    root = r"C:\Users\u\.deadline\physical-ai\job_outputs"
    assert pr._inside(r"c:\users\U\.DEADLINE\physical-ai\job_outputs\job-1\a.usd", root)
    assert pr._inside(root, root)
    assert not pr._inside(r"C:\Users\u\.deadline\physical-ai\job_outputs-x\a.usd", root)
    assert not pr._inside(r"D:\Users\u\.deadline\physical-ai\job_outputs\a.usd", root)
    assert not pr._inside(r"\\server\share\a.usd", root)
    assert not pr._inside(ntpath.normpath(root + r"\..\other\a.usd"), root)


def test_validate_replay_control():
    assert pr.validate_replay_control(pr.replay_control("r", "stop")) == "stop"
    for bad in ("pause", None, ["play"]):
        with pytest.raises(pr.ProtocolError, match="unknown replay action"):
            pr.validate_replay_control(pr.message("replay_control", id="r", action=bad))
