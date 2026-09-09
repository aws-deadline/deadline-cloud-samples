#!/usr/bin/env python3
"""Tests for the OpenDroneMap simple-job Python application."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

BUNDLE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BUNDLE_DIR / "scripts"))

from odm_manifest import MANIFEST_FORMAT  # noqa: E402
from odm_runtime import CONTAINER_LABEL_KEY  # noqa: E402
from run_open_drone_map import (  # noqa: E402
    JobError,
    OpenDroneMapJob,
    RunConfig,
    inventory_input_images,
)


class FakeJob(OpenDroneMapJob):
    failure: JobError | None = None
    canceled = False
    omit_point_cloud = False
    fail_copy_attempt: int | None = None
    copy_attempts = 0

    def check_worker(self) -> None:
        pass

    def run_odm(self) -> None:
        if self.failure is not None:
            raise self.failure
        self.container_exit_code = 143 if self.canceled else 0
        if self.canceled:
            self.cancel_requested = True
            raise JobError("container canceled", 143)
        files = {
            "odm_orthophoto/odm_orthophoto.tif": b"ortho",
            "odm_georeferencing/odm_georeferenced_model.laz": b"points",
            "odm_dem/dsm.tif": b"dsm",
            "odm_texturing/odm_textured_model_geo.obj": b"obj",
            "odm_texturing/odm_textured_model_geo.mtl": b"mtl",
            "odm_texturing/texture.jpg": b"texture",
            "odm_report/report.pdf": b"report",
        }
        if self.omit_point_cloud:
            files.pop("odm_georeferencing/odm_georeferenced_model.laz")
        for relative, contents in files.items():
            path = self.survey_dir / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(contents)
        self.log_path.write_text("ODM log\n", encoding="utf-8")

    def stop_container(self) -> None:
        pass

    def remove_container(self) -> None:
        pass

    def copy_results(self) -> None:
        self.copy_attempts += 1
        if self.copy_attempts == self.fail_copy_attempt:
            raise OSError("injected copy failure")
        super().copy_results()


class TestOpenDroneMapJob(unittest.TestCase):
    def make_job(self, root: Path) -> FakeJob:
        input_images = root / "input"
        input_images.mkdir()
        (input_images / "image.jpg").write_bytes(b"jpeg input")
        return FakeJob(
            RunConfig(
                input_images=input_images,
                output_dir=root / "output",
                session_working_dir=root / "session",
                orthophoto_resolution=10,
                feature_quality="low",
                point_cloud_quality="lowest",
                generate_dsm=True,
                generate_dtm=False,
                max_concurrency=2,
            )
        )

    @staticmethod
    def manifest(job: OpenDroneMapJob) -> dict[str, object]:
        return json.loads(
            (job.result_dir / "manifest.json").read_text(encoding="utf-8")
        )

    def test_success_writes_versioned_odm_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            job = self.make_job(Path(temporary))
            self.assertEqual(job.run(), 0)
            manifest = self.manifest(job)
            self.assertEqual(manifest["format"], MANIFEST_FORMAT)
            self.assertEqual(manifest["schema_version"], 1)
            self.assertEqual(manifest["kind"], "simple_run")
            self.assertEqual(manifest["runtime"]["status"], "success")
            self.assertEqual(manifest["input"]["image_count"], 1)
            self.assertEqual(
                manifest["input"]["images"][0]["relative_path"], "image.jpg"
            )
            self.assertEqual(job.copy_attempts, 1)
            self.assertTrue(
                any(
                    artifact["role"] == "orthophoto"
                    for artifact in manifest["artifacts"]
                )
            )

    def test_external_failure_is_recorded(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            job = self.make_job(Path(temporary))
            job.failure = JobError("ODM container failed", 17)
            self.assertEqual(job.run(), 17)
            manifest = self.manifest(job)
            self.assertEqual(manifest["runtime"]["status"], "failed")
            self.assertEqual(manifest["runtime"]["exit_code"], 17)

    def test_missing_artifact_fails_validation(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            job = self.make_job(Path(temporary))
            job.omit_point_cloud = True
            self.assertEqual(job.run(), 66)
            self.assertEqual(self.manifest(job)["runtime"]["status"], "failed")

    def test_cancellation_is_recorded(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            job = self.make_job(Path(temporary))
            job.canceled = True
            self.assertEqual(job.run(), 143)
            manifest = self.manifest(job)
            self.assertEqual(manifest["runtime"]["status"], "canceled")
            self.assertEqual(manifest["runtime"]["container_exit_code"], 143)

    def test_copy_failure_changes_success_manifest_to_failed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            job = self.make_job(Path(temporary))
            job.fail_copy_attempt = 1
            self.assertEqual(job.run(), 1)
            self.assertEqual(job.copy_attempts, 2)
            manifest = self.manifest(job)
            self.assertEqual(manifest["runtime"]["status"], "failed")
            self.assertEqual(manifest["runtime"]["exit_code"], 1)

    def test_task_container_is_labeled_and_disposable(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            job = self.make_job(Path(temporary))
            job.session_id = "test-session"
            command = job.odm_command()
        self.assertIn("--rm", command)
        label_index = command.index("--label")
        self.assertEqual(
            command[label_index + 1],
            f"{CONTAINER_LABEL_KEY}=test-session",
        )
        self.assertIn("/datasets/survey", command)

    def test_inventory_recurses_and_sorts_images(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "b").mkdir()
            (root / "a").mkdir()
            (root / "b" / "second.JPEG").write_bytes(b"second")
            (root / "a" / "first.jpg").write_bytes(b"first")
            (root / "ignored.txt").write_text("ignored", encoding="utf-8")
            inventory = inventory_input_images(root)
        self.assertEqual(
            [item["relative_path"] for item in inventory],
            ["a/first.jpg", "b/second.JPEG"],
        )

    def test_inventory_rejects_duplicate_flattened_names(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "a").mkdir()
            (root / "b").mkdir()
            (root / "a" / "image.jpg").write_bytes(b"first")
            (root / "b" / "IMAGE.JPG").write_bytes(b"second")
            with self.assertRaisesRegex(JobError, "duplicate names"):
                inventory_input_images(root)

if __name__ == "__main__":
    unittest.main()
