"""Resolve a shot's context from the studio config hierarchy.

The "resolved context" is the heart of the pipeline. It is a single dictionary,
produced by deep-merging the config layers from least to most specific:

    studio.yaml  <  project.yaml  <  sequence.yaml  <  shot.yaml

Every other part of the pipeline consumes this dictionary — the workstation
launch, the job-parameter mapping at submit time, and (indirectly, through the
job parameters) the render on the worker. Keeping resolution in one place means
the workstation and the farm always agree on what a shot "is".
"""
from __future__ import annotations

import copy
import os
from dataclasses import dataclass, field
from typing import Any

import yaml


class ContextError(Exception):
    """A shot path could not be resolved against the config hierarchy."""


def studio_root() -> str:
    """The shared-drive root, from $STUDIO_ROOT.

    Everything in the pipeline is addressed relative to this so the same configs
    and code work on a workstation, in CI, and on a worker.
    """
    root = os.environ.get("STUDIO_ROOT")
    if not root:
        raise ContextError(
            "STUDIO_ROOT is not set. Point it at the studio/ shared-drive root, e.g.\n"
            "  export STUDIO_ROOT=/path/to/job_bundles/vfx_pipeline/studio"
        )
    if not os.path.isdir(root):
        raise ContextError(f"STUDIO_ROOT does not exist: {root}")
    return os.path.abspath(root)


def _load_yaml(path: str) -> dict[str, Any]:
    if not os.path.isfile(path):
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    """Recursively merge `override` onto `base`, returning a new dict.

    Nested dicts merge key-by-key; every other type (including lists) is
    replaced wholesale. This means a shot that sets `render.resolution` replaces
    the project's resolution but keeps the project's `render.samples`.
    """
    result = copy.deepcopy(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = copy.deepcopy(value)
    return result


@dataclass
class ShotContext:
    """A fully resolved shot, ready to drive a launch or a submission."""

    project: str
    sequence: str
    shot: str
    data: dict[str, Any] = field(default_factory=dict)

    @property
    def shot_id(self) -> str:
        """A flat, stable identifier, e.g. 'moonrise_seq010_sh010'."""
        return f"{self.project}_{self.sequence}_{self.shot}"

    @property
    def asset_path(self) -> str:
        """Absolute path to the shot's .blend asset on the shared drive."""
        rel = self.data.get("asset")
        if not rel:
            raise ContextError(f"Shot {self.shot_id} has no 'asset' in its config.")
        return os.path.join(studio_root(), "assets", rel)

    def render(self, key: str, default: Any = None) -> Any:
        return self.data.get("render", {}).get(key, default)

    def flow(self, key: str, default: Any = None) -> Any:
        return self.data.get("flow", {}).get(key, default)


def parse_shot_path(shot_path: str) -> tuple[str, str, str]:
    """Split 'project/sequence/shot' into its three parts."""
    parts = [p for p in shot_path.strip("/").split("/") if p]
    if len(parts) != 3:
        raise ContextError(
            f"Shot path must be 'project/sequence/shot', got: {shot_path!r}"
        )
    return parts[0], parts[1], parts[2]


def resolve(shot_path: str) -> ShotContext:
    """Resolve 'project/sequence/shot' into a merged ShotContext.

    Walks the four config layers under $STUDIO_ROOT/config and deep-merges them.
    Raises ContextError if the shot's own config file is missing (the studio /
    project / sequence layers are allowed to be absent and simply contribute
    nothing).
    """
    project, sequence, shot = parse_shot_path(shot_path)
    config_root = os.path.join(studio_root(), "config")
    project_dir = os.path.join(config_root, "projects", project)
    sequence_dir = os.path.join(project_dir, "sequences", sequence)
    shot_dir = os.path.join(sequence_dir, "shots", shot)

    shot_file = os.path.join(shot_dir, "shot.yaml")
    if not os.path.isfile(shot_file):
        raise ContextError(
            f"No shot config at {shot_file}. Check the project/sequence/shot path."
        )

    layers = [
        os.path.join(config_root, "studio.yaml"),
        os.path.join(project_dir, "project.yaml"),
        os.path.join(sequence_dir, "sequence.yaml"),
        shot_file,
    ]

    merged: dict[str, Any] = {}
    for layer in layers:
        merged = _deep_merge(merged, _load_yaml(layer))

    return ShotContext(project=project, sequence=sequence, shot=shot, data=merged)
