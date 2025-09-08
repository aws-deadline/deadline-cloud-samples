#!/bin/sh
set -xeuo pipefail

# Where we will install V-Ray
VRAY_ROOT="opt/vray-$PKG_VERSION"
VRAY_INSTALL_DIR="$PREFIX/$VRAY_ROOT"
mkdir -p "$VRAY_INSTALL_DIR"
cd "$VRAY_INSTALL_DIR"

# Run the installer to extract the files
chmod u+x $SRC_DIR/vray*
$SRC_DIR/vray* -unpackInstall .

# Remove the samples, they're not needed on the farm
rm -rf "$VRAY_INSTALL_DIR/samples"
# Remove the docs, they're not needed on the farm
rm -rf "$VRAY_INSTALL_DIR/docs"

# Add relative RPATHs for the vray executable and the plugins using patchelf. This is so we can
# follow the recommendation of https://docs.conda.io/projects/conda-build/en/latest/resources/use-shared-libraries.html
# to never use LD_LIBRARY_PATH in Conda environments.
for FILE in "$VRAY_INSTALL_DIR"/bin/*.bin "$VRAY_INSTALL_DIR"/bin/*.so; do
    patchelf --add-rpath '$ORIGIN/.:$ORIGIN/../lib:$ORIGIN/../lib/aux' "$FILE"
done
for FILE in "$VRAY_INSTALL_DIR"/bin/plugins/*.so; do
    patchelf --add-rpath '$ORIGIN/.:$ORIGIN/../../bin:$ORIGIN/../../lib:$ORIGIN/../../lib/aux' "$FILE"
done

# Create symlinks from the environment's bin folder
mkdir -p "$PREFIX/bin"
for BINARY in "$VRAY_INSTALL_DIR/bin"/*.bin; do
    # Provide symlinks both with and without the '.bin' extension
    FILENAME="$(basename "$BINARY")"
    FILENAME_WITHOUT_EXT="${FILENAME%.*}"
    ln -r -s "$BINARY" "$PREFIX/bin/$FILENAME"
    ln -r -s "$BINARY" "$PREFIX/bin/$FILENAME_WITHOUT_EXT"
done

# Install dependencies not available on Deadline Cloud service-managed fleets
mkdir -p "$SRC_DIR/download"
cd "$SRC_DIR/download"
dnf download --resolve -y --arch $(uname -m) \
    libglvnd-glx mesa-libGLU pango libXft fontconfig libX11 libXext \
    libXinerama libXxf86vm libSM cairo libxkbcommon libICE libxcb \
    xcb-util-renderutil xcb-util-keysyms xcb-util xcb-util-image xcb-util-wm

for rpm_file in "$SRC_DIR"/download/*.rpm; do
    rpm2cpio "$rpm_file" | cpio -idm
done

# Remove a broken symlink from mesa-libGLU
rm -f ./usr/lib64/libGLX_system.so.0

# Copy .so's to the V-Ray installation. We place these in a separate auxiliary directory so they're clearly
# separated from what came with V-Ray.
mkdir -p "$VRAY_INSTALL_DIR/lib/aux"
find . -iname "*.so.*" -exec cp -P -r {} "$VRAY_INSTALL_DIR/lib/aux/" \;

# Script to set environment variables during activation
mkdir -p "$PREFIX/etc/conda/activate.d"
cat <<EOF > "$PREFIX/etc/conda/activate.d/$PKG_NAME-$PKG_VERSION-vars.sh"
export "VRAY=\$CONDA_PREFIX/$VRAY_ROOT"
export "VRAY_EULA=https://docs.chaos.com/display/VNS/End+User+License+Agreement"
EOF
cat "$PREFIX/etc/conda/activate.d/$PKG_NAME-$PKG_VERSION-vars.sh"

mkdir -p "$PREFIX/etc/conda/deactivate.d"
cat <<EOF > "$PREFIX/etc/conda/deactivate.d/$PKG_NAME-$PKG_VERSION-vars.sh"
unset VRAY
unset VRAY_EULA
EOF
cat "$PREFIX/etc/conda/deactivate.d/$PKG_NAME-$PKG_VERSION-vars.sh"