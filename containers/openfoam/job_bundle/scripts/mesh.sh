#!/usr/bin/env bash
# Clone an OpenFOAM tutorial case and run blockMesh on it.
# Usage: mesh.sh TUTORIAL BASE_CASE
set -euo pipefail

: "${FOAM_TUTORIALS:?OpenFOAM is not loaded. Build the image with BASH_ENV pointing at its bashrc}"
tutorial="$FOAM_TUTORIALS/$1"
base=$2

if [ ! -d "$tutorial" ]; then
    echo "no tutorial case at $tutorial" >&2
    exit 1
fi

rm -rf "$base"
foamCloneCase "$tutorial" "$base"
cd "$base"
if ! blockMesh > log.blockMesh 2>&1; then
    echo "blockMesh failed:" >&2
    tail -40 log.blockMesh >&2
    exit 1
fi
echo "meshed $base"
grep -E '^ *n(Points|Cells|Faces):' log.blockMesh
