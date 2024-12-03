#!/bin/sh
set -xeuo pipefail

# Get the version number without the update
MAYA_VERSION=${PKG_VERSION%.*}

# This is where to install MtoA within the installation prefix
MTOA_ROOT="usr/autodesk/arnold/maya$MAYA_VERSION"

# Change the current directory to the installation prefix
mkdir -p "$PREFIX/$MTOA_ROOT"
cd "$PREFIX/$MTOA_ROOT"

# Extract the MtoA package file into the installation prefix
unzip "$SRC_DIR/installer/Packages/package.zip"

# Create the mtoa.mod file so Maya loads the plugin.
#
# The maya package has set the Maya module path to include virtual environment-equivalents of
# the system module paths, so this is the usual installation location after the virtual environment
# prefix.
mkdir -p "$PREFIX/usr/autodesk/modules/maya/$MAYA_VERSION"
cat <<EOF > "$PREFIX/usr/autodesk/modules/maya/$MAYA_VERSION/mtoa.mod"
+ mtoa any $PREFIX/$MTOA_ROOT
PATH +:= bin
MAYA_CUSTOM_TEMPLATE_PATH +:= scripts/mtoa/ui/templates
MAYA_SCRIPT_PATH +:= scripts/mtoa/mel
MAYA_RENDER_DESC_PATH += $PREFIX/$MTOA_ROOT
MAYA_PXR_PLUGINPATH_NAME += $PREFIX/$MTOA_ROOT/usd
EOF

# Make symlinks to the MtoA commands from the Maya installation
mkdir -p "$PREFIX/bin"
for BINARY in kick maketx noice oslc oslinfo; do
    chmod u+x "$PREFIX/$MTOA_ROOT/bin/$BINARY"
    ln -r -s "$PREFIX/$MTOA_ROOT/bin/$BINARY" "$MAYA_LOCATION/bin/$BINARY"
done
