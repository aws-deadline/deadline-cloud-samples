#!/usr/bin/env python3
"""Prepare the Python and Docker runtime for an ODM worker session."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import venv
from pathlib import Path

from odm_manifest import ODM_IMAGE

ODM_IMAGE_DIGEST = ODM_IMAGE.rsplit("@", 1)[1]
PILLOW_REQUIREMENT = "Pillow==11.3.0"
CONTAINER_LABEL_KEY = "deadline-cloud-samples.odm-session"


class RuntimeSetupError(RuntimeError):
    """Raised when the job environment cannot prepare or clean its runtime."""


def docker(*args: str, capture_output: bool = False) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            ["docker", *args],
            text=True,
            capture_output=capture_output,
            check=False,
        )
    except FileNotFoundError as exc:
        raise RuntimeSetupError("Required command is unavailable: docker") from exc


def session_identifier(session_working_dir: Path) -> str:
    value = os.fspath(session_working_dir.resolve()).encode("utf-8")
    return hashlib.sha256(value).hexdigest()[:20]


def cleanup_containers(session_working_dir: Path) -> None:
    identifier = session_identifier(session_working_dir)
    result = docker(
        "ps",
        "--all",
        "--quiet",
        "--filter",
        f"label={CONTAINER_LABEL_KEY}={identifier}",
        capture_output=True,
    )
    if result.returncode != 0:
        raise RuntimeSetupError("Cannot list ODM task containers")
    container_ids = result.stdout.split()
    if not container_ids:
        return
    removed = docker("rm", "--force", *container_ids, capture_output=True)
    if removed.returncode != 0:
        raise RuntimeSetupError("Cannot remove leftover ODM task containers")
    print(f"Removed {len(container_ids)} leftover ODM task container(s)", flush=True)


def pull_and_verify_image() -> None:
    status = docker("info", capture_output=True)
    if status.returncode != 0:
        raise RuntimeSetupError("Docker daemon is unavailable")
    print("Pulling pinned OpenDroneMap 3.6.1 image", flush=True)
    pulled = docker("pull", ODM_IMAGE)
    if pulled.returncode != 0:
        raise RuntimeSetupError("Docker image pull failed")
    inspected = docker(
        "image",
        "inspect",
        "--format",
        "{{json .RepoDigests}}",
        ODM_IMAGE,
        capture_output=True,
    )
    if inspected.returncode != 0:
        raise RuntimeSetupError("Cannot inspect the pulled ODM image")
    try:
        repository_digests = json.loads(inspected.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeSetupError("Docker returned invalid image metadata") from exc
    if not isinstance(repository_digests, list) or not any(
        isinstance(value, str) and ODM_IMAGE_DIGEST in value
        for value in repository_digests
    ):
        raise RuntimeSetupError(
            "Pulled ODM image does not expose the pinned manifest digest"
        )


def install_pillow(session_working_dir: Path) -> Path:
    environment_dir = session_working_dir / ".odm-python"
    shutil.rmtree(environment_dir, ignore_errors=True)
    print(f"Creating Python environment with {PILLOW_REQUIREMENT}", flush=True)
    venv.EnvBuilder(with_pip=True).create(environment_dir)
    binary_dir = environment_dir / ("Scripts" if os.name == "nt" else "bin")
    python = binary_dir / ("python.exe" if os.name == "nt" else "python")
    installed = subprocess.run(
        [
            os.fspath(python),
            "-m",
            "pip",
            "install",
            "--disable-pip-version-check",
            "--only-binary=:all:",
            PILLOW_REQUIREMENT,
        ],
        check=False,
    )
    if installed.returncode != 0:
        raise RuntimeSetupError(f"Cannot install {PILLOW_REQUIREMENT}")
    verified = subprocess.run(
        [os.fspath(python), "-c", "import PIL; print('Pillow', PIL.__version__)"],
        check=False,
    )
    if verified.returncode != 0:
        raise RuntimeSetupError("Cannot import Pillow from the job environment")
    return binary_dir


def enter(session_working_dir: Path, with_pillow: bool) -> None:
    session_working_dir.mkdir(parents=True, exist_ok=True)
    cleanup_containers(session_working_dir)
    pull_and_verify_image()
    if with_pillow:
        binary_dir = install_pillow(session_working_dir)
        path = os.pathsep.join((os.fspath(binary_dir), os.environ.get("PATH", "")))
        print(f"openjd_env: PATH={path}", flush=True)
        print(f"openjd_env: VIRTUAL_ENV={binary_dir.parent}", flush=True)
        print("openjd_env: PYTHONNOUSERSITE=1", flush=True)
    print(
        f"openjd_env: ODM_SESSION_ID={session_identifier(session_working_dir)}",
        flush=True,
    )
    print("OpenDroneMap runtime ready", flush=True)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("enter", "exit"))
    parser.add_argument("--session-working-dir", type=Path, required=True)
    parser.add_argument("--with-pillow", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        if args.action == "enter":
            enter(args.session_working_dir, args.with_pillow)
        else:
            cleanup_containers(args.session_working_dir)
    except RuntimeSetupError as exc:
        print(f"openjd_fail: {exc}", file=sys.stderr, flush=True)
        return 69
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
