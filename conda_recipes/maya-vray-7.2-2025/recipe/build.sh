#!/bin/sh
set -xeuo pipefail

MAYA_VERSION=2025

# Where we will install V-Ray for Maya
MAYA_VRAY_ROOT="$PREFIX/opt/chaos/maya-vray-$MAYA_VERSION"
MAYA_VRAY_VRAY_ROOT="$MAYA_VRAY_ROOT/vray"
MAYA_VRAY_MAYA_ROOT="$MAYA_VRAY_ROOT/maya_vray"
mkdir -p $MAYA_VRAY_ROOT
cd $MAYA_VRAY_ROOT

# Run the installer to extract the files
chmod u+x $SRC_DIR/vray*
$SRC_DIR/vray* -unpackInstall .

# Remove the samples, they're not needed on the farm
rm -rf "$MAYA_VRAY_VRAY_ROOT/samples"
# Remove the docs, they're not needed on the farm
rm -rf "$MAYA_VRAY_VRAY_ROOT/docs"

# Add relative RPATHs for the vray executable and the plugins using patchelf. This is so we can
# follow the recommendation of https://docs.conda.io/projects/conda-build/en/latest/resources/use-shared-libraries.html
# to never use LD_LIBRARY_PATH in Conda environments.
for FILE in "$MAYA_VRAY_MAYA_ROOT"/lib/*.so; do
    patchelf --add-rpath '$ORIGIN/.' "$FILE"
done
for FILE in "$MAYA_VRAY_VRAY_ROOT"/lib/*.so.*; do
    patchelf --add-rpath '$ORIGIN/.:$ORIGIN/../../lib/aux' "$FILE"
done

patchelf --add-rpath '$ORIGIN/../../vray/lib' $MAYA_VRAY_MAYA_ROOT/plug-ins/vrayformaya.so

# Install dependencies not available on Deadline Cloud service-managed fleets
mkdir -p $SRC_DIR/download
cd $SRC_DIR/download
dnf download --resolve -y xcb-util-image xcb-util-renderutil xcb-util-cursor \
    xcb-util-wm xcb-util-keysyms libxkbcommon-x11 xcb-util

for rpm_file in $(realpath $SRC_DIR/download/*.rpm); do
    rpm2cpio "$rpm_file" | cpio -idm
done

# Copy .so's to the V-Ray installation. We place these in a separate auxiliary directory so they're clearly
# separated from what came with V-Ray.
mkdir -p "$MAYA_VRAY_ROOT/lib/aux"
find . -iname "*.so.*" -exec cp -P -r {} "$MAYA_VRAY_ROOT/lib/aux/" \;

for FILE in "$MAYA_VRAY_ROOT"/lib/aux/*.so.*; do
    patchelf --add-rpath '$ORIGIN/.' "$FILE"
done

mkdir -p "$PREFIX/usr/autodesk/modules/maya/$MAYA_VERSION"
cp $MAYA_VRAY_ROOT/maya_root/modules/VRayForMaya.module $PREFIX/usr/autodesk/modules/maya/$MAYA_VERSION
sed -i "s|+ VRayForMaya2025rhel8 0.9 ../../maya_vray|+ VRayForMaya2025rhel8 0.9 $MAYA_VRAY_MAYA_ROOT|" $PREFIX/usr/autodesk/modules/maya/$MAYA_VERSION/VRayForMaya.module
if grep -q "$MAYA_VRAY_MAYA_ROOT" "$PREFIX/usr/autodesk/modules/maya/$MAYA_VERSION/VRayForMaya.module"; then
    echo "Changing maya_root/VRayForMaya.module file path to $MAYA_VRAY_MAYA_ROOT succeeded"
else
    echo "Failed to change maya_root/VRayForMaya.module file path "
    exit 1
fi

# Script to set environment variables during activation
mkdir -p $PREFIX/etc/conda/activate.d
cat <<EOF > $PREFIX/etc/conda/activate.d/$PKG_NAME-$PKG_VERSION-vars.sh
export "VRAY_EULA=https://docs.chaos.com/display/VNS/End+User+License+Agreement"
EOF

mkdir -p $PREFIX/etc/conda/deactivate.d
cat <<EOF > $PREFIX/etc/conda/deactivate.d/$PKG_NAME-$PKG_VERSION-vars.sh
if ! [ -z \$VRAY ]; then 
    unset VRAY_EULA
fi
EOF