"""Run-manifest support for the OpenDroneMap simple sample.

The ODM-specific manifest makes a run auditable by recording its input image
inventory, pinned application identity, processing parameters, outcome, and
checksummed output artifacts. OpenJD schedules the task; this manifest verifies
what the task consumed and produced. It is not an OpenJD or repository-wide
manifest format.
"""

from __future__ import annotations

import hashlib
import json
import os
import platform
import tempfile
from pathlib import Path
from typing import Any

MANIFEST_FORMAT = "opendronemap-sample-manifest"
SCHEMA_VERSION = 1
ODM_VERSION = "3.6.1"
ODM_IMAGE = (
    "opendronemap/odm:3.6.1@"
    "sha256:b5fda2c0f02308c1a7fb7a07b4405aa051cf509bcc8c46eb12d10af9cbfbaf8d"
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def atomic_write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", dir=path.parent
    )
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            json.dump(value, stream, indent=2, sort_keys=True, ensure_ascii=False)
            stream.write("\n")
        os.replace(temporary_name, path)
    except Exception:
        Path(temporary_name).unlink(missing_ok=True)
        raise


def artifact_role(relative_path: str) -> str:
    roles = {
        "odm_orthophoto/odm_orthophoto.tif": "orthophoto",
        "odm_georeferencing/odm_georeferenced_model.laz": "point_cloud",
        "odm_dem/dsm.tif": "dsm",
        "odm_dem/dtm.tif": "dtm",
        "odm_report/report.pdf": "processing_report",
        "odm.log": "processing_log",
    }
    if relative_path.startswith("odm_texturing/"):
        return "textured_model"
    return roles.get(relative_path, "supporting_file")


def collect_artifacts(result_dir: Path) -> list[dict[str, Any]]:
    artifacts = []
    for path in sorted(result_dir.rglob("*")):
        if not path.is_file() or path.name == "manifest.json":
            continue
        relative_path = path.relative_to(result_dir).as_posix()
        artifacts.append(
            {
                "path": relative_path,
                "role": artifact_role(relative_path),
                "sha256": sha256_file(path),
                "size_bytes": path.stat().st_size,
            }
        )
    return artifacts


def write_run_manifest(
    result_dir: Path,
    *,
    status: str,
    exit_code: int,
    container_exit_code: int | None,
    started_at: str,
    finished_at: str,
    duration_seconds: int,
    parameters: dict[str, Any],
    input_images: list[dict[str, Any]],
) -> None:
    if status not in {"success", "failed", "canceled"}:
        raise ValueError(f"unsupported run status: {status}")
    document = {
        "format": MANIFEST_FORMAT,
        "schema_version": SCHEMA_VERSION,
        "kind": "simple_run",
        "application": {
            "name": "OpenDroneMap",
            "version": ODM_VERSION,
            "container_image": ODM_IMAGE,
        },
        "input": {
            "source": "job_attachment",
            "image_count": len(input_images),
            "images": input_images,
        },
        "parameters": parameters,
        "runtime": {
            "status": status,
            "exit_code": exit_code,
            "container_exit_code": container_exit_code,
            "started_at": started_at,
            "finished_at": finished_at,
            "duration_seconds": duration_seconds,
            "host": {
                "architecture": platform.machine(),
                "operating_system": platform.system(),
                "worker_user": os.environ.get("USER", ""),
            },
        },
        "artifacts": collect_artifacts(result_dir),
    }
    atomic_write_json(result_dir / "manifest.json", document)
