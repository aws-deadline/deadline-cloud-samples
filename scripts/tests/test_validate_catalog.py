from __future__ import annotations

import sys
import unittest
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS_DIR))

from validate_catalog import (  # noqa: E402
    ValidationFailure,
    validate_schema,
    validate_title_uniqueness,
)


class ValidateSchemaTests(unittest.TestCase):
    def test_boolean_does_not_equal_integer_const(self) -> None:
        with self.assertRaises(ValidationFailure):
            validate_schema(True, {"const": 1}, {})

    def test_boolean_does_not_equal_integer_enum_value(self) -> None:
        with self.assertRaises(ValidationFailure):
            validate_schema(True, {"enum": [1]}, {})

    def test_date_rejects_compact_iso_form(self) -> None:
        with self.assertRaises(ValidationFailure):
            validate_schema("20260714", {"type": "string", "format": "date"}, {})

    def test_date_rejects_iso_week_date(self) -> None:
        with self.assertRaises(ValidationFailure):
            validate_schema("2026-W29-2", {"type": "string", "format": "date"}, {})

    def test_date_accepts_rfc3339_full_date(self) -> None:
        validate_schema("2026-07-14", {"type": "string", "format": "date"}, {})

    def test_date_rejects_invalid_calendar_date(self) -> None:
        with self.assertRaises(ValidationFailure):
            validate_schema("2026-02-30", {"type": "string", "format": "date"}, {})

    def test_semantically_duplicate_titles_are_rejected(self) -> None:
        samples = [
            {"path": "samples/one", "title": "Redshift for Maya: Conda Recipe"},
            {"path": "samples/two", "title": "redshift-for-maya conda recipe"},
        ]
        with self.assertRaisesRegex(ValidationFailure, "semantically duplicate titles"):
            validate_title_uniqueness(samples)

    def test_version_distinguished_titles_are_accepted(self) -> None:
        samples = [
            {"path": "samples/2025", "title": "Redshift 2025 for Maya Conda Recipe"},
            {"path": "samples/2026", "title": "Redshift 2026 for Maya Conda Recipe"},
        ]
        validate_title_uniqueness(samples)


if __name__ == "__main__":
    unittest.main()
