#!/bin/sh
set -xeuo pipefail

INSTALL_DIR="$PREFIX/blender-plugins"
mkdir -p "$INSTALL_DIR"

# All the addons are moved into the $INSTALL_DIR
mv $SRC_DIR/plugins/* "$INSTALL_DIR"

# If any of your addons need addition dependencies, add installation commands here.

mkdir -p $PREFIX/etc/conda/activate.d
mkdir -p $PREFIX/etc/conda/deactivate.d

# This python script installs all zip addons, enables them and saves the user preferences.
cat <<EOF > "$INSTALL_DIR/install_addons.py"
import bpy
import os
import glob

plugin_dir = r"$INSTALL_DIR"
zip_files = glob.glob(os.path.join(plugin_dir, "*.zip"))

print(f"Installing {len(zip_files)} addons")
for zip_file in zip_files:
    print(f"Installing addon: {zip_file}")
    bpy.ops.preferences.addon_install(enable_on_install=True, filepath=zip_file)

print("Saving Preferences")
bpy.ops.wm.save_userpref()
print("Complete")
EOF

# This python script uninstalls all addons and saves the user preferences.
cat <<EOF > "$INSTALL_DIR/uninstall_addons.py"
import bpy
import os
import glob
import zipfile

plugin_dir = r"$INSTALL_DIR"
zip_files = glob.glob(os.path.join(plugin_dir, "*.zip"))

print(f"Uninstalling {len(zip_files)} addons")
for zip_file in zip_files:
    # Extract addon name from zip file to remove it
    with zipfile.ZipFile(zip_file, 'r') as z:
        for name in z.namelist():
            if name.endswith('__init__.py'):
                addon_name = name.split('/')[0]
                print(f"Uninstalling addon: {addon_name}")
                try:
                    bpy.ops.preferences.addon_remove(module=addon_name)
                except:
                    print(f"Failed to remove addon: {addon_name}")

print("Saving Preferences")
bpy.ops.wm.save_userpref()
print("Complete")
EOF

# When activating the environment, we run the addon install script.
cat <<EOF > "$PREFIX/etc/conda/activate.d/$PKG_NAME-$PKG_VERSION-vars.sh"
echo "Installing Blender plugins..."
"\$BLENDER_LOCATION/blender" --background --python "$INSTALL_DIR/install_addons.py"
EOF

# When deactivating the environment, we run the uninstall script.
cat <<EOF > "$PREFIX/etc/conda/deactivate.d/$PKG_NAME-$PKG_VERSION-vars.sh"
echo "Uninstalling Blender plugins..."
"\$BLENDER_LOCATION/blender" --background --python "$INSTALL_DIR/uninstall_addons.py"
EOF