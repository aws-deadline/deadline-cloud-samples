#!/bin/sh
set -xeuo pipefail

# Install the add-on where Blender looks for user add-ons: <scripts>/addons/.
SCRIPTS_DIR="$PREFIX/share/blender/scripts"
ADDON_DIR="$SCRIPTS_DIR/addons/moonrise_scatter"
mkdir -p "$ADDON_DIR"
cp -r "$SRC_DIR/moonrise_scatter/." "$ADDON_DIR/"

# Point Blender at that scripts dir on activation. BLENDER_USER_SCRIPTS makes the
# add-on discoverable so the render script can just call
# bpy.ops.preferences.addon_enable(module="moonrise_scatter") — no per-run
# install. Uses rattler-build's JSON env_vars.d mechanism (portable, works with
# conda activation and pixi trampolines), same as the Blender recipe.
mkdir -p "$PREFIX/etc/conda/env_vars.d"
cat > "$PREFIX/etc/conda/env_vars.d/$PKG_NAME-$PKG_VERSION.json" << EOF
{
  "BLENDER_USER_SCRIPTS": "$SCRIPTS_DIR"
}
EOF
