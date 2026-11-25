# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
"""The Qt views, offscreen, driven through their widgets with a fake runner.

Skipped when PySide6 (or a library its QtWidgets needs) is not importable.
"""

from __future__ import annotations

import json
from typing import Any

import pytest

QtWidgets = pytest.importorskip("PySide6.QtWidgets", reason="PySide6 is not importable")
from PySide6 import QtCore

from deadline.isaac_sim_submitter.app import controllers as ct
from deadline.isaac_sim_submitter.app import protocol as pr
from deadline.isaac_sim_submitter.app import qt_app

from .test_controllers import FakeRunner, _listing


class QtRunner(FakeRunner):
    """Answers at once, so there is nothing to poll or cancel."""

    def poll(self):
        pass

    def cancel_all(self):
        pass


@pytest.fixture(scope="module")
def qapp():
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication(["test"])
    yield app


class FakeLink:
    """Stands in for :class:`bridge.KitLink`; ``requests`` holds (type, fields, callback)."""

    def __init__(self, capabilities=pr.CAPABILITIES):
        self.connected, self.closed = True, False
        self.kit_version, self.extension_version = "6.2.0", "0.3.0"
        self.capabilities = list(capabilities)
        self.requests: list = []
        self.on_change: Any = lambda: None
        self.on_focus: Any = lambda: None
        self.on_eof: Any = lambda: None

    def has(self, cap):
        return self.connected and cap in self.capabilities

    def poll(self):
        pass

    def request(self, msg_type, callback, timeout_s=None, **fields):
        self.requests.append((msg_type, fields, callback))

    def fetch_stage(self, callback):
        self.request(pr.GET_STAGE, lambda r: callback(r.get("path", "")))


def _runner(tmp_path, items, kind="trajectory"):
    local = {p: tmp_path / p.replace("/", "_") for p in items}
    for f in local.values():
        if kind in ct.INPUT_KINDS:
            f.mkdir()
        else:
            f.write_bytes(b"x")
    return (
        QtRunner(
            {
                "config get defaults.farm_id": ("farm-1\n", 0),
                "config get defaults.queue_id": ("queue-1\n", 0),
                "farm list": ("- farmId: farm-1\n  displayName: Farm\n  region: r\n", 0),
                "queue list --farm-id": ("- queueId: queue-1\n  displayName: Queue\n", 0),
                "jobs list --farm-id": (
                    json.dumps(
                        {
                            "jobs": [
                                {
                                    "name": "job one",
                                    "jobId": "job-1",
                                    "endedAt": "2026-11-11 19:38:05+00:00",
                                }
                            ],
                            "total": 1,
                            "next_offset": None,
                        }
                    ),
                    0,
                ),
                "outputs list job-1": (_listing("job-1", items, kind), 0),
                "outputs fetch job-1": (
                    json.dumps(
                        {"dest": str(tmp_path), "items": {p: str(f) for p, f in local.items()}}
                    ),
                    0,
                ),
            }
        ),
        local,
    )


def _window(qapp, monkeypatch, runner, link=None):
    monkeypatch.setattr(ct, "_tools", lambda: ("deadline", "PATH", "pai", "PATH"))
    win = qt_app.MainWindow(link, runner=runner)
    win.timer.stop()  # the tests tick by hand
    qapp.processEvents()  # the first refresh
    win.tick()
    return win


def _pick_job_and_tick(win, path):
    pane = win.outputs
    pane.jobs.selectRow(0)
    win.tick()
    for r in range(pane.outputs.rowCount()):
        cell = pane.outputs.item(r, 0)
        if cell.data(qt_app.ROLE) == path:
            cell.setCheckState(QtCore.Qt.CheckState.Checked)
            pane.outputs.setCurrentCell(r, 0)
    win.tick()


def test_standalone_lists_and_loads(qapp, monkeypatch, tmp_path):
    runner, _ = _runner(tmp_path, ["eval/ep.trajectory.npz"])
    win = _window(qapp, monkeypatch, runner)
    pane = win.outputs
    assert pane.farm.currentText() == "Farm  (default)" and pane.queue.isEnabled()
    assert not pane.set_default.isEnabled()  # already the default pair
    assert pane.jobs.rowCount() == 1 and pane.jobs.item(0, 0).text() == "job one"
    assert "Standalone" in win.connection.text()
    _pick_job_and_tick(win, "eval/ep.trajectory.npz")
    assert pane.ctl.s.checked == {"eval/ep.trajectory.npz"}
    assert pane.load.isEnabled() and pane.load.text() == "Download selected (1)"
    assert pane.kind.count() == 2 and pane.kind.itemText(1) == "Trajectories (1)"
    for b in (pane.isaac_load, pane.play, pane.stop, pane.replay_info):
        assert b.isHidden()  # Isaac Sim actions only when connected
    header = pane.outputs.horizontalHeader()
    assert header.font().bold() and pane.jobs.horizontalHeader().font().bold()
    assert header.defaultAlignment() & QtCore.Qt.AlignmentFlag.AlignLeft
    assert pane.outputs.columnWidth(0) == qt_app.NAME_COLUMN_WIDTH
    pane.load.click()
    win.tick()
    assert "Downloaded" in pane.notes_view.toPlainText()
    assert pane.outputs.item(0, 2).text() == "downloaded"
    opened: list = []
    monkeypatch.setattr(qt_app.cb, "open_with_os", opened.append)
    pane.outputs.cellDoubleClicked.emit(0, 0)  # double-click opens the downloaded file
    assert opened and opened[0].endswith("ep.trajectory.npz")
    win.close()


def test_connected_sends_loads_and_replay_controls(qapp, monkeypatch, tmp_path):
    runner, local = _runner(tmp_path, ["eval/ep.trajectory.npz"])
    link = FakeLink()
    win = _window(qapp, monkeypatch, runner, link)
    pane = win.outputs
    assert "Connected to Isaac Sim 6.2.0" in win.connection.text()
    _pick_job_and_tick(win, "eval/ep.trajectory.npz")
    assert not pane.isaac_load.isHidden() and pane.isaac_load.isEnabled()
    assert not pane.play.isEnabled()
    pane.load.click()  # Download selected only downloads, even when connected
    assert not [r for r in link.requests if r[0] == pr.LOAD]
    pane.ctl.toggle("eval/ep.trajectory.npz", True)
    win.tick()
    pane.isaac_load.click()  # already downloaded, so it goes straight to Isaac Sim
    loads = [r for r in link.requests if r[0] == pr.LOAD]
    assert loads[-1][1] == {"kind": "trajectory", "path": str(local["eval/ep.trajectory.npz"])}
    loads[-1][2](pr.result("r1", True, "ep: 4 frames"))
    win.tick()
    assert "ep: 4 frames" in pane.notes_view.toPlainText() and pane.play.isEnabled()
    assert pane.replay_info.text() == "Loaded: eval/ep.trajectory.npz (job one)"
    pane.stop.click()
    assert link.requests[-1][:2] == (pr.REPLAY_CONTROL, {"action": "stop"})
    link.requests[-1][2](pr.result("r9", False, "Load a trajectory first."))
    win.tick()
    assert "Load a trajectory first." in pane.notes_view.toPlainText()
    win.close()


def test_failed_load_is_shown(qapp, monkeypatch, tmp_path):
    runner, _ = _runner(tmp_path, ["scene/a.usda"], kind="usd")
    link = FakeLink()
    win = _window(qapp, monkeypatch, runner, link)
    _pick_job_and_tick(win, "scene/a.usda")
    win.outputs.isaac_load.click()
    load = [r for r in link.requests if r[0] == pr.LOAD][-1]
    assert load[1]["kind"] == "usd"
    load[2](pr.result("r1", False, "not inside the download folder"))
    win.tick()
    text = win.outputs.notes_view.toPlainText()
    assert "could not load" in text and "not inside the download folder" in text
    win.close()


def test_submit_with_dataset_switches_to_submit(qapp, monkeypatch, tmp_path):
    runner, _ = _runner(tmp_path, ["gen/dataset"], kind="lerobot")
    win = _window(qapp, monkeypatch, runner)
    _pick_job_and_tick(win, "gen/dataset")
    assert win.outputs.load.text() == "Submit pipeline job with dataset"
    win.outputs.load.click()
    win.tick()
    assert win._current_pane() is win.submit
    assert "No job bundle here takes a dataset" in win.submit.error.text()
    win.close()


def test_submit_pane_lists_bundles_and_notes_unsaved_stage(qapp, monkeypatch, tmp_path):
    import yaml

    from deadline.isaac_sim_submitter.app import settings as st

    d = tmp_path / "bundles" / "scene"
    d.mkdir(parents=True)
    (d / "template.yaml").write_text(
        yaml.safe_dump(
            {
                "specificationVersion": "jobtemplate-2023-09",
                "name": "Scene job",
                "description": "Renders a scene.",
                "parameterDefinitions": [
                    {"name": "StageFile", "type": "PATH", "objectType": "FILE"},
                    {"name": "train_Datasets", "type": "PATH", "objectType": "DIRECTORY"},
                ],
            }
        )
    )
    st.set_str(st.BUNDLE_DIRS, str(tmp_path / "bundles"))
    link = FakeLink()
    runner, _ = _runner(tmp_path, [])
    win = _window(qapp, monkeypatch, runner, link)
    stage_asks = [r for r in link.requests if r[0] == pr.GET_STAGE]
    assert len(stage_asks) == 1  # asked on connect
    win.tabs.setCurrentWidget(win.submit.page)
    win.tick()
    sub = win.submit
    assert sub.bundles.count() == 1 and sub.bundles.item(0).text() == "Scene job"
    assert sub.folders.text() == str(tmp_path / "bundles")
    link.requests[-1][2](pr.result("r2", True, "", path=""))
    win.tick()
    assert (
        "unsaved" in sub.details.toPlainText() and "Renders a scene." in sub.details.toPlainText()
    )
    assert "train_Datasets is empty" in sub.missing.text() and sub.open.isEnabled()
    link.requests[-1][2](pr.result("r3", True, "", path="/s/scene.usd"))
    win.tick()
    assert "Prefilled StageFile = /s/scene.usd" in sub.details.toPlainText()
    win.close()


def test_focus_and_kit_gone(qapp, monkeypatch, tmp_path):
    runner, _ = _runner(tmp_path, [])
    link = FakeLink()
    win = _window(qapp, monkeypatch, runner, link)
    win.show()
    link.on_focus()
    assert win.isVisible()
    monkeypatch.setattr(QtWidgets.QApplication, "quit", lambda *a: None)
    link.on_eof()
    assert not win.isVisible()


def test_views_keep_their_height_and_show_messages_inside(qapp):
    from deadline.isaac_sim_submitter.app import views

    t = qt_app._table(["A", "B"])
    views.fix_rows(t)
    h = t.height()
    views.show_message(t, "Reading parameters...")
    cell = t.item(0, 0)
    assert views.is_message(t) and cell is not None and cell.text() == "Reading parameters..."
    assert t.columnSpan(0, 0) == 2 and t.height() == h
    views.clear_message(t)
    assert t.rowCount() == 0 and not views.is_message(t)
    lst = QtWidgets.QListWidget()
    views.show_message(lst, "No job bundles")
    assert views.is_message(lst)
    views.clear_message(lst)
    assert lst.count() == 0


def test_farm_and_queue_sit_above_the_tabs(qapp, monkeypatch, tmp_path):
    runner, _local = _runner(tmp_path, ["ev/a.npz"])
    win = _window(qapp, monkeypatch, runner)
    lay = win.centralWidget().layout()
    assert lay.itemAt(0).widget() is win.outputs.target_bar
    assert lay.itemAt(1).widget() is win.tabs
    assert win.outputs.jobs.minimumHeight() == win.outputs.jobs.maximumHeight()
    info = win._submit_target()
    assert set(info) == {"target", "default", "farm", "queue"}
    win.close()


def test_window_opens_to_its_content_within_the_screen(qapp, monkeypatch, tmp_path):
    runner, _local = _runner(tmp_path, ["ev/a.npz"])
    win = _window(qapp, monkeypatch, runner)
    pages = [win.tabs.widget(i) for i in range(win.tabs.count())]
    # Each tab asks for its whole page, not QScrollArea's 24-line cap.
    for area in pages:
        assert area.sizeHint().height() >= area.widget().sizeHint().height()
    avail = win.screen().availableGeometry().height() - qt_app.FRAME_ALLOWANCE
    tallest = max(a.widget().sizeHint().height() for a in pages)
    assert win.height() == min(win.sizeHint().height(), avail)
    assert win.height() > tallest or win.height() == avail
    assert win.width() >= qt_app.MIN_WIDTH
    # Growing (e.g. on connecting) never shrinks a window the user enlarged.
    win.resize(win.width() + 50, win.height())
    wide = win.width()
    win.fit_to_content(grow_only=True)
    assert win.width() == wide
    win.close()


def test_replay_setup_shows_only_when_isaac_offers_it(qapp, monkeypatch, tmp_path):
    runner, _local = _runner(tmp_path, ["ev/a.npz"])
    link = FakeLink()
    win = _window(qapp, monkeypatch, runner, link)
    pane = win.outputs
    pane.redraw()
    assert not pane.prims_box.isHidden()
    assert any(t == pr.GET_REPLAY_PRIMS for t, _f, _cb in link.requests)  # read on showing
    _t, _f, cb = next(r for r in link.requests if r[0] == pr.GET_REPLAY_PRIMS)
    cb(
        {
            "ok": True,
            "prims": {"robot": "/World/R", "object": "", "reference": ""},
            "exists": {"robot": False, "object": False, "reference": False},
        }
    )
    pane.redraw()
    assert pane.prim_edits["robot"].text() == "/World/R"
    assert pane.prim_notes["robot"].text() == "Not in the open stage"
    old = FakeLink(capabilities=[c for c in pr.CAPABILITIES if c != pr.CAP_REPLAY_PRIMS])
    win2 = _window(qapp, monkeypatch, runner, old)
    win2.outputs.redraw()
    assert win2.outputs.prims_box.isHidden()
    win.close()
    win2.close()


_CLOSE_WINDOW = """
import sys
from PySide6 import QtCore
from deadline.isaac_sim_submitter.app import qt_app
init = qt_app.MainWindow.__init__
def closing(self, *a, **k):
    init(self, *a, **k)
    QtCore.QTimer.singleShot(500, self.close)  # the user closes the window
qt_app.MainWindow.__init__ = closing
sys.exit(qt_app.main(bridge=True))
"""


def test_closing_the_bridged_window_exits_cleanly(tmp_path):
    """Isaac Sim keeps the app's stdin open while the user closes the window. Interpreter
    shutdown then aborted ("could not acquire lock for <_io.BufferedReader name='<stdin>'>"),
    which Isaac Sim reported as exit code 3221226505 with "<no Python frame>"."""
    import os
    import subprocess
    import sys

    env = dict(
        os.environ,
        QT_QPA_PLATFORM="offscreen",
        DEADLINE_CLOUD_FOR_ISAAC_SIM_SETTINGS=str(tmp_path / "settings.json"),
    )
    log = tmp_path / "stderr.txt"
    with open(log, "wb") as err:
        p = subprocess.Popen(
            [sys.executable, "-c", _CLOSE_WINDOW],
            stdin=subprocess.PIPE,  # held open (not communicate(), which closes it)
            stdout=subprocess.DEVNULL,
            stderr=err,
            env=env,
        )
        try:
            p.wait(timeout=60)
        finally:
            if p.poll() is None:
                p.kill()
            if p.stdin is not None:
                p.stdin.close()
    text = log.read_text(errors="replace")
    assert p.returncode == 0, text[-2000:]
    assert "Fatal Python error" not in text
