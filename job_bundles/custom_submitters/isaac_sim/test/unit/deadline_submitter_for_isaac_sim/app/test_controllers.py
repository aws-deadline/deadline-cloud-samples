# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
import json
import os

from deadline.isaac_sim_submitter.app import cli_backend as cb
from deadline.isaac_sim_submitter.app import controllers as ct
from deadline.isaac_sim_submitter.app import settings as st


class FakeRunner:
    def __init__(self, replies):
        self.replies, self.calls = replies, []

    def __call__(self, argv, on_done, exe="", timeout_s=None, on_progress=None):
        self.calls.append(argv)
        key = " ".join(argv[1:4])
        out, code = self.replies.get(key, ("", 0))
        on_done(cb.Result(argv, code, out, ""))


def test_load_flow(monkeypatch, tmp_path):
    monkeypatch.setattr(ct, "_tools", lambda: ("deadline", "PATH", "pai", "PATH"))
    st.set_str(st.DOWNLOAD_DIR, str(tmp_path))
    local = tmp_path / "job-1" / "ep_003.trajectory.npz"
    local.parent.mkdir()
    local.write_bytes(b"npz")
    listing = {
        "job_id": "job-1",
        "file_count": 9,
        "eval_summary": {"episodes": 56, "successes": 12},
        "items": [
            {
                "kind": "trajectory",
                "path": "evaluate/ep_003.trajectory.npz",
                "label": "x",
                "meta": {},
            },
            {"kind": "video", "path": "evaluate/a.mp4", "label": "a", "meta": {}},
        ],
    }
    runner = FakeRunner(
        {
            "config get defaults.farm_id": ("farm-1\n", 0),
            "config get defaults.queue_id": ("queue-1\n", 0),
            "farm list": (
                (
                    "INFO: x\n- region: us-west-2\n  farmId: farm-1\n  displayName: Zeta\n"
                    "- region: us-east-1\n  farmId: farm-0\n  displayName: Alpha\n"
                ),
                0,
            ),
            "queue list --farm-id": (
                "- queueId: queue-1\n  displayName: GPU\n- queueId: queue-2\n  displayName: CPU\n",
                0,
            ),
            "jobs list --farm-id": (
                json.dumps(
                    {
                        "jobs": [{"name": "n", "jobId": "job-1", "endedAt": "x"}],
                        "total": 1,
                        "next_offset": None,
                    }
                ),
                0,
            ),
            "outputs list job-1": (json.dumps(listing), 0),
            "outputs fetch job-1": (
                json.dumps(
                    {
                        "dest": str(tmp_path / "job-1"),
                        "items": {"evaluate/ep_003.trajectory.npz": str(local)},
                    }
                ),
                0,
            ),
        }
    )
    loaded = []
    c = ct.LoadController(runner, on_loaded=lambda items, job: loaded.extend(items))
    c.refresh()
    assert c.s.target.farm_id == "farm-1" and c.s.target.region == "us-west-2"
    assert [f["name"] for f in c.s.farms] == ["Alpha", "Zeta"] and [
        q["name"] for q in c.s.queues
    ] == ["CPU", "GPU"]
    assert [j["jobId"] for j in c.s.jobs] == ["job-1"]
    assert "--region" in runner.calls[-1] and "us-west-2" in runner.calls[-1]
    c.select_job("job-1")
    # Listing a job's outputs is not loading them: nothing is remembered as loaded yet.
    assert c.kind_counts() == {"trajectory": 1, "video": 1}
    assert st.get_str(st.LAST_LOADED_JOB) == ""
    c.set_kind_filter("video")
    assert [i["kind"] for i in c.visible_items()] == ["video"]
    c.toggle("evaluate/ep_003.trajectory.npz", True)
    c.load_checked()
    assert loaded[0]["local_path"] == str(local) and not c.s.error and not c.s.download
    assert st.get_str(st.LAST_LOADED_JOB) == "job-1"
    fetch = runner.calls[-1]
    assert fetch[:3] == ["pai", "outputs", "fetch"] and "--progress" in fetch
    assert fetch[fetch.index("--path") + 1] == "evaluate/ep_003.trajectory.npz"
    assert fetch[fetch.index("--dest") + 1] == str(tmp_path / "job-1")
    assert [(x["job_id"], x["kind"], x["local_path"]) for x in ct.SESSION.loaded] == [
        ("job-1", "trajectory", str(local))
    ]
    assert c.s.checked == set() and c.fetched_path("evaluate/ep_003.trajectory.npz") == str(local)


def test_load_errors(monkeypatch):
    monkeypatch.setattr(ct, "_tools", lambda: ("deadline", "PATH", "", "not found"))
    c = ct.LoadController(FakeRunner({}))
    c.select_job("job-1")
    assert "deadline-physical-ai not found" in c.s.error
    monkeypatch.setattr(ct, "_tools", lambda: ("deadline", "PATH", "pai", "PATH"))
    c = ct.LoadController(
        FakeRunner(
            {
                "config get defaults.farm_id": ("", 0),
                "config get defaults.queue_id": ("", 0),
                "farm list": ("", 0),
            }
        )
    )
    c.refresh()
    assert "No farms visible" in c.s.error
    c.load_checked()
    assert "Tick at least one" in c.s.error


def test_switch_farm_and_set_default(monkeypatch):
    monkeypatch.setattr(ct, "_tools", lambda: ("deadline", "PATH", "pai", "PATH"))
    runner = FakeRunner(
        {
            "config get defaults.farm_id": ("farm-1\n", 0),
            "config get defaults.queue_id": ("queue-1\n", 0),
            "farm list": (
                (
                    "- region: us-west-2\n  farmId: farm-1\n  displayName: A\n"
                    "- region: us-east-2\n  farmId: farm-2\n  displayName: B\n"
                ),
                0,
            ),
            "queue list --farm-id": ("- queueId: queue-9\n  displayName: Q\n", 0),
        }
    )
    c = ct.LoadController(runner)
    c.refresh()
    c.select_farm("farm-2")
    assert c.s.target.region == "us-east-2" and c.s.target.queue_id == "queue-9"
    c.set_default()
    sets = [a for a in runner.calls if a[1:3] == ["config", "set"]]
    assert sets == [
        ["deadline", "config", "set", "defaults.farm_id", "farm-2"],
        ["deadline", "config", "set", "defaults.queue_id", "queue-9"],
    ]
    assert c.s.default_farm == "farm-2" and "Saved" in c.s.status


def test_farm_list_credentials_error(monkeypatch):
    monkeypatch.setattr(ct, "_tools", lambda: ("deadline", "PATH", "pai", "PATH"))
    runner = FakeRunner(
        {"config get defaults.farm_id": ("", 0), "config get defaults.queue_id": ("", 0)}
    )
    runner.replies["farm list"] = ("", 1)
    c = ct.LoadController(runner)
    orig = runner.__call__

    def call(argv, on_done, exe="", timeout_s=None):
        if argv[1:3] == ["farm", "list"]:
            on_done(
                cb.Result(
                    argv,
                    1,
                    "",
                    "botocore.exceptions.NoCredentialsError: Unable to locate credentials",
                )
            )
        else:
            orig(argv, on_done, exe, timeout_s)

    c.runner = call
    c.refresh()
    assert c.s.busy == "" and "No AWS credentials" in c.s.error


def test_format_time():
    assert ct.format_time("") == ""
    out = ct.format_time("2026-11-11 19:38:05.894000+00:00")
    assert out.startswith("Nov 1") and ":" in out


class PagedRunner(FakeRunner):
    """Answers ``jobs list`` by its ``--offset`` (default 0)."""

    def __init__(self, replies, pages):
        super().__init__(replies)
        self.pages = pages

    def __call__(self, argv, on_done, exe="", timeout_s=None, on_progress=None):
        if argv[1:3] == ["jobs", "list"]:
            self.calls.append(argv)
            offset = int(argv[argv.index("--offset") + 1]) if "--offset" in argv else 0
            on_done(cb.Result(argv, 0, json.dumps(self.pages[offset]), ""))
            return
        super().__call__(argv, on_done, exe, timeout_s, on_progress)


def test_finished_jobs_load_page_by_page(monkeypatch):
    monkeypatch.setattr(ct, "_tools", lambda: ("deadline", "PATH", "pai", "PATH"))
    job = lambda i: {"name": f"j{i}", "jobId": f"job-{i}", "endedAt": "x"}
    pages = {
        0: {"jobs": [job(1), job(2)], "total": 3, "next_offset": 2},
        2: {"jobs": [job(2), job(3)], "total": 3, "next_offset": None},  # job-2 repeats
    }
    runner = PagedRunner(
        {
            "config get defaults.farm_id": ("farm-1\n", 0),
            "config get defaults.queue_id": ("queue-1\n", 0),
            "farm list": ("- region: us-west-2\n  farmId: farm-1\n  displayName: A\n", 0),
            "queue list --farm-id": ("- queueId: queue-1\n  displayName: Q\n", 0),
        },
        pages,
    )
    c = ct.LoadController(runner)
    c.refresh()
    assert [j["jobId"] for j in c.s.jobs] == ["job-1", "job-2"]
    assert c.s.jobs_next_offset == 2 and c.s.jobs_total == 3
    c.list_jobs(more=True)
    assert runner.calls[-1][-2:] == ["--offset", "2"]
    assert [j["jobId"] for j in c.s.jobs] == ["job-1", "job-2", "job-3"]
    assert c.s.jobs_next_offset is None and "3 of 3" in c.s.status
    n = len(runner.calls)
    c.list_jobs(more=True)  # nothing more to load
    assert len(runner.calls) == n


def _dataset_runner(local_dir):
    listing = {
        "job_id": "job-2",
        "file_count": 3,
        "items": [
            {
                "kind": "lerobot",
                "path": "generate/dataset",
                "label": "generate dataset",
                "meta": {},
            },
            {"kind": "lerobot", "path": "collect/dataset", "label": "collect dataset", "meta": {}},
        ],
    }
    return FakeRunner(
        {
            "outputs list job-2": (json.dumps(listing), 0),
            "outputs fetch job-2": (
                json.dumps({"dest": str(local_dir), "items": {"generate/dataset": str(local_dir)}}),
                0,
            ),
        }
    )


def test_submit_with_dataset_clears_selection_and_reuses_download(monkeypatch, tmp_path):
    monkeypatch.setattr(ct, "_tools", lambda: ("deadline", "PATH", "pai", "PATH"))
    runner = _dataset_runner(tmp_path)
    handed: list = []
    c = ct.LoadController(runner, on_submit_with=handed.append)
    c.select_job("job-2")
    c.toggle("generate/dataset", True)
    assert [i["path"] for i in c.checked_inputs()] == ["generate/dataset"]
    c.load_checked(submit=True)
    assert (
        not c.s.checked and not c.s.error and handed and handed[0][0]["local_path"] == str(tmp_path)
    )
    n_fetch = sum(1 for a in runner.calls if a[1:3] == ["outputs", "fetch"])
    # Again: no second download (it used to fail with "file already exists").
    c.toggle("generate/dataset", True)
    c.load_checked(submit=True)
    assert sum(1 for a in runner.calls if a[1:3] == ["outputs", "fetch"]) == n_fetch
    assert "already downloaded" in c.s.status and len(handed) == 2
    # Re-reading the same job keeps what was downloaded.
    c.select_job("job-2")
    assert c.fetched_path("generate/dataset") == str(tmp_path)


def test_session_latest_datasets_replace_earlier():
    s = ct.Session()
    s.add(
        [{"kind": "lerobot", "local_path": "/a"}, {"kind": "trajectory", "local_path": "/t"}],
        "job-1",
    )
    s.add([{"kind": "lerobot", "local_path": "/b"}], "job-2")
    assert s.loaded == [
        {"kind": "trajectory", "local_path": "/t", "job_id": "job-1"},
        {"kind": "lerobot", "local_path": "/b", "job_id": "job-2"},
    ]


def test_session_add_matrix():
    s = ct.Session()
    s.add(
        [{"kind": "lerobot", "local_path": "/a"}, {"kind": "lerobot", "local_path": "/b"}], "job-1"
    )
    assert [x["local_path"] for x in s.of_kind("lerobot")] == [
        "/a",
        "/b",
    ]  # loaded together: both kept
    s.add([{"kind": "trajectory", "local_path": "/t"}], "job-2")
    assert [x["local_path"] for x in s.of_kind("lerobot")] == [
        "/a",
        "/b",
    ]  # a replay keeps the datasets
    s.add([{"kind": "trajectory", "local_path": "/t"}], "job-3")
    assert [(x["local_path"], x["job_id"]) for x in s.of_kind("trajectory")] == [
        ("/t", "job-3")
    ]  # no duplicate
    s.add([{"kind": "checkpoint", "local_path": "/c1"}], "job-4")
    s.add([{"kind": "lerobot", "local_path": "/d"}], "job-5")
    assert [x["local_path"] for x in s.of_kind("checkpoint")] == ["/c1"]
    assert [x["local_path"] for x in s.of_kind("lerobot")] == ["/d"]
    s.add([{"kind": "checkpoint", "local_path": "/c2"}], "job-6")
    assert [x["local_path"] for x in s.of_kind("checkpoint")] == ["/c2"]
    assert [x["local_path"] for x in s.of_kind("lerobot")] == ["/d"]


def test_use_inputs_selects_bundle_and_flags_missing(monkeypatch, tmp_path):
    import yaml

    def bundle(name, params):
        d = tmp_path / name
        d.mkdir()
        (d / "template.yaml").write_text(
            yaml.safe_dump(
                {
                    "specificationVersion": "jobtemplate-2023-09",
                    "name": name,
                    "parameterDefinitions": params,
                    "steps": [],
                }
            )
        )

    bundle(
        "a_images",
        [{"name": "ImagesDir", "type": "PATH", "objectType": "DIRECTORY", "dataFlow": "IN"}],
    )
    bundle(
        "b_retrain",
        [{"name": "train_Datasets", "type": "PATH", "objectType": "DIRECTORY", "dataFlow": "IN"}],
    )
    monkeypatch.setattr(st, "get_str", lambda k: str(tmp_path) if k == st.BUNDLE_DIRS else "")
    c = ct.SubmitController(lambda *a, **k: None)
    c.scan()
    c.select(next(b.path for b in c.s.bundles if b.name == "b_retrain"))
    assert c.missing_inputs() == ["train_Datasets"]
    c.select(next(b.path for b in c.s.bundles if b.name == "a_images"))
    ct.SESSION.add([{"kind": "lerobot", "local_path": str(tmp_path)}], "job-2")
    c.use_inputs(ct.SESSION.of_kind("lerobot"))
    assert c.bundle().name == "b_retrain" and c.s.prefill == {"train_Datasets": str(tmp_path)}
    assert c.missing_inputs() == [] and not c.s.error


class DeferredRunner:
    """Keeps each command's callback so a test can answer them in any order."""

    def __init__(self):
        self.calls = []

    def __call__(self, argv, on_done, exe="", timeout_s=None, on_progress=None, env_extra=None):
        self.calls.append((argv, on_done))
        self.envs = getattr(self, "envs", []) + [env_extra]

    def argvs(self, *words):
        return [i for i, (a, _) in enumerate(self.calls) if a[1 : 1 + len(words)] == list(words)]

    def reply(self, i, out="", code=0):
        argv, done = self.calls[i]
        done(cb.Result(argv, code, out, ""))


def _three_farms(c):
    c.deadline = "deadline"
    c.s.farms = [{"id": f"farm-{x}", "name": x, "region": f"r-{x}"} for x in "ABC"]
    c.s.target.farm_id = "farm-A"


def test_stale_queue_list_is_dropped(monkeypatch):
    monkeypatch.setattr(ct, "_tools", lambda: ("deadline", "PATH", "pai", "PATH"))
    r = DeferredRunner()
    c = ct.LoadController(r)
    _three_farms(c)
    c.select_farm("farm-B")
    c.select_farm("farm-C")
    qb, qc = r.argvs("queue", "list")
    r.reply(qc, "- queueId: queue-C\n  displayName: QC\n")
    r.reply(qb, "- queueId: queue-B\n  displayName: QB\n")
    assert (c.s.target.farm_id, c.s.target.queue_id) == ("farm-C", "queue-C")
    assert [q["id"] for q in c.s.queues] == ["queue-C"] and c.s.busy.startswith("Listing jobs")
    jobs = r.argvs("jobs", "list")
    assert len(jobs) == 1 and "farm-C" in r.calls[jobs[0]][0]


def test_stale_job_list_is_dropped_and_queue_switch_clears_jobs(monkeypatch):
    monkeypatch.setattr(ct, "_tools", lambda: ("deadline", "PATH", "pai", "PATH"))
    r = DeferredRunner()
    c = ct.LoadController(r)
    _three_farms(c)
    c.s.target.queue_id = "queue-0"
    c.s.jobs = [{"jobId": "job-old", "taskRunStatus": "SUCCEEDED"}]
    c.select_queue("queue-1")
    assert c.s.jobs == []
    c.select_queue("queue-2")
    j1, j2 = r.argvs("jobs", "list")
    r.reply(j2, json.dumps({"jobs": [{"name": "two", "jobId": "job-2"}], "total": 1}))
    r.reply(j1, json.dumps({"jobs": [{"name": "one", "jobId": "job-1"}], "total": 1}))
    assert [j["jobId"] for j in c.s.jobs] == ["job-2"] and c.s.target.queue_id == "queue-2"


def test_duplicate_refresh_runs_one_chain(monkeypatch):
    monkeypatch.setattr(ct, "_tools", lambda: ("deadline", "PATH", "pai", "PATH"))
    r = DeferredRunner()
    c = ct.LoadController(r)
    c.refresh()
    c.refresh()
    for i in r.argvs("config", "get"):
        r.reply(i, "farm-1\n" if "farm_id" in r.calls[i][0][-1] else "queue-1\n")
    assert len(r.argvs("farm", "list")) == 1


def _listing(job_id, paths, kind="trajectory"):
    return json.dumps(
        {
            "job_id": job_id,
            "file_count": len(paths),
            "items": [{"kind": kind, "path": p, "label": p, "meta": {}} for p in paths],
        }
    )


def test_stale_outputs_list_is_dropped(monkeypatch):
    monkeypatch.setattr(ct, "_tools", lambda: ("deadline", "PATH", "pai", "PATH"))
    r = DeferredRunner()
    c = ct.LoadController(r)
    c.select_job("job-A")
    c.select_job("job-B")
    a, b = r.argvs("outputs", "list")
    r.reply(b, _listing("job-B", ["b.npz"]))
    r.reply(a, _listing("job-A", ["a.npz"]))
    assert c.s.job_id == "job-B" and [i["path"] for i in c.visible_items()] == ["b.npz"]
    # Listing is not loading: the previous-job prefill still names no job.
    assert st.get_str(st.LAST_LOADED_JOB) == "" and c.s.busy == ""


def test_job_switch_mid_download_does_not_leak(monkeypatch, tmp_path):
    monkeypatch.setattr(ct, "_tools", lambda: ("deadline", "PATH", "pai", "PATH"))
    f = tmp_path / "ep.npz"
    f.write_bytes(b"a")
    r = DeferredRunner()
    loaded = []
    c = ct.LoadController(r, on_loaded=lambda items, job: loaded.append(items))
    c.select_job("job-A")
    r.reply(r.argvs("outputs", "list")[-1], _listing("job-A", ["eval/ep.trajectory.npz"]))
    c.toggle("eval/ep.trajectory.npz", True)
    c.load_checked()
    fetch = r.argvs("outputs", "fetch")[-1]
    # Pipeline jobs repeat item paths: job B has the same one.
    c.select_job("job-B")
    r.reply(r.argvs("outputs", "list")[-1], _listing("job-B", ["eval/ep.trajectory.npz"]))
    c.toggle("eval/ep.trajectory.npz", True)
    assert (
        c.s.busy == "" and c.s.download and not c.can_load()
    )  # listing done, download still running
    c.load_checked()
    assert len(r.argvs("outputs", "fetch")) == 1
    r.reply(fetch, json.dumps({"dest": str(tmp_path), "items": {"eval/ep.trajectory.npz": str(f)}}))
    assert (
        loaded == []
        and c.s.job_id == "job-B"
        and c.s.checked == {"eval/ep.trajectory.npz"}
        and not c.s.download
    )
    assert c.fetched_path("eval/ep.trajectory.npz") == "" and c.can_load()
    assert [(x["job_id"], x["local_path"]) for x in ct.SESSION.loaded] == [("job-A", str(f))]
    # Back on job A, the file is known and loads without a second download.
    c.select_job("job-A")
    r.reply(r.argvs("outputs", "list")[-1], _listing("job-A", ["eval/ep.trajectory.npz"]))
    assert c.fetched_path("eval/ep.trajectory.npz") == str(f)


def test_fetch_loads_only_reported_existing_paths(monkeypatch, tmp_path):
    monkeypatch.setattr(ct, "_tools", lambda: ("deadline", "PATH", "pai", "PATH"))
    got = tmp_path / "a.npz"
    got.write_bytes(b"a")
    reply = {
        "dest": str(tmp_path),
        "items": {"a.npz": str(got), "b.npz": str(tmp_path / "never.npz")},
        "missing": ["c.npz"],
    }
    runner = FakeRunner(
        {
            "outputs list job-1": (_listing("job-1", ["a.npz", "b.npz", "c.npz"]), 0),
            "outputs fetch job-1": (json.dumps(reply), 0),
        }
    )
    loaded = []
    c = ct.LoadController(runner, on_loaded=lambda items, job: loaded.extend(items))
    c.select_job("job-1")
    for p in ("a.npz", "b.npz", "c.npz"):
        c.toggle(p, True)
    c.load_checked()
    assert [i["path"] for i in loaded] == ["a.npz"]
    assert "b.npz" in c.s.error and "c.npz" in c.s.error and "Loaded 1" in c.s.status
    assert c.fetched_path("b.npz") == "" and [x["local_path"] for x in ct.SESSION.loaded] == [
        str(got)
    ]
    # A malformed reply is an error, not an exception.
    runner.replies["outputs fetch job-1"] = (json.dumps({"dest": "/x", "items": ["b.npz"]}), 0)
    c.toggle("b.npz", True)
    c.load_checked()
    assert "b.npz" in c.s.error and not c.s.download


def test_runner_reports_callback_exception():
    import sys
    import time

    logged: list = []
    got: list = []

    def done(res):
        got.append(res)
        if len(got) == 1:
            raise ValueError("boom")

    r = ct.Runner(log=logged.append)
    r([sys.executable, "-c", "print('ok')"], done, on_progress=lambda p: 1 / 0)
    t0 = time.monotonic()
    while r._cmds and time.monotonic() - t0 < 20:
        r.poll()
        time.sleep(0.02)
    assert [g.code for g in got] == [0, 1] and "ValueError: boom" in got[1].stderr and logged


def test_listing_clears_busy_when_the_reply_is_garbage(monkeypatch):
    import sys
    import time

    monkeypatch.setattr(ct, "_tools", lambda: (sys.executable, "PATH", sys.executable, "PATH"))
    monkeypatch.setattr(
        cb,
        "finished_jobs_argv",
        lambda pai, t, status="succeeded", offset=0: [
            sys.executable,
            "-c",
            "print('not json'); raise SystemExit(1)",
        ],
    )
    runner = ct.Runner()
    c = ct.LoadController(runner)
    c.list_jobs()
    t0 = time.monotonic()
    while runner._cmds and time.monotonic() - t0 < 20:
        runner.poll()
        time.sleep(0.02)
    assert c.s.busy == "" and "Could not list jobs" in c.s.error and "not json" in c.s.error


def test_set_default_saves_ids_from_when_it_was_pressed():
    r = DeferredRunner()
    c = ct.LoadController(r)
    _three_farms(c)
    c.s.target.queue_id = "queue-A"
    c.set_default()
    c.s.target.farm_id, c.s.target.queue_id = "farm-B", ""  # what select_farm does meanwhile
    for i in r.argvs("config", "set"):
        r.reply(i)
    assert (c.s.default_farm, c.s.default_queue) == ("farm-A", "queue-A")


def _bundles(tmp_path, monkeypatch, defs, extra=None):
    import yaml

    for name, params in defs.items():
        d = tmp_path / "bundles" / name
        d.mkdir(parents=True)
        (d / "template.yaml").write_text(
            yaml.safe_dump(
                {
                    "specificationVersion": "jobtemplate-2023-09",
                    "name": name,
                    "parameterDefinitions": params,
                    "steps": [],
                }
            )
        )
    vals = dict({st.BUNDLE_DIRS: str(tmp_path / "bundles")}, **(extra or {}))
    monkeypatch.setattr(st, "get_str", lambda k, d=None: vals.get(k, ""))


def _dir_param(name, **kw):
    return dict({"name": name, "type": "PATH", "objectType": "DIRECTORY", "dataFlow": "IN"}, **kw)


def test_submit_gathers_into_a_fresh_folder_and_blocks_a_second_dialog(monkeypatch, tmp_path):
    _bundles(tmp_path, monkeypatch, {"retrain": [_dir_param("train_Datasets")]})
    monkeypatch.setattr(cb, "resolve", lambda name, override="": ("deadline", "PATH"))
    for n in ("a", "b"):
        (tmp_path / "ds" / n / "meta").mkdir(parents=True)
        (tmp_path / "ds" / n / "meta" / "info.json").write_text("{}")
    ct.SESSION.add(
        [{"kind": "lerobot", "local_path": str(tmp_path / "ds" / n)} for n in "ab"], "job-1"
    )
    r = DeferredRunner()
    c = ct.SubmitController(r)
    c.scan()
    c.submit()
    first = c.s.prefill["train_Datasets"]
    assert len(os.listdir(first)) == 2 and c.s.busy
    c.submit()  # a second click while the dialog is open must not touch the folder it uploads
    assert len(r.calls) == 1 and len(os.listdir(first)) == 2
    r.reply(0, '{"status": "CANCELED"}')
    c.submit()
    second = c.s.prefill["train_Datasets"]
    assert second != first and len(os.listdir(second)) == 2 and not os.path.exists(first)


def test_submit_with_inputs_survives_the_visibility_scan(monkeypatch, tmp_path):
    _bundles(
        tmp_path,
        monkeypatch,
        {"a_images": [_dir_param("ImagesDir")], "b_retrain": [_dir_param("train_Datasets")]},
    )
    ct.SESSION.add([{"kind": "lerobot", "local_path": str(tmp_path)}], "job-1")
    for order in ("apply first", "show first"):
        c = ct.SubmitController(lambda *a, **k: None)
        c.scan()
        assert c.bundle().name == "a_images"
        c.request_inputs(ct.SESSION.of_kind("lerobot"), opening=True)
        steps = [c.apply_requested_inputs, c.on_shown]
        for step in steps if order == "apply first" else steps[::-1]:
            step()
        assert (
            c.bundle().name == "b_retrain" and "selected for the loaded dataset" in c.s.status
        ), order
    # Without queued inputs, opening the window rescans.
    c.s.status = ""
    c.on_shown()
    assert c.s.status == "2 bundles"


def test_use_inputs_prefers_current_and_keeps_selection_without_match(monkeypatch, tmp_path):
    _bundles(
        tmp_path,
        monkeypatch,
        {
            "a_retrain": [_dir_param("train_Datasets")],
            "b_retrain": [_dir_param("train_Datasets")],
            "c_other": [_dir_param("Images")],
        },
    )
    ct.SESSION.add([{"kind": "lerobot", "local_path": str(tmp_path)}], "job-1")
    c = ct.SubmitController(lambda *a, **k: None)
    c.scan()
    c.select(next(b.path for b in c.s.bundles if b.name == "b_retrain"))
    c.use_inputs(ct.SESSION.of_kind("lerobot"))
    assert c.bundle().name == "b_retrain" and not c.s.error
    c.select(next(b.path for b in c.s.bundles if b.name == "c_other"))
    c.use_inputs([{"kind": "checkpoint", "local_path": "/ck"}])
    assert c.bundle().name == "c_other" and "takes a checkpoint" in c.s.error


def test_missing_inputs_ignores_out_inout_and_defaulted(monkeypatch, tmp_path):
    _bundles(
        tmp_path,
        monkeypatch,
        {
            "x": [
                _dir_param("train_Datasets", dataFlow="OUT"),
                _dir_param("eval_Datasets", dataFlow="INOUT"),
                _dir_param("ref_Dataset", default="/d"),
                _dir_param("ImagesDir"),
                _dir_param("eval_CheckpointDir"),
            ]
        },
    )
    c = ct.SubmitController(lambda *a, **k: None)
    c.scan()
    assert c.missing_inputs() == ["eval_CheckpointDir"]
    assert c.missing_hint("ImagesDir") == ""  # only the submit dialog can fill it
    assert "Submit pipeline job with dataset" in c.missing_hint("train_Datasets")
    assert "Submit pipeline job with checkpoint" in c.missing_hint("eval_CheckpointDir")


def test_gather_folder_sits_beside_the_datasets(monkeypatch, tmp_path):
    """The system temp dir is usually another filesystem, where os.link fails with EXDEV
    and gather_datasets copies gigabytes instead of linking."""
    _bundles(tmp_path, monkeypatch, {"retrain": [_dir_param("train_Datasets")]})
    monkeypatch.setattr(cb, "resolve", lambda name, override="": ("deadline", "PATH"))
    dl = tmp_path / "downloads" / "job-1"
    for n in ("a", "b"):
        (dl / n / "meta").mkdir(parents=True)
        (dl / n / "meta" / "info.json").write_text("{}")
    ct.SESSION.add([{"kind": "lerobot", "local_path": str(dl / n)} for n in "ab"], "job-1")
    r = DeferredRunner()
    c = ct.SubmitController(r)
    c.scan()
    c.submit()
    folder = c.s.prefill["train_Datasets"]
    assert os.path.dirname(folder) == str(dl)
    assert os.path.basename(folder).startswith(ct.GATHER_PREFIX)
    linked = os.path.join(folder, "job-1_a", "meta", "info.json")
    assert os.stat(linked).st_ino == os.stat(dl / "a" / "meta" / "info.json").st_ino
    assert os.stat(linked).st_nlink == 2
    r.reply(0, '{"status": "CANCELED"}')
    assert not os.path.exists(folder)  # removed when the dialog closes


def test_previous_job_prefill_is_the_job_that_was_loaded(monkeypatch, tmp_path):
    """Listing a job's outputs is not loading it: the previous-job parameter must name the
    job whose dataset is on disk, not whichever job the list is showing."""
    import yaml

    monkeypatch.setattr(ct, "_tools", lambda: ("deadline", "PATH", "pai", "PATH"))
    local = tmp_path / "dl" / "job-A" / "ds"
    local.mkdir(parents=True)
    runner = FakeRunner(
        {
            "outputs list job-A": (_listing("job-A", ["ds"], kind="lerobot"), 0),
            "outputs list job-B": (_listing("job-B", ["ds"], kind="lerobot"), 0),
            "outputs fetch job-A": (
                json.dumps({"dest": str(tmp_path / "dl"), "items": {"ds": str(local)}}),
                0,
            ),
        }
    )
    c = ct.LoadController(runner)
    c.select_job("job-A")
    assert st.get_str(st.LAST_LOADED_JOB) == ""
    c.toggle("ds", True)
    c.load_checked()
    assert st.get_str(st.LAST_LOADED_JOB) == "job-A"
    c.select_job("job-B")
    assert st.get_str(st.LAST_LOADED_JOB) == "job-A"
    d = tmp_path / "bundles" / "retrain"
    d.mkdir(parents=True)
    (d / "template.yaml").write_text(
        yaml.safe_dump(
            {
                "specificationVersion": "jobtemplate-2023-09",
                "name": "retrain",
                "parameterDefinitions": [
                    {"name": "FromJobId", "type": "STRING"},
                    _dir_param("train_Datasets"),
                ],
                "steps": [],
            }
        )
    )
    st.set_str(st.BUNDLE_DIRS, str(tmp_path / "bundles"))
    s = ct.SubmitController(lambda *a, **k: None)
    s.scan()
    assert s.s.prefill == {"FromJobId": "job-A", "train_Datasets": str(local)}


def test_usd_item_loads_the_file_inside_its_fetched_folder(monkeypatch, tmp_path):
    """The CLI fetches the folder beside a .usd file (its references and textures); the
    item still loads from the file itself."""
    monkeypatch.setattr(ct, "_tools", lambda: ("deadline", "PATH", "pai", "PATH"))
    scenes = tmp_path / "scenes"
    scenes.mkdir()
    (scenes / "table.usda").write_text("#usda 1.0")
    (scenes / "wood.png").write_bytes(b"png")
    runner = FakeRunner(
        {
            "outputs list job-1": (_listing("job-1", ["scenes/table.usda"], kind="usd"), 0),
            "outputs fetch job-1": (
                json.dumps(
                    {
                        "dest": str(tmp_path),
                        "items": {"scenes/table.usda": str(scenes / "table.usda")},
                    }
                ),
                0,
            ),
        }
    )
    loaded = []
    c = ct.LoadController(runner, on_loaded=lambda items, job: loaded.extend(items))
    c.select_job("job-1")
    c.toggle("scenes/table.usda", True)
    c.load_checked()
    fetch = runner.calls[-1]
    assert fetch[fetch.index("--path") + 1] == "scenes/table.usda"
    assert loaded[0]["local_path"] == str(scenes / "table.usda")
    assert os.path.isfile(loaded[0]["local_path"]) and (scenes / "wood.png").exists()


def _stage_bundle(tmp_path, monkeypatch):
    _bundles(
        tmp_path,
        monkeypatch,
        {
            "scene": [
                {
                    "name": "StageFile",
                    "type": "PATH",
                    "objectType": "FILE",
                    "dataFlow": "IN",
                }
            ]
        },
    )
    monkeypatch.setattr(cb, "resolve", lambda name, override="": ("deadline", "PATH"))


def test_standalone_submit_has_no_stage_and_no_host(monkeypatch, tmp_path):
    _stage_bundle(tmp_path, monkeypatch)
    r = DeferredRunner()
    c = ct.SubmitController(r, ext_version="1.0.0")
    c.scan()
    assert c.s.prefill == {} and not c.s.stage_checked
    c.submit()
    argv = r.calls[0][0]
    assert not any(a.startswith("host_application") for a in argv)
    assert "submitter_package_version=1.0.0" in argv


def test_connected_submit_asks_for_the_stage_every_time(monkeypatch, tmp_path):
    _stage_bundle(tmp_path, monkeypatch)
    asked: list = []
    r = DeferredRunner()
    c = ct.SubmitController(r, fetch_stage=asked.append, app_version="6.2.0")
    c.scan()  # selecting the bundle asks for the stage for the preview
    assert len(asked) == 1 and c.s.prefill == {}
    asked[0]("/s/a.usd")
    assert c.s.prefill == {"StageFile": "/s/a.usd"} and c.s.stage_checked
    c.submit()  # asks again rather than reusing /s/a.usd
    assert len(asked) == 2 and c.s.busy and not r.calls
    c.submit()  # a second click while waiting does nothing
    assert len(asked) == 2
    asked[1]("/s/saved-as.usd")
    argv = r.calls[0][0]
    assert "StageFile=/s/saved-as.usd" in argv and "host_application_version=6.2.0" in argv
    assert "host_application_name=Isaac Sim" in argv and c.s.busy == "Submit dialog open..."


def test_stale_stage_reply_is_dropped(monkeypatch, tmp_path):
    _stage_bundle(tmp_path, monkeypatch)
    asked: list = []
    c = ct.SubmitController(lambda *a, **k: None, fetch_stage=asked.append)
    c.scan()
    c.select(c.s.selected)
    asked[1]("/s/new.usd")
    asked[0]("/s/old.usd")
    assert c.s.stage == "/s/new.usd"
    asked.clear()
    c.refresh_stage()
    asked[0]("")  # unsaved stage
    assert c.s.prefill == {} and c.s.stage_checked and c.s.stage == ""


def test_job_status_filter_relists(monkeypatch):
    monkeypatch.setattr(ct, "_tools", lambda: ("deadline", "PATH", "pai", "PATH"))
    job = {"name": "f", "jobId": "job-9", "endedAt": "x", "taskRunStatus": "FAILED"}
    runner = PagedRunner(
        {
            "config get defaults.farm_id": ("farm-1\n", 0),
            "config get defaults.queue_id": ("queue-1\n", 0),
            "farm list": ("- region: us-west-2\n  farmId: farm-1\n  displayName: A\n", 0),
            "queue list --farm-id": ("- queueId: queue-1\n  displayName: Q\n", 0),
        },
        {0: {"jobs": [job], "total": 1, "next_offset": None}},
    )
    c = ct.LoadController(runner)
    c.refresh()
    assert runner.calls[-1][runner.calls[-1].index("--status") + 1] == "succeeded"
    c.s.job_id = "job-9"
    c.set_job_status("failed")
    assert runner.calls[-1][runner.calls[-1].index("--status") + 1] == "failed"
    assert c.s.job_status == "failed" and c.s.job_id == "" and c.s.compare_id == ""
    assert "1 of 1 failed jobs" in c.s.status
    n = len(runner.calls)
    c.set_job_status("failed")  # unchanged
    c.set_job_status("bogus")
    assert len(runner.calls) == n


def test_parameter_rows_all_or_only_differences():
    a = {"Steps": "500", "Lr": "0.001", "Only": "a"}
    b = {"Steps": "1000", "Lr": "0.001", "New": "b"}
    assert ct.parameter_rows(a) == [("Lr", "0.001", ""), ("Only", "a", ""), ("Steps", "500", "")]
    assert ct.parameter_rows(a, b) == [
        ("New", "", "b"),
        ("Only", "a", ""),
        ("Steps", "500", "1000"),
    ]


def test_parameters_load_once_and_compare(monkeypatch):
    monkeypatch.setattr(ct, "_tools", lambda: ("deadline", "PATH", "pai", "PATH"))
    r = DeferredRunner()
    c = ct.LoadController(r)
    c.s.target = cb.Target(farm_id="farm-1", queue_id="queue-1")

    def answer(i, *pairs):
        r.reply(
            i,
            json.dumps({"jobs": [{"job_id": j, "name": j, "parameters": p} for j, p in pairs]}),
        )

    c.select_job("job-1")
    (i,) = r.argvs("jobs", "params")
    assert r.calls[i][0][3] == "job-1"
    assert c.parameter_rows() == []  # still loading
    answer(i, ("job-1", {"Steps": "500", "Lr": "1"}))
    assert c.parameter_rows() == [("Lr", "1", ""), ("Steps", "500", "")]
    c.set_compare("job-2")
    i2 = r.argvs("jobs", "params")[-1]
    assert r.calls[i2][0][3:4] == ["job-2"]  # job-1 is cached
    answer(i2, ("job-2", {"Steps": "900", "Lr": "1"}))
    assert c.parameter_rows() == [("Steps", "500", "900")]
    n = len(r.argvs("jobs", "params"))
    c.set_compare("")
    c.set_compare("job-2")
    c.select_job("job-1")
    assert len(r.argvs("jobs", "params")) == n  # everything cached
    c.set_compare("job-1")  # comparing a job with itself means no comparison
    assert c.s.compare_id == ""


def test_parameter_errors_are_reported(monkeypatch):
    monkeypatch.setattr(ct, "_tools", lambda: ("deadline", "PATH", "pai", "PATH"))
    r = DeferredRunner()
    c = ct.LoadController(r)
    c.s.target = cb.Target(farm_id="farm-1", queue_id="queue-1")
    c.select_job("job-1")
    (i,) = r.argvs("jobs", "params")
    r.reply(i, "", code=1)
    assert c.s.params_error.startswith("Could not read job parameters")


def test_resubmit_selects_the_matching_bundle_and_prefills_its_values(monkeypatch, tmp_path):
    steps = {"name": "Steps", "type": "INT"}
    _bundles(
        tmp_path,
        monkeypatch,
        {
            "eval": [{"name": "Checkpoint", "type": "STRING"}],
            "train": [steps, {"name": "Lr", "type": "FLOAT"}],
        },
    )
    c = ct.SubmitController(lambda *a, **k: None)
    c.scan()
    assert c.bundle().name == "eval"
    job = {
        "job_id": "job-7",
        "name": "run 7",
        "parameters": {"Steps": "500", "Lr": "0.1", "X": "1"},
    }
    c.request_resubmit(job, opening=True)
    c.on_shown()  # skipped: the request rescans itself
    c.apply_requested_inputs()
    assert c.bundle().name == "train"
    assert c.s.prefill == {"Steps": "500", "Lr": "0.1"}
    assert "2 of 3 parameters prefilled" in c.s.status
    c.select(next(b.path for b in c.s.bundles if b.name == "eval"))
    assert c.s.prefill == {}  # eval defines none of the job's parameters
    c.clear_resubmit()
    assert c.s.resubmit == {}


def test_resubmit_without_a_matching_bundle_says_so(monkeypatch, tmp_path):
    _bundles(tmp_path, monkeypatch, {"eval": [{"name": "Checkpoint", "type": "STRING"}]})
    c = ct.SubmitController(lambda *a, **k: None)
    c.resubmit({"job_id": "job-7", "name": "n", "parameters": {"Steps": "1"}})
    assert "No bundle in your bundle folders or job history" in c.s.error


def test_load_controller_hands_the_job_to_resubmit(monkeypatch):
    got: list = []
    c = ct.LoadController(lambda *a, **k: None, on_resubmit=got.append)
    c.resubmit()  # nothing selected
    c.s.jobs = [{"jobId": "job-1", "name": "n"}]
    c.s.job_id = "job-1"
    assert not c.can_resubmit()  # parameters not read yet
    c.s.params = {"job-1": {"Steps": "5"}}
    c.resubmit()
    assert got == [{"job_id": "job-1", "name": "n", "parameters": {"Steps": "5"}}]


def _hist_bundle(root, month, name, params):
    import yaml

    d = root / month / name
    d.mkdir(parents=True)
    (d / "template.yaml").write_text(
        yaml.safe_dump(
            {
                "specificationVersion": "jobtemplate-2023-09",
                "name": "Train",
                "parameterDefinitions": params,
                "steps": [],
            }
        )
    )


def test_resubmit_falls_back_to_the_job_history(monkeypatch, tmp_path):
    _bundles(tmp_path, monkeypatch, {"eval": [{"name": "Checkpoint", "type": "STRING"}]})
    hist = tmp_path / "history"
    p = [{"name": "Steps", "type": "INT"}, {"name": "Lr", "type": "FLOAT"}]
    _hist_bundle(hist, "2026-10", "2026-10-01-01-JobBundle-Train", p[:1])
    _hist_bundle(hist, "2026-11", "2026-11-02-01-JobBundle-Train", p)
    c = ct.SubmitController(lambda *a, **k: None)
    c.deadline_dirs = {"bundles": "", "history": str(hist)}
    c.resubmit({"job_id": "job-7", "name": "Train", "parameters": {"Steps": "5", "Lr": "1"}})
    assert c.bundle().name == "Train (job history)"
    assert "2026-11" in c.bundle().path and c.s.prefill == {"Steps": "5", "Lr": "1"}
    c.scan()  # a rescan keeps the history bundle while resubmitting
    assert any(b.name == "Train (job history)" for b in c.s.bundles)
    c.clear_resubmit()
    assert not any("job history" in b.name for b in c.s.bundles)


def test_deadline_folders_are_read_once_and_searched(monkeypatch, tmp_path, real_deadline_dirs):
    _bundles(tmp_path, monkeypatch, {"own": [{"name": "A", "type": "STRING"}]})
    other = tmp_path / "dl-bundles"
    (other / "shared").mkdir(parents=True)
    (other / "shared" / "template.yaml").write_text(
        "specificationVersion: jobtemplate-2023-09\nname: Shared\nsteps: []\n"
    )
    monkeypatch.setattr(cb, "resolve", lambda name, override="": ("deadline", "PATH"))
    r = DeferredRunner()
    c = ct.SubmitController(r)
    c.scan()
    c.scan()
    asks = r.argvs("config", "get")
    assert len(asks) == 2  # asked once
    r.reply(asks[0], f"{other}\n")
    r.reply(asks[1], "~/nowhere\n")
    assert c.deadline_dirs == {"bundles": str(other), "history": "~/nowhere"}
    assert sorted(b.name for b in c.s.bundles) == ["Shared", "own"]


def test_submit_uses_the_chosen_farm_and_queue_on_a_config_copy(monkeypatch, tmp_path):
    _stage_bundle(tmp_path, monkeypatch)
    monkeypatch.setattr(cb, "resolve", lambda name, override="": ("deadline", "PATH"))
    user_config = tmp_path / "user-config"
    user_config.write_text("[defaults]\naws_profile_name = p\n")
    monkeypatch.setenv(cb.CONFIG_FILE_ENV, str(user_config))
    r = DeferredRunner()
    c = ct.SubmitController(r)
    t = cb.Target(farm_id="farm-2", queue_id="queue-2")
    c.target = lambda: {"target": t, "default": False, "farm": "F", "queue": "Q"}
    c.scan()
    c.submit()
    assert r.calls[0][0][1:4] == ["config", "set", "defaults.farm_id"]
    copy = r.envs[0][cb.CONFIG_FILE_ENV]
    assert copy != str(user_config)
    with open(copy) as fh:
        assert fh.read() == user_config.read_text()
    r.reply(0)
    assert r.calls[1][0][1:5] == ["config", "set", "defaults.queue_id", "queue-2"]
    r.reply(1)
    assert r.calls[2][0][1:3] == ["bundle", "gui-submit"] and r.envs[2] == r.envs[0]
    r.reply(2, json.dumps({"status": "CANCELED"}))
    assert not os.path.exists(copy)  # removed when the dialog closes
    assert user_config.read_text() == "[defaults]\naws_profile_name = p\n"


def test_submit_to_the_default_farm_and_queue_uses_the_real_config(monkeypatch, tmp_path):
    _stage_bundle(tmp_path, monkeypatch)
    monkeypatch.setattr(cb, "resolve", lambda name, override="": ("deadline", "PATH"))
    r = DeferredRunner()
    c = ct.SubmitController(r)
    t = cb.Target(farm_id="farm-1", queue_id="queue-1")
    c.target = lambda: {"target": t, "default": True, "farm": "F", "queue": "Q"}
    c.scan()
    c.submit()
    assert r.calls[0][0][1:3] == ["bundle", "gui-submit"] and r.envs == [None]


def test_selecting_the_farm_and_queue_failing_reports_it(monkeypatch, tmp_path):
    _stage_bundle(tmp_path, monkeypatch)
    monkeypatch.setattr(cb, "resolve", lambda name, override="": ("deadline", "PATH"))
    r = DeferredRunner()
    c = ct.SubmitController(r)
    t = cb.Target(farm_id="farm-2", queue_id="queue-2")
    c.target = lambda: {"target": t, "default": False, "farm": "F", "queue": "Q"}
    c.scan()
    c.submit()
    r.reply(0, "", code=1)
    assert c.s.error.startswith("Could not select the farm and queue") and not c.s.busy
    assert len(r.calls) == 1


def _eval_rows():
    def row(i, rate, lr, seed="0", metrics=None):
        e = {"episodes": 50, "successes": int(rate * 50), "success_rate": rate, "ci95": [0.1, 0.9]}
        if metrics:
            e["metrics"] = metrics
        return {
            "jobId": f"job-{i}",
            "name": f"run {i}",
            "endedAt": "2026-11-11T10:00:00+00:00",
            "parameters": {"Lr": lr, "Seed": seed, "OutputDir": f"/o/{i}"},
            "eval": e,
        }

    return [
        row(1, 0.5, "0.1", metrics={"len": 10.0}),
        row(2, 0.8, "0.01"),
        {"jobId": "job-3", "name": "no eval", "parameters": {"Lr": "9"}, "eval": None},
    ]


def test_eval_table_shows_only_varying_parameters(monkeypatch):
    monkeypatch.setattr(ct, "_tools", lambda: ("deadline", "PATH", "pai", "PATH"))
    r = DeferredRunner()
    t = cb.Target(farm_id="farm-1", queue_id="queue-1")
    c = ct.EvalController(r, target=lambda: t)
    assert c.stale()
    c.load()
    (i,) = r.argvs("jobs", "evals")
    r.reply(i, json.dumps({"jobs": _eval_rows(), "total": 3, "next_offset": None}))
    assert not c.stale() and "2 of 3" in c.s.status
    headers, rows = c.table()
    assert headers == [
        "Job",
        "Success",
        "95% CI",
        "Episodes",
        "Checkpoint",
        "Finished",
        "Lr",
        "len",
    ]
    assert rows[0][1] == ("50.0%", 0.5) and rows[1][6] == ("0.01", (0, 0.01, ""))
    assert rows[1][7][0] == ""  # no such metric
    assert rows[0][2][0] == "10 to 90%"
    t.queue_id = "queue-2"
    assert c.stale()


def test_eval_csv_has_every_parameter(monkeypatch, tmp_path):
    c = ct.EvalController(lambda *a, **k: None)
    c.s.jobs = _eval_rows()
    path = tmp_path / "out.csv"
    assert c.write_csv(str(path)) == 2
    lines = path.read_text().splitlines()
    assert lines[0].endswith("param.Lr,param.OutputDir,param.Seed")
    assert lines[1].startswith("job-1,run 1,") and "/o/1" in lines[1]


def test_eval_load_needs_a_queue_and_reports_errors(monkeypatch):
    monkeypatch.setattr(ct, "_tools", lambda: ("deadline", "PATH", "pai", "PATH"))
    r = DeferredRunner()
    c = ct.EvalController(r, target=lambda: cb.Target())
    c.load()
    assert "Pick a farm and queue" in c.s.error and not r.calls
    c.target = lambda: cb.Target(farm_id="f", queue_id="q")
    c.load()
    r.reply(0, "", code=1)
    assert c.s.error.startswith("Could not read eval summaries") and not c.s.busy


def test_eval_read_clears_the_previous_count(monkeypatch):
    monkeypatch.setattr(ct, "_tools", lambda: ("deadline", "PATH", "pai", "PATH"))
    r = DeferredRunner()
    c = ct.EvalController(r, target=lambda: cb.Target(farm_id="f", queue_id="q"))
    c.s.status = "0 of 3 completed jobs read have an eval summary"
    c.load()
    assert c.s.status == "" and c.s.busy


class _PrimLink:
    """Stands in for KitLink.request: answers replay prim requests from a dict."""

    def __init__(self, selection=("/World/Cube",)):
        self.saved = {"robot": "/World/Robot", "object": "", "reference": ""}
        self.stage = {"/World/Robot", "/World/Cube", "/World/Base"}
        self.selection = list(selection)
        self.calls: list = []

    def _state(self) -> dict:
        exists = {r: bool(p) and p in self.stage for r, p in self.saved.items()}
        return {"ok": True, "prims": dict(self.saved), "exists": exists}

    def __call__(self, msg_type, callback, timeout_s=None, **fields):
        self.calls.append((msg_type, fields))
        if msg_type == "get_replay_prims":
            callback(self._state())
        elif msg_type == "set_replay_prims":
            self.saved.update(fields["prims"])
            callback(self._state())
        elif msg_type == "get_selection":
            callback({"ok": True, "paths": list(self.selection)})


def test_replay_prims_read_set_and_notes():
    link = _PrimLink()
    c = ct.ReplayPrimsController(link)
    assert c.note("robot") == ""  # not read yet
    c.refresh()
    assert c.note("robot") == "Found in the stage" and c.note("object") == "Not set (optional)"
    c.use_selection("object")
    assert link.saved["object"] == "/World/Cube"
    assert c.note("object") == "Found; set Reference too to place the object"
    assert "next trajectory" in c.s.status
    c.set_prim("reference", "/World/Missing")
    assert c.note("reference") == "Not in the open stage"
    c.set_prim("robot", "")
    assert c.note("robot") == "Not set: replay needs it"
    n = len(link.calls)
    c.set_prim("robot", "")  # unchanged: nothing sent
    c.set_prim("robot", "World/Robot")  # not absolute: refused locally
    assert len(link.calls) == n and "absolute prim path" in c.s.error


def test_replay_prims_selection_must_be_one_prim():
    for sel, words in (((), "Select one prim"), (("/a", "/b"), "2 prims are selected")):
        c = ct.ReplayPrimsController(_PrimLink(selection=sel))
        c.refresh()
        c.use_selection("object")
        assert words in c.s.error


def test_replay_prims_report_isaac_errors_and_do_nothing_standalone():
    c = ct.ReplayPrimsController(lambda t, cb, **f: cb({"ok": False, "message": "no stage"}))
    c.refresh()
    assert c.s.error == "no stage" and not c.s.busy
    standalone = ct.ReplayPrimsController(None)
    standalone.refresh()
    standalone.set_prim("robot", "/World/R")
    assert not standalone.s.loaded and not standalone.s.busy


def test_submit_fills_a_new_output_folder_even_on_resubmit(monkeypatch, tmp_path):
    out = {"name": "OutputDir", "type": "PATH", "objectType": "DIRECTORY", "dataFlow": "INOUT"}
    _bundles(tmp_path, monkeypatch, {"sdg": [out, {"name": "Steps", "type": "INT"}]})
    monkeypatch.setattr(cb, "resolve", lambda name, override="": ("deadline", "PATH"))
    root = tmp_path / "job-outputs"
    monkeypatch.setattr(ct.st, "output_root", lambda: str(root))
    r = DeferredRunner()
    c = ct.SubmitController(r)
    c.scan()
    preview = c.s.prefill["OutputDir"]
    assert preview.startswith(str(root / "sdg")) and not root.exists()  # nothing made yet
    c.submit()
    first = c.s.prefill["OutputDir"]
    assert os.path.isdir(first) and os.listdir(first) == []
    argv = r.calls[0][0]
    assert f"OutputDir={first}" in argv
    r.reply(0, json.dumps({"status": "CANCELED"}))
    # Resubmitting the job: its old OutputDir is replaced with a new folder.
    c.request_resubmit(
        {"job_id": "job-7", "name": "n", "parameters": {"OutputDir": first, "Steps": "5"}},
        opening=True,
    )
    c.apply_requested_inputs()
    c.submit()
    second = c.s.prefill["OutputDir"]
    assert second != first and os.path.isdir(second) and c.s.prefill["Steps"] == "5"
