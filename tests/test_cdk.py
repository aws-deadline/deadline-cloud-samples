# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
"""Cross-tree checks for the AWS CDK sample apps.

Almost everything worth knowing about a CDK app is proven by building it: the
CDK CI job (``.github/workflows/cdk_checks.yml``) runs ``npm ci``, ``tsc``,
``jest``, ``cdk synth``, and ``cfn-lint``, and each of those fails on its own if
the app is misconfigured. There is no value in re-asserting here that, say,
``cdk.json`` names a file that exists -- ``cdk synth`` says so louder.

What is left is the one thing no per-app check can see: a CDK app ships a
byte-identical copy of a queue environment that also lives under
``queue_environments/``, and nothing notices if the two drift apart. That
comparison spans two directories, so it belongs in this repo-wide suite.

The queue environment templates themselves are validated by
``test_openjd_templates.py``, which discovers every OpenJD template in the
repository, including the copies under ``cdk/``.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from conftest import REPO_ROOT, find_cdk_apps, rel

# A CDK app that ships a copy of a shared queue environment must keep it
# byte-identical to the original, so a fix to one is a fix to both. Maps the
# copy's filename to the shared file it must match.
_SHARED_QUEUE_ENVIRONMENT_COPIES = {
    "conda_queue_env_inline_improved_caching.yaml": (
        "queue_environments/conda_queue_env_inline_improved_caching.yaml"
    ),
}


def _shared_queue_environment_copies() -> list[tuple[Path, str]]:
    """Every (copy, shared original) pair present in the CDK apps.

    Enumerated up front so each pair is its own test case and none of them is
    skipped -- a skipped check is indistinguishable from a passing one.
    """
    pairs = []
    for app_dir in find_cdk_apps():
        for filename, shared_relpath in _SHARED_QUEUE_ENVIRONMENT_COPIES.items():
            copy = app_dir / filename
            if copy.is_file():
                pairs.append((copy, shared_relpath))
    return pairs


_QUEUE_ENVIRONMENT_COPIES = _shared_queue_environment_copies()


def test_shared_queue_environment_copies_discovered():
    """Guard against the discovery silently finding nothing (e.g. a moved app)."""
    assert _QUEUE_ENVIRONMENT_COPIES, (
        "no CDK app ships a copy of a shared queue environment; if that is "
        "intentional, remove this check and _SHARED_QUEUE_ENVIRONMENT_COPIES"
    )


@pytest.mark.parametrize(
    ("copy", "shared_relpath"),
    _QUEUE_ENVIRONMENT_COPIES,
    ids=[rel(copy) for copy, _ in _QUEUE_ENVIRONMENT_COPIES],
)
def test_shared_queue_environment_copy_has_not_drifted(copy: Path, shared_relpath: str):
    """A copied queue environment must stay identical to its shared original."""
    shared = REPO_ROOT / shared_relpath
    assert shared.is_file(), (
        f"{rel(copy)} is meant to be a copy of {shared_relpath}, which does not "
        f"exist. Update _SHARED_QUEUE_ENVIRONMENT_COPIES in this test."
    )
    assert copy.read_bytes() == shared.read_bytes(), (
        f"{rel(copy)} has drifted from {shared_relpath}. Keep them identical so a "
        f"fix to one applies to both, or stop treating it as a copy."
    )
