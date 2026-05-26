#!/bin/sh
set -xeuo pipefail

# Get the version number without the update
MAYA_VERSION=${PKG_VERSION%.*}

# This is where to install MtoA within the installation prefix
MTOA_ROOT="usr/autodesk/maya-mtoa-$MAYA_VERSION"

# Change the current directory to the installation prefix
mkdir -p "$PREFIX/$MTOA_ROOT"
cd "$PREFIX/$MTOA_ROOT"

# Extract the MtoA package file into the installation prefix
unzip "$SRC_DIR/installer/Packages/package.zip"

# Remove the licensing installers, they're not needed on the farm
rm -r $PREFIX/$MTOA_ROOT/license/installer
# Remove the docs, they're not needed on the farm
rm -r $PREFIX/$MTOA_ROOT/docs

# Add a relative RPATH from MtoA into Maya using patchelf, which is part of
# the conda-build virtual environment. This is so we can follow the recommendation
# of https://docs.conda.io/projects/conda-build/en/latest/resources/use-shared-libraries.html
# to never use LD_LIBRARY_PATH in Conda environments.
patchelf --add-rpath '$ORIGIN/../../maya2026/lib' $PREFIX/$MTOA_ROOT/bin/libai_renderview.so

# Add RPATH for libraries in $MTOA_ROOT/procedurals to $MAYA_LOCATION/plug-ins/xgen/lib for libAdskSeExpr.so
for file in "$PREFIX/$MTOA_ROOT/procedurals"/*.so; do
    patchelf --set-rpath '$ORIGIN/../../maya2026/plug-ins/xgen/lib' "$file"
done

# Create symlinks for utilities allowing them to be run directly from the command line
mkdir -p $PREFIX/bin
ln -r -s $PREFIX/$MTOA_ROOT/bin/kick $PREFIX/bin/kick
ln -r -s $PREFIX/$MTOA_ROOT/bin/oslc $PREFIX/bin/oslc
ln -r -s $PREFIX/$MTOA_ROOT/bin/oslinfo $PREFIX/bin/oslinfo
ln -r -s $PREFIX/$MTOA_ROOT/bin/maketx $PREFIX/bin/maketx
ln -r -s $PREFIX/$MTOA_ROOT/bin/maketx $PREFIX/bin/noice

# Create the mtoa.mod file so Maya loads the plugin.
#
# The maya package has set the Maya module path to include virtual environment-equivalents of
# the system module paths, so this is the usual installation location after the virtual environment
# prefix.
mkdir -p "$PREFIX/usr/autodesk/modules/maya/$MAYA_VERSION"
cat <<EOF > "$PREFIX/usr/autodesk/modules/maya/$MAYA_VERSION/mtoa.mod"
+ mtoa any $PREFIX/$MTOA_ROOT
MAYA_CUSTOM_TEMPLATE_PATH +:= scripts/mtoa/ui/templates
MAYA_SCRIPT_PATH +:= scripts/mtoa/mel
MAYA_RENDER_DESC_PATH += $PREFIX/$MTOA_ROOT
MAYA_PXR_PLUGINPATH_NAME += $PREFIX/$MTOA_ROOT/usd
ARNOLD_PLUGIN_PATH += $PREFIX/$MTOA_ROOT/shaders
EOF
