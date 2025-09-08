#!/bin/env bash
set -xeuo pipefail

# Uses COLMAP and GLOMAP to solve Structure-from-Motion for images extracted from a video,
# and saves a pinhole model with undistorted images.

SCRIPT_DIR="$(dirname "$0")"
INPUT_IMAGES_DIR="$1"
SFM_WORKSPACE="$2"
OUTPUT_MODEL_DIR="$3"
OUTPUT_UNDISTORTED_IMAGES_DIR="$4"

mkdir -p "$SFM_WORKSPACE"

echo "openjd_status: COLMAP: Extracting features from images"
colmap feature_extractor \
    --ImageReader.single_camera 1 \
    --image_path "$INPUT_IMAGES_DIR" \
    --database_path "$SFM_WORKSPACE"/database.db

echo "openjd_status: COLMAP: Matching image pairs"
colmap sequential_matcher \
    --database_path "$SFM_WORKSPACE/database.db"

echo "openjd_status: GLOMAP: Solving SfM"
mkdir -p "$SFM_WORKSPACE"/sparse
glomap mapper \
    --database_path "$SFM_WORKSPACE"/database.db \
    --image_path "$INPUT_IMAGES_DIR" \
    --output_path "$SFM_WORKSPACE"/sparse

echo "openjd_status: COLMAP: Undistorting images"
UNDISTORT_DIR="$SFM_WORKSPACE"/image_undistorter
mkdir -p "$UNDISTORT_DIR"
colmap image_undistorter \
    --image_path "$INPUT_IMAGES_DIR" \
    --input_path "$SFM_WORKSPACE"/sparse/0 \
    --output_path "$UNDISTORT_DIR" \
    --output_type COLMAP

# Move the pinhole model and undistorted images to the output directories
mkdir -p "$OUTPUT_MODEL_DIR"
mv "$UNDISTORT_DIR"/sparse/* "$OUTPUT_MODEL_DIR"
mkdir -p "$OUTPUT_UNDISTORTED_IMAGES_DIR"
mv "$UNDISTORT_DIR"/images/* "$OUTPUT_UNDISTORTED_IMAGES_DIR"

# Clean up remaining data from the undistortion dir
rm -r "$UNDISTORT_DIR"

python "$SCRIPT_DIR/print_workspace_dir_summary.py" .
