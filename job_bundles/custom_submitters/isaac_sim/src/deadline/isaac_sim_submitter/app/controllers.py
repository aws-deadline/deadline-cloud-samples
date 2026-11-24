# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
"""State and actions for the app's two panes, with no Qt in them.

The views (``qt_app.py``) render a controller's state and call its methods; the
controller runs CLI commands through a ``runner`` (``runner(argv, on_done)``, see
:class:`Runner`) and calls ``on_change`` when the view should redraw. Tests drive the
controllers with a fake runner.
"""

from __future__ import annotations

import os
import tempfile
from dataclasses import dataclass, field
from typing import Any

from . import bundles as bd
from . import cli_backend as cb
from . import protocol as pr
from . import settings as st


def format_time(value: str) -> str:
    """``2026-11-11 19:38:05.894000+00:00`` -> ``Nov 11, 11:38`` in local time ("" if unparsable)."""
    import datetime

    if not value:
        return ""
    try:
        dt = datetime.datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return value[:16]
    if dt.tzinfo is not None:
        dt = dt.astimezone()
    return dt.strftime("%b %d, %H:%M")


class Session:
    """What "Job outputs" has downloaded this session, shared with "Submit" so a loaded
    dataset or checkpoint can be the next job's input."""

    def __init__(self):
        self.loaded: list = []  # item dicts with local_path and job_id

    def add(self, items: list, job_id: str) -> None:
        """Remember a load. Datasets and checkpoints loaded together replace the earlier
        ones of that kind: the next job uses what was picked last, not everything ever loaded."""
        new = [dict(it, job_id=job_id) for it in items]
        replaced = {it.get("kind") for it in new} & set(INPUT_KINDS)
        keep = [
            x
            for x in self.loaded
            if x.get("kind") not in replaced
            and x.get("local_path") not in {it.get("local_path") for it in new}
        ]
        self.loaded = keep + new

    def of_kind(self, kind: str) -> list:
        return [x for x in self.loaded if x.get("kind") == kind]


#: Name prefix of the per-submit folder of hard links to several datasets.
GATHER_PREFIX = ".gathered-"


def gather_dir(paths: list) -> str:
    """A fresh folder for :func:`bundles.gather_datasets`, on the same filesystem as the
    datasets.

    ``os.link`` fails with ``EXDEV`` across filesystems, and the system temp dir usually
    is one, so gathering there copies the datasets (gigabytes) instead of linking them.
    The folder is hidden and sits in the datasets' common parent (their download folder),
    unique per submit; the system temp dir is the fallback when that parent cannot hold
    it."""
    try:
        full = [os.path.abspath(p) for p in paths]
        common = os.path.commonpath(full)
        return tempfile.mkdtemp(
            prefix=GATHER_PREFIX, dir=os.path.dirname(common) if common in full else common
        )
    except (OSError, ValueError):
        return tempfile.mkdtemp(prefix="isaacsim-deadline-datasets-")


#: Output kinds that are inputs to the next job rather than things to view in the stage.
INPUT_KINDS = ("lerobot", "checkpoint")
#: Which parameter-name word each input kind fills.
INPUT_WORD = {"lerobot": "dataset", "checkpoint": "checkpoint"}
INPUT_NOUN = {"lerobot": "dataset", "checkpoint": "checkpoint"}

SESSION = Session()

#: Log prefix.
LOG_NAME = "deadline-cloud-for-isaac-sim"


class Runner:
    """Starts :class:`cli_backend.Command` children and polls them every frame.

    A callback that raises (unexpected CLI output, say) must not escape into the UI's
    timer or leave its pane stuck on "Listing jobs...": the error is logged
    and the same ``on_done`` is called once more with a failed :class:`Result`
    carrying the traceback, so the controller's own error path clears its busy state."""

    def __init__(self, log=print):
        self._cmds: list = []
        self.log = log

    def __call__(
        self,
        argv: list,
        on_done,
        exe: str = "",
        timeout_s: float | None = 90.0,
        on_progress=None,
        env_extra: dict | None = None,
    ) -> None:
        on_done = self._guard_done(argv, on_done)
        try:
            self._cmds.append(
                cb.Command(
                    argv,
                    on_done,
                    env={**cb.child_env(exe or argv[0]), **(env_extra or {})},
                    timeout_s=timeout_s,
                    on_progress=on_progress and self._guard_progress(argv, on_progress),
                )
            )
        except OSError as exc:
            on_done(cb.Result(argv, 127, "", str(exc)))

    def _guard_done(self, argv: list, on_done):
        import traceback

        def call(r: cb.Result) -> None:
            try:
                on_done(r)
            except Exception:  # noqa: BLE001
                tb = traceback.format_exc()
                self.log(f"[{LOG_NAME}] {argv[1:3]} result handler failed:\n{tb}")
                try:
                    on_done(cb.Result(r.argv, r.code or 1, "", r.stderr + "\n" + tb))
                except Exception:  # noqa: BLE001
                    self.log(
                        f"[{LOG_NAME}] {argv[1:3]} error handler failed:\n"
                        f"{traceback.format_exc()}"
                    )

        return call

    def _guard_progress(self, argv: list, on_progress):
        def call(p: dict) -> None:
            try:
                on_progress(p)
            # Progress is cosmetic: never stop a download over it.
            except Exception as exc:  # noqa: BLE001
                self.log(f"[{LOG_NAME}] {argv[1:3]} progress: {exc!r}")

        return call

    def poll(self) -> None:
        if not self._cmds:
            return
        # Callbacks may start new commands; those land in the fresh list.
        cmds, self._cmds = self._cmds, []
        keep = [c for c in cmds if not c.poll()]
        self._cmds = keep + self._cmds

    def cancel_all(self) -> None:
        for c in self._cmds:
            c.cancel()
        self._cmds = []


def _tools() -> tuple:
    dl, dl_how = cb.resolve("deadline", st.get_str(st.DEADLINE_EXECUTABLE))
    pai, pai_how = cb.resolve("deadline-physical-ai", st.get_str(st.PHYSICAL_AI_EXECUTABLE))
    return dl, dl_how, pai, pai_how


# ---------------------------------------------------------------- Job outputs --


#: Job status filter choices: (``jobs list --status`` value, label).
JOB_STATUSES = (
    ("succeeded", "Succeeded"),
    ("failed", "Failed"),
    ("canceled", "Canceled"),
    ("any", "Any finished"),
)


def job_status_label(status: str) -> str:
    return dict(JOB_STATUSES).get(status, status)


def parameter_rows(params: dict, other: dict | None = None) -> list:
    """``(name, value, other_value)`` rows: every parameter of ``params``, or with ``other``
    only the parameters whose values differ (missing on one side shows as "")."""
    if other is None:
        return [(k, params[k], "") for k in sorted(params)]
    names = sorted(set(params) | set(other))
    return [
        (k, params.get(k, ""), other.get(k, "")) for k in names if params.get(k) != other.get(k)
    ]


@dataclass
class LoadState:
    target: cb.Target = field(default_factory=cb.Target)
    farms: list = field(default_factory=list)  # [{id, name, region}]
    queues: list = field(default_factory=list)
    default_farm: str = ""
    default_queue: str = ""
    jobs: list = field(default_factory=list)
    job_status: str = "succeeded"  # a JOB_STATUSES value
    jobs_next_offset: int | None = None  # set while more jobs can be loaded
    jobs_total: int = 0
    job_id: str = ""
    job: dict = field(default_factory=dict)  # outputs list result
    compare_id: str = ""  # a second selected job whose parameters are diffed against job_id
    params: dict = field(default_factory=dict)  # job id -> {name: value text}
    params_error: str = ""
    kind_filter: str = ""  # "" = all kinds
    checked: set = field(default_factory=set)  # item paths
    # (job id, item path) -> local path. Keyed by job: pipeline jobs repeat item paths.
    fetched: dict = field(default_factory=dict)
    status: str = ""
    error: str = ""
    busy: str = ""  # listing farms, queues, jobs or outputs
    download: str = ""  # a download in progress (runs alongside listing)


class LoadController:
    KINDS = ("trajectory", "usd", "eval_summary", "lerobot", "checkpoint", "video", "hdf5")

    def __init__(
        self,
        runner,
        on_change=lambda: None,
        on_loaded=lambda items, job: None,
        on_submit_with=lambda items: None,
        on_resubmit=lambda job: None,
    ):
        self.runner, self.on_change, self.on_loaded = runner, on_change, on_loaded
        self.on_submit_with = on_submit_with
        self.on_resubmit = on_resubmit
        self.s = LoadState()
        self.deadline = self.pai = ""
        # Generation per kind of request. Starting one bumps it; a reply whose generation
        # is no longer current answers an older selection and is dropped.
        self._gen: dict = {}

    # -- helpers --
    def _bump(self, *ops: str) -> int:
        for op in ops:
            self._gen[op] = self._gen.get(op, 0) + 1
        return self._gen[ops[0]]

    def _stale(self, op: str, gen: int) -> bool:
        return self._gen.get(op, 0) != gen

    def _set(self, **kw) -> None:
        for k, v in kw.items():
            setattr(self.s, k, v)
        self.on_change()

    def _tools_ok(self, need_pai: bool) -> bool:
        self.deadline, dl_how, self.pai, pai_how = _tools()
        if not self.deadline:
            self._set(
                error=f"deadline CLI not found ({dl_how}). Install the Deadline Cloud client or set its path.",
                busy="",
            )
            return False
        if need_pai and not self.pai:
            self._set(
                error=f"deadline-physical-ai not found ({pai_how}); needed to list jobs and outputs.",
                busy="",
            )
            return False
        return True

    # -- farm / queue --
    def refresh(self) -> None:
        """Defaults from the Deadline Cloud config, then the farms and queues by name."""
        if not self._tools_ok(False):
            return
        gen = self._bump("refresh", "farms", "queues", "jobs")
        self._set(busy="Reading the default farm and queue...", error="")
        pending: dict = {"farm_id": None, "queue_id": None}

        def got(key):
            def done(r: cb.Result):
                if self._stale("refresh", gen):
                    return
                pending[key] = (
                    r.stdout.strip().splitlines()[-1].strip() if r.ok and r.stdout.strip() else ""
                )
                if all(v is not None for v in pending.values()):
                    self.s.default_farm, self.s.default_queue = (
                        pending["farm_id"],
                        pending["queue_id"],
                    )
                    self.s.target.farm_id = self.s.target.farm_id or self.s.default_farm
                    self.s.target.queue_id = self.s.target.queue_id or self.s.default_queue
                    self.list_farms()

            return done

        self.runner(cb.config_get_argv(self.deadline, "defaults.farm_id"), got("farm_id"))
        self.runner(cb.config_get_argv(self.deadline, "defaults.queue_id"), got("queue_id"))

    def list_farms(self) -> None:
        gen = self._bump("farms", "queues", "jobs")
        self._set(busy="Listing farms...", error="")

        def done(r: cb.Result):
            if self._stale("farms", gen):
                return
            farms = cb.parse_yaml_list(r.stdout, "farmId") if r.ok else []
            if not r.ok:
                self._set(busy="", error="deadline farm list failed: " + r.error())
                return
            if not farms:
                self._set(
                    busy="",
                    farms=[],
                    error="No farms visible with these credentials. Sign in with Deadline "
                    "Cloud Monitor or set a profile in deadline config gui.",
                )
                return
            ids = [f["id"] for f in farms]
            if self.s.target.farm_id not in ids:
                self.s.target.farm_id = ids[0]
            self.s.target.region = next(
                f["region"] for f in farms if f["id"] == self.s.target.farm_id
            )
            self._set(busy="", farms=farms)
            self.list_queues()

        self.runner(cb.farm_list_argv(self.deadline, self.s.target), done)

    def list_queues(self) -> None:
        gen = self._bump("queues", "jobs")
        self._set(busy="Listing queues...", error="", queues=[], jobs=[], jobs_next_offset=None)

        def done(r: cb.Result):
            if self._stale("queues", gen):
                return
            if not r.ok:
                self._set(busy="", error="deadline queue list failed: " + r.error())
                return
            queues = cb.parse_yaml_list(r.stdout, "queueId")
            ids = [q["id"] for q in queues]
            if self.s.target.queue_id not in ids:
                self.s.target.queue_id = ids[0] if ids else ""
            self._set(busy="", queues=queues)
            if self.s.target.queue_id:
                self.list_jobs()

        self.runner(cb.queue_list_argv(self.deadline, self.s.target), done)

    def select_farm(self, farm_id: str) -> None:
        if farm_id == self.s.target.farm_id:
            return
        f = next((x for x in self.s.farms if x["id"] == farm_id), None)
        self.s.target.farm_id, self.s.target.queue_id = farm_id, ""
        self.s.target.region = f["region"] if f else ""
        self._bump("outputs")
        self.s.job_id, self.s.job, self.s.checked, self.s.compare_id = "", {}, set(), ""
        self.list_queues()

    def select_queue(self, queue_id: str) -> None:
        if queue_id == self.s.target.queue_id:
            return
        self.s.target.queue_id = queue_id
        self._bump("outputs")
        self.s.job_id, self.s.job, self.s.checked, self.s.jobs = "", {}, set(), []
        self.s.compare_id = ""
        self.list_jobs()

    def set_default(self) -> None:
        """Make the selected farm and queue the Deadline Cloud defaults (also used by the
        submit dialog and every other Deadline Cloud tool on this machine)."""
        # Copy the ids now: the live target changes if another farm is picked meanwhile.
        farm_id, queue_id = self.s.target.farm_id, self.s.target.queue_id
        if not (farm_id and queue_id):
            self._set(error="Pick a farm and a queue first.")
            return
        done_n = {"n": 0}

        def done(r: cb.Result):
            if not r.ok:
                self._set(error="deadline config set failed: " + r.error())
                return
            done_n["n"] += 1
            if done_n["n"] == 2:
                self.s.default_farm, self.s.default_queue = farm_id, queue_id
                self._set(status="Saved as the default farm and queue.")

        self.runner(cb.config_set_argv(self.deadline, "defaults.farm_id", farm_id), done)
        self.runner(cb.config_set_argv(self.deadline, "defaults.queue_id", queue_id), done)

    def set_job_status(self, status: str) -> None:
        """List finished jobs with another status (a ``JOB_STATUSES`` value)."""
        if status == self.s.job_status or status not in dict(JOB_STATUSES):
            return
        self.s.job_status = status
        self._bump("outputs")
        self.s.job_id, self.s.job, self.s.checked, self.s.jobs = "", {}, set(), []
        self.s.jobs_next_offset, self.s.compare_id = None, ""
        if self.s.target.queue_id:
            self.list_jobs()
        else:
            self._set()

    def list_jobs(self, more: bool = False) -> None:
        """The newest page of finished jobs with the chosen status, or with ``more`` the
        next page appended."""
        if more and self.s.jobs_next_offset is None:
            return
        if not self._tools_ok(True):
            return
        offset = self.s.jobs_next_offset if more else 0
        gen = self._bump("jobs")  # a newer listing (or a farm/queue switch) drops this one
        self._set(busy="Loading more jobs..." if more else "Listing jobs...", error="")

        def done(r: cb.Result):
            if self._stale("jobs", gen):
                return
            j = r.json()
            if not r.ok or j.get("status") == "error":
                self._set(busy="", error="Could not list jobs: " + r.error())
                return
            page = [x for x in j.get("jobs") or [] if isinstance(x, dict) and x.get("jobId")]
            seen = {x["jobId"] for x in self.s.jobs} if more else set()
            jobs = (self.s.jobs if more else []) + [x for x in page if x["jobId"] not in seen]
            total = int(j.get("total") or len(jobs))
            nxt = j.get("next_offset")
            self._set(
                busy="",
                jobs=jobs,
                jobs_total=total,
                jobs_next_offset=nxt if isinstance(nxt, int) else None,
                status=f"{len(jobs)} of {total} {job_status_label(status).lower()} jobs",
            )

        status = self.s.job_status
        argv = cb.finished_jobs_argv(self.pai, self.s.target, status, offset=offset or 0)
        self.runner(argv, done)

    # -- one job --
    def select_job(self, job_id: str) -> None:
        if not self._tools_ok(True):
            return
        gen = self._bump("outputs")
        self._set(
            job_id=job_id, job={}, checked=set(), busy="Reading the job's outputs...", error=""
        )
        self._load_params(job_id, self.s.compare_id)

        def done(r: cb.Result):
            if self._stale("outputs", gen) or job_id != self.s.job_id:
                return
            j = r.json()
            if not r.ok or j.get("status") == "error":
                self._set(busy="", error="Could not list outputs: " + r.error())
                return
            n = len(j.get("items") or [])
            self._set(
                busy="",
                job=j,
                status=f"{n} loadable items in {j.get('file_count', 0)} output files",
            )

        self.runner(cb.outputs_list_argv(self.pai, self.s.target, job_id), done)

    def set_compare(self, job_id: str) -> None:
        """Diff the selected job's parameters against ``job_id`` ("" to stop comparing)."""
        if job_id == self.s.job_id:
            job_id = ""
        if job_id == self.s.compare_id:
            return
        self._set(compare_id=job_id)
        self._load_params(self.s.job_id, job_id)

    def _load_params(self, *job_ids: str) -> None:
        """Read parameters for the jobs not read yet. A job's parameters never change, so
        each job is read once per session."""
        want = [j for j in dict.fromkeys(job_ids) if j and j not in self.s.params]
        if not want:
            self._set(params_error="")
            return
        self._set(params_error="")

        # No staleness check: parameters are cached by job ID, so every reply is still
        # useful, and overlapping reads (pick a job, then a second one) must both land.
        def done(r: cb.Result):
            j = r.json()
            if not r.ok or j.get("status") == "error":
                self._set(params_error="Could not read job parameters: " + r.error())
                return
            got = dict(self.s.params)
            for job in j.get("jobs") or []:
                if isinstance(job, dict) and isinstance(job.get("parameters"), dict):
                    got[str(job.get("job_id"))] = {
                        str(k): str(v) for k, v in job["parameters"].items()
                    }
            self._set(params=got)

        self.runner(cb.job_params_argv(self.pai, self.s.target, want), done)

    def can_resubmit(self) -> bool:
        return bool(self.s.job_id) and self.s.job_id in self.s.params

    def resubmit(self) -> None:
        """Hand the selected job's name and parameters to Submit (``on_resubmit``)."""
        if not self.can_resubmit():
            return
        name = next((j["name"] for j in self.s.jobs if j["jobId"] == self.s.job_id), "")
        self.on_resubmit(
            {
                "job_id": self.s.job_id,
                "name": name,
                "parameters": dict(self.s.params[self.s.job_id]),
            }
        )

    def parameter_rows(self) -> list:
        """Rows for the parameters table (see :func:`parameter_rows`); ``[]`` while loading."""
        mine = self.s.params.get(self.s.job_id)
        if mine is None:
            return []
        if not self.s.compare_id:
            return parameter_rows(mine)
        other = self.s.params.get(self.s.compare_id)
        return [] if other is None else parameter_rows(mine, other)

    def visible_items(self) -> list:
        items = self.s.job.get("items") or []
        return [i for i in items if not self.s.kind_filter or i["kind"] == self.s.kind_filter]

    def kind_counts(self) -> dict:
        out: dict = {}
        for i in self.s.job.get("items") or []:
            out[i["kind"]] = out.get(i["kind"], 0) + 1
        return out

    def set_kind_filter(self, kind: str) -> None:
        self._set(kind_filter=kind)

    def fetched_path(self, path: str) -> str:
        """Where this session downloaded ``path`` of the selected job ("" if it has not)."""
        return self.s.fetched.get((self.s.job_id, path), "")

    def can_load(self) -> bool:
        """Load / Submit-with is clickable: items ticked, nothing listing or downloading."""
        return bool(self.s.job_id and self.s.checked) and not (self.s.busy or self.s.download)

    def toggle(self, path: str, value: bool) -> None:
        # No redraw: the checkbox already shows the new value, and rebuilding the view
        # from inside that checkbox's own callback would destroy the widget mid-event.
        (self.s.checked.add if value else self.s.checked.discard)(path)

    def checked_inputs(self) -> list:
        """The ticked items that are inputs for a next job (datasets, checkpoints)."""
        items = {i["path"]: i for i in self.s.job.get("items") or []}
        return [
            items[p]
            for p in sorted(self.s.checked)
            if p in items and items[p]["kind"] in INPUT_KINDS
        ]

    def load_checked(self, submit: bool = False) -> None:
        """Download the ticked items (files already downloaded this session are reused)
        and hand them to the view; with ``submit``, then open Submit pipeline job with
        the ticked datasets or checkpoints as the next job's inputs.

        The job is captured now: if the user picks another job before the download
        ends, the files are still recorded for this job (SESSION, ``fetched``), but not
        shown or opened under the other one."""
        if self.s.download:
            return
        paths = sorted(self.s.checked)
        if not paths:
            self._set(error="Tick at least one item to load.")
            return
        job_id, job = self.s.job_id, self.s.job
        items = {i["path"]: i for i in job.get("items") or []}

        def finish(local: dict, where: str, note: str = "") -> None:
            loaded = [
                dict(items[p], local_path=local[p]) for p in paths if p in local and p in items
            ]
            SESSION.add(loaded, job_id)
            if loaded:
                # The job the next submit's "previous job" parameter names: the one whose
                # items are on disk, not whichever job the outputs list is showing.
                st.set_str(st.LAST_LOADED_JOB, job_id)
            if job_id != self.s.job_id:
                self._set(
                    download="",
                    status=f"Downloaded {len(loaded)} item(s) of the previously selected job{where}",
                )
                return
            self.s.checked = set()  # done: the button goes back to "Download selected"
            self._set(download="", error=note, status=f"Loaded {len(loaded)} item(s){where}")
            self.on_loaded(loaded, job)
            inputs = [x for x in loaded if x["kind"] in INPUT_KINDS]
            if submit and inputs:
                self.on_submit_with(inputs)

        have = {
            p: self.s.fetched[(job_id, p)]
            for p in paths
            if os.path.exists(self.s.fetched.get((job_id, p), ""))
        }
        if len(have) == len(paths):
            finish(have, " (already downloaded)")
            return
        dest = st.get_str(st.DOWNLOAD_DIR)
        dest = os.path.join(os.path.expanduser(dest), job_id) if dest else ""
        label = f"Downloading {len(paths)} item(s)"
        self._set(download=label + "...", error="")

        def moved(p: dict) -> None:
            self._set(download=f"{label}: {cb.format_progress(p)}")

        def done(r: cb.Result):
            j = r.json()
            if not r.ok or j.get("status") == "error":
                self._set(download="", error="Download failed: " + r.error())
                return
            reported = j.get("items")
            if not isinstance(reported, dict):
                self._set(
                    download="",
                    error="Download failed: unexpected reply from deadline-physical-ai "
                    f"(items: {type(reported).__name__}); missing {', '.join(paths)}",
                )
                return
            # Only what the tool says it downloaded and what is really on disk counts.
            local = {
                p: v
                for p, v in reported.items()
                if p in items and isinstance(v, str) and os.path.exists(v)
            }
            for p, v in local.items():
                self.s.fetched[(job_id, p)] = v
            missing = [
                str(m) for m in (j.get("missing") or []) if isinstance(j.get("missing"), list)
            ]
            missing += [p for p in paths if p not in local and p not in missing]
            note = (
                f"{len(missing)} item(s) were not downloaded: {', '.join(missing)}"
                if missing
                else ""
            )
            finish(local, f" to {j.get('dest', '')}", note)

        self.runner(
            cb.outputs_fetch_argv(self.pai, self.s.target, job_id, paths, dest),
            done,
            timeout_s=3600,
            on_progress=moved,
        )  # a dataset can be gigabytes


# ---------------------------------------------------------------- Evaluations --

#: Parameters left out of the comparison columns: they differ for every job by design.
EVAL_SKIP_PARAMS = ("OutputDir",)


def fmt_rate(value: Any) -> str:
    return f"{value * 100:.1f}%" if isinstance(value, (int, float)) else ""


def fmt_ci(ci: Any) -> str:
    if isinstance(ci, (list, tuple)) and len(ci) == 2:
        return f"{ci[0] * 100:.0f} to {ci[1] * 100:.0f}%"
    return ""


@dataclass
class EvalState:
    jobs: list = field(default_factory=list)  # ``jobs evals`` rows, with or without "eval"
    next_offset: int | None = None
    total: int = 0
    busy: str = ""
    error: str = ""
    status: str = ""
    key: tuple = ()  # (farm, queue) the rows were read from


class EvalController:
    """Eval summaries across the queue chosen above the tabs (``target()``)."""

    def __init__(self, runner, on_change=lambda: None, target=cb.Target):
        self.runner, self.on_change, self.target = runner, on_change, target
        self.s = EvalState()
        self._gen = 0

    def _set(self, **kw) -> None:
        for k, v in kw.items():
            setattr(self.s, k, v)
        self.on_change()

    def stale(self) -> bool:
        """The rows are from another farm or queue than the one now chosen."""
        t = self.target()
        return self.s.key != (t.farm_id, t.queue_id)

    def load(self, more: bool = False) -> None:
        if more and self.s.next_offset is None:
            return
        t = self.target()
        if not (t.farm_id and t.queue_id):
            self._set(error="Pick a farm and queue first.")
            return
        _dl, _how, pai, pai_how = _tools()
        if not pai:
            self._set(error=f"deadline-physical-ai not found ({pai_how}).")
            return
        offset = self.s.next_offset if more else 0
        self._gen += 1
        gen, key = self._gen, (t.farm_id, t.queue_id)
        self._set(busy="Reading eval summaries...", error="", status="")
        if not more:
            self.s.jobs, self.s.key = [], key

        def done(r: cb.Result):
            if gen != self._gen:
                return
            j = r.json()
            if not r.ok or j.get("status") == "error":
                self._set(busy="", error="Could not read eval summaries: " + r.error())
                return
            page = [x for x in j.get("jobs") or [] if isinstance(x, dict) and x.get("jobId")]
            seen = {x["jobId"] for x in self.s.jobs}
            jobs = self.s.jobs + [x for x in page if x["jobId"] not in seen]
            nxt = j.get("next_offset")
            n = sum(1 for x in jobs if x.get("eval"))
            self._set(
                busy="",
                jobs=jobs,
                key=key,
                total=int(j.get("total") or len(jobs)),
                next_offset=nxt if isinstance(nxt, int) else None,
                status=f"{n} of {len(jobs)} completed jobs read have an eval summary",
            )

        self.runner(cb.job_evals_argv(pai, t, offset=offset or 0), done, timeout_s=None)

    def rows(self) -> list:
        """Jobs that have an eval summary."""
        return [x for x in self.s.jobs if isinstance(x.get("eval"), dict)]

    def varying_params(self) -> list:
        """Parameter names whose values differ between the jobs with an eval summary."""
        rows = self.rows()
        names = sorted({k for r in rows for k in (r.get("parameters") or {})})
        return [
            k
            for k in names
            if k not in EVAL_SKIP_PARAMS
            and len({(r.get("parameters") or {}).get(k) for r in rows}) > 1
        ]

    def metric_names(self) -> list:
        return sorted({k for r in self.rows() for k in (r["eval"].get("metrics") or {})})

    def table(self) -> tuple:
        """``(headers, rows)``: each row a list of ``(text, sort key)``."""
        params, metrics = self.varying_params(), self.metric_names()
        headers = ["Job", "Success", "95% CI", "Episodes", "Checkpoint", "Finished"]
        headers += params + metrics
        out = []
        for r in self.rows():
            e, p = r["eval"], r.get("parameters") or {}
            rate = e.get("success_rate")
            row = [
                (r.get("name") or r["jobId"], (r.get("name") or "").lower()),
                (fmt_rate(rate), rate if isinstance(rate, (int, float)) else -1.0),
                (fmt_ci(e.get("ci95")), (e.get("ci95") or [-1.0])[0]),
                (str(e.get("episodes", "")), e.get("episodes", -1)),
                (str(e.get("checkpoint", "")), str(e.get("checkpoint", ""))),
                (format_time(str(r.get("endedAt") or "")), str(r.get("endedAt") or "")),
            ]
            for k in params:
                v = str(p.get(k, ""))
                row.append((v, _sort_key(v)))
            for k in metrics:
                m = (e.get("metrics") or {}).get(k)
                row.append(("" if m is None else f"{m:g}", m if m is not None else float("-inf")))
            out.append(row)
        return headers, out

    def write_csv(self, path: str) -> int:
        """Every job with an eval summary, one row each, with all of its parameters; returns
        the number of rows."""
        import csv

        rows = self.rows()
        params = sorted({k for r in rows for k in (r.get("parameters") or {})})
        metrics = self.metric_names()
        conds = sorted({c for r in rows for c in (r["eval"].get("by_condition") or {})})
        with open(path, "w", newline="", encoding="utf-8") as fh:
            w = csv.writer(fh)
            w.writerow(
                ["job_id", "name", "ended_at", "episodes", "successes", "success_rate"]
                + ["ci95_low", "ci95_high", "checkpoint"]
                + [f"metric.{m}" for m in metrics]
                + [f"condition.{c}.success_rate" for c in conds]
                + [f"param.{k}" for k in params]
            )
            for r in rows:
                e, p = r["eval"], r.get("parameters") or {}
                ci = e.get("ci95") or ["", ""]
                by = e.get("by_condition") or {}
                w.writerow(
                    [r["jobId"], r.get("name", ""), r.get("endedAt", "")]
                    + [e.get("episodes", ""), e.get("successes", ""), e.get("success_rate", "")]
                    + [ci[0], ci[1], e.get("checkpoint", "")]
                    + [(e.get("metrics") or {}).get(m, "") for m in metrics]
                    + [(by.get(c) or {}).get("success_rate", "") for c in conds]
                    + [p.get(k, "") for k in params]
                )
        return len(rows)


def _sort_key(text: str) -> Any:
    """Numbers sort as numbers, before text."""
    try:
        return (0, float(text), "")
    except ValueError:
        return (1, 0.0, text.lower())


# --------------------------------------------------------------- Replay setup --

#: Replay roles (protocol names), their labels and whether a replay needs them.
REPLAY_ROLE_LABELS = (
    ("robot", "Robot", True),
    ("object", "Object", False),
    ("reference", "Reference", False),
)
_ROLE_LABEL = {role: label for role, label, _ in REPLAY_ROLE_LABELS}
_ROLE_NEEDED = {role: needed for role, _, needed in REPLAY_ROLE_LABELS}


@dataclass
class ReplayPrimsState:
    prims: dict = field(default_factory=dict)  # role -> prim path in Isaac Sim's settings
    exists: dict = field(default_factory=dict)  # role -> found in the open stage
    loaded: bool = False  # Isaac Sim has answered at least once
    busy: str = ""
    error: str = ""
    status: str = ""


class ReplayPrimsController:
    """The robot, object and reference prims replay uses, kept in Isaac Sim's persistent
    settings. ``request(type, callback, **fields)`` is the Kit link's (``None`` standalone)."""

    def __init__(self, request=None, on_change=lambda: None):
        self.request, self.on_change = request, on_change
        self.s = ReplayPrimsState()

    def _set(self, **kw) -> None:
        for k, v in kw.items():
            setattr(self.s, k, v)
        self.on_change()

    def _apply(self, r: dict, status: str = "") -> None:
        if not r.get("ok"):
            self._set(busy="", error=str(r.get("message") or "Isaac Sim did not answer."))
            return
        prims, exists = r.get("prims"), r.get("exists")
        self._set(
            busy="",
            error="",
            loaded=True,
            prims={k: str(v) for k, v in (prims or {}).items()} if isinstance(prims, dict) else {},
            exists=(
                {k: bool(v) for k, v in (exists or {}).items()} if isinstance(exists, dict) else {}
            ),
            status=status,
        )

    def refresh(self) -> None:
        """Read the prims from Isaac Sim and whether the open stage has them."""
        if self.request is None:
            return
        self._set(busy="Reading replay prims...")
        self.request(pr.GET_REPLAY_PRIMS, self._apply)

    def set_prim(self, role: str, path: str) -> None:
        """Save ``path`` ("" for none) as ``role``'s prim in Isaac Sim."""
        path = path.strip()
        if self.request is None or role not in pr.REPLAY_ROLES:
            return
        if path == self.s.prims.get(role, ""):
            return
        if not pr.valid_prim_path(path):
            self._set(error=f"{path!r} is not an absolute prim path such as /World/Robot.")
            return
        label = _ROLE_LABEL[role]
        self._set(busy="Saving replay prims...", error="")
        self.request(
            pr.SET_REPLAY_PRIMS,
            lambda r: self._apply(
                r,
                (
                    f"{label} prim saved in Isaac Sim; the next trajectory loaded uses it."
                    if r.get("ok")
                    else ""
                ),
            ),
            prims={role: path},
        )

    def use_selection(self, role: str) -> None:
        """Set ``role`` to the one prim selected in Isaac Sim."""
        if self.request is None:
            return

        def got(r: dict) -> None:
            paths = r.get("paths") if r.get("ok") else None
            if not isinstance(paths, list):
                self._set(busy="", error=str(r.get("message") or "Isaac Sim did not answer."))
                return
            if len(paths) != 1:
                self._set(
                    busy="",
                    error=(
                        "Select one prim in Isaac Sim's stage first."
                        if not paths
                        else f"{len(paths)} prims are selected in Isaac Sim; select one."
                    ),
                )
                return
            self.s.busy = ""
            self.set_prim(role, str(paths[0]))

        self._set(busy="Reading the selection...", error="")
        self.request(pr.GET_SELECTION, got)

    def note(self, role: str) -> str:
        """Short state of one role: found, missing from the stage, or not set."""
        path = self.s.prims.get(role, "")
        if not self.s.loaded:
            return ""
        if not path:
            return "Not set: replay needs it" if _ROLE_NEEDED[role] else "Not set (optional)"
        if not self.s.exists.get(role):
            return "Not in the open stage"
        other = {"object": "reference", "reference": "object"}.get(role)
        if other and not self.s.prims.get(other):
            return f"Found; set {other.title()} too to place the object"
        return "Found in the stage"


# --------------------------------------------------------------------- Submit --


@dataclass
class SubmitState:
    bundles: list = field(default_factory=list)
    selected: str = ""  # bundle path
    prefill: dict = field(default_factory=dict)
    status: str = ""
    error: str = ""
    busy: str = ""
    last_job_id: str = ""
    #: "Resubmit with changes": ``{job_id, name, parameters}`` of the job being resubmitted.
    #: Its values prefill the selected bundle (over the inferred ones) until cleared.
    resubmit: dict = field(default_factory=dict)
    #: The open Isaac Sim stage's file from the last ``get_stage`` reply ("" when unsaved,
    #: standalone, or not answered yet). Asked for again on every select and submit.
    stage: str = ""
    #: A ``get_stage`` reply has arrived for the current selection.
    stage_checked: bool = False


class SubmitController:
    """``fetch_stage(callback)`` asks the connected Isaac Sim for its stage's file and calls
    ``callback(path)`` ("" for none or no answer); ``None`` when standalone. ``app_version``
    is the connected Isaac Sim's version, ``ext_version`` this package's."""

    def __init__(
        self, runner, on_change=lambda: None, fetch_stage=None, app_version="", ext_version=""
    ):
        self.runner, self.on_change, self.fetch_stage = runner, on_change, fetch_stage
        self.app_version, self.ext_version = app_version, ext_version
        #: ``target()`` -> ``{"target": cb.Target, "default": bool, "farm": name, "queue":
        #: name}`` for the farm and queue chosen in the app, or ``{}`` for the defaults.
        self.target: Any = dict
        self.s = SubmitState()
        # Inputs (a list) or {"resubmit": job} from Job outputs, applied on the next update.
        self._requested: Any = None
        self._skip_show_scan = False
        self._gathered: list = []  # temp folders built for the open dialog
        self._stage_gen = 0
        #: deadline-cloud's own bundle folder and job history folder (``deadline config``),
        #: read once; ``None`` until both replies arrive.
        self.deadline_dirs: dict | None = None
        self._dirs_asked = False
        self._pending_resubmit: dict | None = None  # waits for deadline_dirs
        #: Bundles found only in the job history for a resubmit, kept in the list while
        #: that resubmit is active.
        self._extra: list = []

    def _set(self, **kw) -> None:
        for k, v in kw.items():
            setattr(self.s, k, v)
        self.on_change()

    def folders(self) -> list:
        """The app's bundle folders (setting), editable in the tab."""
        return [f.strip() for f in st.get_str(st.BUNDLE_DIRS).split(";") if f.strip()]

    def search_folders(self) -> list:
        """The app's folders plus deadline-cloud's default job bundle folder."""
        out = self.folders()
        extra = (self.deadline_dirs or {}).get("bundles", "")
        norm = {os.path.normpath(os.path.expanduser(f)) for f in out}
        if extra and os.path.normpath(os.path.expanduser(extra)) not in norm:
            out.append(extra)
        return out

    def _ask_deadline_dirs(self) -> None:
        """Read ``settings.job_bundle_default_directory`` and ``settings.job_history_dir``
        from the deadline config once, then rescan (and finish a waiting resubmit)."""
        if self._dirs_asked:
            return
        deadline, _how = cb.resolve("deadline", st.get_str(st.DEADLINE_EXECUTABLE))
        if not deadline:
            self.deadline_dirs = {}
            return
        self._dirs_asked = True
        got: dict = {}
        keys = {
            "bundles": "settings.job_bundle_default_directory",
            "history": "settings.job_history_dir",
        }

        def reply(name):
            def done(r: cb.Result):
                out = r.stdout.strip()
                got[name] = out.splitlines()[-1].strip() if r.ok and out else ""
                if len(got) == len(keys):
                    self.deadline_dirs = got
                    job, self._pending_resubmit = self._pending_resubmit, None
                    if job is not None:
                        self.resubmit(job)
                    else:
                        self.scan()

            return done

        for name, key in keys.items():
            self.runner(cb.config_get_argv(deadline, key), reply(name))

    def history_bundles(self) -> list:
        """Bundles saved in deadline-cloud's job history (one per submit from this
        machine), newest first."""
        folder = (self.deadline_dirs or {}).get("history", "")
        if not folder:
            return []
        found = bd.discover([folder], max_depth=2)
        return sorted(found, key=lambda b: b.path, reverse=True)

    def set_folders(self, text: str) -> None:
        st.set_str(st.BUNDLE_DIRS, text)
        self.scan()

    def scan(self) -> None:
        self._ask_deadline_dirs()
        found = bd.discover(self.search_folders()) + self._extra
        sel = (
            self.s.selected
            if any(b.path == self.s.selected for b in found)
            else (found[0].path if found else "")
        )
        self._set(
            bundles=found,
            error="" if found else "No job bundles found in: " + "; ".join(self.search_folders()),
            status=f"{len(found)} bundles",
        )
        self.select(sel)

    def on_shown(self) -> None:
        """The pane became visible: rescan, unless it opened for requested inputs.
        ``use_inputs`` rescans itself, and a later plain scan would wipe its selection
        message or error."""
        if self._skip_show_scan:
            self._skip_show_scan = False
            return
        self.scan()

    def request_inputs(self, items: list, opening: bool) -> None:
        """Queue "Submit pipeline job with dataset" inputs for :meth:`apply_requested_inputs`.
        ``opening``: the pane is being shown, so skip the scan that triggers."""
        self._requested = list(items)
        self._skip_show_scan = opening

    def apply_requested_inputs(self) -> None:
        items, self._requested = self._requested, None
        if isinstance(items, dict) and "resubmit" in items:
            self.resubmit(items["resubmit"])
        elif items is not None:
            self.s.resubmit = {}
            self.use_inputs(items)

    def bundle(self):
        return next((b for b in self.s.bundles if b.path == self.s.selected), None)

    def _prefill(self, b, gather: bool) -> dict:
        ds = [x["local_path"] for x in SESSION.of_kind("lerobot")]
        ck = [x["local_path"] for x in SESSION.of_kind("checkpoint")]
        if gather and len(ds) > 1:
            # A fresh folder per submit: the dialog uploads from it while it is open.
            folder = gather_dir(ds)
            self._gathered.append(folder)
            datasets = bd.gather_datasets(ds, folder)
        elif gather:
            datasets = bd.gather_datasets(ds, "")
        else:  # preview: don't build the folder until submit
            datasets = ds[0] if len(ds) == 1 else (f"<{len(ds)} loaded datasets>" if ds else "")
        out = bd.prefill(
            b,
            stage_path=self.s.stage,
            from_job_id=st.get_str(st.LAST_LOADED_JOB),
            datasets=datasets,
            checkpoint=ck[-1] if ck else "",
            several_datasets=len(ds) > 1,
        )
        if self.s.resubmit:
            out.update(bd.resubmit_values(b, self.s.resubmit.get("parameters") or {}))
        return out

    def select(self, path: str) -> None:
        self.s.selected = path
        b = self.bundle()
        self._set(prefill=self._prefill(b, gather=False) if b else {})
        self.refresh_stage()

    def refresh_stage(self, then=None) -> None:
        """Ask the connected Isaac Sim for its stage's file, redo the preview with it, then
        call ``then()``. Standalone: ``then()`` at once. Only the newest request's reply
        counts; the path is never reused for a later submit without asking again."""
        if self.fetch_stage is None:
            self.s.stage, self.s.stage_checked = "", False
            if then is not None:
                then()
            return
        self._stage_gen += 1
        gen = self._stage_gen

        def got(path: str) -> None:
            if gen != self._stage_gen:
                return
            self.s.stage, self.s.stage_checked = str(path or ""), True
            b = self.bundle()
            self._set(prefill=self._prefill(b, gather=False) if b else {})
            if then is not None:
                then()

        self.fetch_stage(got)

    def request_resubmit(self, job: dict, opening: bool) -> None:
        """Queue "Resubmit with changes" for :meth:`apply_requested_inputs`."""
        self._requested = {"resubmit": dict(job)}
        self._skip_show_scan = opening

    def resubmit(self, job: dict) -> None:
        """Rescan, select the bundle the job most likely came from, and prefill the job's
        parameter values. The user changes what they want in the submit dialog."""
        if self.deadline_dirs is None:
            self._pending_resubmit = dict(job)
            self._ask_deadline_dirs()
            if self.deadline_dirs is None:  # replies pending: resubmit() runs again then
                self._set(status="Looking for the job's bundle...", error="")
                return
            self._pending_resubmit = None
        found = bd.discover(self.search_folders())
        params = job.get("parameters") or {}
        name = str(job.get("name") or "")
        pick = bd.match_job(found, name, params)
        self._extra = []
        if pick is None or not set(params) <= {str(p.get("name")) for p in pick.parameters}:
            # Not (fully) in the bundle folders: every gui-submit from this machine saved
            # a copy of its bundle in the job history.
            hist = bd.match_job(self.history_bundles(), name, params)
            if hist is not None and (
                pick is None
                or len(bd.resubmit_values(hist, params)) > len(bd.resubmit_values(pick, params))
            ):
                import dataclasses

                pick = dataclasses.replace(hist, name=f"{hist.name} (job history)")
                self._extra = [pick]
                found = found + self._extra
        self.s.bundles = found
        self.s.resubmit = dict(job)
        if pick is None:
            self._set(
                error="No bundle in your bundle folders or job history defines this job's "
                "parameters. Choose its bundle folder.",
                status="",
            )
            self.select(self.s.selected)
            return
        n = len(bd.resubmit_values(pick, params))
        self.s.error = ""
        self.s.status = (
            f"Resubmitting {job.get('name') or job.get('job_id')}: {pick.name} selected, "
            f"{n} of {len(params)} parameters prefilled."
        )
        self.select(pick.path)

    def clear_resubmit(self) -> None:
        self.s.resubmit = {}
        self._extra = []
        self.scan()

    def add_folder(self, folder: str) -> None:
        """Add a bundle folder (Choose bundle folder...), then rescan, or redo the waiting
        resubmit so it can match in the new folder."""
        if not folder:
            return
        folders = self.folders()
        if folder not in folders:
            folders.append(folder)
        st.set_str(st.BUNDLE_DIRS, ";".join(folders))
        if self.s.resubmit:
            self.resubmit(self.s.resubmit)
        else:
            self.scan()

    def use_inputs(self, items: list) -> None:
        """Called after "Submit pipeline job with dataset": rescan, then select the bundle
        that takes these inputs (the current one if it does, else the first that does)."""
        found = bd.discover(self.search_folders())
        self.s.bundles = found
        kinds = {x["kind"] for x in items}

        def takes(b) -> bool:
            pf = self._prefill(b, gather=False)
            return all(
                any(bd.wants_input(p, INPUT_WORD[k]) and p.get("name") in pf for p in b.parameters)
                for k in kinds
            )

        cur = self.bundle()
        pick = cur if cur is not None and takes(cur) else next((b for b in found if takes(b)), None)
        what = " and ".join(sorted({INPUT_NOUN[k] for k in kinds}))
        if pick is None:
            self._set(
                error=f"No job bundle here takes a {what}; pick one or add its folder.", status=""
            )
            self.select(self.s.selected)
            return
        self.s.error, self.s.status = "", f"{pick.name} selected for the loaded {what}."
        self.select(pick.path)

    def missing_hint(self, name: str) -> str:
        """How to fill a missing input from this app ("" when only the dialog can)."""
        for word in ("dataset", "checkpoint"):
            if word in name.lower():
                return f"select a {word} in Job outputs and press Submit pipeline job with {word}"
        return ""

    def missing_inputs(self) -> list:
        """Dataset and checkpoint input folders of the selected bundle that have neither a
        prefilled value nor a default, e.g. a training bundle's Datasets with nothing loaded."""
        b = self.bundle()
        if b is None:
            return []
        return [
            str(p["name"])
            for p in b.parameters
            if isinstance(p, dict)
            and p.get("type") == "PATH"
            and p.get("dataFlow", "IN") in ("IN", "INOUT")
            and not p.get("default")
            and str(p.get("name")) not in self.s.prefill
            and (bd.wants_input(p, "dataset") or bd.wants_input(p, "checkpoint"))
        ]

    def submit(self) -> None:
        """Open the submit dialog for the selected bundle, after asking the connected Isaac
        Sim for its stage."""
        if self.s.busy:  # a dialog is still running, or the stage is being read
            return
        if self.bundle() is None:
            self._set(error="Pick a job bundle first.")
            return
        if self.fetch_stage is None:
            self._open_dialog()
            return
        self._set(busy="Reading the open stage from Isaac Sim...", error="")

        def then() -> None:
            self.s.busy = ""
            self._open_dialog()

        self.refresh_stage(then)

    def _open_dialog(self) -> None:
        b = self.bundle()
        if b is None:
            self._set(error="Pick a job bundle first.")
            return
        deadline, how = cb.resolve("deadline", st.get_str(st.DEADLINE_EXECUTABLE))
        if not deadline:
            self._set(error=f"deadline CLI not found ({how}).")
            return
        self.s.prefill = self._prefill(b, gather=True)
        gathered, self._gathered = self._gathered, []
        argv = cb.gui_submit_argv(
            deadline,
            b.path,
            self.s.prefill,
            app_version=self.app_version,
            ext_version=self.ext_version,
        )
        self._set(busy="Submit dialog open...", error="")
        info = self.target() or {}
        t = info.get("target")
        config_dir = ""
        env: dict = {}
        if t is not None and t.farm_id and t.queue_id and not info.get("default"):
            # gui-submit has no farm or queue options and opens on the configured defaults,
            # so run it on a copy of the config with the chosen farm and queue as defaults.
            config_dir = tempfile.mkdtemp(prefix="deadline-submit-config-")
            env = {cb.CONFIG_FILE_ENV: cb.copy_deadline_config(config_dir)}

        def done(r: cb.Result):
            import shutil

            for folder in gathered:  # the dialog has closed, so its upload is over
                shutil.rmtree(folder, ignore_errors=True)
            if config_dir:
                shutil.rmtree(config_dir, ignore_errors=True)
            res = cb.parse_submit_result(r.stdout)
            if res.get("status") == "SUBMITTED":
                self._set(
                    busy="",
                    last_job_id=str(res.get("jobId", "")),
                    status=f"Submitted {res.get('jobId', '')}",
                    resubmit={},
                )
            elif res.get("status") == "CANCELED":
                self._set(busy="", status="Submit dialog closed without submitting.")
            else:
                self._set(busy="", error="Submit failed: " + r.error())

        def open_dialog() -> None:  # the dialog stays open as long as the user needs
            if env:
                self.runner(argv, done, timeout_s=None, env_extra=env)
            else:
                self.runner(argv, done, timeout_s=None)

        if not env or t is None:
            open_dialog()
            return
        steps = [
            cb.config_set_argv(deadline, "defaults.farm_id", t.farm_id),
            cb.config_set_argv(deadline, "defaults.queue_id", t.queue_id),
        ]

        def next_step(r: cb.Result | None = None) -> None:
            if r is not None and not r.ok:
                import shutil

                shutil.rmtree(config_dir, ignore_errors=True)
                self._set(busy="", error="Could not select the farm and queue: " + r.error())
                return
            if steps:
                self.runner(steps.pop(0), next_step, env_extra=env)
            else:
                open_dialog()

        next_step()
