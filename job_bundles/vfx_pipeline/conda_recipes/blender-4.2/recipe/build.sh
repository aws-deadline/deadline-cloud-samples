#!/bin/sh
set -xeuo pipefail

# Drop the Blender tree into the prefix and put `blender` on PATH. That is all
# the pipeline needs — the render scripts invoke `blender` and nothing else.
mkdir -p "$PREFIX/opt"
cp -r "$SRC_DIR/blender" "$PREFIX/opt/"

mkdir -p "$PREFIX/bin"
ln -r -s "$PREFIX/opt/blender/blender" "$PREFIX/bin/blender"
