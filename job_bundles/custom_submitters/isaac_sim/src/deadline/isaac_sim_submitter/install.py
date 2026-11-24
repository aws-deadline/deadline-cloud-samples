# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
"""Install the ``isaacsim.deadline.submitter`` extension into Isaac Sim with a directory link.

Nothing is copied: the link points at the extension folder shipped in this package, so
upgrading the package upgrades the extension.

Where the link goes:

* If the ``isaacsim`` pip package is importable (in this environment, or in the one whose
  Python is passed as ``isaac_sim_python``): ``<isaacsim package>/extsUser/``. Kit scans
  that folder with no configuration.
* Otherwise: the per-user Kit folder ``~/Documents/Kit/shared/exts`` (Windows:
  ``%USERPROFILE%\\Documents\\Kit\\shared\\exts``), or ``kit_user_folder``.

The link is a symlink on POSIX and a directory junction on Windows (junctions need no
administrator rights or Developer Mode).

``enable`` adds the extension to ``persistent.app.exts.enabled`` in the Isaac Sim GUI app's
``user.config.json`` (Windows: ``%LOCALAPPDATA%\\ov\\data\\Kit\\Isaac-Sim Full\\<major.minor>``;
Linux: ``~/.local/share/ov/data/Kit/Isaac-Sim Full/<major.minor>``). The file is written
atomically and the previous content is kept as ``user.config.json.bak``. Kit rewrites this
file when Isaac Sim exits, so run this with Isaac Sim closed.

The ``isaacsim`` package is located with :func:`importlib.util.find_spec`, which does not
import it (importing it starts Isaac Sim's bootstrap).
"""

from __future__ import annotations

import importlib.metadata
import importlib.util
import json
import os
import stat
import subprocess
import sys
import tempfile
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from . import EXTENSION_NAME, extension_path

APP_NAME = "Isaac-Sim Full"
USER_CONFIG = "user.config.json"
ENABLED_KEYS = ("persistent", "app", "exts", "enabled")
ISAACSIM_DISTRIBUTION = "isaacsim"

METHOD_PACKAGE = "isaacsim-package"
METHOD_KIT_USER = "kit-user-folder"


class InstallError(RuntimeError):
    """The extension could not be installed or uninstalled; the message says why."""


@dataclass
class IsaacSimPackage:
    """Where an ``isaacsim`` pip package lives, and its version (``""`` if unknown)."""

    path: str
    version: str = ""


@dataclass
class InstallResult:
    action: str  # "install" | "uninstall"
    method: str  # METHOD_PACKAGE | METHOD_KIT_USER
    extension_path: str
    link: str
    link_status: str  # "created" | "exists" | "replaced" | "removed" | "absent"
    isaac_sim_version: str = ""
    user_config: str = ""
    enabled: str = "skipped"  # "added" | "present" | "removed" | "absent" | "skipped"
    notes: list = field(default_factory=list)

    def to_dict(self) -> dict:
        d = asdict(self)
        d["status"] = "ok"
        d["extension"] = EXTENSION_NAME
        return d


# ------------------------------------------------------------- locate Isaac Sim --

_PROBE = r"""
import importlib.metadata, importlib.util, json, os
spec = importlib.util.find_spec("isaacsim")
out = {"path": "", "version": ""}
if spec is not None:
    locs = [str(x) for x in (spec.submodule_search_locations or [])]
    with_user = [x for x in locs if os.path.isdir(os.path.join(x, "extsUser"))]
    out["path"] = (with_user or locs or [""])[0]
    try:
        out["version"] = importlib.metadata.version("isaacsim")
    except importlib.metadata.PackageNotFoundError:
        pass
print(json.dumps(out))
"""


def _package_dir(locations: list) -> str:
    """The location holding ``extsUser`` if one does, else the first one."""
    for loc in locations:
        if os.path.isdir(os.path.join(loc, "extsUser")):
            return str(loc)
    return str(locations[0]) if locations else ""


def find_isaacsim() -> IsaacSimPackage | None:
    """The ``isaacsim`` pip package importable here, without importing it."""
    try:
        spec = importlib.util.find_spec(ISAACSIM_DISTRIBUTION)
    except (ImportError, ValueError):
        return None
    if spec is None:
        return None
    path = _package_dir(list(spec.submodule_search_locations or []))
    if not path:
        return None
    try:
        version = importlib.metadata.version(ISAACSIM_DISTRIBUTION)
    except importlib.metadata.PackageNotFoundError:
        version = ""
    return IsaacSimPackage(path, version)


def probe_python(python: str, timeout_s: float = 60.0) -> IsaacSimPackage:
    """The ``isaacsim`` package seen by another Python (for example Isaac Sim's own)."""
    if not os.path.isfile(python):
        raise InstallError(f"--isaac-sim-python {python!r} is not a file")
    try:
        done = subprocess.run(
            [python, "-c", _PROBE],
            capture_output=True,
            text=True,
            timeout=timeout_s,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise InstallError(f"could not run {python}: {exc}") from exc
    if done.returncode != 0:
        raise InstallError(f"{python} failed: {(done.stderr or done.stdout).strip()[-500:]}")
    try:
        found = json.loads(done.stdout.strip().splitlines()[-1])
    except (ValueError, IndexError) as exc:
        raise InstallError(f"unexpected output from {python}: {done.stdout[-200:]!r}") from exc
    if not found.get("path"):
        raise InstallError(f"the isaacsim package is not installed for {python}")
    return IsaacSimPackage(str(found["path"]), str(found.get("version") or ""))


def major_minor(version: str) -> str:
    """``"5.1.0.0"`` -> ``"5.1"``; ``""`` when it is not a version."""
    parts = version.strip().split(".")
    if len(parts) < 2 or not (parts[0].isdigit() and parts[1].isdigit()):
        return ""
    return f"{int(parts[0])}.{int(parts[1])}"


def _home() -> Path:
    return Path(os.path.expanduser("~"))


def kit_user_exts() -> Path:
    """The per-user Kit extension folder Kit scans by default (the same on every OS)."""
    return _home() / "Documents" / "Kit" / "shared" / "exts"


def user_config_path(version: str, platform: str = sys.platform) -> Path:
    """The Isaac Sim GUI app's ``user.config.json`` for ``major.minor`` ``version``."""
    if platform == "win32":
        base = os.environ.get("LOCALAPPDATA") or str(_home() / "AppData" / "Local")
        data = Path(base) / "ov" / "data"
    else:
        data = _home() / ".local" / "share" / "ov" / "data"
    return data / "Kit" / APP_NAME / version / USER_CONFIG


# ------------------------------------------------------------------- links --


def is_link(path: Path) -> bool:
    """A symlink, or (Windows) a directory junction or other reparse point."""
    if os.path.islink(path):
        return True
    isjunction = getattr(os.path, "isjunction", None)  # Python 3.12+
    if isjunction is not None and isjunction(path):
        return True
    try:
        attrs = getattr(os.lstat(path), "st_file_attributes", 0)
    except OSError:
        return False
    return bool(attrs & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400))


def _same(a: Path, b: Path) -> bool:
    try:
        return os.path.normcase(os.path.realpath(a)) == os.path.normcase(os.path.realpath(b))
    except OSError:
        return False


def make_link(link: Path, target: Path, platform: str = sys.platform) -> None:
    """A directory link at ``link`` pointing at ``target``."""
    if platform != "win32":
        os.symlink(target, link, target_is_directory=True)
        return
    try:
        import _winapi

        _winapi.CreateJunction(str(target), str(link))  # type: ignore[attr-defined]
        return
    except (ImportError, AttributeError):
        pass
    done = subprocess.run(
        ["cmd", "/c", "mklink", "/J", str(link), str(target)],
        capture_output=True,
        text=True,
        check=False,
    )
    if done.returncode != 0:
        raise InstallError(f"mklink /J failed: {(done.stderr or done.stdout).strip()}")


def remove_link(link: Path, platform: str = sys.platform) -> None:
    """Remove the link itself, never what it points at."""
    if platform == "win32" and not os.path.islink(link):
        os.rmdir(link)  # a junction: rmdir removes the junction, not the target's files
    else:
        os.unlink(link)


def _place_link(link: Path, target: Path, platform: str) -> str:
    if os.path.lexists(link):
        if not is_link(link):
            raise InstallError(
                f"{link} already exists and is not a link; refusing to replace it. Move or "
                "delete it, then run this again."
            )
        if _same(link, target):
            return "exists"
        remove_link(link, platform)
        make_link(link, target, platform)
        return "replaced"
    link.parent.mkdir(parents=True, exist_ok=True)
    make_link(link, target, platform)
    return "created"


# ---------------------------------------------------------------- enabling --


def _read_config(path: Path) -> dict:
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise InstallError(f"cannot read {path}: {exc}; fix or remove it, then retry") from exc
    if not isinstance(data, dict):
        raise InstallError(f"{path} does not hold a JSON object")
    return data


def _enabled_list(data: dict, path: Path, create: bool) -> list | None:
    node: Any = data
    for key in ENABLED_KEYS[:-1]:
        child = node.get(key)
        if child is None:
            if not create:
                return None
            child = node[key] = {}
        if not isinstance(child, dict):
            raise InstallError(f"{path}: {'.'.join(ENABLED_KEYS)} is not where it is expected")
        node = child
    enabled = node.get(ENABLED_KEYS[-1])
    if enabled is None:
        if not create:
            return None
        enabled = node[ENABLED_KEYS[-1]] = []
    if not isinstance(enabled, list):
        raise InstallError(f"{path}: {'.'.join(ENABLED_KEYS)} is not a list")
    return enabled


def _write_config(path: Path, data: dict) -> None:
    """Back up the current file to ``.bak``, then replace it atomically."""
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.is_file():
        backup = path.with_name(path.name + ".bak")
        backup.write_bytes(path.read_bytes())
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=".tmp-", suffix=".json")
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as fh:
            json.dump(data, fh, indent=4)
            fh.write("\n")
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def set_enabled(path: Path, enabled: bool) -> str:
    """Add or remove the extension in ``persistent.app.exts.enabled``; idempotent."""
    data = _read_config(path)
    names = _enabled_list(data, path, create=enabled)
    if enabled:
        assert names is not None
        if any(n == EXTENSION_NAME or str(n).startswith(EXTENSION_NAME + "-") for n in names):
            return "present"
        names.append(EXTENSION_NAME)
        _write_config(path, data)
        return "added"
    # Kit rewrites a bare name to "name-<version>" once it has run, so match both.
    ours = [
        n for n in names or [] if n == EXTENSION_NAME or str(n).startswith(EXTENSION_NAME + "-")
    ]
    if names is None or not ours:
        return "absent"
    names[:] = [n for n in names if n not in ours]
    _write_config(path, data)
    return "removed"


# -------------------------------------------------------------------- entry --


def install(
    *,
    enable: bool = False,
    uninstall: bool = False,
    isaac_sim_python: str = "",
    kit_user_folder: str = "",
    isaac_sim_version: str = "",
    platform: str = sys.platform,
) -> InstallResult:
    """Link (or unlink, with ``uninstall``) the extension; see the module docstring."""
    if isaac_sim_python and kit_user_folder:
        raise InstallError("pass --isaac-sim-python or --kit-user-folder, not both")
    target = extension_path()
    package: IsaacSimPackage | None = None
    if kit_user_folder:
        exts = Path(os.path.expanduser(kit_user_folder))
    else:
        package = probe_python(isaac_sim_python) if isaac_sim_python else find_isaacsim()
        exts = Path(package.path) / "extsUser" if package else kit_user_exts()
    method = METHOD_PACKAGE if package else METHOD_KIT_USER

    version = ""
    if isaac_sim_version:
        version = major_minor(isaac_sim_version)
        if not version:
            raise InstallError(
                f"--isaac-sim-version {isaac_sim_version!r} is not like 5.1 or 6.0.1"
            )
    elif package:
        version = major_minor(package.version)
    if enable and not version:
        raise InstallError(
            "cannot tell which Isaac Sim version to enable the extension for; pass "
            "--isaac-sim-version (for example 5.1)"
        )

    link = exts / EXTENSION_NAME
    result = InstallResult(
        action="uninstall" if uninstall else "install",
        method=method,
        extension_path=str(target),
        link=str(link),
        link_status="",
        isaac_sim_version=version,
    )
    if uninstall:
        if not os.path.lexists(link):
            result.link_status = "absent"
        elif not is_link(link):
            raise InstallError(f"{link} is not a link; refusing to delete it")
        else:
            remove_link(link, platform)
            result.link_status = "removed"
    else:
        result.link_status = _place_link(link, target, platform)

    if version and (enable or uninstall):
        config = user_config_path(version, platform)
        result.user_config = str(config)
        result.enabled = set_enabled(config, not uninstall)
    elif uninstall:
        result.notes.append(
            "the enabled-extensions entry was not checked: pass --isaac-sim-version to remove it"
        )
    if method == METHOD_KIT_USER and not uninstall:
        result.notes.append(
            "no isaacsim pip package found here; linked into the per-user Kit folder, which "
            "Isaac Sim scans by default"
        )
    return result
