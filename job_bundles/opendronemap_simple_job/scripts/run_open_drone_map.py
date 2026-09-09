#!/usr/bin/env python3
"""Run a user-selected survey with the pinned OpenDroneMap application."""

from __future__ import annotations

import argparse
import os
import shutil
import signal
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from odm_manifest import ODM_IMAGE, sha256_file, write_run_manifest
from odm_runtime import CONTAINER_LABEL_KEY

PROJECT_NAME = "survey"
MINIMUM_FREE_BYTES = 20 * 1024**3
QUALITY_VALUES = ("ultra", "high", "medium", "low", "lowest")
JPEG_EXTENSIONS = {".jpg", ".jpeg"}
RESULT_DIRECTORIES = (
    "odm_orthophoto",
    "odm_georeferencing",
    "odm_dem",
    "odm_texturing",
    "odm_report",
)
STAGE_PROGRESS = (
    ("Running dataset stage", "ODM: loading the aerial images", 22),
    ("Running split stage", "ODM: preparing the reconstruction", 24),
    ("Running merge stage", "ODM: preparing the reconstruction", 26),
    ("Running opensfm stage", "ODM: matching images and solving camera poses", 30),
    ("Running openmvs stage", "ODM: building the dense point cloud", 45),
    ("Running odm_filterpoints stage", "ODM: filtering the point cloud", 58),
    ("Running odm_meshing stage", "ODM: generating the mesh", 65),
    ("Running mvs_texturing stage", "ODM: texturing the 3D model", 73),
    ("Running odm_georeferencing stage", "ODM: georeferencing outputs", 80),
    ("Running odm_dem stage", "ODM: generating elevation models", 87),
    ("Running odm_orthophoto stage", "ODM: rendering the orthophoto", 93),
    ("Running odm_report stage", "ODM: creating the processing report", 96),
    ("Running odm_postprocess stage", "ODM: finalizing results", 98),
)


class JobError(RuntimeError):
    def __init__(self, message: str, exit_code: int = 1):
        super().__init__(message)
        self.exit_code = exit_code


def parse_bool(value: str) -> bool:
    if value not in {"True", "False"}:
        raise argparse.ArgumentTypeError("expected True or False")
    return value == "True"


@dataclass(frozen=True)
class RunConfig:
    input_images: Path
    output_dir: Path
    session_working_dir: Path
    orthophoto_resolution: int
    feature_quality: str
    point_cloud_quality: str
    generate_dsm: bool
    generate_dtm: bool
    max_concurrency: int

    def manifest_parameters(self) -> dict[str, Any]:
        return {
            "orthophoto_resolution_cm_per_pixel": self.orthophoto_resolution,
            "feature_quality": self.feature_quality,
            "point_cloud_quality": self.point_cloud_quality,
            "generate_dsm": self.generate_dsm,
            "generate_dtm": self.generate_dtm,
            "max_concurrency": self.max_concurrency,
        }


def status(message: str) -> None:
    print(f"openjd_status: {message}", flush=True)


def progress(value: int | float) -> None:
    print(f"openjd_progress: {value}", flush=True)


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def inventory_input_images(root: Path) -> list[dict[str, Any]]:
    """Return a deterministic, checksummed inventory safe to flatten for ODM."""
    if not root.is_dir() or root.is_symlink():
        raise JobError(f"InputImages must be a directory, not a symlink: {root}", 65)

    images: list[dict[str, Any]] = []
    staged_names: dict[str, str] = {}
    content_hashes: dict[str, str] = {}
    for current_root, directory_names, file_names in os.walk(
        root, followlinks=False
    ):
        directory_names.sort(key=str.casefold)
        file_names.sort(key=str.casefold)
        current = Path(current_root)
        for name in directory_names:
            candidate = current / name
            if candidate.is_symlink():
                raise JobError(
                    "InputImages contains an unsupported directory symlink: "
                    f"{candidate.relative_to(root).as_posix()}",
                    65,
                )
        for name in file_names:
            source = current / name
            if source.suffix.lower() not in JPEG_EXTENSIONS:
                continue
            relative = source.relative_to(root).as_posix()
            if source.is_symlink():
                raise JobError(
                    f"InputImages contains an unsupported file symlink: {relative}",
                    65,
                )
            if source.stat().st_size <= 0:
                raise JobError(f"InputImages contains an empty JPEG: {relative}", 65)
            staged_key = source.name.casefold()
            if staged_key in staged_names:
                raise JobError(
                    "InputImages contains duplicate names after flattening: "
                    f"{staged_names[staged_key]} and {relative}",
                    65,
                )
            digest = sha256_file(source)
            if digest in content_hashes:
                raise JobError(
                    "InputImages contains duplicate image content: "
                    f"{content_hashes[digest]} and {relative}",
                    65,
                )
            staged_names[staged_key] = relative
            content_hashes[digest] = relative
            images.append(
                {
                    "source_path": source,
                    "relative_path": relative,
                    "staged_name": source.name,
                    "size_bytes": source.stat().st_size,
                    "sha256": digest,
                }
            )
    images.sort(
        key=lambda image: (
            str(image["relative_path"]).casefold(),
            str(image["relative_path"]),
        )
    )
    if not images:
        raise JobError(
            "InputImages contains no JPEG files (.jpg or .jpeg, case-insensitive)",
            65,
        )
    return images


class OpenDroneMapJob:
    def __init__(self, config: RunConfig):
        self.config = config
        self.work_root = config.session_working_dir / "open_drone_map"
        self.datasets_dir = self.work_root / "datasets"
        self.survey_dir = self.datasets_dir / PROJECT_NAME
        self.result_dir = config.output_dir / "open_drone_map"
        self.log_path = self.work_root / "odm.log"
        self.session_id = os.environ.get("ODM_SESSION_ID", "")
        self.container_name = f"deadline-odm-{self.session_id}-{os.getpid()}"
        self.container_started = False
        self.cancel_requested = False
        self.container_exit_code: int | None = None
        self.input_inventory: list[dict[str, Any]] = []

    def request_cancel(self, _signum: int, _frame: Any) -> None:
        self.cancel_requested = True
        status("Cancellation requested; stopping the ODM container")
        self.stop_container()

    def ensure_not_canceled(self) -> None:
        if self.cancel_requested:
            raise JobError("OpenDroneMap processing was canceled", 130)

    def docker(
        self, *args: str, check: bool = False, capture_output: bool = False
    ) -> subprocess.CompletedProcess[str]:
        try:
            return subprocess.run(
                ["docker", *args],
                check=check,
                text=True,
                capture_output=capture_output,
            )
        except FileNotFoundError as exc:
            raise JobError("Required command is unavailable: docker", 69) from exc

    def stop_container(self) -> None:
        if not self.container_started:
            return
        inspected = self.docker(
            "container", "inspect", self.container_name, capture_output=True
        )
        if inspected.returncode == 0:
            self.docker("stop", "--time", "20", self.container_name, capture_output=True)

    def remove_container(self) -> None:
        if self.container_started:
            self.docker("rm", "-f", self.container_name, capture_output=True)
            self.container_started = False

    def prepare_directories(self) -> None:
        shutil.rmtree(self.work_root, ignore_errors=True)
        shutil.rmtree(self.result_dir, ignore_errors=True)
        (self.survey_dir / "images").mkdir(parents=True)
        self.result_dir.mkdir(parents=True)
        self.log_path.touch()

    def check_worker(self) -> None:
        status("Checking the worker and Docker daemon")
        progress(1)
        if not self.session_id:
            raise JobError("ODM runtime job environment is not initialized", 69)
        result = self.docker("info", capture_output=True)
        if result.returncode != 0:
            raise JobError("Docker daemon is unavailable", result.returncode or 69)
        free_bytes = shutil.disk_usage(self.work_root).free
        if free_bytes < MINIMUM_FREE_BYTES:
            raise JobError("At least 20 GiB of free session disk is required", 69)

    def stage_input_images(self) -> None:
        status("Inventorying the attached survey images")
        progress(5)
        images = inventory_input_images(self.config.input_images)
        status(f"Staging {len(images)} source images")
        progress(13)
        for image in images:
            destination = self.survey_dir / "images" / str(image["staged_name"])
            shutil.copy2(
                image["source_path"],
                destination,
            )
            if sha256_file(destination) != image["sha256"]:
                raise JobError(
                    f"Staged image checksum mismatch: {image['relative_path']}",
                    65,
                )
        self.input_inventory = [
            {key: value for key, value in image.items() if key != "source_path"}
            for image in images
        ]

    def odm_command(self) -> list[str]:
        command = [
            "docker",
            "run",
            "--name",
            self.container_name,
            "--label",
            f"{CONTAINER_LABEL_KEY}={self.session_id}",
            "--rm",
            "--init",
            "--network",
            "none",
            "--stop-timeout",
            "20",
            "--user",
            f"{os.getuid()}:{os.getgid()}",
            "--env",
            "HOME=/tmp",
            "--volume",
            f"{self.datasets_dir}:/datasets",
            "--workdir",
            f"/datasets/{PROJECT_NAME}",
            ODM_IMAGE,
            "--project-path",
            "/datasets",
            PROJECT_NAME,
            "--orthophoto-resolution",
            str(self.config.orthophoto_resolution),
            "--feature-quality",
            self.config.feature_quality,
            "--pc-quality",
            self.config.point_cloud_quality,
            "--max-concurrency",
            str(self.config.max_concurrency),
        ]
        if self.config.generate_dsm:
            command.append("--dsm")
        if self.config.generate_dtm:
            command.append("--dtm")
        return command

    def run_odm(self) -> None:
        status("Starting OpenDroneMap")
        progress(20)
        try:
            process = subprocess.Popen(
                self.odm_command(),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
            )
        except FileNotFoundError as exc:
            raise JobError("Required command is unavailable: docker", 69) from exc
        self.container_started = True
        assert process.stdout is not None
        with self.log_path.open("a", encoding="utf-8") as log:
            for line in process.stdout:
                print(line, end="", flush=True)
                log.write(line)
                log.flush()
                for marker, message, value in STAGE_PROGRESS:
                    if marker in line:
                        status(message)
                        progress(value)
                        break
        while True:
            try:
                return_code = process.wait()
                break
            except InterruptedError:
                continue
        self.container_exit_code = return_code
        if return_code != 0:
            raise JobError(
                f"OpenDroneMap container exited with status {return_code}", return_code
            )

    def copy_results(self) -> None:
        for directory_name in RESULT_DIRECTORIES:
            source = self.survey_dir / directory_name
            if source.is_dir():
                shutil.copytree(
                    source, self.result_dir / directory_name, dirs_exist_ok=True
                )
        if self.log_path.is_file():
            shutil.copy2(self.log_path, self.result_dir / "odm.log")

    def validate_results(self) -> None:
        required = [
            "odm_orthophoto/odm_orthophoto.tif",
            "odm_georeferencing/odm_georeferenced_model.laz",
            "odm_texturing/odm_textured_model_geo.obj",
            "odm_texturing/odm_textured_model_geo.mtl",
            "odm_report/report.pdf",
            "odm.log",
        ]
        if self.config.generate_dsm:
            required.append("odm_dem/dsm.tif")
        if self.config.generate_dtm:
            required.append("odm_dem/dtm.tif")
        missing = [
            relative
            for relative in required
            if not (self.result_dir / relative).is_file()
            or (self.result_dir / relative).stat().st_size == 0
        ]
        texture_dir = self.result_dir / "odm_texturing"
        texture_extensions = {".jpg", ".jpeg", ".png", ".tif"}
        textures = (
            [
                path
                for path in texture_dir.iterdir()
                if path.is_file() and path.suffix.lower() in texture_extensions
            ]
            if texture_dir.is_dir()
            else []
        )
        if not textures:
            missing.append("odm_texturing/<texture image>")
        if missing:
            for relative in missing:
                print(f"Missing expected artifact: {relative}", file=sys.stderr)
            raise JobError(
                "ODM exited successfully but required output artifacts are missing", 66
            )

    def run(self) -> int:
        started_monotonic = time.monotonic()
        started_at = utc_now()
        exit_code = 0
        run_status = "failed"
        results_collected = False
        signal.signal(signal.SIGTERM, self.request_cancel)
        signal.signal(signal.SIGINT, self.request_cancel)
        try:
            self.prepare_directories()
            self.check_worker()
            self.ensure_not_canceled()
            self.stage_input_images()
            self.ensure_not_canceled()
            self.run_odm()
            self.copy_results()
            results_collected = True
            self.validate_results()
            run_status = "success"
        except JobError as exc:
            exit_code = exc.exit_code
            print(f"openjd_fail: {exc}", file=sys.stderr, flush=True)
        except KeyboardInterrupt:
            self.cancel_requested = True
            exit_code = 130
        except BaseException as exc:
            exit_code = 1
            print(
                f"openjd_fail: unexpected OpenDroneMap failure: {exc}",
                file=sys.stderr,
                flush=True,
            )
        finally:
            self.stop_container()
            self.remove_container()
            if (
                not results_collected
                and self.survey_dir.exists()
                and self.result_dir.exists()
            ):
                try:
                    self.copy_results()
                except OSError as exc:
                    if exit_code == 0:
                        exit_code = 1
                    run_status = "failed"
                    print(f"openjd_fail: cannot collect results: {exc}", file=sys.stderr)
            if self.cancel_requested:
                run_status = "canceled"
                if exit_code == 0:
                    exit_code = 130
            finished_at = utc_now()
            if self.result_dir.exists():
                try:
                    write_run_manifest(
                        self.result_dir,
                        status=run_status,
                        exit_code=exit_code,
                        container_exit_code=self.container_exit_code,
                        started_at=started_at,
                        finished_at=finished_at,
                        duration_seconds=max(
                            0, round(time.monotonic() - started_monotonic)
                        ),
                        parameters=self.config.manifest_parameters(),
                        input_images=self.input_inventory,
                    )
                except OSError as exc:
                    if exit_code == 0:
                        exit_code = 1
                        run_status = "failed"
                    print(f"openjd_fail: cannot write manifest: {exc}", file=sys.stderr)

        if run_status == "success":
            status("OpenDroneMap processing complete")
            progress(100)
        elif run_status == "canceled":
            print(
                "openjd_fail: OpenDroneMap processing was canceled",
                file=sys.stderr,
                flush=True,
            )
        return exit_code


def parse_args() -> RunConfig:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-images", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--session-working-dir", required=True, type=Path)
    parser.add_argument("--orthophoto-resolution", required=True, type=int)
    parser.add_argument("--feature-quality", required=True, choices=QUALITY_VALUES)
    parser.add_argument("--point-cloud-quality", required=True, choices=QUALITY_VALUES)
    parser.add_argument("--generate-dsm", required=True, type=parse_bool)
    parser.add_argument("--generate-dtm", required=True, type=parse_bool)
    parser.add_argument("--max-concurrency", required=True, type=int)
    args = parser.parse_args()
    if args.orthophoto_resolution <= 0:
        parser.error("--orthophoto-resolution must be positive")
    if args.max_concurrency <= 0:
        parser.error("--max-concurrency must be positive")
    return RunConfig(
        input_images=args.input_images,
        output_dir=args.output_dir,
        session_working_dir=args.session_working_dir,
        orthophoto_resolution=args.orthophoto_resolution,
        feature_quality=args.feature_quality,
        point_cloud_quality=args.point_cloud_quality,
        generate_dsm=args.generate_dsm,
        generate_dtm=args.generate_dtm,
        max_concurrency=args.max_concurrency,
    )


if __name__ == "__main__":
    raise SystemExit(OpenDroneMapJob(parse_args()).run())
