# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
"""Syntax checks for the standalone scripts under ``utility_scripts/``.

Unlike a host configuration script, these are not uploaded to the service, so the
``scriptBody`` length limit does not apply. What does apply is that they parse: a
sample that does not is broken for everyone who copies it, and these run as root or
an administrator, where a syntax error can surface halfway through an install.

The same reasoning as ``test_host_configuration_scripts.py`` applies to the tools --
``bash`` and ``pwsh`` are required, and a missing one fails rather than skips,
because a skipped check is indistinguishable from a passing one.
"""
from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

from conftest import find_utility_scripts, rel, require_tool

_SCRIPTS = find_utility_scripts()
_SHELL_SCRIPTS = [s for s in _SCRIPTS if s.suffix == ".sh"]
_POWERSHELL_SCRIPTS = [s for s in _SCRIPTS if s.suffix == ".ps1"]


def test_utility_scripts_discovered():
    assert _SCRIPTS, "no utility scripts were discovered"


@pytest.mark.parametrize("script", _SCRIPTS, ids=rel)
def test_script_is_not_empty(script: Path):
    assert script.read_text(encoding="utf-8", errors="replace").strip(), f"{rel(script)} is empty"


@pytest.mark.parametrize("script", _SHELL_SCRIPTS, ids=rel)
def test_shell_script_syntax(script: Path):
    """`bash -n` catches syntax errors without executing anything."""
    bash = require_tool("bash", "install bash (present by default on Linux/macOS)")
    result = subprocess.run(
        [bash, "-n", str(script)], capture_output=True, text=True, timeout=30
    )
    assert result.returncode == 0, (
        f"bash syntax check failed for {rel(script)}:\n{result.stderr}"
    )


@pytest.mark.parametrize("script", _POWERSHELL_SCRIPTS, ids=rel)
def test_powershell_script_syntax(script: Path):
    """Parse each PowerShell script with the PowerShell parser (no execution)."""
    pwsh = require_tool(
        "pwsh",
        "install PowerShell (https://learn.microsoft.com/powershell/); "
        "pre-installed on GitHub-hosted runners",
    )
    # The script path goes through an environment variable rather than being
    # interpolated into the command, so it cannot be interpreted as PowerShell.
    ps_command = (
        "$p = $env:PWSH_TARGET_SCRIPT; $errors = $null; "
        "[System.Management.Automation.Language.Parser]::ParseFile("
        "$p, [ref]$null, [ref]$errors) | Out-Null; "
        "if ($errors) { $errors | ForEach-Object { Write-Output $_.ToString() }; exit 1 } "
        "else { exit 0 }"
    )
    result = subprocess.run(
        [pwsh, "-NoProfile", "-NonInteractive", "-Command", ps_command],
        capture_output=True,
        text=True,
        timeout=60,
        env={**os.environ, "PWSH_TARGET_SCRIPT": str(script)},
    )
    assert result.returncode == 0, (
        f"PowerShell parse failed for {rel(script)}:\n{result.stdout}\n{result.stderr}"
    )
