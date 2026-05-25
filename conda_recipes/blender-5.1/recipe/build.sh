#!/bin/sh
set -xeuo pipefail

# Copy the Blender installation into the prefix
mkdir -p $PREFIX/opt
cp -r $SRC_DIR/blender $PREFIX/opt/

# The version without the build number
BLENDER_VERSION=${PKG_VERSION%.*}

# Create symlinks to the Blender commands
mkdir -p $PREFIX/bin
for BINARY in blender blender-launcher blender-softwaregl blender-thumbnailer; do
    ln -r -s $PREFIX/opt/blender/$BINARY $PREFIX/bin/$BINARY
done

# Set environment variables using the JSON env_vars.d mechanism.
# See https://rattler-build.prefix.dev/latest/special_files/ for details.
# This is more portable than activation scripts and works with pixi trampolines.
mkdir -p $PREFIX/etc/conda/env_vars.d
cat > $PREFIX/etc/conda/env_vars.d/$PKG_NAME-$PKG_VERSION.json << VAREOF
{
  "BLENDER_LOCATION": "$PREFIX/opt/blender",
  "BLENDER_VERSION": "$BLENDER_VERSION",
  "BLENDER_LIBRARY_PATH": "$PREFIX/opt/blender/lib",
  "BLENDER_SCRIPTS_PATH": "$PREFIX/opt/blender/$BLENDER_VERSION/scripts",
  "BLENDER_PYTHON_PATH": "$PREFIX/opt/blender/$BLENDER_VERSION/python",
  "BLENDER_DATAFILES_PATH": "$PREFIX/opt/blender/$BLENDER_VERSION/datafiles"
}
VAREOF

# --- Plugin Sync ---
# Copies the plugin delivery scripts into the conda activate.d/deactivate.d
# directories. These run AFTER the main blender env vars are set (zzz- prefix
# ensures lexicographic ordering).
#
# See zzz-blender-plugins-activate.sh for the full implementation.

mkdir -p $PREFIX/etc/conda/activate.d
cp $RECIPE_DIR/zzz-blender-plugins-activate.sh \
   $PREFIX/etc/conda/activate.d/zzz-$PKG_NAME-$PKG_VERSION-plugins.sh

mkdir -p $PREFIX/etc/conda/deactivate.d
cp $RECIPE_DIR/zzz-blender-plugins-deactivate.sh \
   $PREFIX/etc/conda/deactivate.d/zzz-$PKG_NAME-$PKG_VERSION-plugins.sh