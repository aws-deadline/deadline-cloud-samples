# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
"""Static checks for the CloudFormation templates.

The checks are twofold:

* The template parses as CloudFormation YAML, including the intrinsic-function
  short forms (``!Sub``, ``!Ref``, ``!GetAtt``, ...) that plain YAML loaders
  choke on, and has the required top-level ``Resources`` section.
* When ``cfn-lint`` is installed it must pass with no errors. ``cfn-lint`` is
  the authoritative linter for CloudFormation; if it is not available (for
  example in a minimal local environment) that portion is skipped, but CI
  installs it so the lint always runs there.
"""
from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

import pytest
import yaml

from conftest import REPO_ROOT, find_cloudformation_templates, rel, require_tool

_TEMPLATES = find_cloudformation_templates()


class _CfnLoader(yaml.SafeLoader):
    """A SafeLoader that understands CloudFormation ``!Tag`` short forms."""


def _cfn_tag_constructor(loader: yaml.Loader, tag_suffix: str, node):
    # Represent intrinsics generically; we only care that they parse, not that
    # they resolve. Preserve the tag name so the structure round-trips sensibly.
    if isinstance(node, yaml.ScalarNode):
        return {tag_suffix: loader.construct_scalar(node)}
    if isinstance(node, yaml.SequenceNode):
        return {tag_suffix: loader.construct_sequence(node)}
    return {tag_suffix: loader.construct_mapping(node)}


_CfnLoader.add_multi_constructor("!", _cfn_tag_constructor)


def test_cloudformation_templates_discovered():
    assert _TEMPLATES, "no CloudFormation templates were discovered"


@pytest.mark.parametrize("template", _TEMPLATES, ids=rel)
def test_cloudformation_template_parses(template: Path):
    try:
        doc = yaml.load(template.read_text(encoding="utf-8"), Loader=_CfnLoader)
    except yaml.YAMLError as exc:
        pytest.fail(f"{rel(template)} is not valid YAML:\n{exc}")

    assert isinstance(doc, dict), f"{rel(template)} did not parse to a mapping"
    assert "Resources" in doc, (
        f"{rel(template)} has no top-level 'Resources' section; is it a "
        f"CloudFormation template?"
    )
    assert doc["Resources"], f"{rel(template)} has an empty 'Resources' section"


@pytest.mark.parametrize("template", _TEMPLATES, ids=rel)
def test_cloudformation_template_passes_cfn_lint(template: Path):
    cfn_lint = require_tool("cfn-lint", "pip install cfn-lint")
    result = subprocess.run(
        [cfn_lint, "--format", "json", str(template)],
        capture_output=True,
        text=True,
        timeout=120,
    )
    if result.returncode == 0:
        return

    # cfn-lint exit codes: bit 0x2 => error, 0x4 => warning, 0x8 => informational.
    # Only fail the test on errors so style warnings don't block sample PRs.
    #
    # A nonzero exit with no parseable JSON is a tool failure (internal error,
    # or the process killed by the timeout), NOT a clean bill of health. Treat
    # it as a failure rather than letting an empty ``[]`` mask it as a pass.
    stdout = result.stdout.strip()
    if not stdout:
        pytest.fail(
            f"cfn-lint exited {result.returncode} for {rel(template)} with no "
            f"output:\n{result.stderr}"
        )
    try:
        findings = json.loads(stdout)
    except json.JSONDecodeError:
        pytest.fail(
            f"cfn-lint failed for {rel(template)}:\n{result.stdout}\n{result.stderr}"
        )

    errors = [f for f in findings if f.get("Level") == "Error"]
    assert not errors, (
        f"cfn-lint reported {len(errors)} error(s) for {rel(template)}:\n"
        + "\n".join(
            f"  {e.get('Rule', {}).get('Id', '?')}: {e.get('Message', '')}"
            for e in errors
        )
    )


# A CloudFormation template that inlines a queue environment living under
# ``queue_environments/`` must keep the copy identical, so a fix to one is a fix
# to both. The relationship is declared in the template rather than registered
# here, so a new template is covered the moment it is written:
#
#     Template: |
#       ### START_QUEUE_ENV from queue_environments/docker_queue_env.yaml
#       <the shared file, indented>
#       ### END_QUEUE_ENV
#
# Templates whose delimiters carry no ``from`` path are deliberately excluded.
# starter_farm and cuda_farm inline a conda environment that
# apply-conda-queue-env.py rewrites on the way in (it replaces the CondaChannels
# default), so those copies are intentionally not byte-identical.
_INLINE_QUEUE_ENV_START = re.compile(
    r"^(?P<indent>[ \t]*)### START_QUEUE_ENV from (?P<source>\S+)\s*$", re.MULTILINE
)


def _inlined_queue_environments() -> list[tuple[Path, str, str]]:
    """Every (template, declared source, de-indented inlined text) triple.

    Enumerated up front so each is its own test case. A skipped check is
    indistinguishable from a passing one.
    """
    found = []
    for template in find_cloudformation_templates():
        text = template.read_text(encoding="utf-8")
        for match in _INLINE_QUEUE_ENV_START.finditer(text):
            indent = match.group("indent")
            body_start = match.end() + 1
            end = text.find(f"{indent}### END_QUEUE_ENV", body_start)
            assert end != -1, (
                f"{rel(template)} opens START_QUEUE_ENV at the same indentation "
                f"without a matching '{indent}### END_QUEUE_ENV'"
            )
            lines = text[body_start:end].splitlines()
            deindented = [
                line[len(indent):] if line.startswith(indent) else line for line in lines
            ]
            found.append((template, match.group("source"), "\n".join(deindented) + "\n"))
    return found


_INLINED_QUEUE_ENVS = _inlined_queue_environments()


def test_inlined_queue_environments_discovered():
    """Guard against the regex silently matching nothing after a reformat."""
    assert _INLINED_QUEUE_ENVS, (
        "no CloudFormation template declares '### START_QUEUE_ENV from <path>'; "
        "if that is intentional, remove this check and the drift test below"
    )


@pytest.mark.parametrize(
    ("template", "source", "inlined"),
    _INLINED_QUEUE_ENVS,
    ids=[f"{rel(t)}::{s}" for t, s, _ in _INLINED_QUEUE_ENVS],
)
def test_inlined_queue_environment_has_not_drifted(template: Path, source: str, inlined: str):
    """An inlined queue environment must match the shared file it names."""
    shared = REPO_ROOT / source
    assert shared.is_file(), (
        f"{rel(template)} declares its queue environment comes from {source}, "
        f"which does not exist"
    )
    assert inlined == shared.read_text(encoding="utf-8"), (
        f"{rel(template)} has drifted from {source}. Re-inline the shared file so "
        f"a fix to one applies to both, or drop the 'from {source}' declaration "
        f"if the copy is deliberately different."
    )
