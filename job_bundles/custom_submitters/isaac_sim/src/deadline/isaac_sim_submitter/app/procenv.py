# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
"""Find the Deadline Cloud CLIs and give child processes a clean environment.

Shared by the app (``deadline.isaac_sim_submitter.app.procenv``) and the Isaac Sim
extension (``isaacsim.deadline.submitter.procenv``), which cannot import site-packages in
every Isaac Sim install. The two files must stay identical (a unit test checks), so this
module imports only the standard library.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys

# Kit's Python and Qt state that must not reach a child Python (PYTHONHOME is fatal
# to a console script; QT_* breaks a child's Qt plugins).
_DROP = (
    "PYTHONHOME",
    "PYTHONPATH",
    "PYTHONSTARTUP",
    "PYTHONEXECUTABLE",
    "PYTHONNOUSERSITE",
    "PYTHONOPTIMIZE",
    "PYTHONDONTWRITEBYTECODE",
    "LD_PRELOAD",
    "QT_PLUGIN_PATH",
    "QT_QPA_PLATFORM_PLUGIN_PATH",
    "QT_QPA_PLATFORM",
    "QT_API",
    "QML_IMPORT_PATH",
    "QML2_IMPORT_PATH",
    "CARB_APP_PATH",
    "EXP_PATH",
    "ISAAC_PATH",
)

_PROBES = {
    "deadline": (
        "~/deadline-venv/bin/deadline",
        "~/.local/bin/deadline",
        "/usr/local/bin/deadline",
        "/opt/deadline/bin/deadline",
        r"C:\Program Files\DeadlineCloudSubmitter\DeadlineClient\deadline.exe",
        "~/DeadlineCloudSubmitter/DeadlineClient/deadline",
    ),
    "deadline-physical-ai": (
        "~/.local/bin/deadline-physical-ai",
        "/usr/local/bin/deadline-physical-ai",
    ),
}

#: ``creationflags`` that keep a console window from opening for a Windows child.
NO_WINDOW = 0x08000000 if sys.platform == "win32" else 0  # CREATE_NO_WINDOW


def _usable(path: str) -> bool:
    return bool(path) and os.path.isfile(path) and os.access(path, os.X_OK)


def beside_python(tool: str, executable: str | None = None) -> str:
    """``tool`` in the scripts folder of the Python running this code (``""`` if absent).

    With ``pip install`` into the same environment as Isaac Sim, the console scripts land
    next to its Python (``Scripts\\`` on Windows, ``bin/`` on POSIX), which is often not
    on ``PATH``."""
    exe = executable if executable is not None else sys.executable
    if not exe:
        return ""
    here = os.path.dirname(os.path.abspath(exe))
    folders = [here, os.path.join(here, "Scripts" if sys.platform == "win32" else "bin")]
    names = (tool + ".exe", tool) if sys.platform == "win32" else (tool,)
    for folder in folders:
        for name in names:
            p = os.path.join(folder, name)
            if _usable(p):
                return p
    return ""


def resolve(
    tool: str,
    override: str = "",
    env: dict | None = None,
    executable: str | None = None,
    prefer_beside_python: bool = False,
) -> tuple[str, str]:
    """``(path, how)``; ``path`` is ``""`` when not found. Order: the setting, ``PATH``,
    next to this Python, the usual install locations, then (for ``deadline-physical-ai``)
    next to ``deadline``. ``prefer_beside_python`` checks next to this Python before
    ``PATH``: the app runs from the environment its CLIs were installed into."""
    environ = os.environ if env is None else env
    if override:
        p = os.path.expanduser(override)
        return (
            (p, "setting") if _usable(p) else ("", f"setting is not an executable file: {override}")
        )
    beside = beside_python(tool, executable)
    if prefer_beside_python and beside:
        return beside, "next to this Python"
    found = shutil.which(tool, path=environ.get("PATH"))
    if found and _usable(found):
        return found, "PATH"
    if beside:
        return beside, "next to this Python"
    for c in _PROBES.get(tool, ()):
        p = os.path.expanduser(c)
        if _usable(p):
            return p, c
    # A conda/venv install puts both tools in one bin folder.
    if tool == "deadline-physical-ai":
        d, _ = resolve("deadline", env=env, executable=executable)
        if d:
            for name in ("deadline-physical-ai", "deadline-physical-ai.exe"):
                p = os.path.join(os.path.dirname(d), name)
                if _usable(p):
                    return p, "next to deadline"
    return "", "not found on PATH or in the usual install locations"


def child_env(exe: str, base: dict | None = None) -> dict:
    """``base`` (default: this process's environment) without Kit's Python and Qt state,
    with UTF-8 pipes, and with ``exe``'s folder first on ``PATH``."""
    env = dict(os.environ if base is None else base)
    for k in _DROP:
        env.pop(k, None)
    orig = env.get("LD_LIBRARY_PATH_ORIG")
    if orig is not None:
        env["LD_LIBRARY_PATH"] = orig
    else:
        env.pop("LD_LIBRARY_PATH", None)
    # Overriding any user value is deliberate: the parent decodes the child's pipes as
    # UTF-8, so the child must write UTF-8. Without this the default on Windows is the
    # console code page, which garbles non-ASCII paths and job names.
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUTF8"] = "1"
    if exe:
        env["PATH"] = os.path.dirname(os.path.abspath(exe)) + os.pathsep + env.get("PATH", "")
    return env


def open_with_os(path: str) -> None:
    """Open ``path`` in the OS default application, with the cleaned environment.

    ``xdg-open`` starts an ordinary desktop application, so it needs the same cleaned
    environment as the CLIs (:func:`child_env`): Kit's ``LD_LIBRARY_PATH``, ``PYTHONHOME``
    and Qt plugin paths make the handler load Kit's libraries instead of its own. Its stdin
    is closed: this process's stdin may be a pipe that must not be shared."""
    if sys.platform == "win32":
        os.startfile(path)  # the shell association, never a shell command line
        return
    opener = "open" if sys.platform == "darwin" else "xdg-open"
    subprocess.Popen([opener, path], env=child_env(""), stdin=subprocess.DEVNULL)
