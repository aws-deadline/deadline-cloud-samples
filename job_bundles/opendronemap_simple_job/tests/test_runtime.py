#!/usr/bin/env python3
"""Tests for the ODM job-environment runtime."""

from __future__ import annotations

import argparse
import io
import json
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

BUNDLE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BUNDLE_DIR / "scripts"))

import odm_runtime  # noqa: E402


class TestRuntime(unittest.TestCase):
    @staticmethod
    def result(returncode: int = 0, stdout: str = "") -> argparse.Namespace:
        return argparse.Namespace(returncode=returncode, stdout=stdout, stderr="")

    def test_pull_and_verify_pinned_image(self) -> None:
        repository_digests = json.dumps(
            [f"opendronemap/odm@{odm_runtime.ODM_IMAGE_DIGEST}"]
        )
        with mock.patch.object(
            odm_runtime,
            "docker",
            side_effect=[
                self.result(),
                self.result(),
                self.result(stdout=repository_digests),
            ],
        ) as docker:
            odm_runtime.pull_and_verify_image()
        self.assertEqual(docker.call_args_list[1].args, ("pull", odm_runtime.ODM_IMAGE))
        self.assertIn("image", docker.call_args_list[2].args)

    def test_cleanup_removes_only_session_labeled_containers(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            session = Path(temporary)
            identifier = odm_runtime.session_identifier(session)
            with mock.patch.object(
                odm_runtime,
                "docker",
                side_effect=[
                    self.result(stdout="container-one\ncontainer-two\n"),
                    self.result(),
                ],
            ) as docker:
                odm_runtime.cleanup_containers(session)
        self.assertEqual(
            docker.call_args_list[0].args[-1],
            f"label={odm_runtime.CONTAINER_LABEL_KEY}={identifier}",
        )
        self.assertEqual(
            docker.call_args_list[1].args,
            ("rm", "--force", "container-one", "container-two"),
        )

    def test_enter_exports_python_and_session_environment(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            session = Path(temporary)
            binary_dir = session / ".odm-python" / "bin"
            output = io.StringIO()
            with (
                mock.patch.object(odm_runtime, "cleanup_containers"),
                mock.patch.object(odm_runtime, "pull_and_verify_image"),
                mock.patch.object(
                    odm_runtime, "install_pillow", return_value=binary_dir
                ),
                mock.patch.dict(os.environ, {"PATH": "/usr/bin"}),
                redirect_stdout(output),
            ):
                odm_runtime.enter(session, with_pillow=True)
        value = output.getvalue()
        self.assertIn(f"openjd_env: PATH={binary_dir}{os.pathsep}/usr/bin", value)
        self.assertIn("openjd_env: VIRTUAL_ENV=", value)
        self.assertIn("openjd_env: ODM_SESSION_ID=", value)


if __name__ == "__main__":
    unittest.main()
