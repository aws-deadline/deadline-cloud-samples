#!/usr/bin/env python3
"""Run all repository-wide static validation."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
CHECKS = (
    (
        "unit tests",
        sys.executable,
        "-m",
        "unittest",
        "discover",
        "-s",
        str(REPOSITORY_ROOT / "scripts" / "tests"),
        "-p",
        "test_*.py",
    ),
    ("Markdown links", sys.executable, str(REPOSITORY_ROOT / "scripts" / "check_markdown_links.py")),
)


def main() -> int:
    for label, *command in CHECKS:
        print(f"==> {label}", flush=True)
        result = subprocess.run(command, cwd=REPOSITORY_ROOT, check=False)
        if result.returncode:
            return result.returncode
    print("Repository validation passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
