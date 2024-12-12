#!/bin/sh
set -xeuo pipefail

MAYA_VERSION=2025

# Run the installer extracting to a temporary directory
ls -l $SRC_DIR
chmod u+x $SRC_DIR/vray*
mkdir "$SRC_DIR/extracted"
$SRC_DIR/vray* -unpackInstall $SRC_DIR/extracted

cd $PREFIX

# Copy the vray relocatable (aka portable) installation from the temporary directory to the prefix
mkdir -p "$PREFIX/usr/autodesk"
MAYA_VRAY_ROOT="usr/autodesk/maya-vray-$MAYA_VERSION"
MAYA_VRAY_MODULE_PATH="$MAYA_VRAY_ROOT/maya_root/modules"
MAYA_VRAY_VRAY_ROOT="$MAYA_VRAY_ROOT/vray"
MAYA_VRAY_MAYA_ROOT="$MAYA_VRAY_ROOT/maya_vray"
cp -r "$SRC_DIR/extracted/" "$PREFIX/$MAYA_VRAY_ROOT"

# Remove the samples, they're not needed on the farm
rm -rf $PREFIX/$MAYA_VRAY_VRAY_ROOT/samples
# Remove the docs, they're not needed on the farm
rm -rf $PREFIX/$MAYA_VRAY_VRAY_ROOT/docs

# Create symlinks
mkdir -p $PREFIX/bin
ln -r -s $PREFIX/$MAYA_VRAY_MAYA_ROOT/bin/vray $PREFIX/bin/vray
ln -r -s $PREFIX/$MAYA_VRAY_VRAY_ROOT/bin/bump2gloss $PREFIX/bin/bump2gloss
ln -r -s $PREFIX/$MAYA_VRAY_VRAY_ROOT/bin/imapviewer $PREFIX/bin/imapviewer
ln -r -s $PREFIX/$MAYA_VRAY_VRAY_ROOT/bin/img2tiledexr $PREFIX/bin/img2tiledexr
ln -r -s $PREFIX/$MAYA_VRAY_VRAY_ROOT/bin/ply2vrmesh $PREFIX/bin/ply2vrmesh
ln -r -s $PREFIX/$MAYA_VRAY_VRAY_ROOT/bin/vdenoise $PREFIX/bin/vdenoise
ln -r -s $PREFIX/$MAYA_VRAY_VRAY_ROOT/bin/vraydr_check $PREFIX/bin/vraydr_check
ln -r -s $PREFIX/$MAYA_VRAY_VRAY_ROOT/bin/vrimg2exr $PREFIX/bin/vrimg2exr
ln -r -s $PREFIX/$MAYA_VRAY_VRAY_ROOT/bin/vrmesh_viewer $PREFIX/bin/vrmesh_viewer
ln -r -s $PREFIX/$MAYA_VRAY_VRAY_ROOT/bin/vrstconvert $PREFIX/bin/vrstconvert

# Install dependencies not available on Deadline Cloud service-managed fleets
mkdir -p $SRC_DIR/download
cd $SRC_DIR/download
dnf download --resolve -y xcb-util-image xcb-util-renderutil

for rpm_file in $(realpath $SRC_DIR/download/*.rpm); do
    rpm2cpio "$rpm_file" | cpio -idm
done

# Copy .so's to the V-Ray installation
find . -iname "*.so.*" -exec cp -P -r {} "$PREFIX/$MAYA_VRAY_VRAY_ROOT/lib/." \;

mkdir -p "$PREFIX/usr/autodesk/modules/maya/$MAYA_VERSION"
cp $CONDA_PREFIX/$MAYA_VRAY_ROOT/maya_root/modules/VRayForMaya.module $CONDA_PREFIX/usr/autodesk/modules/maya/$MAYA_VERSION
sed -i "s|+ VRayForMaya2025rhel8 0.9 ../../maya_vray|+ VRayForMaya2025rhel8 0.9 $CONDA_PREFIX/$MAYA_VRAY_MAYA_ROOT|" $CONDA_PREFIX/usr/autodesk/modules/maya/$MAYA_VERSION/VRayForMaya.module
if grep -q "$CONDA_PREFIX/$MAYA_VRAY_MAYA_ROOT" "$CONDA_PREFIX/usr/autodesk/modules/maya/$MAYA_VERSION/VRayForMaya.module"; then
    echo "Changing maya_root/VRayForMaya.module file path to $CONDA_PREFIX/$MAYA_VRAY_MAYA_ROOT succeeded"
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