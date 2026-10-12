"""Guard job-bundle parameters against the scripts that consume them.

A template `allowedValues` list and the matching argparse `choices` tuple are
two separate sources of truth for the same set. When they drift, the template
accepts a value the script rejects, and the task fails at startup with an
argparse usage dump -- after the worker has scaled out and pulled a multi-gigabyte
image. `openjd check` cannot catch it, because the template alone is valid.

That is not hypothetical: `SceneSource=usd` was added to the Isaac Sim SDG
template's allowedValues without being added to `generate_sdg.py`, and the
mismatch survived unit tests of the scene functions (which bypass argparse) and
`openjd check`, surfacing only on a real worker.

Standard library only, per AGENTS.md. The template is read with a narrow regex
rather than a YAML parser for the same reason.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path
from unittest import TestCase, main

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]

# (bundle, template parameter, script, argparse option) tuples to keep in step.
CHOICE_PAIRS = [
    (
        "job_bundles/isaacsim_replicator_sdg/template.yaml",
        "SceneSource",
        "job_bundles/isaacsim_replicator_sdg/scripts/generate_sdg.py",
        "--scene-source",
    ),
]


def template_allowed_values(template: Path, parameter: str) -> set[str]:
    """Read one parameter's `allowedValues` from a job template.

    Deliberately narrow: it finds the named `- name: <parameter>` entry and
    returns the first inline `allowedValues: [...]` beneath it, before the next
    parameter begins.
    """
    text = template.read_text()
    start = re.search(rf"^- name: {re.escape(parameter)}\s*$", text, re.MULTILINE)
    if start is None:
        raise AssertionError(f"{template}: no parameter named {parameter}")

    rest = text[start.end():]
    next_param = re.search(r"^- name: ", rest, re.MULTILINE)
    block = rest[: next_param.start()] if next_param else rest

    found = re.search(r"^\s*allowedValues:\s*\[([^\]]*)\]", block, re.MULTILINE)
    if found is None:
        raise AssertionError(f"{template}: {parameter} declares no allowedValues")
    return {v.strip().strip("'\"") for v in found.group(1).split(",") if v.strip()}


def argparse_choices(script: Path, option: str) -> set[str]:
    """Read an argparse `choices=` sequence for one option, via the AST.

    Parsing rather than importing, because these scripts import Isaac Sim
    modules at call time and must not be executed here.
    """
    tree = ast.parse(script.read_text())
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if not (isinstance(func, ast.Attribute) and func.attr == "add_argument"):
            continue
        literals = [a.value for a in node.args if isinstance(a, ast.Constant)]
        if option not in literals:
            continue
        for keyword in node.keywords:
            if keyword.arg == "choices" and isinstance(
                keyword.value, (ast.Tuple, ast.List, ast.Set)
            ):
                return {
                    element.value
                    for element in keyword.value.elts
                    if isinstance(element, ast.Constant)
                }
        raise AssertionError(f"{script}: {option} declares no literal choices")
    raise AssertionError(f"{script}: no add_argument for {option}")


class JobBundleChoiceConsistencyTests(TestCase):
    def test_template_allowed_values_match_script_choices(self) -> None:
        for template_path, parameter, script_path, option in CHOICE_PAIRS:
            with self.subTest(parameter=parameter):
                template = REPOSITORY_ROOT / template_path
                script = REPOSITORY_ROOT / script_path
                self.assertTrue(template.is_file(), f"missing {template}")
                self.assertTrue(script.is_file(), f"missing {script}")

                allowed = template_allowed_values(template, parameter)
                choices = argparse_choices(script, option)
                self.assertEqual(
                    allowed,
                    choices,
                    f"{parameter} allowedValues {sorted(allowed)} != {option} "
                    f"choices {sorted(choices)}. A value the template accepts and "
                    f"the script rejects fails the task at startup.",
                )

    def test_helpers_detect_a_mismatch(self) -> None:
        """Prove the check can fail. A guard never seen to fail is not a guard."""
        import tempfile

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            template = root / "template.yaml"
            template.write_text(
                "- name: SceneSource\n"
                "  type: STRING\n"
                "  allowedValues: [primitives, workshop, usd]\n"
                "- name: Other\n"
            )
            script = root / "script.py"
            script.write_text(
                "import argparse\n"
                "p = argparse.ArgumentParser()\n"
                "p.add_argument('--scene-source', choices=('primitives', 'workshop'))\n"
            )
            self.assertEqual(
                template_allowed_values(template, "SceneSource"),
                {"primitives", "workshop", "usd"},
            )
            self.assertEqual(
                argparse_choices(script, "--scene-source"),
                {"primitives", "workshop"},
            )
            self.assertNotEqual(
                template_allowed_values(template, "SceneSource"),
                argparse_choices(script, "--scene-source"),
            )


if __name__ == "__main__":
    main()
