# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
"""Shared discovery helpers for the static validation tests.

Everything here is filesystem-only so the tests run fast and need no network or
AWS credentials. Discovery walks the repository from its root (the parent of the
``tests`` directory) and deliberately skips directories that hold scratch or
vendored copies (for example ``.claude`` worktrees and ``.git``) so those never
affect CI results.
"""
from __future__ import annotations

import re
import shutil
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent


def require_tool(name: str, install_hint: str) -> str:
    """Return the path to a required executable, or FAIL the test if it is absent.

    These checks are meant to run in CI where every required tool is installed.
    A missing tool always fails -- it is never skipped -- because a skipped
    check is indistinguishable from a passing one and is exactly how a bad
    sample slips through. There is deliberately no environment-variable escape
    hatch: run the checks with the tools installed, or they fail.
    """
    path = shutil.which(name)
    if not path:
        pytest.fail(
            f"required tool {name!r} is not installed. Install it with: {install_hint}",
            pytrace=False,
        )
    return path

# Directories anywhere in the tree whose contents are not part of the samples we
# ship and should never be validated.
_EXCLUDED_DIR_NAMES = {
    ".git",
    ".claude",
    ".kiro",
    "node_modules",
    "__pycache__",
    "build",
}

# Directory name prefixes excluded the same way as ``_EXCLUDED_DIR_NAMES``. CDK
# synthesis writes ``cdk.out/`` by default, and the CDK CI job synthesizes into
# ``cdk.out.<name>/`` directories. All of them hold generated copies of the
# CloudFormation template and of ``cdk.json``, none of which are samples we ship.
_EXCLUDED_DIR_PREFIXES = ("cdk.out",)

# Matches the OpenJD ``specificationVersion`` header of a standalone template.
# Anchored at column 0 (no leading whitespace) on purpose: a standalone OpenJD
# template file has this as a top-level key, whereas a template *embedded* inside
# another document (for example an environment template nested in a
# CloudFormation resource) is indented. Only standalone template files are
# validated with ``openjd check``.
_SPEC_VERSION_RE = re.compile(
    r"""^specificationVersion\s*:\s*['"]?(?P<version>[A-Za-z0-9._-]+)""",
    re.MULTILINE,
)


def _is_excluded(path: Path) -> bool:
    return any(
        part in _EXCLUDED_DIR_NAMES or part.startswith(_EXCLUDED_DIR_PREFIXES)
        for part in path.parts
    )


def _iter_yaml_files() -> list[Path]:
    files = []
    for pattern in ("*.yaml", "*.yml"):
        for path in REPO_ROOT.rglob(pattern):
            if not _is_excluded(path.relative_to(REPO_ROOT)):
                files.append(path)
    return sorted(set(files))


def spec_version(path: Path) -> str | None:
    """Return the OpenJD ``specificationVersion`` of a YAML file, or ``None``.

    Reads only the head of the file; the header appears at the top of every
    OpenJD template.
    """
    try:
        head = path.read_text(encoding="utf-8", errors="replace")[:4096]
    except OSError:
        return None
    match = _SPEC_VERSION_RE.search(head)
    return match.group("version") if match else None


def find_openjd_templates() -> list[Path]:
    """All OpenJD job and environment templates in the repository."""
    return [
        p
        for p in _iter_yaml_files()
        if (v := spec_version(p)) is not None
        and (v.startswith("jobtemplate-") or v.startswith("environment-"))
    ]


def find_job_templates() -> list[Path]:
    return [p for p in find_openjd_templates() if (spec_version(p) or "").startswith("jobtemplate-")]


def find_environment_templates() -> list[Path]:
    return [p for p in find_openjd_templates() if (spec_version(p) or "").startswith("environment-")]


def find_host_configuration_scripts() -> list[Path]:
    """Host configuration shell / PowerShell scripts."""
    base = REPO_ROOT / "host_configuration_scripts"
    if not base.is_dir():
        return []
    scripts = []
    for pattern in ("*.sh", "*.ps1"):
        for path in base.rglob(pattern):
            if not _is_excluded(path.relative_to(REPO_ROOT)):
                scripts.append(path)
    return sorted(set(scripts))


def find_cloudformation_templates() -> list[Path]:
    """CloudFormation templates (YAML files under ``cloudformation/``).

    Excludes the OpenJD job templates that happen to live under that tree (for
    example the ``test-job.yaml`` samples) since those are validated by the
    OpenJD checks instead.
    """
    base = REPO_ROOT / "cloudformation"
    if not base.is_dir():
        return []
    templates = []
    for pattern in ("*.yaml", "*.yml"):
        for path in base.rglob(pattern):
            rel = path.relative_to(REPO_ROOT)
            if _is_excluded(rel) or spec_version(path) is not None:
                continue
            templates.append(path)
    return sorted(set(templates))


def find_cdk_apps() -> list[Path]:
    """Directories under ``cdk/`` that are AWS CDK apps (they have a ``cdk.json``)."""
    base = REPO_ROOT / "cdk"
    if not base.is_dir():
        return []
    apps = []
    for path in base.rglob("cdk.json"):
        if not _is_excluded(path.relative_to(REPO_ROOT)):
            apps.append(path.parent)
    return sorted(set(apps))


def find_conda_recipe_dirs() -> list[Path]:
    """Directories under ``conda_recipes/`` that contain a ``deadline-cloud.yaml``."""
    base = REPO_ROOT / "conda_recipes"
    if not base.is_dir():
        return []
    dirs = []
    for path in base.rglob("deadline-cloud.yaml"):
        rel = path.relative_to(REPO_ROOT)
        if not _is_excluded(rel):
            dirs.append(path.parent)
    return sorted(set(dirs))


def rel(path: Path) -> str:
    """Repo-relative string form of a path, for readable test ids."""
    try:
        return str(path.relative_to(REPO_ROOT))
    except ValueError:
        return str(path)
