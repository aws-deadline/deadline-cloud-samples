from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS_DIR))

import check_markdown_links as checker  # noqa: E402


class MarkdownLinkCheckerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)
        self.original_root = checker.REPOSITORY_ROOT
        checker.REPOSITORY_ROOT = Path(self.temporary_directory.name)
        self.addCleanup(setattr, checker, "REPOSITORY_ROOT", self.original_root)
        self.source = checker.REPOSITORY_ROOT / "README.md"

    def write(self, relative_path: str, content: str) -> Path:
        path = checker.REPOSITORY_ROOT / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return path

    def test_missing_heading_fragment_is_rejected(self) -> None:
        self.write("SAMPLES.md", "# Sample catalog\n")
        self.source.write_text("source\n", encoding="utf-8")
        error = checker.check_target(self.source, "SAMPLES.md#definitely-not-a-heading")
        self.assertIn("broken local fragment", error or "")

    def test_existing_heading_fragment_is_accepted(self) -> None:
        self.write("SAMPLES.md", "# Sample catalog\n\n## Render content\n")
        self.source.write_text("source\n", encoding="utf-8")
        self.assertIsNone(checker.check_target(self.source, "SAMPLES.md#render-content"))

    def test_existing_same_document_fragment_is_accepted(self) -> None:
        self.source.write_text("# Overview\n\n## Render content\n", encoding="utf-8")
        self.assertIsNone(checker.check_target(self.source, "#render-content"))

    def test_missing_same_document_fragment_is_rejected(self) -> None:
        self.source.write_text("# Overview\n", encoding="utf-8")
        error = checker.check_target(self.source, "#missing-heading")
        self.assertIn("broken local fragment", error or "")

    def test_empty_links_are_accepted(self) -> None:
        self.source.write_text("# Overview\n", encoding="utf-8")
        self.assertIsNone(checker.check_target(self.source, ""))
        self.assertIsNone(checker.check_target(self.source, "#"))

    def test_multiline_link_label_is_scanned(self) -> None:
        targets = checker.extract_targets("[a useful\nmultiline label](docs/guide.md)\n")
        self.assertEqual(["docs/guide.md"], targets)

    def test_unquoted_html_target_is_scanned(self) -> None:
        targets = checker.extract_targets("<img src=images/example.png alt=Example>\n")
        self.assertEqual(["images/example.png"], targets)

    def test_links_inside_html_comments_are_ignored(self) -> None:
        text = "before\n<!-- [hidden](missing.md)\n<a href=also-missing.md> -->\nafter\n"
        self.assertEqual([], checker.extract_targets(text))

    def test_brackets_followed_by_spaced_parenthetical_are_not_links(self) -> None:
        targets = checker.extract_targets("Region [0,0,960,540] (top-left)\n")
        self.assertEqual([], targets)

    def test_shorter_fence_does_not_close_four_backtick_block(self) -> None:
        text = (
            "````markdown\n"
            "[hidden](missing-one.md)\n"
            "```\n"
            "[still hidden](missing-two.md)\n"
            "````\n"
            "[visible](present.md)\n"
        )
        self.assertEqual(["present.md"], checker.extract_targets(text))

    def test_duplicate_headings_use_github_suffixes(self) -> None:
        fragments = checker.heading_fragments("# Example\n## Example\n## Example\n")
        self.assertEqual({"example", "example-1", "example-2"}, fragments)

    def test_explicit_unquoted_html_anchor_is_supported(self) -> None:
        fragments = checker.heading_fragments("<a id=custom-anchor></a>\n")
        self.assertIn("custom-anchor", fragments)


if __name__ == "__main__":
    unittest.main()
