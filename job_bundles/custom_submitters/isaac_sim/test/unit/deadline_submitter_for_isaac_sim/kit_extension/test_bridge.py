# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
"""The extension's end of the bridge: :class:`Host` on its own, then real app children
over real pipes (a tiny fake app, and the real app offscreen when PySide6 imports)."""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

import pytest
from isaacsim.deadline.submitter import procenv
from isaacsim.deadline.submitter import protocol as pr
from isaacsim.deadline.submitter.bridge import AppProcess, Host


def _host(**kw):
    calls: list = []

    def load(kind: str, path: str) -> str:
        calls.append((kind, path))
        return f"loaded {os.path.basename(path)}"

    def replay_control(action: str) -> str:
        calls.append(action)
        return action

    saved = {"robot": "/World/Robot", "object": "", "reference": ""}

    def replay_prims() -> dict:
        return {"prims": dict(saved), "exists": {r: r == "robot" for r in saved}}

    def set_replay_prims(prims: dict) -> dict:
        calls.append(("set", prims))
        saved.update(prims)
        return replay_prims()

    defaults = {
        "stage_path": lambda: "/s/scene.usd",
        "load": load,
        "replay_control": replay_control,
        "log": lambda m: None,
        "replay_prims": replay_prims,
        "set_replay_prims": set_replay_prims,
        "selection": lambda limit: ["/World/Cube", "/World/Table"][:limit],
    }
    defaults.update(kw)
    host = Host("6.2.0", "0.3.0", **defaults)  # type: ignore[arg-type]
    host.calls = calls  # type: ignore[attr-defined]
    return host


def test_host_hello_and_ack(tmp_path):
    host = _host()
    assert host.hello() == pr.hello("6.2.0", "0.3.0", pr.CAPABILITIES)
    assert host.handle(pr.hello_ack("1.0", str(tmp_path))) is None
    assert host.download_root == str(tmp_path) and host.app_version == "1.0"
    host.handle(pr.hello_ack("1.0", ""))  # an empty root does not clear the known one
    assert host.download_root == str(tmp_path)


def test_host_answers_and_refuses(tmp_path):
    traj = tmp_path / "job-1" / "ep.trajectory.npz"
    traj.parent.mkdir()
    traj.write_bytes(b"npz")
    host = _host()
    # Before hello_ack there is no download folder, so no load is allowed.
    r = host.handle(pr.load("r0", "trajectory", str(traj)))
    assert r is not None and not r["ok"] and "hello_ack" in r["message"]
    host.handle(pr.hello_ack("1.0", str(tmp_path)))
    r = host.handle(pr.load("r1", "trajectory", str(traj)))
    assert r == pr.result(
        "r1", True, "loaded ep.trajectory.npz", kind="trajectory", path=os.path.realpath(traj)
    )
    numeric = pr.get_stage(7)  # type: ignore[arg-type]
    assert host.handle(numeric) == pr.result(7, True, "", path="/s/scene.usd")
    assert host.handle(pr.replay_control("r2", "stop"))["message"] == "stop"
    assert host.calls == [("trajectory", os.path.realpath(traj)), "stop"]
    for bad in (
        pr.load("r3", "trajectory", str(tmp_path.parent / "elsewhere.trajectory.npz")),
        pr.load("r4", "usd", str(traj)),
        pr.replay_control("r5", "rewind"),
    ):
        reply = host.handle(bad)
        assert reply is not None and reply["id"] == bad["id"] and not reply["ok"]
    assert len(host.calls) == 2  # nothing refused reached the stage
    # No id: nothing to answer. Unknown types and results are ignored.
    assert host.handle(pr.message(pr.GET_STAGE)) is None
    assert host.handle(pr.message(pr.GET_STAGE, id=True)) is None
    assert host.handle(pr.message("future", id="x")) is None
    assert host.handle(pr.result("x", True)) is None


def test_host_capabilities_and_errors():
    def broken(_action):
        raise RuntimeError("timeline gone")

    host = _host(replay_control=broken, capabilities=(pr.CAP_ADD_USD,))
    r = host.handle(pr.get_stage("r1"))
    assert not r["ok"] and "stage_path" in r["message"]
    r = host.handle(pr.replay_control("r2", "play"))
    assert not r["ok"] and "replay" in r["message"]
    host = _host(replay_control=broken)
    r = host.handle(pr.replay_control("r3", "play"))
    assert not r["ok"] and r["message"] == "timeline gone"


# --------------------------------------------------------------- real children --

FAKE_APP = r"""
import sys, time
from deadline.isaac_sim_submitter.app import protocol as pr
from deadline.isaac_sim_submitter.app.bridge import KitLink

root, usd, outside = sys.argv[1:4]
link = KitLink(sys.stdin.buffer, sys.stdout.buffer, "9.9", lambda: root,
               log=lambda m: sys.stderr.write(m + "\n"))
state = {}
link.on_focus = lambda: link.send(pr.message("test_focused"))
link.on_eof = lambda: state.update(eof=True)
link.start()
sys.stdout.buffer.write(b"not a message\n")  # Kit logs and skips it
sys.stdout.buffer.flush()
asked = False


def report(stage, first):
    link.request(pr.LOAD, lambda second: link.send(
        pr.message("test_done", stage=stage, first=first, second=second)),
        kind="usd", path=outside)


while not state.get("eof"):
    link.poll()
    if link.connected and not asked:
        asked = True
        link.fetch_stage(lambda stage: link.request(
            pr.LOAD, lambda first: report(stage, first), kind="usd", path=usd))
    time.sleep(0.01)
"""


def _exchange(app: AppProcess, host: Host, until, timeout=30.0) -> list:
    """Run Kit's side of the loop until ``until(extra)`` holds; ``extra`` collects messages
    the host does not answer."""
    extra: list = []
    t0 = time.monotonic()
    while not until(extra):
        assert time.monotonic() - t0 < timeout, f"timed out; app stderr:\n{app.stderr_tail()}"
        assert app.alive or app.poll(), f"app exited; stderr:\n{app.stderr_tail()}"
        for msg in app.poll():
            reply = host.handle(msg)
            if reply is not None:
                app.send(reply)
            elif msg["type"] != pr.HELLO_ACK:
                extra.append(msg)
        time.sleep(0.01)
    return extra


def test_fake_app_over_real_pipes(tmp_path):
    root = tmp_path / "downloads"
    (root / "job-1").mkdir(parents=True)
    usd = root / "job-1" / "a.usda"
    usd.write_text("#usda 1.0")
    outside = tmp_path / "b.usda"
    outside.write_text("#usda 1.0")
    script = tmp_path / "fake_app.py"
    script.write_text(FAKE_APP)
    logged: list = []
    app = AppProcess(
        [sys.executable, str(script), str(root), str(usd), str(outside)],
        env=procenv.child_env(sys.executable),
        log=logged.append,
    )
    host = _host()
    try:
        assert app.send(host.hello())
        extra = _exchange(app, host, lambda e: any(m["type"] == "test_done" for m in e))
        done = next(m for m in extra if m["type"] == "test_done")
        assert done["stage"] == "/s/scene.usd" and host.download_root == str(root)
        assert done["first"]["ok"] and done["first"]["path"] == os.path.realpath(usd)
        assert not done["second"]["ok"] and "not inside" in done["second"]["message"]
        assert any("not UTF-8 JSON" in m for m in logged)
        assert app.send(pr.focus())
        _exchange(app, host, lambda e: any(m["type"] == "test_focused" for m in e))
    finally:
        app.close(timeout_s=10.0)
    assert app.returncode == 0, app.stderr_tail()  # exited on EOF, not killed


def test_close_kills_an_app_that_ignores_eof(tmp_path):
    app = AppProcess([sys.executable, "-c", "import time; time.sleep(60)"])
    t0 = time.monotonic()
    app.close(timeout_s=0.5)
    assert not app.alive and time.monotonic() - t0 < 10
    assert not app.send(pr.focus())  # stdin is closed


def _qt_importable() -> bool:
    try:
        import PySide6.QtWidgets  # noqa: F401
    except ImportError:
        return False
    return True


@pytest.mark.skipif(not _qt_importable(), reason="PySide6 is not importable")
def test_real_app_offscreen(tmp_path):
    """``deadline-physical-ai gui --bridge``: hello, hello_ack, get_stage, focus, exit on EOF."""
    env = procenv.child_env(sys.executable)
    env["QT_QPA_PLATFORM"] = "offscreen"
    settings = tmp_path / "settings.json"
    # A deadline path that does not exist: the app reports it instead of calling AWS.
    settings.write_text(json.dumps({"deadlineExecutable": str(tmp_path / "no-deadline")}))
    env["DEADLINE_CLOUD_FOR_ISAAC_SIM_SETTINGS"] = str(settings)
    env["DEADLINE_PHYSICAL_AI_HOME"] = str(tmp_path / "pai")
    app = AppProcess([sys.executable, "-m", "deadline.physical_ai.cli", "gui", "--bridge"], env=env)
    asked: list = []

    def stage_path() -> str:
        asked.append(1)
        return "/s/scene.usd"

    host = _host(stage_path=stage_path)
    try:
        app.send(host.hello())
        # The app acks with its download folder and asks for the stage once connected.
        _exchange(app, host, lambda e: bool(host.download_root and asked), timeout=60.0)
        assert Path(host.download_root) == (tmp_path / "pai" / "job_outputs").absolute()
        assert host.app_version  # the package version
        assert app.send(pr.focus()) and app.send(pr.message("from_the_future"))
        time.sleep(0.5)
        assert app.alive, app.stderr_tail()
    finally:
        app.close(timeout_s=20.0)
    assert app.returncode == 0, app.stderr_tail()  # exited on EOF, not killed


def test_host_replay_prims_and_selection():
    host = _host()
    r = host.handle(pr.get_replay_prims("r1"))
    assert r is not None and r["ok"] and r["prims"]["robot"] == "/World/Robot"
    assert r["exists"] == {"robot": True, "object": False, "reference": False}
    r = host.handle(pr.set_replay_prims("r2", {"object": "/World/Cube"}))
    assert r is not None and r["ok"] and r["prims"]["object"] == "/World/Cube"
    assert ("set", {"object": "/World/Cube"}) in host.calls  # type: ignore[attr-defined]
    r = host.handle(pr.get_selection("r3"))
    assert r is not None and r["paths"] == ["/World/Cube", "/World/Table"]


def test_host_refuses_bad_replay_prims():
    host = _host()
    for prims in ({"camera": "/World/C"}, {"robot": "World/Robot"}, {"robot": "/a//b"}, {}):
        r = host.handle(pr.set_replay_prims("r1", prims))
        assert r is not None and not r["ok"]
    assert not any(c[0] == "set" for c in host.calls if isinstance(c, tuple))  # type: ignore[attr-defined]


def test_host_without_replay_prim_callbacks_does_not_offer_them():
    host = _host(replay_prims=None)
    assert pr.CAP_REPLAY_PRIMS not in host.hello()["capabilities"]
    r = host.handle(pr.get_replay_prims("r1"))
    assert r is not None and not r["ok"] and "replay_prims" in r["message"]
