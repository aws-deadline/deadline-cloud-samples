#!/usr/bin/env python3
"""
Pre-submission hook that discovers USD file dependencies and adds them
as input file attachments automatically.

Requires: pip install usd-core
"""

import json
import sys

from pxr import Usd, UsdGeom, UsdUtils


def main():
    metadata = json.load(sys.stdin)
    usd_file = metadata.get("parameters", {}).get("USDSceneFile")

    if not usd_file:
        print(
            "No USDSceneFile parameter found, skipping dependency discovery",
            file=sys.stderr,
        )
        sys.exit(0)

    # Discover all dependencies
    layers, assets, unresolved = UsdUtils.ComputeAllDependencies(usd_file)
    input_files = [layer.realPath for layer in layers] + assets

    if unresolved:
        print(f"WARNING: {len(unresolved)} unresolved paths:", file=sys.stderr)
        for p in unresolved:
            print(f"  {p}", file=sys.stderr)

    # Check for cameras
    stage = Usd.Stage.Open(usd_file)
    cameras = [
        p.GetPath().pathString for p in stage.Traverse() if p.IsA(UsdGeom.Camera)
    ]
    if not cameras:
        print(
            "WARNING: No cameras found in USD stage. The scene may not render.",
            file=sys.stderr,
        )

    # Output discovered files as additional input attachments
    if input_files:
        print(f"Discovered {len(input_files)} dependency file(s)", file=sys.stderr)
        output = {"attachments": {"assetReferences": {"inputFilenames": input_files}}}
        print(json.dumps(output))


if __name__ == "__main__":
    main()
