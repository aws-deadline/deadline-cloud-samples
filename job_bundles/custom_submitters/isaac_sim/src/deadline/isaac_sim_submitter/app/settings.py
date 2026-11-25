# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
"""The app's settings: one JSON object in the user's config folder.

* Windows: ``%APPDATA%\\deadline-cloud-for-isaac-sim\\settings.json``
* Linux and macOS: ``$XDG_CONFIG_HOME/deadline-cloud-for-isaac-sim/settings.json``
  (default ``~/.config/...``)

``DEADLINE_CLOUD_FOR_ISAAC_SIM_SETTINGS`` names another file. A missing or unreadable file
means defaults; a change is written at once, atomically.
"""

from __future__ import annotations

import json
import os
import sys
import tempfile

APP_DIR = "deadline-cloud-for-isaac-sim"
PATH_ENV = "DEADLINE_CLOUD_FOR_ISAAC_SIM_SETTINGS"

#: ";"-separated folders searched for job bundles (Submit pipeline job).
BUNDLE_DIRS = "bundleDirs"
#: Where loaded items go (``<downloadDir>/<job id>``). Empty:
#: ``~/.deadline/physical-ai/job_outputs/<job id>``.
DOWNLOAD_DIR = "downloadDir"
#: Where Submit puts a new, empty folder for each output folder parameter that has no
#: default (``<outputDir>/<bundle folder>/<date-time>``).
OUTPUT_DIR = "outputDir"
DEADLINE_EXECUTABLE = "deadlineExecutable"
PHYSICAL_AI_EXECUTABLE = "physicalAiExecutable"
#: The last job loaded (prefills a previous-job parameter).
LAST_LOADED_JOB = "lastLoadedJob"

DEFAULTS = {BUNDLE_DIRS: "~/DeadlineCloud/JobBundles", OUTPUT_DIR: "~/DeadlineCloud/JobOutputs"}
KEYS = (
    BUNDLE_DIRS,
    DOWNLOAD_DIR,
    OUTPUT_DIR,
    DEADLINE_EXECUTABLE,
    PHYSICAL_AI_EXECUTABLE,
    LAST_LOADED_JOB,
)

#: The file last read and what it held, so a lookup does not read the disk.
_cache: dict = {"path": None, "values": {}}


def settings_path() -> str:
    override = os.environ.get(PATH_ENV)
    if override:
        return os.path.expanduser(override)
    if sys.platform == "win32":
        base = os.environ.get("APPDATA") or os.path.expanduser(
            os.path.join("~", "AppData", "Roaming")
        )
    else:
        base = os.environ.get("XDG_CONFIG_HOME") or os.path.expanduser(os.path.join("~", ".config"))
    return os.path.join(base, APP_DIR, "settings.json")


def _values() -> dict:
    path = settings_path()
    if _cache["path"] != path:
        values: dict = {}
        try:
            with open(path, encoding="utf-8") as fh:
                data = json.load(fh)
            if isinstance(data, dict):
                values = {k: str(v) for k, v in data.items() if isinstance(v, (str, int, float))}
        except (OSError, ValueError):
            # A missing or unreadable settings file means defaults, not an error.
            pass
        _cache.update(path=path, values=values)
    return _cache["values"]


def get_str(key: str, default: str | None = None) -> str:
    if default is None:
        default = DEFAULTS.get(key, "")
    value = _values().get(key)
    return default if value is None else value


def set_str(key: str, value: str) -> None:
    values = dict(_values())
    values[key] = value or ""
    path = settings_path()
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    fd, tmp = tempfile.mkstemp(
        prefix=".settings-", suffix=".json", dir=os.path.dirname(path) or "."
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(values, fh, indent=2, sort_keys=True)
            fh.write("\n")
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            # Best-effort cleanup of the temp file; the original error is re-raised below.
            pass
        raise
    _cache.update(path=path, values=values)


def reload() -> None:
    """Forget the cached file, so the next lookup reads it again."""
    _cache.update(path=None, values={})


def output_root() -> str:
    """The folder Submit's new output folders go under."""
    return os.path.abspath(os.path.expanduser(get_str(OUTPUT_DIR) or DEFAULTS[OUTPUT_DIR]))


def download_root() -> str:
    """The folder every job's downloads go under."""
    configured = get_str(DOWNLOAD_DIR)
    if configured:
        return os.path.abspath(os.path.expanduser(configured))
    from deadline.physical_ai.config import home_dir

    return os.path.abspath(os.path.join(home_dir(), "job_outputs"))
