# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
"""Everything the app asks of AWS goes through command-line tools in a child process,
never ``import deadline`` or boto3 in the app.

* The stock ``deadline`` CLI: default farm and queue, job list, and the bundle submit
  dialog.
* ``deadline-physical-ai outputs list|fetch``: only for the two things the stock CLI
  cannot do yet (list a job's outputs without downloading them, and download chosen
  items into a chosen folder). When the stock CLI can, only the argv builders here
  change.

Commands run asynchronously (:class:`Command`, polled from the UI's timer) so the UI
never waits on the network.
"""

from __future__ import annotations

import json
import os
import subprocess
from dataclasses import dataclass

from . import procenv
from .procenv import beside_python, child_env, open_with_os

# Re-exported so callers keep one import for everything that starts a CLI child.
__all__ = ["beside_python", "child_env", "open_with_os", "resolve"]


def resolve(
    tool: str, override: str = "", env: dict | None = None, executable: str | None = None
) -> tuple[str, str]:
    """:func:`procenv.resolve`, preferring the CLIs next to the app's own Python: the app is
    started by ``deadline-physical-ai gui``, so its environment holds both CLIs."""
    return procenv.resolve(tool, override, env, executable, prefer_beside_python=True)


@dataclass
class Result:
    argv: list
    code: int
    stdout: str
    stderr: str

    @property
    def ok(self) -> bool:
        return self.code == 0

    def json(self) -> dict:
        """The last JSON object line on stdout (both tools print one per message)."""
        for line in reversed(self.stdout.strip().splitlines()):
            line = line.strip()
            if line.startswith("{"):
                try:
                    return json.loads(line)
                except ValueError:
                    continue
        return {}

    def error(self) -> str:
        """One line for the window: a credentials problem in plain words, else the tool's
        own message."""
        j = self.json()
        if j.get("status") == "error" or j.get("messageType") == "error":
            msg = str(j.get("error") or j.get("value") or "")
        else:
            lines = [
                ln
                for ln in (self.stderr + "\n" + self.stdout).strip().splitlines()
                if ln.strip() and not ln.startswith(("INFO:", "WARNING:", "  File ", "Traceback"))
            ]
            msg = lines[-1].strip() if lines else f"exit {self.code}"
        return credentials_hint(self.stderr + "\n" + self.stdout) or msg


#: Substrings (matched case-insensitively) that mean "no usable AWS credentials", and
#: what to tell the user. Kept specific: "could not be found" or a bare "expired" also
#: appear in unrelated errors (a missing job, an expired license) and would mislead.
_CRED_HINTS = (
    (
        ("Unable to locate credentials", "NoCredentialsError"),
        "No AWS credentials. Sign in with Deadline Cloud Monitor, or set a profile with `deadline config gui`.",
    ),
    (
        (
            "ExpiredToken",
            "expired token",
            "token has expired",
            "token is expired",
            "UnauthorizedSSOToken",
            "SSO session associated with this profile",
            "create_o_auth2_token",
        ),
        (
            "Your Deadline Cloud credentials have expired. Sign in again (Deadline Cloud Monitor or your profile) "
            "and Refresh."
        ),
    ),
    (
        ("AccessDenied", "AccessDeniedException", "not authorized", "UnrecognizedClientException"),
        (
            "These credentials aren't allowed to do this. Check the profile in `deadline config gui`, or ask your admin for "
            "Deadline Cloud access to this farm."
        ),
    ),
)


def credentials_hint(text: str) -> str:
    low = text.lower()
    for needles, hint in _CRED_HINTS:
        if any(n.lower() in low for n in needles):
            return hint
    return ""


class Command:
    """A child process polled from the UI loop: call :meth:`poll` each frame.

    stdout and stderr are drained by background threads from the start. Reading them only
    after exit deadlocks as soon as the child writes more than the OS pipe buffer (a few
    KB on Windows, e.g. a 50-job ``deadline job list``): the child blocks writing while we
    wait for it to finish. A child that runs past ``timeout_s`` is killed and reported as
    an error, so a CLI waiting on a sign-in cannot leave the window stuck."""

    TIMEOUT_EXIT = 124

    def __init__(
        self,
        argv: list,
        on_done,
        env: dict | None = None,
        timeout_s: float | None = 90.0,
        on_progress=None,
    ):
        import threading
        import time

        self.argv, self.on_done, self.on_progress = list(argv), on_done, on_progress
        self._progress_seen: dict | None = None
        self._deadline = time.monotonic() + timeout_s if timeout_s else None
        self._proc = subprocess.Popen(
            self.argv,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            stdin=subprocess.DEVNULL,
            text=True,
            encoding="utf-8",
            errors="replace",
            env=env,
            creationflags=procenv.NO_WINDOW,
        )
        self._out: list = []
        self._err: list = []
        self._readers = [
            threading.Thread(target=self._drain, args=(self._proc.stdout, self._out), daemon=True),
            threading.Thread(target=self._drain, args=(self._proc.stderr, self._err), daemon=True),
        ]
        for t in self._readers:
            t.start()
        self.done = False

    @staticmethod
    def _drain(stream, sink: list) -> None:
        # Line by line: ``read(n)`` on a text pipe blocks until n chars or EOF, which
        # would hold every PROGRESS line back until the child exits.
        try:
            sink.extend(iter(stream.readline, ""))
        except (OSError, ValueError):
            pass
        finally:
            try:
                stream.close()
            except OSError:
                pass

    def _finish(self, code: int, extra_err: str = "") -> None:
        for t in self._readers:
            t.join(timeout=5)
        self.done = True
        self.on_done(Result(self.argv, code, "".join(self._out), "".join(self._err) + extra_err))

    #: How many stderr chunks :meth:`progress` looks back through for a PROGRESS line.
    PROGRESS_LOOKBACK = 200

    def progress(self) -> dict | None:
        """The last complete ``PROGRESS {json}`` line the child wrote to stderr, if any.
        A line still being written, or one that is not a JSON object, is skipped so the
        previous good value stays on screen."""
        lines = "".join(self._err[-self.PROGRESS_LOOKBACK :]).split("\n")
        for line in reversed(lines[:-1]):  # the last piece has no newline yet
            if not line.startswith("PROGRESS "):
                continue
            try:
                p = json.loads(line[9:])
            except ValueError:
                continue
            if isinstance(p, dict):
                return p
        return None

    def poll(self) -> bool:
        if self.done:
            return True
        if self.on_progress is not None:
            p = self.progress()
            if p is not None and p != self._progress_seen:
                self._progress_seen = p
                self.on_progress(p)
        code = self._proc.poll()
        if code is not None:
            self._finish(code)
            return True
        import time

        if self._deadline is not None and time.monotonic() > self._deadline:
            self._proc.kill()
            self._proc.wait()
            text = "".join(self._err) + "".join(self._out)
            self._finish(
                self.TIMEOUT_EXIT,
                "\n"
                + (
                    credentials_hint(text)
                    or "Timed out waiting for the Deadline "
                    "Cloud CLI; it may be waiting for a sign-in. Check your "
                    "credentials and Refresh."
                ),
            )
            return True
        return False

    def cancel(self) -> None:
        if not self.done and self._proc.poll() is None:
            self._proc.kill()


# ----------------------------------------------------------- argv + parsing --


@dataclass
class Target:
    farm_id: str = ""
    queue_id: str = ""
    profile: str = ""
    region: str = ""

    def flags(self) -> list:
        out = []
        for flag, v in (
            ("--farm-id", self.farm_id),
            ("--queue-id", self.queue_id),
            ("--profile", self.profile),
            ("--region", self.region),
        ):
            if v:
                out += [flag, v]
        return out


#: The deadline CLI reads its config from this file when set (default ``~/.deadline/config``).
CONFIG_FILE_ENV = "DEADLINE_CONFIG_FILE_PATH"


def copy_deadline_config(folder: str) -> str:
    """Copy the deadline config in use into ``folder`` and return the copy's path (an empty
    file when there is none yet). Changing the copy never touches the user's defaults."""
    import shutil

    src = os.environ.get(CONFIG_FILE_ENV) or os.path.join(
        os.path.expanduser("~"), ".deadline", "config"
    )
    dst = os.path.join(folder, "config")
    if os.path.isfile(src):
        shutil.copyfile(src, dst)
    else:
        open(dst, "w").close()
    return dst


def config_get_argv(deadline: str, key: str) -> list:
    return [deadline, "config", "get", key]


def config_set_argv(deadline: str, key: str, value: str) -> list:
    return [deadline, "config", "set", key, value]


def farm_list_argv(deadline: str, target: Target) -> list:
    t = Target(profile=target.profile, region=target.region)
    return [deadline, "farm", "list", *t.flags()]


def queue_list_argv(deadline: str, target: Target) -> list:
    t = Target(farm_id=target.farm_id, profile=target.profile, region=target.region)
    return [deadline, "queue", "list", *t.flags()]


def parse_yaml_list(stdout: str, id_key: str) -> list:
    """``deadline farm list`` / ``queue list`` print a YAML list (log lines may precede it):
    ``[{id, name, region}]``, sorted by name."""
    import yaml

    lines, started = [], False
    for line in stdout.splitlines():
        if line.startswith("- "):
            started = True
        if started and (line.startswith(("- ", "  ")) or not line.strip()):
            lines.append(line)
        elif started:
            break
    try:
        data = yaml.safe_load("\n".join(lines)) if lines else []
    except yaml.YAMLError:  # not the YAML we expect: the caller reports "nothing found"
        return []
    out = []
    for d in data if isinstance(data, list) else []:
        if isinstance(d, dict) and d.get(id_key):
            out.append(
                {
                    "id": str(d[id_key]),
                    "name": str(d.get("displayName") or d[id_key]),
                    "region": str(d.get("region") or ""),
                }
            )
    return sorted(out, key=lambda x: x["name"].lower())


def job_list_argv(deadline: str, target: Target, page_size: int = 50) -> list:
    return [deadline, "job", "list", *target.flags(), "--page-size", str(page_size)]


def finished_jobs_argv(
    pai: str, target: Target, status: str = "succeeded", offset: int = 0, limit: int = 50
) -> list:
    """``deadline-physical-ai jobs list``: the service filters by status and sorts, so older
    finished jobs behind the newest page of all jobs still show."""
    argv = [pai, "jobs", "list", *target.flags(), "--status", status]
    argv += ["--limit", str(limit), "--json"]
    return argv + (["--offset", str(offset)] if offset else [])


def parse_job_list(stdout: str) -> list:
    """``deadline job list`` prints a header line, then a YAML list of jobs."""
    import yaml

    text = stdout
    i = text.find("\n- ")
    if i >= 0:
        text = text[i + 1 :]
    elif not text.lstrip().startswith("- "):
        return []
    try:
        data = yaml.safe_load(text) or []
    except yaml.YAMLError:
        return []
    jobs = []
    for j in data if isinstance(data, list) else []:
        if isinstance(j, dict) and j.get("jobId"):
            jobs.append(
                {
                    k: ("" if j.get(k) is None else str(j.get(k)))
                    for k in ("jobId", "name", "taskRunStatus", "createdBy", "createdAt", "endedAt")
                }
            )
    return jobs


def short_principal(arn: str) -> str:
    """``arn:aws:sts::123456789012:assumed-role/role/session-name`` -> ``session-name``."""
    return arn.rsplit("/", 1)[-1] if "/" in arn else arn


def job_params_argv(pai: str, target: Target, job_ids: list) -> list:
    """``deadline-physical-ai jobs params``: each job's name and parameters as text."""
    return [pai, "jobs", "params", *job_ids, *target.flags(), "--json"]


def job_evals_argv(pai: str, target: Target, offset: int = 0, limit: int = 50) -> list:
    """``deadline-physical-ai jobs evals``: completed jobs with parameters and eval summary."""
    argv = [pai, "jobs", "evals", *target.flags(), "--limit", str(limit), "--json"]
    return argv + (["--offset", str(offset)] if offset else [])


def outputs_list_argv(pai: str, target: Target, job_id: str) -> list:
    return [pai, "outputs", "list", job_id, *target.flags(), "--json"]


def outputs_fetch_argv(pai: str, target: Target, job_id: str, paths: list, dest: str) -> list:
    argv = [pai, "outputs", "fetch", job_id, *target.flags(), "--json", "--progress"]
    for p in paths:
        argv += ["--path", p]
    if dest:
        argv += ["--dest", dest]
    return argv


def gui_submit_argv(
    deadline: str,
    bundle_dir: str,
    prefill: dict | None = None,
    *,
    app_version: str = "",
    ext_version: str = "",
) -> list:
    """``--install-gui`` is required: without it, a missing PySide6 makes the CLI prompt on
    stdin, and the app's children have no terminal, so it hangs. Any ``submitter_name``
    other than ``JobBundle`` makes the dialog close itself after a successful submit.
    ``app_version`` is the connected Isaac Sim's version; standalone there is no host
    application to report."""
    argv = [
        deadline,
        "bundle",
        "gui-submit",
        bundle_dir,
        "--output",
        "json",
        "--install-gui",
        "--submitter-info",
        "submitter_name=IsaacSim",
        "--submitter-info",
        "submitter_package_name=deadline-cloud-for-isaac-sim",
    ]
    if app_version:
        argv += ["--submitter-info", "host_application_name=Isaac Sim"]
        argv += ["--submitter-info", f"host_application_version={app_version}"]
    if ext_version:
        argv += ["--submitter-info", f"submitter_package_version={ext_version}"]
    # ``-p Name=Value`` pairs, not ``-p file://...``: older deadline CLIs accept only the
    # pair form (the file form arrived later), and argv items need no shell quoting.
    for k, v in (prefill or {}).items():
        argv += ["-p", f"{k}={v}"]
    return argv


def format_progress(p: dict) -> str:
    """``{"bytes", "total", "files", "file_total"}`` -> ``412 / 876 MB (47%), 640 / 1755 files``.
    The file counts are left out when the tool does not report them."""
    done, total = int(p.get("bytes") or 0), int(p.get("total") or 0)

    def size(n: int) -> str:
        return (
            f"{n / 1e9:.2f} GB"
            if total >= 1e9
            else f"{n / 1e6:.0f} MB" if total >= 1e6 else f"{n / 1e3:.0f} KB"
        )

    pct = f" ({100 * done // total}%)" if total else ""
    files = (
        ""
        if p.get("file_total") is None
        else f", {int(p.get('files') or 0)} / {int(p['file_total'])} files"
    )
    return f"{size(done).split()[0]} / {size(total)}{pct}{files}"


def parse_submit_result(stdout: str) -> dict:
    """The last JSON object on stdout with a ``status`` key (``{}`` if none):
    ``{"status": "SUBMITTED", "jobId": ...}`` or ``{"status": "CANCELED"}``."""
    for line in reversed((stdout or "").splitlines()):
        line = line.strip()
        if line.startswith("{") and line.endswith("}"):
            try:
                obj = json.loads(line)
            except ValueError:
                continue
            if isinstance(obj, dict) and "status" in obj:
                return obj
    return {}
