#!/bin/env bash
set -xeuo pipefail

# Uses NeRF Studio's gsplat library to train Gaussian splats, outputting a .ply Gaussian Splatting point cloud.

SCRIPT_DIR="$(dirname "$0")"
INPUT_DATA_DIR="$1"
MAX_NUM_ITERATIONS="$2"
OUTPUT_PLY_FILE="$3"
shift 3

# Use ns-process-data to create the images_N directories that simple_trainer.py expects
echo "openjd_status: NeRF Studio: Processing input"
ns-process-data images \
    --data "$INPUT_DATA_DIR/images" \
    --skip-colmap \
    --colmap-model-path "$INPUT_DATA_DIR/sparse" \
    --output-dir .

echo "openjd_status: GSplat simple_trainer.py mcmc: Training model"
gsplat_simple_trainer "$@" \
    --max-steps "$MAX_NUM_ITERATIONS" \
    --disable-viewer \
    --data-dir "$INPUT_DATA_DIR" \
    --result-dir gsplat_workspace \
    --ply-steps "$MAX_NUM_ITERATIONS" \
    --save-ply

python "$SCRIPT_DIR/print_workspace_dir_summary.py" .

# Save the output .ply file
mkdir -p "$(dirname "$OUTPUT_PLY_FILE")"
cp "gsplat_workspace/ply/point_cloud_$((MAX_NUM_ITERATIONS - 1)).ply" "$OUTPUT_PLY_FILE"
