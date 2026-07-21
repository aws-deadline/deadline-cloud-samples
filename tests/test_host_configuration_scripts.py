# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
"""Static checks for fleet host configuration scripts.

A host configuration script is uploaded verbatim to the service as
``HostConfiguration.scriptBody`` on ``UpdateFleet``. The service rejects a body
longer than 15000 characters. A sample that exceeds that limit looks fine in the
repository but fails the moment a customer tries to apply it -- this suite makes
that failure show up in CI instead.

Beyond the length limit, the checks confirm Linux shell scripts are
syntactically valid (``bash -n``) and Windows PowerShell scripts parse without
errors (PowerShell parser). These syntax checks always run in CI -- they are
never skipped, because a skipped check is indistinguishable from a passing one.
"""
from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

from conftest import find_host_configuration_scripts, rel, require_tool
from service_limits import HOST_CONFIGURATION_SCRIPT_MAX_CHARS

_SCRIPTS = find_host_configuration_scripts()
_SHELL_SCRIPTS = [s for s in _SCRIPTS if s.suffix == ".sh"]
_POWERSHELL_SCRIPTS = [s for s in _SCRIPTS if s.suffix == ".ps1"]


def test_host_configuration_scripts_discovered():
    assert _SCRIPTS, "no host configuration scripts were discovered"


@pytest.mark.parametrize("script", _SCRIPTS, ids=rel)
def test_script_within_service_length_limit(script: Path):
    """The most important check: stay under the service scriptBody limit.

    Uses byte length, matching how the service measures the uploaded body and
    giving the more conservative bound for any non-ASCII content.
    """
    size = len(script.read_bytes())
    assert size <= HOST_CONFIGURATION_SCRIPT_MAX_CHARS, (
        f"{rel(script)} is {size} bytes, which exceeds the AWS Deadline Cloud "
        f"host configuration script limit of {HOST_CONFIGURATION_SCRIPT_MAX_CHARS}. "
        f"Split the work or move installation payloads out of the inline script."
    )


@pytest.mark.parametrize("script", _SCRIPTS, ids=rel)
def test_script_is_not_empty(script: Path):
    assert script.read_text(encoding="utf-8", errors="replace").strip(), (
        f"{rel(script)} is empty"
    )


# NOTE: host configuration scripts are uploaded as a body and run by the service
# with a known interpreter, so a shebang is not required (and some samples, such
# as worker_reboot/linux.sh, are intentionally interpreter-line-free fragments).
# We therefore do not assert on shebangs; syntax validity is checked below.


@pytest.mark.parametrize("script", _SHELL_SCRIPTS, ids=rel)
def test_shell_script_syntax(script: Path):
    """`bash -n` catches syntax errors without executing anything.

    ``bash`` is a required tool -- if it is missing this fails rather than
    skips, so the syntax check cannot silently disappear in CI.
    """
    bash = require_tool("bash", "install bash (present by default on Linux/macOS)")
    result = subprocess.run(
        [bash, "-n", str(script)], capture_output=True, text=True, timeout=30
    )
    assert result.returncode == 0, (
        f"bash syntax check failed for {rel(script)}:\n{result.stderr}"
    )


@pytest.mark.parametrize("script", _POWERSHELL_SCRIPTS, ids=rel)
def test_powershell_script_syntax(script: Path):
    """Parse each PowerShell script with the PowerShell parser (no execution).

    Uses ``[Parser]::ParseFile`` and fails on any parse error. ``pwsh`` is a
    required tool (pre-installed on GitHub's Ubuntu runners); a missing ``pwsh``
    fails rather than skips.
    """
    pwsh = require_tool(
        "pwsh",
        "install PowerShell (https://learn.microsoft.com/powershell/); "
        "pre-installed on GitHub-hosted runners",
    )
    # ParseFile populates the [ref] $errors variable; print each error and exit
    # non-zero if any were produced. The script path is passed via an environment
    # variable rather than interpolated into the command, so it cannot break the
    # command or be interpreted as PowerShell.
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
