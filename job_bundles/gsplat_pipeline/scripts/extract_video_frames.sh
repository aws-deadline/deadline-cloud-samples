#!/bin/env bash
set -xeuo pipefail

# Uses FFmpeg to extract every nth frame from the input video to get approximately the desired image count.

SCRIPT_DIR="$(dirname "$0")"
INPUT_VIDEO_FILE="$1"
APPROX_IMAGE_COUNT="$2"
IMAGE_DOWNSCALE_FACTOR="$3"
OUTPUT_IMAGES_DIR="$4"

# Get an estimate of the frame count in the video
FRAME_COUNT=$(ffprobe "$INPUT_VIDEO_FILE" \
                -v error \
                -of json \
                -show_entries stream=width,height,nb_frames | \
                    jq -r '(.streams | map(select(.width != null)))[0].nb_frames')

# Divide the frame count by the approximate desired image count to get every nth frame we want from the video
EVERY_NTH=$(python -c "print(max(1, int($FRAME_COUNT/$APPROX_IMAGE_COUNT + 0.5)))")

IMAGE_BASE=$(basename "$INPUT_VIDEO_FILE")
IMAGE_BASE=${IMAGE_BASE%.*}

echo "openjd_status: FFmpeg: Extracting 1 in every $EVERY_NTH frames from the input video $(basename "$INPUT_VIDEO_FILE")"
mkdir -p "$OUTPUT_IMAGES_DIR"
ffmpeg -i "$INPUT_VIDEO_FILE" \
    -vf "select=not(mod(n\\,$EVERY_NTH)),scale=iw/$IMAGE_DOWNSCALE_FACTOR:-1" \
    -vsync vfr \
    -q:v 2 \
    "$OUTPUT_IMAGES_DIR/${IMAGE_BASE}_%04d.jpg"

python "$SCRIPT_DIR/print_workspace_dir_summary.py" .