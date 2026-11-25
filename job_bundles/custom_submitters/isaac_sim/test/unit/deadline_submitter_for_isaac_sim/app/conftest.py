# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
"""Tests for the app with no display, AWS, Isaac Sim or network.

Each test gets its own settings file and an empty session, so one test's loads and
settings never prefill another's.
"""

from __future__ import annotations

import os
from typing import Any

import pytest

from deadline.isaac_sim_submitter.app import controllers, settings

# Qt tests run offscreen; set before any QApplication exists.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


_REAL_ASK_DEADLINE_DIRS = controllers.SubmitController._ask_deadline_dirs


@pytest.fixture
def real_deadline_dirs(monkeypatch: Any) -> None:
    """Let SubmitController read deadline-cloud's folders through its runner."""
    monkeypatch.setattr(controllers.SubmitController, "_ask_deadline_dirs", _REAL_ASK_DEADLINE_DIRS)


@pytest.fixture(autouse=True)
def _fresh_state(tmp_path_factory: Any, monkeypatch: Any) -> Any:
    path = tmp_path_factory.mktemp("settings") / "settings.json"
    monkeypatch.setenv(settings.PATH_ENV, str(path))
    monkeypatch.setenv("DEADLINE_PHYSICAL_AI_HOME", str(path.parent / "physical-ai"))
    settings.reload()
    # Submit makes new output folders under outputDir: keep them out of the real home.
    monkeypatch.setattr(settings, "output_root", lambda: str(path.parent / "job-outputs"))
    controllers.SESSION.loaded = []
    # Submit reads deadline-cloud's bundle and history folders through the CLI; tests that
    # cover that set ``deadline_dirs`` (or restore the method) themselves.
    monkeypatch.setattr(
        controllers.SubmitController,
        "_ask_deadline_dirs",
        lambda self: setattr(self, "deadline_dirs", self.deadline_dirs or {}),
    )
    yield
    controllers.SESSION.loaded = []
    settings.reload()
