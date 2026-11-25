# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
"""Local folders, and the Deadline Cloud client's defaults (read only).

Farm, queue and profile come from ``~/.deadline/config`` through the client's own reader,
so they resolve the way the ``deadline`` CLI resolves them. This package never writes that
file.
"""

from __future__ import annotations

import os

HOME_ENV = "DEADLINE_PHYSICAL_AI_HOME"


def home_dir() -> str:
    """This package's working folder (default ``~/.deadline/physical-ai``). Read per call
    so tests can repoint it with ``DEADLINE_PHYSICAL_AI_HOME``."""
    return os.path.expanduser(
        os.environ.get(HOME_ENV) or os.path.join("~", ".deadline", "physical-ai")
    )


def deadline_defaults() -> dict:
    """``farm_id``, ``queue_id`` and ``aws_profile_name`` from the Deadline Cloud client's
    configuration. Empty strings when unset or when the client is not installed."""
    out = {"farm_id": "", "queue_id": "", "aws_profile_name": ""}
    try:
        from deadline.client.config import config_file
    except Exception:  # noqa: BLE001
        return out
    for key, setting in (
        ("aws_profile_name", "defaults.aws_profile_name"),
        ("farm_id", "defaults.farm_id"),
        ("queue_id", "defaults.queue_id"),
    ):
        try:
            out[key] = str(config_file.get_setting(setting) or "")
        except Exception:  # noqa: BLE001
            out[key] = ""
    return out
