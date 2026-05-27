#!/bin/bash
# Render a single region tile using V-Ray
set -euo pipefail

# Parse arguments
SETUP_PATH_MAPPING_SCRIPT="$1"
SCENE_FILE="$2"
OUTPUT_DIR="$3"
FILENAME="$4"
PATH_MAPPING_FILE="$5"
FRAME="$6"
REGION_COL="$7"
REGION_ROW="$8"
COLS="$9"
ROWS="${10}"
IMG_WIDTH="${11}"
IMG_HEIGHT="${12}"

echo "=== Render Region Task ==="
echo "Frame: $FRAME, RegionCol: $REGION_COL, RegionRow: $REGION_ROW"
echo "Scene: $SCENE_FILE"

# Convert 1-based to 0-based indices
COL=$((REGION_COL - 1))
ROW=$((REGION_ROW - 1))

# Calculate region boundaries
REGION_WIDTH=$((IMG_WIDTH / COLS))
REGION_HEIGHT=$((IMG_HEIGHT / ROWS))
LEFT=$((COL * REGION_WIDTH))
TOP=$((ROW * REGION_HEIGHT))
RIGHT=$(( COL == COLS - 1 ? IMG_WIDTH : (COL + 1) * REGION_WIDTH ))
BOTTOM=$(( ROW == ROWS - 1 ? IMG_HEIGHT : (ROW + 1) * REGION_HEIGHT ))

echo "Region (col=$COL, row=$ROW): [$LEFT,$TOP,$RIGHT,$BOTTOM]"

# Prepare output filename - V-Ray appends frame number as .NNNN before extension
BASE="${FILENAME%.*}"
EXT="${FILENAME##*.}"
PADDED_FRAME=$(printf "%04d" $FRAME)
OUT_FILE="${OUTPUT_DIR}/${BASE}_f${FRAME}_region_r${ROW}_c${COL}.${PADDED_FRAME}.${EXT}"
echo "Output: $OUT_FILE"

# Enable case-sensitive path remapping
export VRAY_PATH_REMAPPING_CASE_SENSITIVE=1

# Change to scene directory for relative path resolution
SCENE_DIR=$(dirname "$SCENE_FILE")
if [ -d "$SCENE_DIR" ]; then
  echo "Changing to scene directory: $SCENE_DIR"
  cd "$SCENE_DIR"
else
  echo "Warning: Scene directory does not exist: $SCENE_DIR"
fi

# Setup path mapping
echo "Setting up path mapping..."
python3 "$SETUP_PATH_MAPPING_SCRIPT" "$PATH_MAPPING_FILE"

# Build V-Ray command
VRAY_CMD="vray -sceneFile='${SCENE_FILE}' -imgFile='${OUT_FILE}' -display=0 -imgWidth=$IMG_WIDTH -imgHeight=$IMG_HEIGHT -frames=$FRAME -crop='$LEFT;$TOP;$RIGHT;$BOTTOM'"

# Add path remapping if available
if [ -f /tmp/vray_remap_paths.txt ]; then
  REMAP_PATHS=$(cat /tmp/vray_remap_paths.txt)
  if [ -n "$REMAP_PATHS" ]; then
    VRAY_CMD="$VRAY_CMD $REMAP_PATHS"
  fi
fi

echo "Running V-Ray..."
eval $VRAY_CMD

echo "Render complete: $OUT_FILE"
