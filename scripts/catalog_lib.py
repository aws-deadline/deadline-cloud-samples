#!/usr/bin/env python3
"""Shared helpers for the sample catalog tools."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
CATALOG_PATH = REPOSITORY_ROOT / "sample_catalog.json"
SCHEMA_PATH = REPOSITORY_ROOT / "sample_catalog.schema.json"
GENERATED_PATH = REPOSITORY_ROOT / "SAMPLES.md"


def load_json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as stream:
        value = json.load(stream)
    if not isinstance(value, dict):
        raise ValueError(f"{path.relative_to(REPOSITORY_ROOT)} must contain a JSON object")
    return value


def load_catalog() -> dict[str, Any]:
    return load_json(CATALOG_PATH)


def taxonomy_labels(catalog: dict[str, Any], taxonomy: str) -> dict[str, str]:
    return {item["id"]: item["label"] for item in catalog["taxonomy"][taxonomy]}
