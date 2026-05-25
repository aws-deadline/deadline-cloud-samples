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
# directories. These run AFTER env_vars.d JSON is applied (zzz- prefix
# ensures lexicographic ordering).
#
# The activate script invokes plugin_sync_bootstrap.py via
# `blender -b --python`. We ship the bootstrap script under
# $PREFIX/share/blender-plugin-sync/ so it can be edited and unit-tested
# as a standalone Python file rather than a heredoc inside a shell script.
#
# See zzz-blender-plugin-sync-activate.sh for the full implementation.

mkdir -p $PREFIX/etc/conda/activate.d
cp $RECIPE_DIR/zzz-blender-plugin-sync-activate.sh \
   $PREFIX/etc/conda/activate.d/zzz-$PKG_NAME-$PKG_VERSION-plugin-sync.sh

mkdir -p $PREFIX/etc/conda/deactivate.d
cp $RECIPE_DIR/zzz-blender-plugin-sync-deactivate.sh \
   $PREFIX/etc/conda/deactivate.d/zzz-$PKG_NAME-$PKG_VERSION-plugin-sync.sh

mkdir -p $PREFIX/share/blender-plugin-sync
cp $RECIPE_DIR/plugin_sync_bootstrap.py \
   $PREFIX/share/blender-plugin-sync/plugin_sync_bootstrap.py
