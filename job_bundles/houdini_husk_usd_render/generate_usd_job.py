""" 
This script uses OpenUSD libraries to introspect a USD stage, determine all external files it depends on,
and generate a Deadline Cloud job bundle that includes references to these assets
After running this script the Deadline Cloud job submission UI will open ready to submit your job
You may override parameters such as frame range, resolution, or renderer before submission

Usage:
pip3 install deadline usd-core
python3 generate_usd_job.py <usd_file_path>

Example:
python3 generate_usd_job.py /path/to/your/usd/file.usda
"""

import json
from pathlib import Path
from pprint import pprint
import shutil
import subprocess
import sys
from pxr import Usd, UsdGeom, UsdUtils
from deadline.client.job_bundle.submission import AssetReferences
from deadline.client.job_bundle import create_job_history_bundle_dir


def find_camera_paths(stage: Usd.Stage):
    camera_paths = []

    for prim in stage.Traverse():
        if prim.IsA(UsdGeom.Camera):
            camera_paths.append(prim.GetPath().pathString)
    return camera_paths


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python script.py <usd_file_path>")
        sys.exit(1)

    usd_file_path = sys.argv[1]

    usd_stage = Usd.Stage.Open(usd_file_path)

    layers, assets, unresolved = UsdUtils.ComputeAllDependencies(usd_file_path)

    paths = [layer.realPath for layer in layers]
    paths = paths + assets

    usd_abs_path = str(Path(usd_file_path).resolve())

    references = AssetReferences(input_filenames=paths)

    print(
        f"WARNING: {len(unresolved)} paths were not resolved. Your render may not complete successfully:"
    )
    pprint(unresolved)

    parameter_values = [{"name": "USDSceneFile", "value": usd_abs_path}]

    cameras = find_camera_paths(usd_stage)
    if not cameras:
        print(
            "WARNING: No cameras found in USD stage. This scene won't render. Please add a camera and try again"
        )
        sys.exit()

    job_name = f"HuskUSDRender-{usd_file_path}"
    job_bundle_dir = Path(create_job_history_bundle_dir("HuskUSDRender", job_name[:20]))
    print(f"Creating Job Bundle Directory: {job_bundle_dir}")

    # Write out the asset_references and parameter values to this new bundle dir
    # and copy the template as-is
    with open(Path.joinpath(job_bundle_dir, "asset_references.json"), "w") as f:
        json.dump(references.to_dict(), f, indent=1)

    with open(Path.joinpath(job_bundle_dir, "parameter_values.json"), "w") as f:
        json.dump({"parameterValues": parameter_values}, f, indent=1)

    shutil.copyfile(
        Path.joinpath(Path(__file__).parents[0], "template.yaml"),
        Path.joinpath(job_bundle_dir, "template.yaml"),
    )

    # Now pop up the deadline gui submitter for the customer to do the actual submission
    subprocess.run(["deadline", "bundle", "gui-submit", job_bundle_dir])
