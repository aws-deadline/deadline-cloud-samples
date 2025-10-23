#!/bin/sh
set -xeuo pipefail

ADDON_ZIP="FLIP_Fluids_addon_${PKG_VERSION}_demo_.2025-07-17.zip"

INSTALL_DIR="$PREFIX/opt/blender-flipfluids"
mkdir -p $INSTALL_DIR

mv $SRC_DIR/$ADDON_ZIP $INSTALL_DIR

# If your plugin needs extra dependencies, download them here and move them into
# the Blender install in the appropriate location.
#
# For example, you can download python modules with dnf download. In the activate script,
# you'll want to move the modules into Blender's python. Remove those dependencies in the
# deactivate script.

mkdir -p $PREFIX/etc/conda/activate.d
mkdir -p $PREFIX/etc/conda/deactivate.d

# These python scripts install/uninstall the addon to be enabled in Blender
cp "$RECIPE_DIR/install_addon.py" "$INSTALL_DIR"
cp "$RECIPE_DIR/uninstall_addon.py" "$INSTALL_DIR"

# When activating the environment, we run the addon install script.
cat <<EOF > "$PREFIX/etc/conda/activate.d/$PKG_NAME-$PKG_VERSION-vars.sh"
echo "Installing FLIP Fluids addon into Blender..."
PYTHONUNBUFFERED=1 blender --background --python "$INSTALL_DIR/install_addon.py" -- "$INSTALL_DIR/$ADDON_ZIP"
EOF

# When deactivating the environment, we run the uninstall script.
cat <<EOF > "$PREFIX/etc/conda/deactivate.d/$PKG_NAME-$PKG_VERSION-vars.sh"
echo "Uninstalling FLIP Fluids addon from Blender..."
PYTHONUNBUFFERED=1 blender --background --python "$INSTALL_DIR/uninstall_addon.py" -- "FLIP Fluids"
EOF

