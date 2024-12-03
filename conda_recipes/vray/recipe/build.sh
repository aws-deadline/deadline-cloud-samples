#!/bin/sh
set -xeuo pipefail

# Run the installer extracting to a temporary directory
ls -l $SRC_DIR
chmod u+x $SRC_DIR/vray*
mkdir "$SRC_DIR/extracted"
$SRC_DIR/vray* -unpackInstall $SRC_DIR/extracted

cd $PREFIX

# Copy the vray relocatable (aka portable) installation from the temporary directory to the prefix
mkdir -p "$PREFIX/usr"
VRAY_ROOT="usr/vray-$PKG_VERSION"
cp -r "$SRC_DIR/extracted/" "$PREFIX/$VRAY_ROOT"

# Remove the samples, they're not needed on the farm
rm -rf $PREFIX/$VRAY_ROOT/samples
# Remove the docs, they're not needed on the farm
rm -rf $PREFIX/$VRAY_ROOT/docs

mkdir -p $PREFIX/bin

# Add relative RPATHs for the vray executable and the plugins using patchelf, which is part of
# the conda-build virtual environment. This is so we can follow the recommendation
# of https://docs.conda.io/projects/conda-build/en/latest/resources/use-shared-libraries.html
# to never use LD_LIBRARY_PATH in Conda environments.
VRAY_BIN="$CONDA_PREFIX/$VRAY_ROOT/bin"
PATCHELF=$(dirname $CONDA_EXE)/patchelf
$PATCHELF --add-rpath '$ORIGIN/../lib' "$VRAY_BIN/vray.bin"
$PATCHELF --add-rpath '$ORIGIN/../' "$VRAY_BIN/plugins/libvray_ChaosScatter.so"
$PATCHELF --add-rpath '$ORIGIN/../../lib' "$VRAY_BIN/plugins/libvray_MtlOSL.so"
$PATCHELF --add-rpath '$ORIGIN/../../lib' "$VRAY_BIN/plugins/libvray_mtlx_private.so"

# Create symlinks
# For vray.bin, we symlink it to vray
for BINARY in "$VRAY_BIN"/*.bin; do
    # Skip creating a symlink for vray.bin
    if [[ "$(basename "$BINARY")" == "vray.bin" ]]; then
        ln -s "$BINARY" "$PREFIX/bin/vray"
    else
        ln -r -s "$BINARY" "$PREFIX/bin/$(basename "$BINARY")"
    fi
done

# Install dependencies not available on Deadline Cloud service-managed fleets
mkdir -p $SRC_DIR/download
cd $SRC_DIR/download
dnf download --resolve -y --arch $(uname -m) \
    libglvnd-glx mesa-libGLU pango libXft fontconfig libX11 libXext \
    libXinerama libXxf86vm libSM cairo libxkbcommon libICE libxcb \
    xcb-util-renderutil xcb-util-keysyms xcb-util xcb-util-image xcb-util-wm

for rpm_file in $(realpath $SRC_DIR/download/*.rpm); do
    rpm2cpio "$rpm_file" | cpio -idm
done

# Remove a broken symlink from mesa-libGLU
rm -f ./usr/lib64/libGLX_system.so.0

# Copy .so's to the V-Ray installation
find . -iname "*.so.*" -exec cp -P -r {} "$PREFIX/$VRAY_ROOT/lib/." \;

# Script to set environment variables during activation
mkdir -p $PREFIX/etc/conda/activate.d
cat <<EOF > $PREFIX/etc/conda/activate.d/$PKG_NAME-$PKG_VERSION-vars.sh
export "VRAY=\$CONDA_PREFIX/$VRAY_ROOT"
export "VRAY_EULA=https://docs.chaos.com/display/VNS/End+User+License+Agreement"
EOF

mkdir -p $PREFIX/etc/conda/deactivate.d
cat <<EOF > $PREFIX/etc/conda/deactivate.d/$PKG_NAME-$PKG_VERSION-vars.sh
if ! [ -z \$VRAY ]; then 
    unset VRAY
    unset VRAY_EULA
fi
EOF