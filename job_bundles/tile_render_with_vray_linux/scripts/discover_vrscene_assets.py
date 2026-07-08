#!/usr/bin/env python3
"""Pre-submission hook that parses a .vrscene file for referenced textures
and additional files, then adds them to the job attachments."""

import json
import os
import re
import sys

# Patterns that capture file paths in vrscene files:
#   - file="..." parameters (BitmapBuffer textures, GeomMeshFile meshes, etc.)
#   - #include "..." directives for referenced vrscene files
FILE_PARAM_RE = re.compile(r'\bfile\s*=\s*"([^"]+)"', re.IGNORECASE)
INCLUDE_RE = re.compile(r'^\s*#include\s+"([^"]+)"', re.MULTILINE)


def find_referenced_files(vrscene_path):
    """Parse a vrscene file and return all referenced file paths."""
    if not os.path.isfile(vrscene_path):
        print(f"Warning: vrscene not found: {vrscene_path}", file=sys.stderr)
        return set(), []

    with open(vrscene_path, "r", errors="replace") as f:
        content = f.read()

    paths = set()
    scene_dir = os.path.dirname(os.path.abspath(vrscene_path))

    for match in FILE_PARAM_RE.findall(content):
        paths.add(match)
    for match in INCLUDE_RE.findall(content):
        paths.add(match)

    resolved = set()
    missing = []
    for p in paths:
        # Skip empty or placeholder paths
        if not p or p.startswith("<") or p.startswith("$"):
            continue
        abs_path = p if os.path.isabs(p) else os.path.join(scene_dir, p)
        abs_path = os.path.normpath(abs_path)
        if os.path.isfile(abs_path):
            resolved.add(abs_path)
        else:
            missing.append(abs_path)

    return resolved, missing


def log(msg):
    print(msg, file=sys.stderr)


def main():
    metadata = json.load(sys.stdin)
    params = metadata.get("parameters", {})
    vrscene_path = params.get("VraySceneFile", "")

    if not vrscene_path:
        log("[VRScene Hook] No VraySceneFile parameter found, skipping.")
        sys.exit(0)

    log(f"[VRScene Hook] Scanning: {vrscene_path}")
    discovered, missing = find_referenced_files(vrscene_path)

    if missing:
        log(f"[VRScene Hook] WARNING - {len(missing)} referenced file(s) not found:")
        for f in sorted(missing):
            log(f"  MISSING: {f}")

    if not discovered:
        log("[VRScene Hook] No additional files to attach.")
        sys.exit(0)

    log(f"[VRScene Hook] Adding {len(discovered)} file(s) to job attachments:")
    for f in sorted(discovered):
        log(f"  + {f}")

    # Merge with existing input files
    existing = metadata.get("assetReferences", {}).get("inputFilenames", [])
    all_files = sorted(set(existing) | discovered)

    print(json.dumps({
        "attachments": {
            "assetReferences": {
                "inputFilenames": all_files
            }
        }
    }))


if __name__ == "__main__":
    main()
