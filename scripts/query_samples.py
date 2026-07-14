#!/usr/bin/env python3
"""Query sample_catalog.json by controlled metadata."""

from __future__ import annotations

import argparse

from catalog_lib import load_catalog


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--category")
    parser.add_argument("--task")
    parser.add_argument("--journey")
    parser.add_argument("--platform")
    parser.add_argument("--tag")
    args = parser.parse_args()
    samples = load_catalog()["samples"]
    for sample in sorted(samples, key=lambda item: item["path"]):
        if args.category and sample["category"] != args.category:
            continue
        if args.task and args.task not in sample["tasks"]:
            continue
        if args.journey and args.journey not in sample.get("journeys", []):
            continue
        if args.platform and args.platform not in sample.get("platforms", []):
            continue
        if args.tag and args.tag not in sample.get("tags", []):
            continue
        print(f"{sample['path']}\t{sample['title']}\t{sample['description']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
