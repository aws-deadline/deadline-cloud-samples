#!/bin/sh
set -xeuo pipefail

VRAY_ROOT="$PREFIX/opt/vray"
mkdir -p $VRAY_ROOT

# Copy Contents
cp "$SRC_DIR/installer/EULA.html" "$VRAY_ROOT/"
cp "$SRC_DIR/installer/GCPP.html" "$VRAY_ROOT/"
cp -R "$SRC_DIR/installer/appsdk" "$VRAY_ROOT/"
cp -R "$SRC_DIR/installer/packages" "$VRAY_ROOT/"
cp -R "$SRC_DIR/installer/sdk" "$VRAY_ROOT/"
cp -R "$SRC_DIR/installer/ui" "$VRAY_ROOT/"
cp -R "$SRC_DIR/installer/vfh_home" "$VRAY_ROOT/"
cp -R "$SRC_DIR/installer/vraysdk" "$VRAY_ROOT/"

# Add rpaths into the Houdini installation in the same environment
for so_file in $(find "$VRAY_ROOT"/vfh_home/dso_py3*/* -iname "*.so"); do
    patchelf --add-rpath "\$ORIGIN/$(realpath -m --relative-to=$(dirname $so_file) $PREFIX)/opt/houdini/dsolib" $so_file
done

# Modify the VRAY package file so that the install root is pointing within the conda environment and
# place within the Houdini search path for package files
mkdir -p "$PREFIX/opt/houdini/packages"
cp "$VRAY_ROOT/packages/vray_for_houdini.json" "$PREFIX/opt/houdini/packages/vray_for_houdini.json"
sed -i "s|REPLACE_WITH_PATH_TO_UNPACKED_ARCHIVE|$VRAY_ROOT|" "$PREFIX/opt/houdini/packages/vray_for_houdini.json"

mkdir -p $PREFIX/etc/conda/activate.d
cat <<EOF > $PREFIX/etc/conda/activate.d/$PKG_NAME-$PKG_VERSION-vars.sh
export VRAY_ROOT="\$CONDA_PREFIX/opt/vray"
export HOUDINI_VRAY_EULA="\$VRAY_ROOT/EULA.html"
export HOUDINI_VRAY_GCPP="\$VRAY_ROOT/GCPP.html"
EOF

mkdir -p $PREFIX/etc/conda/deactivate.d
cat <<EOF > $PREFIX/etc/conda/deactivate.d/$PKG_NAME-$PKG_VERSION-vars.sh
unset VRAY_ROOT
unset HOUDINI_VRAY_EULA
unset HOUDINI_VRAY_GCPP
EOF
