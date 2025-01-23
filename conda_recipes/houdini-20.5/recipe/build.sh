#!/bin/sh
set -xeuo pipefail

mkdir -p $PREFIX/opt
cd $PREFIX/opt


# The Houdini installer expects `bc` to run, but does not fail when
# it is missing. Ensure that it is installed before running the installer
bc --help
# Example messages:

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
# The Houdini version without the build number
HOUDINI_VERSION=${PKG_VERSION%.*}

# Remove the documentation, it's not needed on the farm
rm -r $HOUDINI_DIR/houdini/help

# Create symlinks
mkdir -p $PREFIX/bin
for BINARY in houdini houdini-bin houdinicore houdinifx \
    hscript hython hbatch karma karma_cc mantra mantra-bin \
    vmantra vmantra-bin; do
ln -r -s $HOUDINI_DIR/bin/$BINARY $PREFIX/bin/$BINARY
done

# Install Houdini dependencies from local package manager
mkdir -p $SRC_DIR/download
cd $SRC_DIR/download
dnf download --resolve -y alsa-lib fontconfig libXScrnSaver libX* libGL libXcomposite libxkbcommon

# Install python deadline package
pip install deadline-cloud-for-houdini


for rpm_file in $(realpath $SRC_DIR/download/*.rpm); do
    rpm2cpio "$rpm_file" | cpio -idm
done

# Copy .so's to Houdini installation
for so_file in $(find . -iname "*.so.*"); do
    cp $so_file $HOUDINI_DIR/dsolib/.
done

# Script to set environment variables during activation
mkdir -p $PREFIX/etc/conda/activate.d
cat <<EOF > $PREFIX/etc/conda/activate.d/houdini-$PKG_VERSION-vars.sh
export "HOUDINI_LOCATION=\$CONDA_PREFIX/opt/houdini"
export "HOUDINI_VERSION=$HOUDINI_VERSION"
export "HOUDINI_BINARY_PATH=\$HOUDINI_LOCATION/bin"
export "HOUDINI_HOUDINI_PATH=\$HOUDINI_LOCATION/houdini"
export "HOUDINI_INCLUDE_PATH=\$HOUDINI_LOCATION/toolkit/include"
export "HOUDINI_LIBRARY_PATH=\$HOUDINI_LOCATION/bin"
export "HB=\$HOUDINI_LOCATION/dsolib"
export "LD_LIBRARY_PATH=\$HOUDINI_LOCATION/dsolib"
export "SESI_LMHOST=localhost"

EOF

mkdir -p $PREFIX/etc/conda/deactivate.d
cat <<EOF > $PREFIX/etc/conda/deactivate.d/houdini-$PKG_VERSION-vars.sh
unset HOUDINI_LIBRARY_PATH
unset HOUDINI_INCLUDE_PATH
unset HOUDINI_HOUDINI_PATH
unset HOUDINI_BINARY_PATH
unset HOUDINI_VERSION
unset HOUDINI_LOCATION
unset LD_LIBRARY_PATH
unset HB
unset SESI_LMHOST

EOF
