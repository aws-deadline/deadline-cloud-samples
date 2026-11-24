# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
import pytest

from deadline.isaac_sim_submitter.app import cli_backend as cb
from deadline.isaac_sim_submitter.app import procenv

JOB_LIST = """Displaying 2 of 83 Jobs starting at 0

- name: 'Evaluate checkpoint A'
  jobId: job-00000000000000000000000000000001
  taskRunStatus: RUNNING
  startedAt: 2026-11-11 19:08:40.904000+00:00
  endedAt: ''
  createdBy: arn:aws:sts::123456789012:assumed-role/Admin/example-user
  createdAt: 2026-11-11 19:07:06+00:00
  estimatedTimeRemaining: 11 minutes
- name: 'Evaluate checkpoint B'
  jobId: job-00000000000000000000000000000002
  taskRunStatus: SUCCEEDED
  endedAt: 2026-11-11 16:14:58.893000+00:00
  createdBy: arn:aws:sts::123456789012:assumed-role/Admin/example-user
  createdAt: 2026-11-11 15:43:02+00:00
"""


def test_parse_job_list():
    jobs = cb.parse_job_list(JOB_LIST)
    assert [j["jobId"] for j in jobs] == [
        "job-00000000000000000000000000000001",
        "job-00000000000000000000000000000002",
    ]
    assert jobs[1]["taskRunStatus"] == "SUCCEEDED" and jobs[0]["endedAt"] == ""
    assert cb.parse_job_list("Displaying 0 of 0 Jobs starting at 0\n") == []
    assert cb.short_principal(jobs[0]["createdBy"]) == "example-user"


def test_argv_shapes():
    t = cb.Target("farm-1", "queue-1")
    assert cb.job_list_argv("deadline", t, 25) == [
        "deadline",
        "job",
        "list",
        "--farm-id",
        "farm-1",
        "--queue-id",
        "queue-1",
        "--page-size",
        "25",
    ]
    assert cb.outputs_fetch_argv("pai", t, "job-1", ["a/b.trajectory.npz", "c"], "/tmp/x")[-6:] == [
        "--path",
        "a/b.trajectory.npz",
        "--path",
        "c",
        "--dest",
        "/tmp/x",
    ]
    g = cb.gui_submit_argv(
        "deadline",
        "/b",
        {"StageFile": "C:\\s\\scene.usda", "FromJobId": "job-1"},
        app_version="6.2.0",
    )
    assert "--install-gui" in g
    assert [g[i + 1] for i, a in enumerate(g) if a == "-p"] == [
        "StageFile=C:\\s\\scene.usda",
        "FromJobId=job-1",
    ]
    assert "host_application_version=6.2.0" in g


def test_results():
    r = cb.Result(
        ["x"], 1, '{"messageType": "progress"}\n{"status": "error", "error": "no manifests"}\n', ""
    )
    assert not r.ok and r.error() == "no manifests"
    assert (
        cb.parse_submit_result('noise\n{"status": "SUBMITTED", "jobId": "job-9"}\n')["jobId"]
        == "job-9"
    )
    assert cb.parse_submit_result('{"status": "CANCELED"}')["status"] == "CANCELED"


def test_child_env_drops_kit_python(tmp_path):
    import os

    tool = os.path.join(str(tmp_path), "bin", "deadline")
    env = cb.child_env(
        tool,
        {"PYTHONHOME": "/kit", "QT_API": "pyside", "PATH": "/usr/bin", "AWS_PROFILE": "p"},
    )
    assert "PYTHONHOME" not in env and "QT_API" not in env and env["AWS_PROFILE"] == "p"
    # The tool's own folder goes first on PATH (compared case-insensitively on Windows).
    first = env["PATH"].split(os.pathsep)[0]
    assert os.path.normcase(first) == os.path.normcase(os.path.dirname(tool))


def test_child_env_forces_utf8_pipes():
    """Command decodes the child's pipes as UTF-8; on Windows the child would otherwise
    write the console code page and garble non-ASCII paths and job names."""
    env = cb.child_env("", {"PYTHONIOENCODING": "cp1252"})
    assert env["PYTHONIOENCODING"] == "utf-8" and env["PYTHONUTF8"] == "1"


def test_command_timeout_reports_error():
    import sys
    import time

    got: list = []
    c = cb.Command([sys.executable, "-c", "import time; time.sleep(30)"], got.append, timeout_s=0.5)
    t0 = time.time()
    while not c.poll() and time.time() - t0 < 10:
        time.sleep(0.05)
    assert got and got[0].code == cb.Command.TIMEOUT_EXIT and "Timed out" in got[0].error()


def test_credentials_hints():
    assert "expired" in cb.Result([], 1, "", "botocore ... ExpiredTokenException ...").error()
    assert (
        "aren't allowed"
        in cb.Result([], 1, "", "An error occurred (AccessDeniedException) ...").error()
    )
    assert cb.Result([], 1, "", "INFO: x\nboom: bad farm id").error() == "boom: bad farm id"


def test_command_large_output_does_not_deadlock():
    import sys
    import time

    got: list = []
    # Generate the output in the child: a 200 KB literal in argv exceeds the Windows
    # command-line limit (32,767 characters).
    c = cb.Command(
        [
            sys.executable,
            "-c",
            "import sys; sys.stdout.write('x' * 200000); sys.stderr.write('e' * 100000)",
        ],
        got.append,
        timeout_s=20,
    )
    t0 = time.time()
    while not c.poll() and time.time() - t0 < 20:
        time.sleep(0.02)
    assert (
        got and got[0].code == 0 and len(got[0].stdout) == 200_000 and len(got[0].stderr) == 100_000
    )


def test_progress_arrives_before_exit():
    """PROGRESS lines must reach on_progress while the child still runs, not at exit."""
    import sys
    import time

    child = (
        "import sys, time\n"
        'sys.stderr.write(\'PROGRESS {"bytes": 5, "total": 10, "files": 1, "file_total": 2}\\n\')\n'
        "sys.stderr.flush(); time.sleep(8)\n"
    )
    seen: list = []
    done: list = []
    c = cb.Command(
        [sys.executable, "-c", child], done.append, timeout_s=30, on_progress=seen.append
    )
    t0 = time.monotonic()
    try:
        while not seen and not c.done and time.monotonic() - t0 < 6:
            c.poll()
            time.sleep(0.05)
        assert seen == [{"bytes": 5, "total": 10, "files": 1, "file_total": 2}] and not c.done
    finally:
        c.cancel()
        while not c.poll() and time.monotonic() - t0 < 20:
            time.sleep(0.05)


def _with_stderr(chunks):
    c = object.__new__(cb.Command)
    c._err = list(chunks)
    return c


def test_progress_parse_edges():
    # The newest line is still being written: fall back to the last complete one.
    assert _with_stderr(['PROGRESS {"bytes": 1}\n', 'PROGRESS {"by']).progress() == {"bytes": 1}
    # Bad JSON (or not an object) is skipped, not fatal.
    assert _with_stderr(['PROGRESS {"bytes": 1}\n', "PROGRESS {bad}\n"]).progress() == {"bytes": 1}
    assert _with_stderr(["PROGRESS [1]\n"]).progress() is None
    # One line split across chunks.
    assert _with_stderr(['PROGRESS {"bytes"', ": 2}\n"]).progress() == {"bytes": 2}
    # Log lines after the last progress line.
    assert _with_stderr(['PROGRESS {"bytes": 3}\n'] + ["INFO: x\n"] * 20).progress() == {"bytes": 3}
    assert _with_stderr(["noise\n"]).progress() is None and _with_stderr([]).progress() is None


def test_format_progress():
    assert (
        cb.format_progress(
            {"bytes": 412_000_000, "total": 876_000_000, "files": 640, "file_total": 1755}
        )
        == "412 / 876 MB (47%), 640 / 1755 files"
    )
    assert (
        cb.format_progress({"bytes": 0, "total": 0, "files": 0, "file_total": 0})
        == "0 / 0 KB, 0 / 0 files"
    )
    assert (
        cb.format_progress(
            {"bytes": 500_000_000, "total": 1_000_000_000, "files": 1, "file_total": 2}
        )
        == "0.50 / 1.00 GB (50%), 1 / 2 files"
    )
    assert (
        cb.format_progress(
            {"bytes": 500_000_000, "total": 999_999_999, "files": 1, "file_total": 2}
        )
        == "500 / 1000 MB (50%), 1 / 2 files"
    )
    assert (
        cb.format_progress({"bytes": 250_000, "total": 500_000, "files": 1, "file_total": 2})
        == "250 / 500 KB (50%), 1 / 2 files"
    )
    assert (
        cb.format_progress({"bytes": 1000, "total": 2000, "files": None, "file_total": None})
        == "1 / 2 KB (50%)"
    )


def test_credentials_hint_needles():
    no_creds = "No AWS credentials"
    expired = "have expired"
    assert no_creds in cb.credentials_hint(
        "botocore.exceptions.NoCredentialsError: Unable to locate credentials"
    )
    for text in (
        "An error occurred (ExpiredTokenException): The security token included in the request is expired",
        "Error when retrieving token from sso: Token has expired and refresh failed",
        "UnauthorizedSSOTokenError: The SSO session associated with this profile has expired",
        "botocore: expired token",
    ):
        assert expired in cb.credentials_hint(text), text
    # Not a credentials problem: say what the tool said.
    for text in (
        "ResourceNotFoundException: Job job-1 could not be found",
        "The config file /x could not be found",
        "The license expired on 2026-01-01",
    ):
        assert cb.credentials_hint(text) == "", text


def test_parse_garbage_returns_empty():
    assert cb.parse_job_list("Displaying 1\n- name: [unclosed\n  jobId: job-1\n") == []
    assert cb.parse_job_list("- : : :\n\t- [\n") == []
    assert cb.parse_yaml_list("- farmId: [unclosed\n", "farmId") == []
    assert cb.parse_yaml_list("- just a string\n", "farmId") == []


def _exe(folder, name):
    import os
    import sys

    os.makedirs(folder, exist_ok=True)
    path = os.path.join(folder, name + (".exe" if sys.platform == "win32" else ""))
    with open(path, "w") as fh:
        fh.write("#!/bin/sh\n")
    os.chmod(path, 0o700)  # executable by its owner, the test
    return path


def test_resolve_finds_tools_next_to_this_python(tmp_path):
    """A same-environment pip install needs no PATH setup."""
    import os
    import sys

    scripts = tmp_path / "venv" / ("Scripts" if sys.platform == "win32" else "bin")
    python = _exe(str(scripts), "python")
    tool = _exe(str(scripts), "deadline-physical-ai")
    empty = {"PATH": str(tmp_path / "nothing-here")}
    assert procenv.resolve("deadline-physical-ai", env=empty, executable=python) == (
        tool,
        "next to this Python",
    )
    # A base install on Windows keeps python.exe above Scripts\, POSIX keeps it above bin/.
    base = tmp_path / "base"
    python2 = _exe(str(base), "python")
    tool2 = _exe(
        os.path.join(str(base), "Scripts" if sys.platform == "win32" else "bin"), "deadline"
    )
    assert procenv.resolve("deadline", env=empty, executable=python2) == (
        tool2,
        "next to this Python",
    )
    # By default (the extension), PATH and the setting come first.
    on_path = _exe(str(tmp_path / "onpath"), "deadline-physical-ai")
    path_env = {"PATH": str(tmp_path / "onpath")}
    # shutil.which on Windows appends the PATHEXT spelling (".EXE"), so compare normalized.
    found = procenv.resolve("deadline-physical-ai", env=path_env, executable=python)[0]
    assert os.path.normcase(found) == os.path.normcase(on_path)
    # The app prefers the CLIs of its own environment over PATH; the setting still wins.
    assert cb.resolve("deadline-physical-ai", env=path_env, executable=python) == (
        tool,
        "next to this Python",
    )
    found = cb.resolve("deadline-physical-ai", env=path_env, executable=python2)[0]
    assert os.path.normcase(found) == os.path.normcase(on_path)
    assert cb.resolve("deadline-physical-ai", override=tool2, env=empty, executable=python) == (
        tool2,
        "setting",
    )
    assert cb.beside_python("deadline-physical-ai", str(tmp_path / "x" / "python")) == ""


def test_open_with_os_cleans_kit_environment(monkeypatch):
    """xdg-open starts an ordinary desktop application: Kit's LD_LIBRARY_PATH, PYTHONHOME
    and Qt plugin paths would make it load Kit's libraries and fail."""
    seen: dict = {}
    monkeypatch.setattr(
        procenv.os,
        "environ",
        {
            "PYTHONHOME": "/kit/py",
            "LD_LIBRARY_PATH": "/kit/lib",
            "QT_QPA_PLATFORM_PLUGIN_PATH": "/kit/qt",
            "HOME": "/home/u",
        },
    )
    monkeypatch.setattr(procenv.sys, "platform", "linux")
    monkeypatch.setattr(
        procenv.subprocess, "Popen", lambda argv, **kw: seen.update(argv=argv, **kw)
    )
    cb.open_with_os("/d/ep_003.mp4")
    assert seen["argv"] == ["xdg-open", "/d/ep_003.mp4"]
    # The app's stdin may be the bridge pipe: the viewer must not inherit it.
    assert seen["stdin"] == procenv.subprocess.DEVNULL
    assert not {"PYTHONHOME", "LD_LIBRARY_PATH", "QT_QPA_PLATFORM_PLUGIN_PATH"} & set(seen["env"])
    assert seen["env"]["HOME"] == "/home/u"


def test_open_with_os_uses_the_shell_association_on_windows(monkeypatch):
    opened: list = []
    monkeypatch.setattr(procenv.sys, "platform", "win32")
    monkeypatch.setattr(procenv.os, "startfile", opened.append, raising=False)
    monkeypatch.setattr(
        procenv.subprocess, "Popen", lambda *a, **k: pytest.fail("no child process")
    )
    cb.open_with_os(r"C:\d\ep.mp4")
    assert opened == [r"C:\d\ep.mp4"]


def test_open_with_os_uses_open_on_macos(monkeypatch):
    seen: dict = {}
    monkeypatch.setattr(procenv.sys, "platform", "darwin")
    monkeypatch.setattr(
        procenv.subprocess, "Popen", lambda argv, **kw: seen.update(argv=argv, **kw)
    )
    cb.open_with_os("/d/ep.mp4")
    assert seen["argv"] == ["open", "/d/ep.mp4"]
