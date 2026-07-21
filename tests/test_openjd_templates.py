# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
"""Validate the Open Job Description templates shipped in this repository.

Every job template and environment template is run through ``openjd check`` --
the same validation the Open Job Description tooling performs -- so that a broken
template can never merge. Environment templates are additionally checked against
the service length limit for a serialized ``EnvironmentTemplate``.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from conftest import (
    find_environment_templates,
    find_job_templates,
    find_openjd_templates,
    rel,
    require_tool,
)
from service_limits import ENVIRONMENT_TEMPLATE_MAX_CHARS

_OPENJD_INSTALL_HINT = "pip install openjd-cli"


def _openjd_check(path: Path) -> subprocess.CompletedProcess:
    openjd = require_tool("openjd", _OPENJD_INSTALL_HINT)
    return subprocess.run(
        [openjd, "check", str(path)],
        capture_output=True,
        text=True,
        timeout=120,
    )


def test_openjd_templates_discovered():
    """Guard against the discovery silently finding nothing (e.g. a bad glob)."""
    assert find_openjd_templates(), "no OpenJD templates were discovered"


@pytest.mark.parametrize("template", find_job_templates(), ids=rel)
def test_job_template_passes_openjd_check(template: Path):
    result = _openjd_check(template)
    assert result.returncode == 0, (
        f"openjd check failed for {rel(template)}:\n"
        f"{result.stdout}\n{result.stderr}"
    )


@pytest.mark.parametrize("template", find_environment_templates(), ids=rel)
def test_environment_template_passes_openjd_check(template: Path):
    result = _openjd_check(template)
    assert result.returncode == 0, (
        f"openjd check failed for {rel(template)}:\n"
        f"{result.stdout}\n{result.stderr}"
    )


@pytest.mark.parametrize("template", find_environment_templates(), ids=rel)
def test_environment_template_within_service_length_limit(template: Path):
    """A queue environment must fit within the service's EnvironmentTemplate limit."""
    size = len(template.read_text(encoding="utf-8"))
    assert size <= ENVIRONMENT_TEMPLATE_MAX_CHARS, (
        f"{rel(template)} is {size} characters, which exceeds the AWS Deadline "
        f"Cloud EnvironmentTemplate limit of {ENVIRONMENT_TEMPLATE_MAX_CHARS}."
    )
