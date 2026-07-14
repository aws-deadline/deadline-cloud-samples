# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
"""Static checks for the Conda package recipes.

Each recipe directory ships a ``deadline-cloud.yaml`` describing the platforms
the package builds for, plus a ``recipe/`` directory containing the recipe in
one of two formats:

* ``recipe.yaml`` -- the rattler-build format. Validated by running
  ``rattler-build build --render-only``, which parses the recipe, evaluates its
  ``context``/``${{ }}`` templating, and renders the full build graph *without*
  building or solving dependencies over the network. This is rattler-build's own
  validation path, so it catches anything rattler-build itself would reject.
* ``meta.yaml`` -- the conda-build format. Validated by rendering its Jinja and
  selector syntax and checking the resulting document against the conda-build
  schema. conda-build's own ``conda render`` requires solving dependencies
  against remote channels (network, non-deterministic), so it is unsuitable for
  CI; this offline renderer performs the equivalent structural validation.

Both validators run in CI and are never skipped: a missing tool fails the run.
"""
from __future__ import annotations

import re
import shutil
import subprocess
import tempfile
from pathlib import Path

import pytest
import yaml

from conftest import find_conda_recipe_dirs, rel, require_tool

_RECIPE_DIRS = find_conda_recipe_dirs()

# Platforms recognised by the Conda / Deadline Cloud tooling.
_KNOWN_PLATFORMS = {"linux-64", "linux-aarch64", "win-64", "osx-64", "osx-arm64"}
# Build tools referenced by these samples.
_KNOWN_BUILD_TOOLS = {"conda-build", "rattler-build"}

_RATTLER_INSTALL_HINT = (
    "install rattler-build (https://rattler.build/latest/installation/); "
    "in CI the workflow downloads the pinned release binary"
)

# Some sample recipes are deliberately fill-in-the-blanks templates: the user
# supplies their own source archive and its checksum before building (e.g.
# blender-plugin-bundle, whose README instructs the user to replace the SHA256).
# rattler-build rightly rejects a non-hex placeholder, so before rendering we
# substitute a syntactically valid dummy checksum. This keeps the FULL recipe
# structure under real rattler-build validation -- only the intentionally-blank
# checksum field is normalized, nothing is skipped.
_PLACEHOLDER_SHA256_RE = re.compile(
    r"(sha256:\s*)(PLACEHOLDER_SHA\w*|<[^>]*>|REPLACE_ME\w*|TODO\w*|CHANGEME\w*|x{6,})",
    re.IGNORECASE,
)
_DUMMY_SHA256 = "0" * 64

# Recipe directories partitioned by which recipe file(s) they contain, so each
# format is validated by the matching tool. A directory can contain both.
_RATTLER_RECIPES = [d for d in _RECIPE_DIRS if (d / "recipe" / "recipe.yaml").exists()]
_CONDA_BUILD_RECIPES = [d for d in _RECIPE_DIRS if (d / "recipe" / "meta.yaml").exists()]


def test_conda_recipes_discovered():
    assert _RECIPE_DIRS, "no conda recipe directories were discovered"


def _load_deadline_cloud_yaml(recipe_dir: Path) -> dict:
    text = (recipe_dir / "deadline-cloud.yaml").read_text(encoding="utf-8")
    doc = yaml.safe_load(text)
    assert isinstance(doc, dict), "deadline-cloud.yaml did not parse to a mapping"
    return doc


@pytest.mark.parametrize("recipe_dir", _RECIPE_DIRS, ids=rel)
def test_deadline_cloud_yaml_schema(recipe_dir: Path):
    doc = _load_deadline_cloud_yaml(recipe_dir)

    platforms = doc.get("condaPlatforms")
    assert isinstance(platforms, list) and platforms, (
        f"{rel(recipe_dir)}/deadline-cloud.yaml must have a non-empty "
        f"'condaPlatforms' list"
    )

    for entry in platforms:
        assert isinstance(entry, dict), "each condaPlatforms entry must be a mapping"

        platform = entry.get("platform")
        assert platform in _KNOWN_PLATFORMS, (
            f"{rel(recipe_dir)}: unknown platform {platform!r} "
            f"(expected one of {sorted(_KNOWN_PLATFORMS)})"
        )

        build_tool = entry.get("buildTool")
        # Normalize trailing inline-comment noise that appears in a couple of files.
        if isinstance(build_tool, str):
            build_tool = build_tool.split("#", 1)[0].strip()
        assert build_tool in _KNOWN_BUILD_TOOLS, (
            f"{rel(recipe_dir)}: platform {platform!r} has unknown buildTool "
            f"{entry.get('buildTool')!r} (expected one of {sorted(_KNOWN_BUILD_TOOLS)})"
        )

        # The declared buildTool must have a matching recipe file to build from.
        if build_tool == "rattler-build":
            assert (recipe_dir / "recipe" / "recipe.yaml").exists(), (
                f"{rel(recipe_dir)}: buildTool is rattler-build but there is no "
                f"recipe/recipe.yaml"
            )
        elif build_tool == "conda-build":
            has_meta = (recipe_dir / "recipe" / "meta.yaml").exists()
            has_recipe = (recipe_dir / "recipe" / "recipe.yaml").exists()
            assert has_meta or has_recipe, (
                f"{rel(recipe_dir)}: buildTool is conda-build but there is no "
                f"recipe/meta.yaml (or recipe.yaml)"
            )


@pytest.mark.parametrize("recipe_dir", _RECIPE_DIRS, ids=rel)
def test_recipe_directory_present(recipe_dir: Path):
    recipe_subdir = recipe_dir / "recipe"
    assert recipe_subdir.is_dir(), (
        f"{rel(recipe_dir)} has a deadline-cloud.yaml but no 'recipe/' directory"
    )
    assert (recipe_subdir / "recipe.yaml").exists() or (
        recipe_subdir / "meta.yaml"
    ).exists(), f"{rel(recipe_subdir)} has neither recipe.yaml nor meta.yaml"


@pytest.mark.parametrize("recipe_dir", _RATTLER_RECIPES, ids=rel)
def test_rattler_recipe_renders(recipe_dir: Path):
    """Validate a rattler-build recipe with ``build --render-only`` (offline)."""
    rattler_build = require_tool("rattler-build", _RATTLER_INSTALL_HINT)
    recipe_yaml = recipe_dir / "recipe" / "recipe.yaml"

    original = recipe_yaml.read_text(encoding="utf-8")
    normalized, n_subs = _PLACEHOLDER_SHA256_RE.subn(
        rf"\g<1>{_DUMMY_SHA256}", original
    )

    if n_subs == 0:
        # No placeholder: render the recipe in place.
        render_path = recipe_yaml
        cleanup_dir = None
    else:
        # Placeholder present: render a copy of the recipe directory with a valid
        # dummy checksum so the whole recipe is still validated by rattler-build.
        cleanup_dir = Path(tempfile.mkdtemp(prefix="recipe_render_"))
        shutil.copytree(recipe_yaml.parent, cleanup_dir / "recipe")
        render_path = cleanup_dir / "recipe" / "recipe.yaml"
        render_path.write_text(normalized, encoding="utf-8")

    try:
        result = subprocess.run(
            [rattler_build, "build", "--render-only", "--recipe", str(render_path)],
            capture_output=True,
            text=True,
            timeout=180,
        )
    finally:
        if cleanup_dir is not None:
            shutil.rmtree(cleanup_dir, ignore_errors=True)

    note = (
        f" (rendered with {n_subs} placeholder checksum(s) replaced by a dummy value)"
        if n_subs
        else ""
    )
    assert result.returncode == 0, (
        f"rattler-build --render-only failed for {rel(recipe_yaml)}{note}:\n"
        f"{result.stdout[-2000:]}\n{result.stderr[-2000:]}"
    )
    # A successful render emits the rendered recipe(s) as JSON on stdout.
    assert result.stdout.strip(), (
        f"rattler-build --render-only produced no output for {rel(recipe_yaml)}"
    )


@pytest.mark.parametrize("recipe_dir", _CONDA_BUILD_RECIPES, ids=rel)
def test_conda_build_recipe_renders(recipe_dir: Path):
    """Render and structurally validate a conda-build ``meta.yaml`` offline.

    conda-build's ``meta.yaml`` mixes Jinja templating and ``# [selector]``
    line comments. This renders both and validates the resulting document has
    the required ``package.name``/``package.version`` -- the equivalent of what
    ``conda render`` checks, but without the network dependency solve that makes
    ``conda render`` unsuitable for CI.
    """
    meta_yaml = recipe_dir / "recipe" / "meta.yaml"
    doc = _render_conda_meta_yaml(meta_yaml)

    assert isinstance(doc, dict), f"{rel(meta_yaml)} did not render to a mapping"

    package = doc.get("package") or {}
    assert isinstance(package, dict) and package.get("name"), (
        f"{rel(meta_yaml)} is missing 'package.name'"
    )
    assert package.get("version") not in (None, ""), (
        f"{rel(meta_yaml)} is missing 'package.version'"
    )

    build = doc.get("build")
    if build is not None:
        assert isinstance(build, dict), f"{rel(meta_yaml)}: 'build' must be a mapping"


# --- conda-build meta.yaml rendering helpers ---------------------------------

# conda-build line selectors, e.g. "  - foo  # [win and not py27]". They are
# stripped before YAML parsing; evaluating them would require a target platform,
# and for structural validation we only need the union of lines to parse.
_SELECTOR_RE = re.compile(r"#\s*\[[^\]]*\]\s*$", re.MULTILINE)


def _render_conda_meta_yaml(meta_yaml: Path) -> object:
    """Render a conda-build meta.yaml (Jinja + selectors) to a Python object."""
    try:
        import jinja2
    except ModuleNotFoundError:  # pragma: no cover - CI always installs jinja2
        require_tool("__jinja2_missing__", "pip install Jinja2")
        raise

    class _Undefined(jinja2.Undefined):
        """Silently resolve unknown Jinja names so templating never crashes."""

        def __getattr__(self, name):
            return _Undefined()

        def __call__(self, *args, **kwargs):
            return _Undefined()

        def __getitem__(self, key):
            return _Undefined()

        def __str__(self):
            return ""

    # The functions/vars conda-build injects into the Jinja context. We provide
    # inert stand-ins so templating succeeds without a build environment.
    context = {
        "compiler": lambda *a, **k: "",
        "cdt": lambda *a, **k: "",
        "stdlib": lambda *a, **k: "",
        "pin_compatible": lambda *a, **k: "",
        "pin_subpackage": lambda *a, **k: "",
        "load_setup_py_data": lambda *a, **k: {},
        "load_file_regex": lambda *a, **k: None,
        "load_file_data": lambda *a, **k: {},
        "load_str_data": lambda *a, **k: {},
        "resolved_packages": lambda *a, **k: [],
        "environ": {},
        "os": __import__("os"),
    }

    # autoescape is enabled to satisfy static analysis; it only affects the
    # output of ``{{ }}`` expressions (never the literal template text). Every
    # substitution here is an inert stand-in or a version/name string with no
    # HTML-special characters, so escaping does not change the parsed YAML.
    env = jinja2.Environment(
        undefined=_Undefined, keep_trailing_newline=True, autoescape=True
    )
    text = meta_yaml.read_text(encoding="utf-8")
    text = _SELECTOR_RE.sub("", text)
    try:
        rendered = env.from_string(text).render(**context)
    except jinja2.TemplateError as exc:
        pytest.fail(f"{rel(meta_yaml)} failed Jinja rendering:\n{exc}")

    try:
        parsed = yaml.safe_load(rendered)
    except yaml.YAMLError as exc:
        pytest.fail(
            f"{rel(meta_yaml)} did not parse as YAML after rendering:\n{exc}"
        )
    return parsed


# NOTE: we intentionally do not check that a platform's ``sourceArchiveDirectory``
# exists. Those paths point into the gitignored ``conda_recipes/archive_files/``
# tree where a builder downloads vendor binaries locally; the directories are not
# committed to the repository, so their absence is expected and correct.
