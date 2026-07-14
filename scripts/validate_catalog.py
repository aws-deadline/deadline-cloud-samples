#!/usr/bin/env python3
"""Validate sample metadata, tracked inventory coverage, and generated output."""

from __future__ import annotations

import fnmatch
import re
import subprocess
import sys
from datetime import date
from pathlib import Path
from typing import Any

from catalog_lib import CATALOG_PATH, GENERATED_PATH, REPOSITORY_ROOT, SCHEMA_PATH, load_catalog, load_json
from generate_samples import render


class ValidationFailure(Exception):
    pass


def fail(message: str) -> None:
    raise ValidationFailure(message)


def resolve_reference(root_schema: dict[str, Any], reference: str) -> dict[str, Any]:
    if not reference.startswith("#/"):
        fail(f"unsupported schema reference: {reference}")
    value: Any = root_schema
    for component in reference[2:].split("/"):
        value = value[component.replace("~1", "/").replace("~0", "~")]
    return value


def json_equal(left: Any, right: Any) -> bool:
    """Compare JSON values without treating booleans as numbers."""
    if type(left) is not type(right):
        return False
    if isinstance(left, dict):
        return left.keys() == right.keys() and all(json_equal(left[key], right[key]) for key in left)
    if isinstance(left, list):
        return len(left) == len(right) and all(json_equal(a, b) for a, b in zip(left, right))
    return left == right


def validate_schema(value: Any, rule: dict[str, Any], root_schema: dict[str, Any], location: str = "$") -> None:
    if "$ref" in rule:
        validate_schema(value, resolve_reference(root_schema, rule["$ref"]), root_schema, location)
        return
    if "const" in rule and not json_equal(value, rule["const"]):
        fail(f"{location}: expected {rule['const']!r}")
    if "enum" in rule and not any(json_equal(value, option) for option in rule["enum"]):
        fail(f"{location}: {value!r} is not one of {rule['enum']!r}")

    expected_type = rule.get("type")
    type_matches = {
        "object": lambda item: isinstance(item, dict),
        "array": lambda item: isinstance(item, list),
        "string": lambda item: isinstance(item, str),
        "boolean": lambda item: isinstance(item, bool),
        "integer": lambda item: isinstance(item, int) and not isinstance(item, bool),
    }
    if expected_type and not type_matches[expected_type](value):
        fail(f"{location}: expected {expected_type}, got {type(value).__name__}")

    if isinstance(value, dict):
        for required in rule.get("required", []):
            if required not in value:
                fail(f"{location}: missing required property {required!r}")
        properties = rule.get("properties", {})
        if rule.get("additionalProperties") is False:
            unexpected = sorted(set(value) - set(properties))
            if unexpected:
                fail(f"{location}: unexpected properties {unexpected!r}")
        for key, child in value.items():
            if key in properties:
                validate_schema(child, properties[key], root_schema, f"{location}.{key}")

    if isinstance(value, list):
        if len(value) < rule.get("minItems", 0):
            fail(f"{location}: expected at least {rule['minItems']} items")
        if rule.get("uniqueItems"):
            for index, item in enumerate(value):
                if any(json_equal(item, earlier) for earlier in value[:index]):
                    fail(f"{location}: array values must be unique")
        if "items" in rule:
            for index, child in enumerate(value):
                validate_schema(child, rule["items"], root_schema, f"{location}[{index}]")

    if isinstance(value, str):
        if len(value) < rule.get("minLength", 0):
            fail(f"{location}: string is shorter than {rule['minLength']} characters")
        if "maxLength" in rule and len(value) > rule["maxLength"]:
            fail(f"{location}: string is longer than {rule['maxLength']} characters")
        if "pattern" in rule and not re.fullmatch(rule["pattern"], value):
            fail(f"{location}: {value!r} does not match {rule['pattern']!r}")
        if rule.get("format") == "date":
            if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
                fail(f"{location}: {value!r} is not an RFC 3339 full-date")
            try:
                date.fromisoformat(value)
            except ValueError:
                fail(f"{location}: {value!r} is not an RFC 3339 full-date")


def tracked_paths() -> list[str]:
    output = subprocess.check_output(["git", "ls-files", "-z"], cwd=REPOSITORY_ROOT).decode("utf-8")
    return [path for path in output.split("\0") if path]


def discover_inventory(catalog: dict[str, Any], tracked: list[str]) -> set[str]:
    discovered: set[str] = set()
    for root in catalog["inventory"]["roots"]:
        prefix = root["path"].rstrip("/") + "/"
        pattern = root.get("pattern", "*")
        if root["kind"] == "directory":
            children = {
                remainder.split("/", 1)[0]
                for path in tracked
                if path.startswith(prefix)
                for remainder in [path[len(prefix) :]]
                if "/" in remainder
            }
        else:
            children = {
                remainder
                for path in tracked
                if path.startswith(prefix)
                for remainder in [path[len(prefix) :]]
                if "/" not in remainder and fnmatch.fnmatchcase(remainder, pattern)
            }
        discovered.update(prefix + child for child in children)
    return discovered


def semantic_title(title: str) -> str:
    """Normalize title presentation differences that should not create distinct samples."""
    return re.sub(r"[\W_]+", " ", title.casefold(), flags=re.UNICODE).strip()


def validate_title_uniqueness(samples: list[dict[str, Any]]) -> None:
    paths_by_title: dict[str, list[str]] = {}
    for sample in samples:
        paths_by_title.setdefault(semantic_title(sample["title"]), []).append(sample["path"])
    duplicates = {title: paths for title, paths in paths_by_title.items() if len(paths) > 1}
    if duplicates:
        details = "; ".join(f"{title!r}: {paths}" for title, paths in sorted(duplicates.items()))
        fail(f"samples: semantically duplicate titles: {details}")


def validate_semantics(catalog: dict[str, Any]) -> None:
    for taxonomy_name in ("categories", "tasks", "journeys"):
        identifiers = [item["id"] for item in catalog["taxonomy"][taxonomy_name]]
        if len(identifiers) != len(set(identifiers)):
            fail(f"taxonomy.{taxonomy_name}: duplicate IDs")

    category_ids = {item["id"] for item in catalog["taxonomy"]["categories"]}
    task_ids = {item["id"] for item in catalog["taxonomy"]["tasks"]}
    journey_ids = {item["id"] for item in catalog["taxonomy"]["journeys"]}
    sample_paths = [sample["path"] for sample in catalog["samples"]]
    if len(sample_paths) != len(set(sample_paths)):
        fail("samples: duplicate paths")
    validate_title_uniqueness(catalog["samples"])

    for sample in catalog["samples"]:
        path = sample["path"]
        if not (REPOSITORY_ROOT / path).exists():
            fail(f"samples: path does not exist: {path}")
        if sample["category"] not in category_ids:
            fail(f"{path}: undefined category {sample['category']}")
        undefined_tasks = set(sample["tasks"]) - task_ids
        undefined_journeys = set(sample.get("journeys", [])) - journey_ids
        if undefined_tasks:
            fail(f"{path}: undefined tasks {sorted(undefined_tasks)}")
        if undefined_journeys:
            fail(f"{path}: undefined journeys {sorted(undefined_journeys)}")
        if sample["description"].rstrip()[-1] not in ".!?":
            fail(f"{path}: description must end with punctuation")

    tracked = tracked_paths()
    discovered = discover_inventory(catalog, tracked)
    exclusions = catalog["inventory"]["exclusions"]
    exclusion_paths = [item["path"] for item in exclusions]
    if len(exclusion_paths) != len(set(exclusion_paths)):
        fail("inventory.exclusions: duplicate paths")
    invalid_exclusions = set(exclusion_paths) - discovered
    if invalid_exclusions:
        fail(f"inventory.exclusions: paths are not discoverable: {sorted(invalid_exclusions)}")

    expected_samples = discovered - set(exclusion_paths)
    actual_samples = set(sample_paths)
    missing = expected_samples - actual_samples
    unexpected = actual_samples - expected_samples
    if missing or unexpected:
        details = []
        if missing:
            details.append(f"missing catalog entries: {sorted(missing)}")
        if unexpected:
            details.append(f"entries outside tracked inventory: {sorted(unexpected)}")
        fail("; ".join(details))

    generated = render(catalog)
    current = GENERATED_PATH.read_text(encoding="utf-8") if GENERATED_PATH.exists() else ""
    if current != generated:
        fail("SAMPLES.md drifted; run: python3 scripts/generate_samples.py")


def main() -> int:
    try:
        catalog = load_catalog()
        schema = load_json(SCHEMA_PATH)
        validate_schema(catalog, schema, schema)
        validate_semantics(catalog)
    except (OSError, ValueError, ValidationFailure) as error:
        print(f"Catalog validation failed: {error}", file=sys.stderr)
        return 1
    print(f"Catalog valid ({len(catalog['samples'])} samples; exact tracked inventory coverage)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
