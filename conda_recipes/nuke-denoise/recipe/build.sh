#!/bin/sh
set -xeuo pipefail

OFX_PLUGIN_PATH=$PREFIX/OFX/Plugins
mkdir -p $OFX_PLUGIN_PATH

INSTALLER=$SRC_DIR/installer/*
cp -r $INSTALLER $OFX_PLUGIN_PATH

# When creating your own conda package, a common issue you may run into with
# your package is that it will be unable to find libraries when you go to run the application.
# Likely, that's caused by the Deadline Cloud service-managed fleet instances
# not having the libraries installed. To fix this, you will need to install them
# in this script, like this.
mkdir -p $SRC_DIR/download
cd $SRC_DIR/download
dnf download --resolve -y libXft 

for rpm_file in $(realpath $SRC_DIR/download/*.rpm); do
    rpm2cpio "$rpm_file" | cpio -idm
done

# On Linux, OFX files are distributed as dynamic shared objects. 
# Here we're adding $ORIGIN to the RPATH so that the OFX files can find
# libraries in the same directory as itself.
for FILE in $(find "$PREFIX/OFX/" -iname "*.ofx"); do 
    patchelf --set-rpath '$ORIGIN' "$FILE"
done

# Copy .so's to all Denoise bundles
for so_file in $(find . -iname "*.so.*"); do
    patchelf --set-rpath '$ORIGIN' "$so_file"
    for bundle in $(find $OFX_PLUGIN_PATH -iname "*.ofx.bundle"); do
        # Learn more about the structure of OpenFX Plugins by
        # going to the OpenFX Plugin packaging reference.
        # https://openfx.readthedocs.io/en/main/Reference/ofxPackaging.html 
        cp -P $so_file $bundle/Contents/Linux-x86-64/
    done
done

# Script to set environment variables during activation
mkdir -p "$PREFIX/etc/conda/activate.d"
cat <<EOF > "$PREFIX/etc/conda/activate.d/$PKG_NAME-$PKG_VERSION-vars.sh"
export OFX_PLUGIN_PATH="\$CONDA_PREFIX/OFX/Plugins/"
EOF


mkdir -p "$PREFIX/etc/conda/deactivate.d"
cat <<EOF > "$PREFIX/etc/conda/deactivate.d/$PKG_NAME-$PKG_VERSION-vars.sh"
unset OFX_PLUGIN_PATH
EOF
