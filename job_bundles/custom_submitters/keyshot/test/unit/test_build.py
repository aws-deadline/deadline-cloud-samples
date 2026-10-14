# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

from pathlib import Path
import sys
import tempfile
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from build import main


class TestBuild:

    def test_build_submitter_comprehensive(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / "built_submitter.py"

            # Mock sys.argv to provide the output argument
            with patch("sys.argv", ["build.py", "--output", str(output_path)]):
                main()

            with open(output_path, "r", encoding="utf-8") as f:
                content = f.read()

            # Test valid Python syntax
            try:
                compile(content, str(output_path), "exec")
            except SyntaxError as e:
                pytest.fail(f"Built submitter has syntax errors: {e}")

            # Test placeholder replacement - check that placeholders were replaced with actual content
            assert (
                '"SESSION_MANAGER_SCRIPT"' not in content
            ), "SESSION_MANAGER_SCRIPT placeholder was not replaced"
            assert (
                '"KEYSHOT_BRIDGE_SCRIPT"' not in content
            ), "KEYSHOT_BRIDGE_SCRIPT placeholder was not replaced"
            assert (
                '"TASK_MANAGER_SCRIPT"' not in content
            ), "TASK_MANAGER_SCRIPT placeholder was not replaced"
            assert (
                '"KEYSHOT_COMMAND_HANDLER_SCRIPT"' not in content
            ), "KEYSHOT_COMMAND_HANDLER_SCRIPT placeholder was not replaced"

            # Test that actual script content was embedded
            assert "KeyShot Session Manager" in content, "Session manager content not found"
            assert "KeyShot Bridge" in content, "Bridge content not found"
            assert "KeyShot Task Script" in content, "Task script content not found"
            assert "JSON commands from STDIN" in content, "Command handler content not found"
