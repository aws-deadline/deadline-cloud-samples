#!/bin/sh
set -xeuo pipefail

mkdir -p $PREFIX/opt
cd $PREFIX/opt


# The Houdini installer expects `bc` to run, but does not fail when
# it is missing. Ensure that it is installed before running the installer
bc --help

# Install Houdini
INSTALLER=$SRC_DIR/installer/houdini.install
# date of the EULA agreement, not the current date
EULAdate=2021-10-13
$INSTALLER \
    --auto-install \
    --accept-EULA $EULAdate \
    --no-install-engine-maya \
    --no-install-engine-unity \
    --no-install-menus \
    --no-install-bin-symlink \
    --no-install-hfs-symlink \
    --no-install-license \
    --no-install-hqueue-server \
    --no-root-check \
    --make-dir $PREFIX/opt/houdini

HOUDINI_DIR=$PREFIX/opt/houdini

# Remove the documentation, it's not needed on the farm
rm -r $HOUDINI_DIR/houdini/help
# Remove the toolkit samples, they're not needed on the farm
rm -r $HOUDINI_DIR/toolkit/samples

# Create symlinks
mkdir -p $PREFIX/bin
for BINARY in houdini houdini-bin houdinicore houdinifx \
    hscript husk hython hbatch karma karma_cc mantra mantra-bin \
    vmantra vmantra-bin; do
ln -r -s $HOUDINI_DIR/bin/$BINARY $PREFIX/bin/$BINARY
done

# Install Houdini dependencies from local package manager
mkdir -p $SRC_DIR/download
cd $SRC_DIR/download
dnf download --resolve -y alsa-lib fontconfig libXScrnSaver


for rpm_file in $(realpath $SRC_DIR/download/*.rpm); do
    rpm2cpio "$rpm_file" | cpio -idm
done

# Add $ORIGIN as a RPATH to any .so's and copy into Houdini's installation
for so_file in $(find . -iname "*.so.*"); do
    patchelf --add-rpath '$ORIGIN' $so_file
    cp $so_file $HOUDINI_DIR/dsolib/.
done

# Script to set environment variables during activation
mkdir -p $PREFIX/etc/conda/activate.d
cat <<EOF > $PREFIX/etc/conda/activate.d/houdini-$PKG_VERSION-vars.sh
export "HOUDINI_LOCATION=\$CONDA_PREFIX/opt/houdini"
export "HOUDINI_VERSION=$PKG_VERSION"
export "HOUDINI_BINARY_PATH=\$HOUDINI_LOCATION/bin"
export "HOUDINI_HOUDINI_PATH=\$HOUDINI_LOCATION/houdini"
export "HOUDINI_INCLUDE_PATH=\$HOUDINI_LOCATION/toolkit/include"
export "HOUDINI_LIBRARY_PATH=\$HOUDINI_LOCATION/bin"

EOF

mkdir -p $PREFIX/etc/conda/deactivate.d
cat <<EOF > $PREFIX/etc/conda/deactivate.d/houdini-$PKG_VERSION-vars.sh
unset HOUDINI_LIBRARY_PATH
unset HOUDINI_INCLUDE_PATH
unset HOUDINI_HOUDINI_PATH
unset HOUDINI_BINARY_PATH
unset HOUDINI_VERSION
unset HOUDINI_LOCATION

EOF