#!/bin/bash

# Submits the so100 sim-to-policy pipeline (Datagen -> Train -> Render) to verify
# the job bundle works end-to-end. Download and review the output video + final
# frame to confirm the learned policy executes the pick.

set -euo pipefail

# cd to job_bundles/ so the bundle can be referenced by name.
JOB_BUNDLES_DIR="$(dirname "$(dirname "$(realpath "$0")")")"
cd "$JOB_BUNDLES_DIR"

# The three steps share OutputDir (a job attachment): Datagen writes dataset/,
# Train writes checkpoint/, Render writes the MP4 + PNG. Pass an absolute path
# so outputs upload and download correctly.
OUTPUT_ABS="$(pwd)/so100_datagen_train_render/output"
mkdir -p "$OUTPUT_ABS"

echo y | deadline bundle submit so100_datagen_train_render \
    --name "so100 Sim-to-Policy: Datagen -> Train -> Render" \
    --known-asset-path "$OUTPUT_ABS" \
    -p "OutputDir=$OUTPUT_ABS" \
    "$@"

echo
echo "Submitted. Watch the 3 steps in the Deadline Cloud Monitor, or:"
echo "  deadline job list --page-size 5"
echo "Collect the dataset + checkpoint + video with:"
echo "  deadline job download-output --job-id <job-id>"
