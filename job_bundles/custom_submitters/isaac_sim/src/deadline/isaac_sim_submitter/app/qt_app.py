# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
"""The app's window (PySide6): a "Job outputs" tab and a "Submit" tab.

The views render :mod:`.controllers` state and call controller methods; a 30 Hz
``QTimer`` on the Qt main thread polls the CLI children (:class:`controllers.Runner`) and,
when started by Isaac Sim, the bridge (:class:`bridge.KitLink`). A pane redraws only when
its controller reports a change.
"""

from __future__ import annotations

import functools
import os
import sys
from collections.abc import Callable
from typing import IO, Any

from PySide6 import QtCore, QtGui, QtWidgets

from . import cli_backend as cb
from . import controllers as ct
from . import protocol as pr
from . import settings as st
from .bridge import KitLink
from .views import clear_message, fix_rows, is_message, show_message

DISTRIBUTION = "deadline-cloud-for-isaac-sim"
TITLE = "AWS Deadline Cloud for Isaac Sim"
POLL_MS = 33  # about 30 Hz
KIND_LABEL = {
    "trajectory": "Trajectories",
    "usd": "USD",
    "eval_summary": "Eval summaries",
    "video": "Videos",
    "lerobot": "Datasets",
    "checkpoint": "Checkpoints",
    "hdf5": "HDF5 datasets",
}
ERROR_STYLE = "color: #d9534f;"
HOW_TO_CONNECT = "open this app from Isaac Sim (Tools > Deadline Cloud > Open Deadline Cloud)."
ROLE = QtCore.Qt.ItemDataRole.UserRole
SORT_ROLE = QtCore.Qt.ItemDataRole.UserRole + 1
#: Extra width per sortable column so the sort arrow doesn't clip its header.
SORT_ARROW_WIDTH = 18
EVAL_SUMMARY_NAME = "eval_summary.json"


def package_version() -> str:
    try:
        from importlib.metadata import version

        return version(DISTRIBUTION)
    except Exception:  # noqa: BLE001
        return ""


def log(text: str) -> None:
    sys.stderr.write(f"[{ct.LOG_NAME}] {text}\n")
    sys.stderr.flush()


def _stderr(text: str) -> None:
    """For messages that carry their own prefix (the Runner's)."""
    sys.stderr.write(text + "\n")
    sys.stderr.flush()


def _label(text: str = "", wrap: bool = True) -> QtWidgets.QLabel:
    w = QtWidgets.QLabel(text)
    w.setWordWrap(wrap)
    w.setTextInteractionFlags(QtCore.Qt.TextInteractionFlag.TextSelectableByMouse)
    return w


def _heading(text: str) -> QtWidgets.QLabel:
    w = QtWidgets.QLabel(text)
    f = w.font()
    f.setBold(True)
    w.setFont(f)
    return w


#: Starting width of a table's first (name) column; users can drag it wider.
NAME_COLUMN_WIDTH = 320
#: Shown for a parameter one compared job doesn't have.
NOT_SET = "(not set)"
#: Starting width of the parameter-name column.
PARAM_COLUMN_WIDTH = 200


def _slot(label: QtWidgets.QLabel) -> QtWidgets.QLabel:
    """A label that keeps one line of space when empty, so text appearing or clearing
    doesn't push the views below it."""
    label.setMinimumHeight(label.fontMetrics().lineSpacing())
    return label


def _table(headers: list) -> QtWidgets.QTableWidget:
    """A read-only, single-row-select table. The first column has a fixed starting width
    the user can drag, and the last column takes the remaining space, so short columns
    sit next to the names instead of at the far edge."""
    t = QtWidgets.QTableWidget(0, len(headers))
    t.setHorizontalHeaderLabels(headers)
    t.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
    t.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.SingleSelection)
    t.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
    t.verticalHeader().setVisible(False)
    header = t.horizontalHeader()
    header.setDefaultAlignment(
        QtCore.Qt.AlignmentFlag.AlignLeft | QtCore.Qt.AlignmentFlag.AlignVCenter
    )
    # Same bold labels in every table, whether or not a row is selected (Qt otherwise
    # bolds the header only while the table holds the current cell).
    header.setHighlightSections(False)
    font = header.font()
    font.setBold(True)
    header.setFont(font)
    header.setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeMode.Interactive)
    t.setColumnWidth(0, NAME_COLUMN_WIDTH)
    for i in range(1, len(headers)):
        header.setSectionResizeMode(i, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
    header.setStretchLastSection(True)
    return t


def _cell(text: str, tooltip: str = "", data: Any = None) -> QtWidgets.QTableWidgetItem:
    item = QtWidgets.QTableWidgetItem(text)
    if tooltip:
        item.setToolTip(tooltip)
    if data is not None:
        item.setData(ROLE, data)
    return item


class _Pane(QtWidgets.QWidget):
    """Redraws on the next tick after its controller reports a change."""

    #: The scroll area that holds this pane in the main window's tabs (see _scrolled).
    page: Any = None

    def __init__(self) -> None:
        super().__init__()
        self._dirty = True
        self._keys: dict = {}

    def request_render(self) -> None:
        self._dirty = True

    def render_if_dirty(self) -> None:
        if self._dirty:
            self._dirty = False
            self.redraw()

    def redraw(self) -> None:  # pragma: no cover - overridden
        raise NotImplementedError

    def _changed(self, name: str, key: Any) -> bool:
        if self._keys.get(name, object()) == key:
            return False
        self._keys[name] = key
        return True


# ---------------------------------------------------------------- Job outputs --


class OutputsPane(_Pane):
    def __init__(
        self,
        runner: Any,
        link: KitLink | None,
        on_submit_with: Callable,
        on_resubmit: Callable = lambda job: None,
    ) -> None:
        super().__init__()
        self.link = link
        self.ctl = ct.LoadController(
            runner, self.request_render, self._on_loaded, on_submit_with, on_resubmit
        )
        self.notes: list = []
        self.replay_ready = False

        self.farm = QtWidgets.QComboBox()
        self.queue = QtWidgets.QComboBox()
        for combo in (self.farm, self.queue):
            combo.setSizeAdjustPolicy(QtWidgets.QComboBox.SizeAdjustPolicy.AdjustToContents)
            combo.setMinimumContentsLength(24)
        self.farm.activated.connect(lambda i: self.ctl.select_farm(self.farm.itemData(i) or ""))
        self.queue.activated.connect(lambda i: self.ctl.select_queue(self.queue.itemData(i) or ""))
        self.set_default = QtWidgets.QPushButton("Set as default")
        self.set_default.setToolTip(
            "Save as the Deadline Cloud default farm and queue on this machine"
        )
        self.set_default.clicked.connect(lambda: self.ctl.set_default())
        self.refresh = QtWidgets.QPushButton("Refresh")
        self.refresh.clicked.connect(lambda: self.ctl.refresh())
        self.message = _slot(_label())

        self.job_status = QtWidgets.QComboBox()
        for value, label in ct.JOB_STATUSES:
            self.job_status.addItem(label, value)
        self.job_status.setToolTip("Which finished jobs to list")
        self.job_status.activated.connect(
            lambda i: self.ctl.set_job_status(self.job_status.itemData(i) or "")
        )
        self.jobs = _table(["Name", "Status", "Finished"])
        # Cmd/Ctrl-click a second job to diff its parameters against the clicked one.
        self.jobs.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.ExtendedSelection)
        self.jobs.setToolTip("Cmd/Ctrl-click a second job to compare parameters")
        self.jobs.itemSelectionChanged.connect(self._job_picked)
        self.more_jobs = QtWidgets.QPushButton("Load more")
        self.more_jobs.setToolTip("Load the next page of jobs")
        self.more_jobs.clicked.connect(lambda: self.ctl.list_jobs(more=True))
        self.resubmit = QtWidgets.QPushButton("Resubmit with changes")
        self.resubmit.setToolTip(
            "Open Submit with this job's bundle and parameters prefilled; change what you "
            "want in the submit dialog"
        )
        self.resubmit.clicked.connect(lambda: self.ctl.resubmit())

        self.params_heading = _heading("Parameters")
        self.params = _table(["Parameter", "Value"])
        fix_rows(self.params)  # fixed height: loading and empty states show inside it
        self.params.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.NoSelection)
        # Values are often long paths: keep both ends visible and fit the table's width,
        # so a compared job's column never scrolls off to the right.
        self.params.setTextElideMode(QtCore.Qt.TextElideMode.ElideMiddle)
        self.params.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.params.setColumnWidth(0, PARAM_COLUMN_WIDTH)

        self.kind = QtWidgets.QComboBox()
        # Wide enough for "Eval summaries (12)" and the like without truncating.
        self.kind.setSizeAdjustPolicy(QtWidgets.QComboBox.SizeAdjustPolicy.AdjustToContents)
        self.kind.setMinimumContentsLength(22)
        self.kind.activated.connect(lambda i: self.ctl.set_kind_filter(self.kind.itemData(i) or ""))
        self.eval = _label(wrap=False)
        self.outputs = _table(["Item", "Kind", ""])
        self.outputs.itemChanged.connect(self._item_ticked)
        self.outputs.currentCellChanged.connect(lambda *_: self.request_render())
        self.outputs.cellDoubleClicked.connect(lambda row, _col: self._open_row(row))
        self.outputs_hint = _slot(_label())

        self.load = QtWidgets.QPushButton("Download selected")
        self.load.clicked.connect(self._load_clicked)
        self.isaac_load = QtWidgets.QPushButton("Load in Isaac Sim")
        self.isaac_load.setToolTip(
            "Download the ticked trajectory or USD (once), then replay it on the robot or "
            "add it to the open stage"
        )
        self.isaac_load.clicked.connect(self._isaac_load_clicked)
        self._send_to_isaac = False
        self.play = QtWidgets.QPushButton("Play")
        self.play.setToolTip("Reset the robot to the recorded start and play the trajectory")
        self.play.clicked.connect(lambda: self._replay_control("play"))
        self.stop = QtWidgets.QPushButton("Stop")
        self.stop.clicked.connect(lambda: self._replay_control("stop"))
        # Names what Play and Stop act on: the trajectory last loaded into Isaac Sim.
        self.replay_info = _label(wrap=False)
        self.replay_info.setText("No trajectory loaded")
        self.replay_name = ""
        # Replay setup: which prims a replay drives and places, kept in Isaac Sim's settings.
        self.prims_ctl = ct.ReplayPrimsController(
            link.request if link is not None else None, self.request_render
        )
        self.prims_box = QtWidgets.QWidget()
        grid = QtWidgets.QGridLayout(self.prims_box)
        grid.setContentsMargins(0, 0, 0, 0)
        heading = QtWidgets.QHBoxLayout()
        heading.addWidget(_heading("Replay setup"))
        self.prims_refresh = QtWidgets.QPushButton("Check stage")
        self.prims_refresh.setToolTip("Read the prims from Isaac Sim and check the open stage")
        self.prims_refresh.clicked.connect(lambda: self.prims_ctl.refresh())
        heading.addStretch(1)
        heading.addWidget(self.prims_refresh)
        grid.addLayout(heading, 0, 0, 1, 4)
        self.prim_edits: dict = {}
        self.prim_notes: dict = {}
        for row, (role, label, _needed) in enumerate(ct.REPLAY_ROLE_LABELS, start=1):
            edit = QtWidgets.QLineEdit()
            edit.setPlaceholderText("/World/..." if role != "robot" else "/World/Robot")
            edit.editingFinished.connect(
                lambda r=role, e=edit: self.prims_ctl.set_prim(r, e.text())
            )
            pick = QtWidgets.QPushButton("Use selection")
            pick.setToolTip(f"Use the prim selected in Isaac Sim as the {label.lower()}")
            pick.clicked.connect(lambda _c=False, r=role: self.prims_ctl.use_selection(r))
            note = _slot(_label(wrap=False))
            grid.addWidget(QtWidgets.QLabel(label), row, 0)
            grid.addWidget(edit, row, 1)
            grid.addWidget(pick, row, 2)
            grid.addWidget(note, row, 3)
            self.prim_edits[role], self.prim_notes[role] = edit, note
        grid.setColumnStretch(1, 1)
        self.prims_message = _slot(_label())
        grid.addWidget(self.prims_message, len(ct.REPLAY_ROLE_LABELS) + 1, 0, 1, 4)
        self._prims_shown = False
        self.notes_view = QtWidgets.QPlainTextEdit()
        self.notes_view.setReadOnly(True)
        self.notes_view.setMaximumHeight(90)

        # Farm and queue apply to every tab, so the main window shows this bar above them.
        self.target_bar = QtWidgets.QWidget()
        top = QtWidgets.QGridLayout()
        top.addWidget(QtWidgets.QLabel("Farm"), 0, 0)
        top.addWidget(self.farm, 0, 1)
        top.addWidget(QtWidgets.QLabel("Queue"), 1, 0)
        top.addWidget(self.queue, 1, 1)
        buttons = QtWidgets.QHBoxLayout()
        buttons.addWidget(self.set_default)
        buttons.addWidget(self.refresh)
        buttons.addStretch(1)
        top.addLayout(buttons, 2, 1)
        top.setColumnStretch(1, 1)
        top.addWidget(self.message, 3, 0, 1, 2)
        top.setContentsMargins(0, 0, 0, 0)
        bar = QtWidgets.QVBoxLayout(self.target_bar)
        bar.setContentsMargins(0, 0, 0, 0)
        bar.addLayout(top)
        fix_rows(self.jobs)
        fix_rows(self.outputs)
        filter_row = QtWidgets.QHBoxLayout()
        filter_row.addWidget(_heading("Outputs"))
        filter_row.addWidget(self.kind)
        filter_row.addStretch(1)
        filter_row.addWidget(self.eval)
        actions = QtWidgets.QHBoxLayout()
        for w in (self.load, self.isaac_load, self.play, self.stop, self.replay_info):
            actions.addWidget(w)
        actions.addStretch(1)
        lay = QtWidgets.QVBoxLayout(self)
        jobs_row = QtWidgets.QHBoxLayout()
        jobs_row.addWidget(_heading("Jobs"))
        jobs_row.addWidget(self.job_status)
        jobs_row.addStretch(1)
        lay.addLayout(jobs_row)
        lay.addWidget(self.jobs)
        more_row = QtWidgets.QHBoxLayout()
        more_row.addWidget(self.resubmit)
        more_row.addStretch(1)
        more_row.addWidget(self.more_jobs)
        lay.addLayout(more_row)
        lay.addWidget(self.params_heading)
        lay.addWidget(self.params)
        lay.addLayout(filter_row)
        lay.addWidget(self.outputs_hint)
        lay.addWidget(self.outputs)
        lay.addLayout(actions)
        lay.addWidget(self.prims_box)
        lay.addWidget(self.notes_view)
        lay.addStretch(1)

    # -- events --
    def _job_picked(self) -> None:
        """The clicked (current) row is the job whose outputs show. With exactly two rows
        selected, the other one is the job its parameters are compared against."""
        rows = sorted(i.row() for i in self.jobs.selectionModel().selectedRows())
        if not rows:
            return
        current = self.jobs.currentRow()
        primary = current if current in rows else rows[0]
        others = [r for r in rows if r != primary]

        def job_at(row: int) -> str:
            cell = self.jobs.item(row, 0)
            return str(cell.data(ROLE) or "") if cell is not None else ""

        job_id = job_at(primary)
        if job_id and job_id != self.ctl.s.job_id:
            self.ctl.select_job(job_id)
        self.ctl.set_compare(job_at(others[0]) if len(others) == 1 else "")

    def _item_ticked(self, item: QtWidgets.QTableWidgetItem) -> None:
        if item.column() != 0:
            return
        on = item.checkState() == QtCore.Qt.CheckState.Checked
        self.ctl.toggle(str(item.data(ROLE)), on)
        self.request_render()  # enables or disables Download selected

    def _load_clicked(self) -> None:
        self._send_to_isaac = False
        self.ctl.load_checked(submit=bool(self.ctl.checked_inputs()))

    def _isaac_load_clicked(self) -> None:
        self._send_to_isaac = True
        self.ctl.load_checked()

    def isaac_kinds(self) -> set:
        """Output kinds the connected Isaac Sim can load (none when standalone)."""
        kinds = set()
        if self._isaac(pr.CAP_REPLAY):
            kinds.add("trajectory")
        if self._isaac(pr.CAP_ADD_USD):
            kinds.add("usd")
        return kinds

    def _checked_kinds(self) -> set:
        items = {i["path"]: i for i in self.ctl.s.job.get("items") or []}
        return {items[p]["kind"] for p in self.ctl.s.checked if p in items}

    def _replay_label(self, item: dict) -> str:
        """``eval/shard_01/diag_ep_000.npz (job name)``: rollouts in different folders share
        file names, so name the item by its path in the job, plus the job."""
        job: dict = next((j for j in self.ctl.s.jobs if j.get("jobId") == self.ctl.s.job_id), {})
        name = job.get("name") or self.ctl.s.job_id
        return f"{item.get('path', '')} ({name})" if name else str(item.get("path", ""))

    def _open_row(self, row: int) -> None:
        """Double-click opens a downloaded file with the OS (videos in the system player)."""
        cell = self.outputs.item(row, 0)
        local = self.ctl.fetched_path(str(cell.data(ROLE))) if cell is not None else ""
        if local and os.path.isfile(local):
            cb.open_with_os(local)
            self._note(f"Opened {os.path.basename(local)}.")

    def current_item(self) -> dict:
        row = self.outputs.currentRow()
        cell = self.outputs.item(row, 0) if row >= 0 else None
        path = cell.data(ROLE) if cell is not None else None
        return next((i for i in self.ctl.visible_items() if i["path"] == path), {})

    def _isaac(self, capability: str) -> bool:
        return self.link is not None and self.link.has(capability)

    # -- Isaac Sim actions --
    def _note(self, text: str) -> int:
        self.notes.append(text)
        self.request_render()
        return len(self.notes) - 1

    def send_load(self, kind: str, path: str, label: str = "") -> None:
        if self.link is None:
            return
        notes = self.notes
        i = self._note(f"Sending {os.path.basename(path)} to Isaac Sim...")

        def done(r: dict) -> None:
            text = str(r.get("message") or ("Done." if r.get("ok") else "Failed."))
            if kind == "trajectory" and r.get("ok"):
                self.replay_ready = True
                self.replay_name = label or os.path.basename(path)
            prefix = "" if r.get("ok") else f"Isaac Sim could not load {os.path.basename(path)}: "
            if notes is self.notes:
                notes[i] = prefix + text
            else:
                self.notes.append(prefix + text)
            self.request_render()

        self.link.request(pr.LOAD, done, timeout_s=60.0, kind=kind, path=path)

    def _replay_control(self, action: str) -> None:
        if self.link is None:
            return

        def done(r: dict) -> None:
            if not r.get("ok"):
                self._note(f"Isaac Sim: {r.get('message') or action + ' failed'}")

        self.link.request(pr.REPLAY_CONTROL, done, action=action)

    def _on_loaded(self, items: list, job: dict) -> None:
        """After a download: "Load in Isaac Sim" sends the trajectory (one replays at a
        time) or USD to Isaac Sim; "Download selected" only reports where files landed."""
        self.notes = []
        send, self._send_to_isaac = self._send_to_isaac, False
        kinds = self.isaac_kinds() if send else set()
        trajectories = [it for it in items if it["kind"] == "trajectory"]
        for it in items:
            p, kind = it["local_path"], it["kind"]
            name = os.path.basename(p)
            try:
                if kind in kinds and not (kind == "trajectory" and it is not trajectories[-1]):
                    self.send_load(kind, p, self._replay_label(it))
                elif kind == "trajectory" and send:
                    self._note(f"Downloaded {p} (one trajectory replays at a time).")
                elif kind in ct.INPUT_KINDS:
                    self._note(
                        f"{it.get('label') or name} is ready as the next job's "
                        f"{ct.INPUT_NOUN[kind]} ({p})."
                    )
                else:
                    self._note(f"Downloaded {p}. Double-click it to open.")
            except Exception as exc:  # noqa: BLE001
                log(f"load {p}: {exc!r}")
                self._note(f"Could not load {name}: {exc}")

    # -- drawing --
    def _fill_combo(
        self, combo: QtWidgets.QComboBox, options: list, current: str, default: str, loading: bool
    ) -> None:
        key = (tuple((o["id"], o["name"]) for o in options), current, default, loading)
        if not self._changed(f"combo{id(combo)}", key):
            return
        combo.blockSignals(True)
        combo.clear()
        if not options:
            combo.addItem("Loading..." if loading else (current or "-"), "")
            combo.setEnabled(False)
        else:
            for o in options:
                combo.addItem(o["name"] + ("  (default)" if o["id"] == default else ""), o["id"])
            ids = [o["id"] for o in options]
            combo.setCurrentIndex(ids.index(current) if current in ids else 0)
            combo.setEnabled(True)
        combo.blockSignals(False)

    def redraw(self) -> None:
        s, t = self.ctl.s, self.ctl.s.target
        self._fill_combo(
            self.farm, s.farms, t.farm_id, s.default_farm, loading="Listing farms" in s.busy
        )
        self._fill_combo(
            self.queue,
            s.queues,
            t.queue_id,
            s.default_queue,
            loading=any(w in s.busy for w in ("Listing farms", "Listing queues")),
        )
        is_default = bool(t.farm_id) and (t.farm_id, t.queue_id) == (
            s.default_farm,
            s.default_queue,
        )
        self.set_default.setEnabled(bool(t.farm_id and t.queue_id) and not is_default)
        self.message.setText(s.error or "  |  ".join(x for x in (s.download, s.busy) if x))
        self.message.setStyleSheet(ERROR_STYLE if s.error else "")
        self.message.setVisible(True)  # keeps its line: see _slot
        self._render_jobs()
        self.resubmit.setEnabled(self.ctl.can_resubmit())
        self._render_params()
        self._render_outputs()
        self._render_actions()
        self._render_prims()
        text = "\n".join(self.notes or ([s.status] if s.status else []))
        if self.notes_view.toPlainText() != text:
            self.notes_view.setPlainText(text)

    def _render_jobs(self) -> None:
        s = self.ctl.s
        message = ""
        if not s.jobs:
            loading = any(w in s.busy for w in ("Listing", "Reading the default"))
            message = (
                "Loading jobs..."
                if loading
                else (
                    "Pick a farm and queue"
                    if not s.target.queue_id
                    else f"No {ct.job_status_label(s.job_status).lower()} jobs in this queue"
                )
            )
        more = s.jobs_next_offset is not None
        self.more_jobs.setEnabled(more and "jobs" not in s.busy)
        self.more_jobs.setText(
            f"Load more ({len(s.jobs)} of {s.jobs_total})" if more else "All loaded"
        )
        if self._changed("jobs", (id(s.jobs), len(s.jobs), message)):
            self.jobs.blockSignals(True)
            if message:
                show_message(self.jobs, message)
                self.jobs.blockSignals(False)
                return
            clear_message(self.jobs)
            self.jobs.setRowCount(len(s.jobs))
            for r, j in enumerate(s.jobs):
                self.jobs.setItem(r, 0, _cell(j["name"], j["jobId"], j["jobId"]))
                self.jobs.setItem(r, 1, _cell(j.get("taskRunStatus", "").title()))
                self.jobs.setItem(r, 2, _cell(ct.format_time(j["endedAt"])))
            self.jobs.blockSignals(False)
        ids = [j["jobId"] for j in s.jobs]
        if s.job_id in ids:
            row = ids.index(s.job_id)
            if self.jobs.currentRow() != row:
                self.jobs.blockSignals(True)
                self.jobs.selectRow(row)
                self.jobs.blockSignals(False)
        elif self.jobs.selectionModel().hasSelection():
            self.jobs.blockSignals(True)
            self.jobs.clearSelection()
            self.jobs.blockSignals(False)

    def _job_name(self, job_id: str) -> str:
        return next((j["name"] for j in self.ctl.s.jobs if j["jobId"] == job_id), job_id)

    def _render_params(self) -> None:
        s = self.ctl.s
        rows = self.ctl.parameter_rows()
        comparing = bool(s.compare_id)
        loaded = s.job_id in s.params and (not comparing or s.compare_id in s.params)
        if not s.job_id:
            message = "Select a job to view its parameters"
        elif s.params_error:
            message = s.params_error
        elif not loaded:
            message = "Reading parameters..."
        elif comparing and not rows:
            message = "Both jobs have the same parameters"
        elif not rows:
            message = "This job has no parameters"
        else:
            message = ""
        self.params_heading.setText(
            "Parameters that differ"
            if comparing
            else "Parameters (Cmd/Ctrl-click a job to compare)"
        )
        key = (s.job_id, s.compare_id, loaded, len(rows), message)
        if not self._changed("params", key):
            return
        if comparing:
            self.params.setColumnCount(3)
            self.params.setHorizontalHeaderLabels(
                ["Parameter", self._job_name(s.job_id), self._job_name(s.compare_id)]
            )
        else:
            self.params.setColumnCount(2)
            self.params.setHorizontalHeaderLabels(["Parameter", "Value"])
        header = self.params.horizontalHeader()
        for col in range(1, self.params.columnCount()):
            header.setSectionResizeMode(col, QtWidgets.QHeaderView.ResizeMode.Stretch)
        if message:
            show_message(self.params, message)
            return
        clear_message(self.params)
        self.params.setRowCount(len(rows))
        for r, (name, value, other) in enumerate(rows):
            self.params.setItem(r, 0, _cell(name, name))
            mine_set = name in s.params.get(s.job_id, {})
            self.params.setItem(r, 1, _cell(value if mine_set else NOT_SET, value))
            if comparing:
                other_set = name in s.params.get(s.compare_id, {})
                self.params.setItem(r, 2, _cell(other if other_set else NOT_SET, other))

    def _render_outputs(self) -> None:
        s, j = self.ctl.s, self.ctl.s.job
        counts = self.ctl.kind_counts()
        if self._changed("kinds", (id(j), tuple(sorted(counts.items())), s.kind_filter)):
            self.kind.blockSignals(True)
            self.kind.clear()
            self.kind.addItem(f"All ({sum(counts.values())})", "")
            for k in self.ctl.KINDS:
                if counts.get(k):
                    self.kind.addItem(f"{KIND_LABEL[k]} ({counts[k]})", k)
            i = self.kind.findData(s.kind_filter)
            self.kind.setCurrentIndex(max(i, 0))
            self.kind.blockSignals(False)
        self.kind.setEnabled(bool(counts))
        summ = j.get("eval_summary") if j else None
        if summ:
            rate = summ.get("success_rate")
            self.eval.setText(
                f"Eval {summ.get('successes')}/{summ.get('episodes')}"
                + (f" ({rate * 100:.1f}%)" if isinstance(rate, (int, float)) else "")
            )
        else:
            self.eval.setText("")
        items = self.ctl.visible_items()
        if not s.job_id:
            message = "Select a job to view its outputs"
        elif not j:
            message = (
                "Reading the job's outputs..." if "outputs" in s.busy else (s.error or "No outputs")
            )
        elif not items:
            message = "No loadable outputs in this job"
        else:
            message = ""
        job_row: dict = next((x for x in s.jobs if x.get("jobId") == s.job_id), {})
        partial = j and job_row.get("taskRunStatus", "SUCCEEDED") != "SUCCEEDED"
        self.outputs_hint.setText(
            "Partial outputs: only the tasks that finished before the job stopped."
            if partial
            else ""
        )

        self.outputs.blockSignals(True)
        if self._changed("outputs", (s.job_id, id(j), s.kind_filter, message)):
            if message:
                show_message(self.outputs, message)
            else:
                clear_message(self.outputs)
                self.outputs.setRowCount(len(items))
                for r, it in enumerate(items):
                    cell = _cell(it["label"], it["path"], it["path"])
                    cell.setFlags(cell.flags() | QtCore.Qt.ItemFlag.ItemIsUserCheckable)
                    cell.setCheckState(QtCore.Qt.CheckState.Unchecked)  # shows the box
                    self.outputs.setItem(r, 0, cell)
                    self.outputs.setItem(r, 1, _cell(KIND_LABEL.get(it["kind"], it["kind"])))
                    self.outputs.setItem(r, 2, _cell(""))
        for r in range(0 if is_message(self.outputs) else self.outputs.rowCount()):
            row, status = self.outputs.item(r, 0), self.outputs.item(r, 2)
            if row is None or status is None:
                continue
            path = str(row.data(ROLE))
            state = (
                QtCore.Qt.CheckState.Checked
                if path in s.checked
                else QtCore.Qt.CheckState.Unchecked
            )
            if row.checkState() != state:
                row.setCheckState(state)
            got = self.ctl.fetched_path(path)
            status.setText("downloaded" if got else "")
            status.setToolTip(got)
        self.outputs.blockSignals(False)

    def _render_prims(self) -> None:
        """Shown while connected to an Isaac Sim that offers replay prims; read once each
        time it appears."""
        shown = self._isaac(pr.CAP_REPLAY_PRIMS)
        self.prims_box.setVisible(shown)
        if shown and not self._prims_shown:
            self.prims_ctl.refresh()
        self._prims_shown = shown
        if not shown:
            return
        p = self.prims_ctl.s
        for role, edit in self.prim_edits.items():
            value = p.prims.get(role, "")
            if not edit.hasFocus() and edit.text() != value:
                edit.setText(value)
            note = self.prims_ctl.note(role)
            self.prim_notes[role].setText(note)
            missing = note.startswith(("Not in", "Not set: replay"))
            self.prim_notes[role].setStyleSheet(ERROR_STYLE if missing else "")
        self.prims_message.setText(p.error or p.busy or p.status)
        self.prims_message.setStyleSheet(ERROR_STYLE if p.error else "")
        self.prims_refresh.setEnabled(not p.busy)

    def _render_actions(self) -> None:
        s = self.ctl.s
        inputs = self.ctl.checked_inputs()
        n = len(s.checked)
        if inputs:
            kinds = {i["kind"] for i in inputs}
            what = ct.INPUT_NOUN[kinds.pop()] if len(kinds) == 1 else "inputs"
            self.load.setText(f"Submit pipeline job with {what}" + (f" ({n})" if n > 1 else ""))
            self.load.setToolTip(
                "Download the selection (once), then open Submit with it prefilled"
            )
        else:
            self.load.setText(f"Download selected ({n})" if n else "Download selected")
            self.load.setToolTip(
                "Download the ticked items; double-click a downloaded row to open it"
            )
        self.load.setEnabled(self.ctl.can_load())
        kinds = self.isaac_kinds()
        self.isaac_load.setVisible(bool(kinds))
        self.isaac_load.setEnabled(self.ctl.can_load() and bool(self._checked_kinds() & kinds))
        replay = "trajectory" in kinds
        self.replay_info.setVisible(replay)
        if self.replay_name:
            self.replay_info.setText(f"Loaded: {self.replay_name}")
            self.replay_info.setToolTip("Play and Stop act on this trajectory in Isaac Sim")
        for b in (self.play, self.stop):
            b.setVisible(replay)
            b.setEnabled(self.replay_ready)


# --------------------------------------------------------------------- Submit --


@functools.total_ordering  # Qt sorts with < only; the other comparisons follow from it
class _SortItem(QtWidgets.QTableWidgetItem):
    """Sorts by its ``SORT_ROLE`` value (numbers as numbers), not its text."""

    def __lt__(self, other: QtWidgets.QTableWidgetItem) -> bool:
        a, b = self.data(SORT_ROLE), other.data(SORT_ROLE)
        try:
            return bool(a < b)
        except TypeError:
            return super().__lt__(other)


class EvalPane(_Pane):
    """Eval summaries of the completed jobs in the queue chosen above the tabs."""

    def __init__(self, runner: Any, target: Callable, open_job: Callable) -> None:
        super().__init__()
        self.ctl = ct.EvalController(runner, self.request_render, target)
        self.open_job = open_job
        self.heading = _heading("Evaluations")
        self.read = QtWidgets.QPushButton("Read eval results from queue")
        self.read.setToolTip(
            "Read each completed job's eval_summary.json or eval_info.json (lists the job's "
            "outputs and downloads only those files)"
        )
        self.read.clicked.connect(lambda: self.ctl.load())
        self.more = QtWidgets.QPushButton("Load more")
        self.more.setToolTip("Read the next page of completed jobs")
        self.more.clicked.connect(lambda: self.ctl.load(more=True))
        self.export = QtWidgets.QPushButton("Export CSV...")
        self.export.clicked.connect(self._export)
        self.message = _label()
        self.table = _table(["Job"])
        fix_rows(self.table)  # fixed height: reading and empty states show inside it
        self.table.setSortingEnabled(True)
        self.table.setToolTip("Click a header to sort; double-click a job to view its outputs")
        self.table.cellDoubleClicked.connect(self._open)
        self.status = _label()

        top = QtWidgets.QHBoxLayout()
        top.addWidget(self.heading)
        top.addStretch(1)
        for w in (self.read, self.more, self.export):
            top.addWidget(w)
        lay = QtWidgets.QVBoxLayout(self)
        lay.addLayout(top)
        lay.addWidget(self.message)
        lay.addWidget(self.table)
        lay.addWidget(self.status)
        lay.addStretch(1)

    def on_shown(self) -> None:
        """Nothing is read until Read eval results from queue: reading lists every job's outputs."""
        self.request_render()

    def _open(self, row: int, _col: int) -> None:
        cell = self.table.item(row, 0)
        if cell is not None and cell.data(ROLE):
            self.open_job(str(cell.data(ROLE)))

    def _export(self) -> None:
        path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self, "Export eval results", "eval_results.csv", "CSV files (*.csv)"
        )
        if not path:
            return
        try:
            n = self.ctl.write_csv(path)
        except OSError as exc:
            self.ctl._set(error=f"Could not write {path}: {exc}")
            return
        self.ctl._set(status=f"Wrote {n} rows to {path}", error="")

    def redraw(self) -> None:
        s = self.ctl.s
        t = self.ctl.target()
        self.message.setText(s.error)
        self.message.setStyleSheet(ERROR_STYLE)
        self.message.setVisible(bool(s.error))
        # Rows read for another farm or queue stay hidden until read again.
        headers, rows = ([], []) if self.ctl.stale() else self.ctl.table()
        if not (t.farm_id and t.queue_id):
            message = "Pick a farm and queue above"
        elif s.busy:
            message = "Reading eval results..."
        elif self.ctl.stale():
            message = "Press Read eval results from queue to compare its completed jobs"
        elif not rows and s.jobs:
            message = (
                f"None of the {len(s.jobs)} jobs read has an {EVAL_SUMMARY_NAME} "
                "or eval_info.json"
            )
        else:
            message = ""
        self.more.setVisible(s.next_offset is not None)
        self.more.setEnabled(not s.busy)
        self.more.setText(f"Load more ({len(s.jobs)} of {s.total} read)")
        self.read.setEnabled(not s.busy)
        self.export.setEnabled(bool(rows))
        self.status.setText(s.status)
        if not self._changed("table", (id(s.jobs), len(s.jobs), tuple(headers), message)):
            return
        self.table.setSortingEnabled(False)  # filling a sorted table scrambles rows
        if message:
            self.table.clear()
            self.table.setColumnCount(max(1, len(headers)))
            self.table.setHorizontalHeaderLabels(headers or ["Job"])
            show_message(self.table, message)
            return
        clear_message(self.table)
        self.table.clear()
        self.table.setColumnCount(len(headers))
        self.table.setHorizontalHeaderLabels(headers)
        self.table.setRowCount(len(rows))
        jobs = self.ctl.rows()
        for r, row in enumerate(rows):
            for c, (text, key) in enumerate(row):
                item = _SortItem(text)
                item.setData(SORT_ROLE, key)
                item.setToolTip(text)
                if c == 0:
                    item.setData(ROLE, jobs[r]["jobId"])
                    item.setToolTip(f"{text} ({jobs[r]['jobId']})")
                self.table.setItem(r, c, item)
        self.table.resizeColumnsToContents()  # narrow numbers, so parameters come into view
        self.table.setColumnWidth(0, min(self.table.columnWidth(0), NAME_COLUMN_WIDTH))
        for col in range(1, self.table.columnCount()):  # room for the sort arrow
            self.table.setColumnWidth(col, self.table.columnWidth(col) + SORT_ARROW_WIDTH)
        self.table.setSortingEnabled(True)
        self.table.sortItems(1, QtCore.Qt.SortOrder.DescendingOrder)


class SubmitPane(_Pane):
    def __init__(self, runner: Any, ext_version: str) -> None:
        super().__init__()
        self.connected = False
        self.ctl = ct.SubmitController(runner, self.request_render, ext_version=ext_version)
        self.folders = QtWidgets.QLineEdit()
        self.folders.setPlaceholderText("~/DeadlineCloud/JobBundles")
        self._folders_edited = False
        self.folders.textEdited.connect(lambda _t: setattr(self, "_folders_edited", True))
        self.folders.returnPressed.connect(self._rescan)
        self.rescan = QtWidgets.QPushButton("Rescan")
        self.rescan.clicked.connect(self._rescan)
        self.add_folder = QtWidgets.QPushButton("Choose bundle folder...")
        self.add_folder.setToolTip("Add a folder that holds job bundles (searched two levels deep)")
        self.add_folder.clicked.connect(self._choose_folder)
        self.searched = _label()
        self.error = _slot(_label())
        self.error.setStyleSheet(ERROR_STYLE)
        self.target_info = _label()
        self.bundles = QtWidgets.QListWidget()
        fix_rows(self.bundles)
        self.bundles.itemSelectionChanged.connect(self._bundle_picked)
        # Scrolls: a bundle's description and a resubmitted job's prefill can be long.
        self.details = QtWidgets.QPlainTextEdit()
        self.details.setReadOnly(True)
        self.details.setMaximumHeight(180)
        self.missing = _label()
        self.missing.setStyleSheet(ERROR_STYLE)
        self.resubmit_info = _label()
        self.stop_resubmit = QtWidgets.QPushButton("Don't reuse its values")
        self.stop_resubmit.setToolTip("Prefill only from the open stage and loaded outputs")
        self.stop_resubmit.clicked.connect(lambda: self.ctl.clear_resubmit())
        self.open = QtWidgets.QPushButton("Open submit dialog")
        self.open.clicked.connect(lambda: self.ctl.submit())
        self.status = _label()

        row = QtWidgets.QHBoxLayout()
        row.addWidget(self.folders, 1)
        row.addWidget(self.rescan)
        row.addWidget(self.add_folder)
        lay = QtWidgets.QVBoxLayout(self)
        lay.addWidget(QtWidgets.QLabel("Job bundle folders (separate with ;)"))
        lay.addLayout(row)
        lay.addWidget(self.searched)
        lay.addWidget(self.error)
        lay.addWidget(self.bundles)
        resubmit_row = QtWidgets.QHBoxLayout()
        resubmit_row.addWidget(self.resubmit_info, 1)
        resubmit_row.addWidget(self.stop_resubmit)
        lay.addLayout(resubmit_row)
        lay.addWidget(self.details)
        lay.addWidget(self.missing)
        lay.addWidget(self.target_info)
        lay.addWidget(self.open)
        lay.addWidget(self.status)
        lay.addStretch(1)

    def _rescan(self) -> None:
        text = self.folders.text()
        self._folders_edited = False  # the setting now holds it
        self.ctl.set_folders(text)

    def _choose_folder(self) -> None:
        folder = QtWidgets.QFileDialog.getExistingDirectory(self, "Choose a job bundle folder")
        if folder:
            self._folders_edited = False
            self.ctl.add_folder(folder)

    def _bundle_picked(self) -> None:
        items = self.bundles.selectedItems()
        if items:
            path = str(items[0].data(ROLE))
            if path != self.ctl.s.selected:
                self.ctl.select(path)

    def redraw(self) -> None:
        s = self.ctl.s
        if not self._folders_edited:
            text = ";".join(self.ctl.folders())
            if self.folders.text() != text:
                self.folders.setText(text)
        self.error.setText(s.error)
        extra = [f for f in self.ctl.search_folders() if f not in self.ctl.folders()]
        self.searched.setText(
            "Also searched: " + "; ".join(extra) + " (deadline-cloud's default bundle folder)"
            if extra
            else ""
        )
        self.searched.setVisible(bool(extra))
        if self._changed("bundles", tuple((b.path, b.name) for b in s.bundles)):
            self.bundles.blockSignals(True)
            self.bundles.clear()
            if not s.bundles:
                show_message(self.bundles, "No job bundles found in these folders")
            for b in s.bundles:
                item = QtWidgets.QListWidgetItem(b.name)
                item.setToolTip(b.path)
                item.setData(ROLE, b.path)
                self.bundles.addItem(item)
            self.bundles.blockSignals(False)
        self.bundles.blockSignals(True)
        for i in range(0 if is_message(self.bundles) else self.bundles.count()):
            item = self.bundles.item(i)
            if (item.data(ROLE) == s.selected) != item.isSelected():
                item.setSelected(item.data(ROLE) == s.selected)
        self.bundles.blockSignals(False)
        b = self.ctl.bundle()
        lines, missing = [], []
        if b is not None:
            if b.description:
                lines.append(b.description)
            lines += [f"Prefilled {k} = {v}" for k, v in s.prefill.items()]
            if self.connected and s.stage_checked and not s.stage:
                lines.append("The open stage is unsaved, so no scene path is prefilled.")
            for name in self.ctl.missing_inputs():
                hint = self.ctl.missing_hint(name)
                missing.append(
                    f"{name} is empty: the job will fail without it. To fill it, "
                    + (f"{hint}, or " if hint else "")
                    + "browse to one in the dialog."
                )
        r = s.resubmit
        self.resubmit_info.setText(
            f"Resubmitting {r.get('name') or r.get('job_id')} ({r.get('job_id')}) with its "
            "parameter values"
            if r
            else ""
        )
        self.resubmit_info.setVisible(bool(r))
        self.stop_resubmit.setVisible(bool(r))
        text = "\n".join(lines)
        if self.details.toPlainText() != text:
            self.details.setPlainText(text)
        self.details.setVisible(bool(text))
        self.missing.setText("\n".join(missing))
        self.missing.setVisible(bool(missing))
        info = self.ctl.target()
        t = info.get("target") if info else None
        if t is not None and t.farm_id and t.queue_id:
            self.target_info.setText(
                f"Submits to {info.get('farm')} / {info.get('queue')}"
                + ("" if info.get("default") else " (chosen above; your defaults are unchanged)")
            )
        else:
            self.target_info.setText("Submits to your Deadline Cloud default farm and queue")
        # Disabled while a dialog is open: a second one would start a second submit.
        self.open.setEnabled(not s.busy and b is not None)
        self.status.setText("\n".join(x for x in (s.busy, s.status) if x))


# ---------------------------------------------------------------- main window --


#: The main window's narrowest width when sized to its content.
MIN_WIDTH = 760
#: Title bar and frame height assumed before the window is shown (the system adds them).
FRAME_ALLOWANCE = 40


class _PageArea(QtWidgets.QScrollArea):
    """A tab's scroll area whose size hint is its whole page. QScrollArea caps its hint at
    24 lines of text, which would open the window too short and scrolling."""

    def sizeHint(self) -> QtCore.QSize:
        page = self.widget()
        if page is None:
            return super().sizeHint()
        f = 2 * self.frameWidth()
        return page.sizeHint() + QtCore.QSize(f, f)


def _scrolled(pane: _Pane) -> QtWidgets.QScrollArea:
    """``pane`` in a scroll area, so the fixed-height views fit short screens (the tab
    scrolls instead of the window growing past the display). ``pane.page`` is the area."""
    area = _PageArea()
    area.setWidgetResizable(True)
    area.setFrameShape(QtWidgets.QFrame.Shape.NoFrame)
    area.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
    area.setWidget(pane)
    pane.page = area
    return area


class MainWindow(QtWidgets.QMainWindow):
    def __init__(self, link: KitLink | None = None, runner: Any = None) -> None:
        super().__init__()
        self.setWindowTitle(TITLE)
        self.runner = runner if runner is not None else ct.Runner(log=_stderr)
        self.link = link
        self.outputs = OutputsPane(self.runner, link, self.submit_with, self.resubmit)
        self.submit = SubmitPane(self.runner, package_version())
        self.evals = EvalPane(self.runner, lambda: self.outputs.ctl.s.target, self.open_job)
        self.tabs = QtWidgets.QTabWidget()
        self.tabs.addTab(_scrolled(self.outputs), "Job outputs")
        self.tabs.addTab(_scrolled(self.submit), "Submit")
        self.tabs.addTab(_scrolled(self.evals), "Evaluations")
        self.tabs.currentChanged.connect(self._tab_changed)
        central = QtWidgets.QWidget()
        lay = QtWidgets.QVBoxLayout(central)
        lay.addWidget(self.outputs.target_bar)
        lay.addWidget(self.tabs, 1)
        self.setCentralWidget(central)
        # Submit opens the dialog on the farm and queue chosen in the bar.
        self.submit.ctl.target = self._submit_target
        self.connection = QtWidgets.QLabel()
        self.statusBar().addWidget(self.connection)
        self._was_connected = False
        self._fit_pending = False
        if link is not None:
            link.on_change = self._link_changed
            link.on_focus = self.bring_to_front
            link.on_eof = self._kit_gone
        self._link_changed()
        self.timer = QtCore.QTimer(self)
        self.timer.timeout.connect(self.tick)
        self.timer.start(POLL_MS)
        QtCore.QTimer.singleShot(0, self.outputs.ctl.refresh)
        for pane in (self.outputs, self.submit, self.evals):
            pane.render_if_dirty()  # measure the panes as they first appear
        self.fit_to_content()

    def fit_to_content(self, grow_only: bool = False) -> None:
        """Size the window to its content (the tallest tab, see ``_PageArea``) within the
        screen's available area; the tabs only scroll when the content is taller than that."""
        lay = self.layout()
        if lay is not None:
            lay.activate()
        hint = self.sizeHint()
        want = QtCore.QSize(max(MIN_WIDTH, hint.width()), hint.height())
        screen = self.screen() or QtGui.QGuiApplication.primaryScreen()
        if screen is not None:
            avail = screen.availableGeometry()
            # Leave room for the title bar and frame, which the window does not count.
            frame = max(self.frameGeometry().height() - self.height(), FRAME_ALLOWANCE)
            want = want.boundedTo(QtCore.QSize(avail.width(), avail.height() - frame))
        if grow_only:
            want = want.expandedTo(self.size())
        if want != self.size():
            self.resize(want)

    def tick(self) -> None:
        try:
            self.runner.poll()
            if self.link is not None:
                self.link.poll()
        except Exception as exc:  # noqa: BLE001 - keep the timer running
            log(f"poll: {exc!r}")
        for pane in (self.outputs, self.submit, self.evals):
            try:
                pane.render_if_dirty()
            except Exception as exc:  # noqa: BLE001 - one pane must not stop the other
                log(f"{type(pane).__name__}: {exc!r}")
        if self._fit_pending:  # content that appeared after opening (e.g. on connecting)
            self._fit_pending = False
            self.fit_to_content(grow_only=True)

    def _submit_target(self) -> dict:
        """The bar's farm and queue for Submit (see ``SubmitController.target``)."""
        s = self.outputs.ctl.s
        t = s.target

        def name(items: list, id_: str) -> str:
            return next((x["name"] for x in items if x["id"] == id_), id_)

        return {
            "target": t,
            "default": (t.farm_id, t.queue_id) == (s.default_farm, s.default_queue),
            "farm": name(s.farms, t.farm_id),
            "queue": name(s.queues, t.queue_id),
        }

    def _current_pane(self) -> QtWidgets.QWidget | None:
        area = self.tabs.currentWidget()
        return area.widget() if isinstance(area, QtWidgets.QScrollArea) else area

    def _tab_changed(self, _i: int) -> None:
        if self._current_pane() is self.submit:
            self.submit.ctl.on_shown()
        elif self._current_pane() is self.evals:
            self.evals.on_shown()

    def open_job(self, job_id: str) -> None:
        """Show this job's outputs (double-click in Evaluations)."""
        self.tabs.setCurrentWidget(self.outputs.page)
        self.outputs.ctl.select_job(job_id)

    def submit_with(self, items: list) -> None:
        """Open Submit with these loaded datasets or checkpoints as the next job's inputs."""
        self.submit.ctl.request_inputs(items, opening=self._current_pane() is not self.submit)
        self.tabs.setCurrentWidget(self.submit.page)
        self.submit.ctl.apply_requested_inputs()

    def resubmit(self, job: dict) -> None:
        """Open Submit for this finished job's bundle with its parameter values."""
        self.submit.ctl.request_resubmit(job, opening=self._current_pane() is not self.submit)
        self.tabs.setCurrentWidget(self.submit.page)
        self.submit.ctl.apply_requested_inputs()

    def _link_changed(self) -> None:
        link = self.link
        connected = link is not None and link.connected
        stage = link is not None and link.has(pr.CAP_STAGE_PATH)
        self.submit.connected = stage
        self.submit.ctl.fetch_stage = link.fetch_stage if stage and link else None
        self.submit.ctl.app_version = link.kit_version if connected and link else ""
        if connected and link is not None:
            self.connection.setText(
                f"Connected to Isaac Sim {link.kit_version}".rstrip()
                + (f" (extension {link.extension_version})" if link.extension_version else "")
            )
        elif link is not None:
            self.connection.setText("Waiting for Isaac Sim..." if not link.closed else "")
        else:
            self.connection.setText("Standalone. For replay and stage actions, " + HOW_TO_CONNECT)
        if connected and not self._was_connected:
            self.submit.ctl.refresh_stage()
            self._fit_pending = True
        self._was_connected = connected
        self.outputs.request_render()
        self.submit.request_render()

    def bring_to_front(self) -> None:
        if self.isMinimized():
            self.showNormal()
        self.show()
        self.raise_()
        self.activateWindow()

    def _kit_gone(self) -> None:
        """Isaac Sim quit or closed the bridge: this app goes with it."""
        log("Isaac Sim closed the bridge; exiting")
        self.close()
        app = QtWidgets.QApplication.instance()
        if app is not None:
            app.quit()

    def closeEvent(self, event: QtGui.QCloseEvent) -> None:
        self.timer.stop()
        self.runner.cancel_all()
        super().closeEvent(event)


def claim_stdout() -> IO[bytes]:
    """A private copy of stdout for the bridge, with file descriptor 1 pointed at stderr so
    stray prints (ours, a library's, a child's) cannot corrupt the message stream."""
    sys.stdout.flush()
    tx = os.fdopen(os.dup(sys.stdout.fileno()), "wb")
    try:
        os.dup2(sys.stderr.fileno(), sys.stdout.fileno())
    except OSError:  # no usable stderr: drop stray output instead
        devnull = os.open(os.devnull, os.O_WRONLY)
        os.dup2(devnull, sys.stdout.fileno())
        os.close(devnull)
    return tx


def main(bridge: bool = False) -> int:
    """Run the app until its window closes (or, with ``bridge``, until Isaac Sim closes
    the app's stdin)."""
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication(
        [sys.argv[0] if sys.argv else "deadline-physical-ai"]
    )
    app.setApplicationName(TITLE)
    link = None
    if bridge:
        link = KitLink(
            sys.stdin.buffer, claim_stdout(), package_version(), st.download_root, log=log
        ).start()
    win = MainWindow(link)
    win.show()
    return int(app.exec())
