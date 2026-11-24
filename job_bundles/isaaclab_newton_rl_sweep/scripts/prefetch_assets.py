"""Download the USD dependency closure a task needs, before the simulator asks for it.

Isaac Lab normally fetches assets on demand through ``omni.client``, which this sample does
not install (see ``omni_client_shim.py``). Its asset root is a plain HTTPS S3 URL, declared
in Isaac Lab's own ``apps/isaaclab.python.kit`` as
``persistent.isaac.asset_root.default``, so ordinary HTTP gets the same files with no extra
dependency.

The closure is computed, not listed. ``cartpole.usd`` is a USD *crate* file referencing
``./Props/instanceable_meshes.usd``, which ``grep`` and ``strings`` cannot read reliably.
This script opens each layer with ``pxr.Sdf`` and follows sublayers, references, payloads,
and asset-valued attributes transitively.

``.mdl`` references are reported and skipped. MDL modules such as ``OmniPBR.mdl`` ship inside
Omniverse Kit, which is absent here, and they are only evaluated by a renderer. A headless
run with no camera sensors never evaluates them.

Usage:
    python prefetch_assets.py --output-dir <dir> [--asset-root URL] [SEED ...]

Exits non-zero if any seed or discovered dependency cannot be downloaded, so a missing asset
fails the job at a readable point rather than deep inside scene construction.
"""

import argparse
import os
import posixpath
import sys
import urllib.error
import urllib.request

# Matches Isaac Lab 3.0's apps/isaaclab.python.kit. Override with --asset-root when pointing at
# a mirror or a newer asset release.
DEFAULT_ASSET_ROOT = "https://omniverse-content-production.s3-us-west-2.amazonaws.com/Assets/Isaac/6.2"

# Dependency seeds for the sample's default task, Isaac-Cartpole-Direct. Isaac Lab resolves
# these from ISAACLAB_NUCLEUS_DIR, which is "<asset root>/Isaac/IsaacLab". Another task needs
# its own seeds: run it once, read the path from the FileNotFoundError, and add it here.
DEFAULT_SEEDS = [
    "Isaac/IsaacLab/Environments/Grid/default_ground_plane_checker_v1/default_ground_plane.usda",
    "Isaac/IsaacLab/Robots/Classic/Cartpole/cartpole.usd",
]

USD_SUFFIXES = (".usd", ".usda", ".usdc", ".usdz")


def _download(asset_root, relative_path, output_dir):
    """Fetch one file, preserving its path under output_dir. Returns the local path."""
    destination = os.path.join(output_dir, relative_path)
    if os.path.exists(destination):
        return destination
    os.makedirs(os.path.dirname(destination), exist_ok=True)
    url = "{}/{}".format(asset_root, relative_path)
    try:
        urllib.request.urlretrieve(url, destination)
    except (urllib.error.URLError, urllib.error.HTTPError, OSError) as exc:
        # urlretrieve can leave a truncated file behind, which a later run would treat as
        # already downloaded.
        if os.path.exists(destination):
            os.remove(destination)
        raise RuntimeError("could not download {}: {}".format(url, exc)) from exc
    return destination


def _references(local_path):
    """Return every relative asset path a USD layer refers to.

    Covers sublayers, references, payloads, and asset-valued attributes, which is what USD
    composition can pull in. Absolute and remote paths are dropped: they are not ours to
    mirror.
    """
    from pxr import Sdf

    layer = Sdf.Layer.FindOrOpen(local_path)
    if layer is None:
        return []

    found = set(layer.subLayerPaths)

    def visit(spec):
        for _, attribute in getattr(spec, "attributes", {}).items():
            value = attribute.default
            if isinstance(value, Sdf.AssetPath) and value.path:
                found.add(value.path)
        reference_list = getattr(spec, "referenceList", None)
        if reference_list is not None:
            for reference in reference_list.GetAddedOrExplicitItems():
                if reference.assetPath:
                    found.add(reference.assetPath)
        payload_list = getattr(spec, "payloadList", None)
        if payload_list is not None:
            for payload in payload_list.GetAddedOrExplicitItems():
                if payload.assetPath:
                    found.add(payload.assetPath)
        for child in getattr(spec, "nameChildren", {}).values():
            visit(child)

    visit(layer.pseudoRoot)
    return [
        reference
        for reference in found
        if reference
        and not reference.startswith(("http://", "https://", "omniverse://", "/"))
    ]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", required=True, help="Local asset root to populate.")
    parser.add_argument("--asset-root", default=DEFAULT_ASSET_ROOT, help="Remote asset root URL.")
    parser.add_argument(
        "seeds",
        nargs="*",
        default=None,
        help="Asset paths relative to the asset root. Defaults to the Isaac-Cartpole-Direct set.",
    )
    args = parser.parse_args()

    asset_root = args.asset_root.rstrip("/")
    seeds = args.seeds or DEFAULT_SEEDS

    pending = list(seeds)
    fetched = {}
    skipped_mdl = set()

    while pending:
        relative_path = posixpath.normpath(pending.pop(0))
        if relative_path in fetched:
            continue
        try:
            local_path = _download(asset_root, relative_path, args.output_dir)
        except RuntimeError as exc:
            # Report the URL and stop. The usual cause is a seed path that does not exist at
            # this asset release.
            print("ERROR: {}".format(exc), file=sys.stderr)
            return 1
        fetched[relative_path] = os.path.getsize(local_path)

        if not relative_path.lower().endswith(USD_SUFFIXES):
            continue
        for reference in _references(local_path):
            if reference.lower().endswith(".mdl"):
                # Ships inside Omniverse Kit and is evaluated only by a renderer.
                skipped_mdl.add(reference)
                continue
            dependency = posixpath.normpath(
                posixpath.join(posixpath.dirname(relative_path), reference)
            )
            if dependency not in fetched:
                pending.append(dependency)

    total = 0
    for relative_path in sorted(fetched):
        print("  {:>9,}  {}".format(fetched[relative_path], relative_path))
        total += fetched[relative_path]
    print("{} files, {:,} bytes into {}".format(len(fetched), total, args.output_dir))

    if skipped_mdl:
        print("skipped (Kit-internal MDL, render-time only): {}".format(", ".join(sorted(skipped_mdl))))

    if not fetched:
        print("ERROR: nothing was downloaded; check --asset-root and the seed paths", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
