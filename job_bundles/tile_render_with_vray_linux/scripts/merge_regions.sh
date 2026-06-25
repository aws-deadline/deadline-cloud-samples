#!/bin/bash
# Merge region tiles into a complete frame using ImageMagick
set -euo pipefail

# Parse arguments
OUTPUT_DIR="$1"
FILENAME="$2"
FRAME="$3"
COLS="$4"
ROWS="$5"

echo "=== Merge Regions Task ==="
echo "Frame: $FRAME, Grid: ${COLS}x${ROWS}"

BASE="${FILENAME%.*}"
EXT="${FILENAME##*.}"
PADDED_FRAME=$(printf "%04d" $FRAME)

# Check all region files exist (V-Ray names them with .NNNN before extension)
echo "Checking region files..."
MISSING=0
for ((row=0; row<ROWS; row++)); do
  for ((col=0; col<COLS; col++)); do
    F="${OUTPUT_DIR}/${BASE}_f${FRAME}_region_r${row}_c${col}.${PADDED_FRAME}.${EXT}"
    if [ ! -f "$F" ]; then
      echo "ERROR: Missing $F"
      MISSING=$((MISSING+1))
    fi
  done
done

if [ $MISSING -gt 0 ]; then
  echo "ERROR: $MISSING region files missing"
  exit 1
fi

# Merge rows horizontally
echo "Merging rows horizontally..."
for ((row=0; row<ROWS; row++)); do
  ROW_FILES=""
  for ((col=0; col<COLS; col++)); do
    ROW_FILES="$ROW_FILES ${OUTPUT_DIR}/${BASE}_f${FRAME}_region_r${row}_c${col}.${PADDED_FRAME}.${EXT}"
  done
  convert $ROW_FILES +append "${OUTPUT_DIR}/${BASE}_f${FRAME}_row_${row}.${EXT}"
done

# Merge all rows vertically
echo "Merging rows vertically..."
ALL_ROWS=""
for ((row=0; row<ROWS; row++)); do
  ALL_ROWS="$ALL_ROWS ${OUTPUT_DIR}/${BASE}_f${FRAME}_row_${row}.${EXT}"
done

FINAL_OUTPUT="${OUTPUT_DIR}/${BASE}.${PADDED_FRAME}.${EXT}"
convert $ALL_ROWS -append "$FINAL_OUTPUT"

# Cleanup intermediate row files
for ((row=0; row<ROWS; row++)); do
  rm -f "${OUTPUT_DIR}/${BASE}_f${FRAME}_row_${row}.${EXT}"
done

echo "Merged image: $FINAL_OUTPUT"
