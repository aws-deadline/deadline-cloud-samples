#!/usr/bin/env python3
"""Check local links in every tracked Markdown file."""

from __future__ import annotations

import html
import os
import re
import subprocess
import sys
from pathlib import Path
from urllib.parse import unquote, urlsplit

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
SCHEME = re.compile(r"^[A-Za-z][A-Za-z0-9+.-]*:")
REFERENCE_DEFINITION = re.compile(r"^\s*\[[^]]+\]:\s*(?:<([^>]+)>|(\S+))", re.MULTILINE)
HTML_TARGET = re.compile(
    r"\b(?:href|src)\s*=\s*(?:\"([^\"]*)\"|'([^']*)'|([^\s>'\"]+))",
    re.IGNORECASE,
)
OPENING_FENCE = re.compile(r"^ {0,3}(`{3,}|~{3,})(.*)$")
ATX_HEADING = re.compile(r"^ {0,3}#{1,6}(?:[ \t]+|$)(.*)$")
SETEXT_HEADING = re.compile(r"^ {0,3}(=+|-+)[ \t]*$")
HTML_ANCHOR = re.compile(
    r"<(?:a\b[^>]*\b(?:id|name)|[A-Za-z][A-Za-z0-9:-]*\b[^>]*\bid)\s*=\s*"
    r"(?:\"([^\"]+)\"|'([^']+)'|([^\s>'\"]+))",
    re.IGNORECASE,
)


def tracked_markdown() -> list[Path]:
    output = subprocess.check_output(
        ["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard"],
        cwd=REPOSITORY_ROOT,
    ).decode("utf-8")
    return [REPOSITORY_ROOT / path for path in output.split("\0") if path.endswith(".md")]


def strip_html_comments(line: str, in_comment: bool) -> tuple[str, bool]:
    visible: list[str] = []
    position = 0
    while position < len(line):
        if in_comment:
            end = line.find("-->", position)
            if end == -1:
                return "".join(visible), True
            position = end + 3
            in_comment = False
            continue
        start = line.find("<!--", position)
        if start == -1:
            visible.append(line[position:])
            break
        visible.append(line[position:start])
        position = start + 4
        in_comment = True
    return "".join(visible), in_comment


def strip_inline_code(line: str) -> str:
    visible: list[str] = []
    position = 0
    while position < len(line):
        if line[position] != "`":
            visible.append(line[position])
            position += 1
            continue
        end_of_run = position
        while end_of_run < len(line) and line[end_of_run] == "`":
            end_of_run += 1
        marker = line[position:end_of_run]
        closing = line.find(marker, end_of_run)
        if closing == -1:
            visible.append(marker)
            position = end_of_run
        else:
            position = closing + len(marker)
    return "".join(visible)


def strip_code(text: str, *, remove_inline_code: bool = True) -> str:
    """Remove fenced code and HTML comments while preserving line boundaries."""
    visible: list[str] = []
    fence: tuple[str, int] | None = None
    in_comment = False
    for original_line in text.splitlines(keepends=True):
        newline = "\n" if original_line.endswith(("\n", "\r")) else ""
        line = original_line.rstrip("\r\n")
        if fence:
            marker, minimum_length = fence
            if re.fullmatch(rf" {{0,3}}{re.escape(marker)}{{{minimum_length},}}[ \t]*", line):
                fence = None
            visible.append(newline)
            continue

        line, in_comment = strip_html_comments(line, in_comment)
        opening = OPENING_FENCE.match(line)
        if opening and not (opening.group(1).startswith("`") and "`" in opening.group(2)):
            fence = (opening.group(1)[0], len(opening.group(1)))
            visible.append(newline)
            continue
        visible.append((strip_inline_code(line) if remove_inline_code else line) + newline)
    return "".join(visible)


def inline_targets(text: str) -> list[str]:
    targets: list[str] = []
    position = 0
    link_start = re.compile(r"!?\[(?:\\.|[^]])*?\]\(", re.DOTALL)
    while True:
        match = link_start.search(text, position)
        if not match:
            break
        start = match.end()
        depth = 1
        escaped = False
        for index in range(start, len(text)):
            character = text[index]
            if escaped:
                escaped = False
            elif character == "\\":
                escaped = True
            elif character == "(":
                depth += 1
            elif character == ")":
                depth -= 1
                if depth == 0:
                    targets.append(text[start:index].strip())
                    position = index + 1
                    break
        else:
            break
    return targets


def extract_targets(text: str) -> list[str]:
    visible = strip_code(text)
    targets = inline_targets(visible)
    targets.extend(match.group(1) or match.group(2) for match in REFERENCE_DEFINITION.finditer(visible))
    targets.extend(next(group for group in match.groups() if group is not None) for match in HTML_TARGET.finditer(visible))
    return targets


def normalize_target(raw_target: str) -> str:
    target = html.unescape(raw_target.strip())
    if target.startswith("<") and ">" in target:
        return target[1 : target.index(">")]
    # Unescaped whitespace starts an optional Markdown link title.
    return re.split(r"\s+(?=['\"])", target, maxsplit=1)[0].strip()


def exact_case_exists(path: Path) -> bool:
    try:
        relative = path.relative_to(REPOSITORY_ROOT)
    except ValueError:
        return False
    current = REPOSITORY_ROOT
    for component in relative.parts:
        try:
            names = os.listdir(current)
        except OSError:
            return False
        if component not in names:
            return False
        current /= component
    return current.exists()


def github_slug(heading: str) -> str:
    heading = re.sub(r"<[^>]+>", "", heading)
    heading = re.sub(r"!?\[([^]]*)\]\([^)]*\)", r"\1", heading)
    heading = html.unescape(heading).lower()
    heading = re.sub(r"[^\w\-\s]", "", heading, flags=re.UNICODE)
    return re.sub(r"\s+", "-", heading.strip())


def heading_fragments(text: str) -> set[str]:
    visible = strip_code(text, remove_inline_code=False)
    fragments: set[str] = set()
    duplicate_counts: dict[str, int] = {}
    lines = visible.splitlines()
    for index, line in enumerate(lines):
        heading: str | None = None
        atx = ATX_HEADING.match(line)
        if atx:
            heading = re.sub(r"[ \t]+#+[ \t]*$", "", atx.group(1)).strip()
        elif index + 1 < len(lines) and line.strip() and SETEXT_HEADING.match(lines[index + 1]):
            heading = line.strip()
        if heading is not None:
            base = github_slug(heading)
            if base:
                duplicate_number = duplicate_counts.get(base, 0)
                fragment = base if duplicate_number == 0 else f"{base}-{duplicate_number}"
                duplicate_counts[base] = duplicate_number + 1
                fragments.add(fragment)
    for match in HTML_ANCHOR.finditer(visible):
        fragments.add(html.unescape(next(group for group in match.groups() if group is not None)))
    return fragments


def fragment_document(path: Path) -> Path | None:
    if path.is_dir():
        readme = path / "README.md"
        return readme if exact_case_exists(readme) else None
    return path if path.suffix.lower() in {".md", ".markdown"} else None


def check_target(source: Path, raw_target: str, heading_cache: dict[Path, set[str]] | None = None) -> str | None:
    target = normalize_target(raw_target)
    if not target or target == "#" or target.startswith("//") or SCHEME.match(target):
        return None
    parsed = urlsplit(target)
    path_part = unquote(parsed.path)
    source_name = source.relative_to(REPOSITORY_ROOT)
    if path_part:
        resolved = (
            (REPOSITORY_ROOT / path_part.lstrip("/"))
            if path_part.startswith("/")
            else (source.parent / path_part)
        )
        resolved = Path(os.path.normpath(resolved))
        if not exact_case_exists(resolved):
            return f"{source_name}: broken local link {target!r}"
    else:
        resolved = source

    if parsed.fragment:
        document = fragment_document(resolved)
        if document:
            cache = heading_cache if heading_cache is not None else {}
            if document not in cache:
                cache[document] = heading_fragments(document.read_text(encoding="utf-8"))
            fragment = unquote(parsed.fragment)
            if fragment not in cache[document]:
                return f"{source_name}: broken local fragment {target!r}"
    return None


def find_errors() -> list[str]:
    errors: list[str] = []
    heading_cache: dict[Path, set[str]] = {}
    for source in tracked_markdown():
        for target in extract_targets(source.read_text(encoding="utf-8")):
            error = check_target(source, target, heading_cache)
            if error:
                errors.append(error)
    return sorted(set(errors))


def main() -> int:
    errors = find_errors()
    if errors:
        print("Markdown link validation failed:", file=sys.stderr)
        for error in errors:
            print(f"  {error}", file=sys.stderr)
        return 1
    print(f"Markdown links valid ({len(tracked_markdown())} repository files checked)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
