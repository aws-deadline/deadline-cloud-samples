#!/usr/bin/env python3
"""Prepare the Python and Docker runtime for an ODM worker session."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

from odm_manifest import ODM_IMAGE

ODM_IMAGE_DIGEST = ODM_IMAGE.rsplit("@", 1)[1]
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


def enter(session_working_dir: Path) -> None:
    session_working_dir.mkdir(parents=True, exist_ok=True)
    cleanup_containers(session_working_dir)
    pull_and_verify_image()
    print(
        f"openjd_env: ODM_SESSION_ID={session_identifier(session_working_dir)}",
        flush=True,
    )
    print("OpenDroneMap runtime ready", flush=True)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("enter", "exit"))
    parser.add_argument("--session-working-dir", type=Path, required=True)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        if args.action == "enter":
            enter(args.session_working_dir)
        else:
            cleanup_containers(args.session_working_dir)
    except RuntimeSetupError as exc:
        print(f"openjd_fail: {exc}", file=sys.stderr, flush=True)
        return 69
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
