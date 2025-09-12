#!/bin/sh
set -xeuo pipefail


INSTALL_DIR="$PREFIX/flipfluids"
mkdir -p $INSTALL_DIR

mv $SRC_DIR/flipfluids/* $INSTALL_DIR

# If your plugin needs extra dependencies, download them here and move them into 
# the Blender install in the appropriate location. 
#
# For example, you can download python modules with dnf download. In the activate script,
# you'll want to move the modules into Blender's python. Remove those dependencies in the 
# deactivate script.

mkdir -p $PREFIX/etc/conda/activate.d
mkdir -p $PREFIX/etc/conda/deactivate.d

# This python script installs the addon, enables it and saves the user preferences.
cat <<EOF > "$INSTALL_DIR/install_addon.py"
import bpy

print("Installing Addon")
bpy.ops.preferences.addon_install(enable_on_install=True, filepath=r"$INSTALL_DIR/FLIP_Fluids_addon_${PKG_VERSION}_demo_.2025-07-17.zip")
print("Saving Preferences")
bpy.ops.wm.save_userpref()
print("Complete")
EOF

# This python script uninstalls the addon and saves the user preferences.
cat <<EOF > "$INSTALL_DIR/uninstall_addon.py"
import bpy

print("Uninstalling Addon")
bpy.ops.preferences.addon_remove(module="FLIP Fluids")
print("Saving Preferences")
bpy.ops.wm.save_userpref()
print("Complete")
EOF


# When activating the environment, we run the addon install script.
cat <<EOF > "$PREFIX/etc/conda/activate.d/$PKG_NAME-$PKG_VERSION-vars.sh"
echo "Adding preferences..."
"\$BLENDER_LOCATION/blender" --background --python "$INSTALL_DIR/install_addon.py"
EOF

# When deactivating the environment, we run the uninstall script.
cat <<EOF > "$PREFIX/etc/conda/deactivate.d/$PKG_NAME-$PKG_VERSION-vars.sh"
echo "Adding preferences..."
"\$BLENDER_LOCATION/blender" --background --python "$INSTALL_DIR/uninstall_addon.py"
EOF

