# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
"""The thin Kit-side glue, with Kit stubbed (see conftest.py)."""

import sys
from typing import ClassVar
from unittest import mock

import numpy as np
import pytest
from isaacsim.deadline.submitter import extension as ex
from isaacsim.deadline.submitter import protocol as pr
from isaacsim.deadline.submitter import stage as sg

from deadline.isaac_sim_submitter import extension_path


class FakeApp:
    """Stands in for :class:`bridge.AppProcess`."""

    made: ClassVar[list] = []

    def __init__(self, argv, env=None, log=print):
        self.argv, self.env, self.sent, self.inbox = argv, env, [], []
        self.alive, self.returncode, self.closed = True, None, False
        FakeApp.made.append(self)

    def poll(self):
        out, self.inbox = self.inbox, []
        return out

    def send(self, msg):
        self.sent.append(msg)
        return True

    def allow_foreground(self):
        pass

    def stderr_tail(self):
        return "Traceback ...\nImportError: no PySide6"

    def close(self, timeout_s=2.0):
        self.closed = True


@pytest.fixture
def ext(monkeypatch, tmp_path):
    FakeApp.made = []
    monkeypatch.setattr(ex, "AppProcess", FakeApp)
    monkeypatch.setattr(
        ex.procenv, "resolve", lambda tool, override="": ("/venv/bin/" + tool, "PATH")
    )
    monkeypatch.setattr(ex, "stage_file_path", lambda: "/s/scene.usd")
    e = ex.Extension()
    e.on_startup("isaacsim.deadline.submitter-1.0.0")
    yield e
    e.on_shutdown()


def test_menu_has_one_item(ext):
    assert ex.OPEN_TITLE == "Open Deadline Cloud"
    (submenu,) = ext._menu_items
    assert ex.make_menu_item_description.call_args[0][1:] == ("Open Deadline Cloud", ext.open_app)
    assert submenu is not None


def test_open_launches_once_then_focuses(ext):
    ext.open_app()
    (app,) = FakeApp.made
    assert app.argv == ["/venv/bin/deadline-physical-ai", "gui", "--bridge"]
    assert "PYTHONHOME" not in app.env and app.sent[0]["type"] == pr.HELLO
    assert set(app.sent[0]["capabilities"]) == set(pr.CAPABILITIES)
    ext.open_app()
    assert len(FakeApp.made) == 1 and app.sent[-1] == pr.focus()


def test_requests_are_answered_on_update(ext, tmp_path):
    usd = tmp_path / "job-1" / "a.usda"
    usd.parent.mkdir()
    usd.write_text("#usda 1.0")
    ext.open_app()
    (app,) = FakeApp.made
    added: list = []

    def load(kind, path):
        added.append((kind, path))
        return "added"

    ext._host.load = load
    app.inbox = [
        pr.hello_ack("1.0.0", str(tmp_path)),
        pr.get_stage("r1"),
        pr.load("r2", "usd", str(usd)),
        pr.load("r3", "usd", "/etc/passwd"),
        pr.replay_control("r4", "play"),
        pr.message("from_the_future", id="r5"),
    ]
    ext._on_update(None)
    replies = {m["id"]: m for m in app.sent if m["type"] == pr.RESULT}
    assert replies["r1"]["path"] == "/s/scene.usd" and replies["r1"]["ok"]
    assert replies["r2"]["ok"] and added and added[0][0] == "usd"
    assert not replies["r3"]["ok"]
    assert not replies["r4"]["ok"] and "Load a trajectory first" in replies["r4"]["message"]
    assert "r5" not in replies


def test_crashed_app_is_reported_and_relaunched(ext):
    ext.open_app()
    first = FakeApp.made[0]
    first.alive, first.returncode = False, 1
    ex.carb.log_error.reset_mock()
    ext._on_update(None)
    assert ext._app is None
    assert "exited with code 1: ImportError: no PySide6" in ex.carb.log_error.call_args[0][0]
    ext.open_app()
    assert len(FakeApp.made) == 2


def test_missing_cli_is_reported(ext, monkeypatch):
    monkeypatch.setattr(ex.procenv, "resolve", lambda tool, override="": ("", "not found"))
    ex.carb.log_error.reset_mock()
    ext.open_app()
    assert (
        not FakeApp.made and "deadline-physical-ai not found" in ex.carb.log_error.call_args[0][0]
    )


def test_shutdown_closes_the_app(monkeypatch):
    FakeApp.made = []
    monkeypatch.setattr(ex, "AppProcess", FakeApp)
    monkeypatch.setattr(ex.procenv, "resolve", lambda tool, override="": ("/x/" + tool, "PATH"))
    e = ex.Extension()
    e.on_startup("isaacsim.deadline.submitter-1.0.0")
    e.open_app()
    e.on_shutdown()
    assert FakeApp.made[0].closed and e._app is None


def test_load_trajectory_plays_and_usd_is_referenced(ext, monkeypatch):
    played: list = []
    monkeypatch.setattr(ext.replay, "load", lambda path: "ep: 4 frames")
    monkeypatch.setattr(ext.replay, "play", lambda: played.append(1))
    assert ext._load("trajectory", "/d/ep.trajectory.npz").startswith("ep: 4 frames. Playing")
    assert played
    monkeypatch.setattr(ex, "add_reference", lambda path: "/World/DeadlineCloud/a")
    assert ext._load("usd", "/d/a.usda") == "Added a.usda to the stage at /World/DeadlineCloud/a."
    ext.replay.traj = object()
    stopped: list = []
    monkeypatch.setattr(ext.replay, "stop", lambda: stopped.append(1))
    assert ext._replay_control("stop") == "Stopped." and stopped
    assert ext._replay_control("play") == "Playing."


def test_replay_error_stops_only_replay(ext, monkeypatch):
    ext.replay.traj = object()
    monkeypatch.setattr(ext.replay, "on_update", mock.MagicMock(side_effect=RuntimeError("gone")))
    ext._on_update(None)
    assert ext.replay.traj is None


def test_update_uses_the_event_dispatcher_when_kit_has_it(monkeypatch):
    dispatcher = mock.MagicMock()
    mod = mock.MagicMock()
    mod.get_eventdispatcher.return_value = dispatcher
    monkeypatch.setitem(sys.modules, "carb.eventdispatcher", mod)
    monkeypatch.setattr(
        ex.omni.kit.app, "GLOBAL_EVENT_UPDATE", "omni.kit.app:update", raising=False
    )

    def fn(_event):
        return None

    assert ex.subscribe_update(fn, "n") is dispatcher.observe_event.return_value
    assert dispatcher.observe_event.call_args.kwargs == {
        "event_name": "omni.kit.app:update",
        "on_event": fn,
        "observer_name": "n",
    }
    # Older Kit: no GLOBAL_EVENT_UPDATE, so the update event stream.
    monkeypatch.setattr(ex.omni.kit.app, "GLOBAL_EVENT_UPDATE", None)
    stream = ex.omni.kit.app.get_app.return_value.get_update_event_stream.return_value
    assert ex.subscribe_update(fn, "n") is stream.create_subscription_to_pop.return_value


def test_version_falls_back_to_the_installed_distribution(monkeypatch):
    import importlib.metadata

    monkeypatch.setattr(
        importlib.metadata, "version", lambda name: "1.2.3" if name == ex.DISTRIBUTION else ""
    )
    assert ex.resolve_version("0.4.0") == "0.4.0"
    assert ex.resolve_version("0.0.0") == "1.2.3" and ex.resolve_version("") == "1.2.3"

    def missing(name):
        raise importlib.metadata.PackageNotFoundError(name)

    monkeypatch.setattr(importlib.metadata, "version", missing)
    assert ex.resolve_version("0.0.0") == "0.0.0"


def test_replay_frame_counts_from_timeline_start(monkeypatch):
    tl = mock.MagicMock()
    tl.is_playing.return_value = True
    tl.get_current_time.return_value = 12.5
    tl.get_start_time.return_value = 10.0
    mod = mock.MagicMock()
    mod.get_timeline_interface.return_value = tl
    monkeypatch.setitem(sys.modules, "omni.timeline", mod)
    monkeypatch.setattr(sys.modules["omni"], "timeline", mod, raising=False)
    frames = []
    monkeypatch.setattr(sg.rp, "apply_frame", lambda binding, traj, k: frames.append(k))
    r = sg.ReplaySession()
    r.traj = mock.MagicMock()
    r.traj.frame_at.side_effect = lambda t: t
    r.on_update()
    assert frames == [2.5]


def test_load_message_reports_joints_without_a_drive(monkeypatch):
    """Joints the user has to fix are named in the reply, not silently counted as bound."""
    traj = sg.rp.Trajectory("/d/ep.trajectory.npz", ["a"], np.zeros((4, 1)), 20.0, label="ep")
    binding = sg.rp.Binding(attrs=[(0, None, 1.0)], undriven=["elbow", "lift"], no_state=["elbow2"])
    monkeypatch.setattr(sg.rp, "load", lambda path: traj)
    monkeypatch.setattr(sg.rp, "bind", lambda stage, root, t: binding)
    monkeypatch.setattr(sg.rp, "set_start_pose", lambda *a: None)
    monkeypatch.setattr(sg.rp, "place_start", lambda *a: "")
    msg = sg.ReplaySession().load("/d/ep.trajectory.npz")
    assert "1 joints bound" in msg and "2 joints have no position drive; replay skips them" in msg
    assert "1 joints have no joint state" in msg
    binding.attrs = []
    with pytest.raises(ValueError, match="2 joints have no position drive"):
        sg.ReplaySession().load("/d/ep.trajectory.npz")


def test_extension_has_no_windows():
    """The UI is the app; the extension adds no omni.ui window and never imports AWS code."""
    pkg = extension_path() / "isaacsim" / "deadline" / "submitter"
    assert not (pkg / "windows.py").exists() and not (pkg / "controllers.py").exists()
    for f in pkg.glob("*.py"):
        text = f.read_text(encoding="utf-8")
        for banned in ("omni.ui", "from omni import ui", "import boto3", "import deadline"):
            assert banned not in text, (f.name, banned)
