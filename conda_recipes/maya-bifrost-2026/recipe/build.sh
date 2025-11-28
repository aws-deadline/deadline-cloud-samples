#!/bin/sh
set -xeuo pipefail

# Get the version number without the update
MAYA_VERSION=${PKG_VERSION%.*}

# This is where to install Bifrost within the installation prefix
BIFROST_ROOT="usr/autodesk/maya-bifrost-$MAYA_VERSION"

# Change the current directory to the installation prefix
mkdir -p "$PREFIX/$BIFROST_ROOT"
cd "$PREFIX/$BIFROST_ROOT"

chmod u+x $SRC_DIR/installer/*.run
$SRC_DIR/installer/*.run --noexec --keep --nox11 --target "$SRC_DIR/extracted" --phase2

# Extract the Bifrost package file into the installation prefix
cd $PREFIX
rpm2cpio $(realpath $SRC_DIR/extracted/*.rpm) | cpio -idm

mv $PREFIX/usr/autodesk/bifrost/maya2026/2.14.1.0 $PREFIX/$BIFROST_ROOT/2.14.1.0

# Create symlinks for utilities allowing them to be run directly from the command line
mkdir -p $PREFIX/bin
ln -r -s $PREFIX/$BIFROST_ROOT/2.14.1.0/bin/bifcmd $PREFIX/bin/bifcmd
ln -r -s $PREFIX/$BIFROST_ROOT/2.14.1.0/bin/bifinfo $PREFIX/bin/bifinfo
ln -r -s $PREFIX/$BIFROST_ROOT/2.14.1.0/bin/bifup $PREFIX/bin/bifup

# Create the bifrost.mod file so Maya loads the plugin.
#
# The maya package has set the Maya module path to include virtual environment-equivalents of
# the system module paths, so this is the usual installation location after the virtual environment
# prefix.
mkdir -p "$PREFIX/usr/autodesk/modules/maya/2026"
cat <<EOF > "$PREFIX/usr/autodesk/modules/maya/2026/bifrost.mod"
+ bifrostPacks 2.14.1.0 $PREFIX/$BIFROST_ROOT/2.14.1.0/bifrost
plug-ins: null

+ PLATFORM:linux LOCALE:en_US Bifrost 2.14.1.0 $PREFIX/$BIFROST_ROOT/2.14.1.0/bifrost
BIFROST_LOCATION:=
[r] scripts: scripts
MAYA_CONTENT_PATH+:=examples/Bifrost_Fluids
MAYA_MODULE_UI_WORKSPACE_PATH+:=resources/workspaces
MAYA_TOOLCLIPS_PATH+:=resources/toolclips
BIFROST_LIB_CONFIG_FILES*:=packs/packs_plugin_config.json
BIFROST_LIB_CONFIG_FILES*:=resources/plugin_config.json
PYTHONPATH+:=python/site-packages
EOF