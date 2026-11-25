# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
"""``deadline-physical-ai isaac-sim install-extension``, against temporary folders only."""

from __future__ import annotations

import importlib.machinery
import json
import os
import sys
from pathlib import Path
from typing import Any

import pytest

from deadline.isaac_sim_submitter import EXTENSION_NAME, extension_path
from deadline.isaac_sim_submitter import install as ins
from deadline.physical_ai import cli

_REAL_FIND = ins.find_isaacsim


@pytest.fixture()
def home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    h = tmp_path / "home"
    h.mkdir()
    monkeypatch.setattr(ins, "_home", lambda: h)
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "localappdata"))
    monkeypatch.setattr(ins, "find_isaacsim", lambda: None)
    return h


@pytest.fixture()
def isaacsim_pkg(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, home: Path) -> Path:
    """A fake ``isaacsim`` pip package that find_spec reports, at version 5.1.0.0."""
    pkg = tmp_path / "site-packages" / "isaacsim"
    (pkg / "extsUser").mkdir(parents=True)
    spec = importlib.machinery.ModuleSpec("isaacsim", None, is_package=True)
    spec.submodule_search_locations = [str(pkg)]
    monkeypatch.setattr(
        ins.importlib.util, "find_spec", lambda name: spec if name == "isaacsim" else None
    )
    monkeypatch.setattr(
        ins.importlib.metadata, "version", lambda name: "5.1.0.0" if name == "isaacsim" else "0"
    )
    monkeypatch.setattr(ins, "find_isaacsim", _REAL_FIND)
    return pkg


def _run(capsys: pytest.CaptureFixture, *args: str) -> tuple[int, dict]:
    code = cli.main(["isaac-sim", "install-extension", "--json", *args])
    return code, json.loads(capsys.readouterr().out)


def test_find_isaacsim_uses_find_spec_without_importing(isaacsim_pkg: Path) -> None:
    found = ins.find_isaacsim()
    assert found is not None and found.path == str(isaacsim_pkg) and found.version == "5.1.0.0"
    assert "isaacsim" not in sys.modules


def test_install_into_the_isaacsim_package_and_enable(
    isaacsim_pkg: Path, tmp_path: Path, capsys: pytest.CaptureFixture
) -> None:
    code, obj = _run(capsys, "--enable")
    assert code == 0 and obj["status"] == "ok", obj
    link = isaacsim_pkg / "extsUser" / EXTENSION_NAME
    assert obj["method"] == ins.METHOD_PACKAGE and obj["link"] == str(link)
    assert obj["link_status"] == "created" and ins.is_link(link)
    assert os.path.samefile(link, extension_path())
    assert (link / "config" / "extension.toml").is_file()
    config = Path(obj["user_config"])
    assert config == ins.user_config_path("5.1") and "5.1" in config.parts
    assert obj["enabled"] == "added" and obj["isaac_sim_version"] == "5.1"
    data = json.loads(config.read_text(encoding="utf-8"))
    assert data["persistent"]["app"]["exts"]["enabled"] == [EXTENSION_NAME]
    # Idempotent.
    code, again = _run(capsys, "--enable")
    assert (again["link_status"], again["enabled"]) == ("exists", "present")
    # Uninstall removes both, and leaves the shipped folder alone.
    code, gone = _run(capsys, "--uninstall")
    assert code == 0 and (gone["link_status"], gone["enabled"]) == ("removed", "removed")
    assert not os.path.lexists(link) and (extension_path() / "config" / "extension.toml").is_file()
    assert (
        json.loads(config.read_text(encoding="utf-8"))["persistent"]["app"]["exts"]["enabled"] == []
    )
    code, twice = _run(capsys, "--uninstall")
    assert (twice["link_status"], twice["enabled"]) == ("absent", "absent")


def test_uninstall_removes_the_versioned_entry_kit_writes(
    isaacsim_pkg: Path, capsys: pytest.CaptureFixture
) -> None:
    """Once Isaac Sim has run, Kit rewrites the bare name to "name-<version>"."""
    code, obj = _run(capsys, "--enable")
    config = Path(obj["user_config"])
    data = json.loads(config.read_text(encoding="utf-8"))
    data["persistent"]["app"]["exts"]["enabled"] = ["other.ext", EXTENSION_NAME + "-0.0.0-post12"]
    config.write_text(json.dumps(data), encoding="utf-8")
    code, again = _run(capsys, "--enable")
    assert again["enabled"] == "present"
    code, gone = _run(capsys, "--uninstall")
    assert code == 0 and gone["enabled"] == "removed"
    enabled = json.loads(config.read_text(encoding="utf-8"))["persistent"]["app"]["exts"]["enabled"]
    assert enabled == ["other.ext"]


def test_enable_preserves_other_settings_and_backs_up(
    isaacsim_pkg: Path, capsys: pytest.CaptureFixture
) -> None:
    config = ins.user_config_path("5.1")
    config.parent.mkdir(parents=True)
    original = {
        "persistent": {"app": {"exts": {"enabled": ["omni.other"]}, "window": {"w": 1}}},
        "keep": [1, 2],
    }
    config.write_text(json.dumps(original), encoding="utf-8")
    code, obj = _run(capsys, "--enable")
    assert code == 0 and obj["enabled"] == "added"
    data = json.loads(config.read_text(encoding="utf-8"))
    assert data["keep"] == [1, 2] and data["persistent"]["app"]["window"] == {"w": 1}
    assert data["persistent"]["app"]["exts"]["enabled"] == ["omni.other", EXTENSION_NAME]
    backup = config.with_name(config.name + ".bak")
    assert json.loads(backup.read_text(encoding="utf-8")) == original
    assert not [p for p in config.parent.iterdir() if p.name.startswith(".tmp-")]


def test_bad_user_config_is_not_overwritten(
    isaacsim_pkg: Path, capsys: pytest.CaptureFixture
) -> None:
    config = ins.user_config_path("5.1")
    config.parent.mkdir(parents=True)
    config.write_text("{not json", encoding="utf-8")
    code, obj = _run(capsys, "--enable")
    assert code == cli.EXIT_ERROR and obj["status"] == "error" and "cannot read" in obj["error"]
    assert config.read_text(encoding="utf-8") == "{not json"
    config.write_text(
        json.dumps({"persistent": {"app": {"exts": {"enabled": "x"}}}}), encoding="utf-8"
    )
    code, obj = _run(capsys, "--enable")
    assert code == cli.EXIT_ERROR and "is not a list" in obj["error"]


def test_fallback_to_the_kit_user_folder(home: Path, capsys: pytest.CaptureFixture) -> None:
    code, obj = _run(capsys)
    link = home / "Documents" / "Kit" / "shared" / "exts" / EXTENSION_NAME
    assert code == 0 and obj["method"] == ins.METHOD_KIT_USER and obj["link"] == str(link)
    assert ins.is_link(link) and obj["enabled"] == "skipped" and obj["notes"]
    # --enable needs a version when there is no isaacsim package to read it from.
    code, obj = _run(capsys, "--enable")
    assert code == cli.EXIT_ERROR and "--isaac-sim-version" in obj["error"]
    code, obj = _run(capsys, "--enable", "--isaac-sim-version", "6.0.1")
    assert (
        code == 0
        and obj["enabled"] == "added"
        and obj["user_config"] == str(ins.user_config_path("6.0"))
    )
    code, obj = _run(capsys, "--uninstall", "--isaac-sim-version", "6.0")
    assert (obj["link_status"], obj["enabled"]) == ("removed", "removed")


def test_explicit_kit_user_folder(
    home: Path, tmp_path: Path, capsys: pytest.CaptureFixture
) -> None:
    exts = tmp_path / "kitx"
    code, obj = _run(capsys, "--kit-user-folder", str(exts))
    assert (
        code == 0 and obj["link"] == str(exts / EXTENSION_NAME) and obj["link_status"] == "created"
    )
    code, obj = _run(capsys, "--kit-user-folder", str(exts), "--uninstall")
    assert obj["link_status"] == "removed" and "--isaac-sim-version" in obj["notes"][0]
    assert exts.is_dir() and not list(exts.iterdir())


def test_refuses_to_replace_a_real_folder(
    home: Path, tmp_path: Path, capsys: pytest.CaptureFixture
) -> None:
    exts = tmp_path / "kitx"
    (exts / EXTENSION_NAME / "config").mkdir(parents=True)
    (exts / EXTENSION_NAME / "config" / "extension.toml").write_text("x")
    for extra in ([], ["--uninstall"]):
        code, obj = _run(capsys, "--kit-user-folder", str(exts), *extra)
        assert code == cli.EXIT_ERROR and "not a link" in obj["error"]
        assert (exts / EXTENSION_NAME / "config" / "extension.toml").read_text() == "x"


def test_replaces_a_stale_link(home: Path, tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
    exts = tmp_path / "kitx"
    exts.mkdir()
    old = tmp_path / "old-install"
    old.mkdir()
    (old / "keep.txt").write_text("k")
    ins.make_link(exts / EXTENSION_NAME, old)
    code, obj = _run(capsys, "--kit-user-folder", str(exts))
    assert code == 0 and obj["link_status"] == "replaced"
    assert os.path.samefile(exts / EXTENSION_NAME, extension_path())
    assert (old / "keep.txt").read_text() == "k"


def test_options_are_validated(home: Path, tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
    with pytest.raises(SystemExit):
        cli.main(
            ["isaac-sim", "install-extension", "--kit-user-folder", "x", "--isaac-sim-python", "y"]
        )
    capsys.readouterr()
    code, obj = _run(capsys, "--kit-user-folder", str(tmp_path / "k"), "--isaac-sim-version", "six")
    assert code == cli.EXIT_ERROR and "--isaac-sim-version" in obj["error"]
    code, obj = _run(capsys, "--isaac-sim-python", str(tmp_path / "no-python"))
    assert code == cli.EXIT_ERROR and "is not a file" in obj["error"]


def test_isaac_sim_python_probe(
    home: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    """Another Python's isaacsim package: this Python, with a fake isaacsim on PYTHONPATH
    that fails if imported (the probe must only locate it)."""
    site = tmp_path / "other-site"
    pkg = site / "isaacsim"
    (pkg / "extsUser").mkdir(parents=True)
    (pkg / "__init__.py").write_text("raise RuntimeError('must not be imported')\n")
    monkeypatch.setenv("PYTHONPATH", str(site))
    got = ins.probe_python(sys.executable)
    assert Path(got.path) == pkg and got.version == ""
    code, obj = _run(capsys, "--isaac-sim-python", sys.executable)
    assert code == 0 and obj["link"] == str(pkg / "extsUser" / EXTENSION_NAME), obj
    monkeypatch.delenv("PYTHONPATH")
    with pytest.raises(ins.InstallError, match="not installed"):
        ins.probe_python(sys.executable)


def test_major_minor() -> None:
    assert ins.major_minor("5.1.0.0") == "5.1" and ins.major_minor("6.2") == "6.2"
    assert ins.major_minor("6") == "" and ins.major_minor("x.y") == ""


@pytest.mark.parametrize("platform", ["win32", "linux"])
def test_user_config_locations(home: Path, tmp_path: Path, platform: str) -> None:
    got = ins.user_config_path("6.0", platform)
    base = tmp_path / "localappdata" if platform == "win32" else home / ".local" / "share"
    assert got == base / "ov" / "data" / "Kit" / "Isaac-Sim Full" / "6.0" / "user.config.json"


def test_real_link_on_this_platform(tmp_path: Path) -> None:
    """A symlink on POSIX, a directory junction on Windows; removing it keeps the target."""
    target = tmp_path / "target"
    target.mkdir()
    (target / "f.txt").write_text("f")
    link = tmp_path / "link"
    ins.make_link(link, target)
    assert ins.is_link(link) and (link / "f.txt").read_text() == "f"
    assert not ins.is_link(target)
    ins.remove_link(link)
    assert not os.path.lexists(link) and (target / "f.txt").read_text() == "f"


def test_windows_falls_back_to_mklink(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    calls: list = []

    class Done:
        returncode = 0
        stdout = stderr = ""

    def run(argv: list, **kw: Any) -> Done:
        calls.append(argv)
        return Done()

    monkeypatch.setitem(sys.modules, "_winapi", None)  # import fails: use mklink
    monkeypatch.setattr(ins.subprocess, "run", run)
    ins.make_link(tmp_path / "l", tmp_path / "t", platform="win32")
    assert calls == [["cmd", "/c", "mklink", "/J", str(tmp_path / "l"), str(tmp_path / "t")]]
    Done.returncode = 1
    with pytest.raises(ins.InstallError, match="mklink"):
        ins.make_link(tmp_path / "l", tmp_path / "t", platform="win32")


def test_find_isaacsim_absent(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(ins.importlib.util, "find_spec", lambda name: None)
    assert _REAL_FIND() is None
