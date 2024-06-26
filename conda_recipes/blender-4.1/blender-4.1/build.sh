#!/bin/sh
set -xeuo pipefail

mkdir -p $PREFIX/opt
cp -r $SRC_DIR/blender $PREFIX/opt/

# The version without the build number
BLENDER_VERSION=${PKG_VERSION%.*}

# Create symlinks
mkdir -p $PREFIX/bin
for BINARY in blender blender-softwaregl blender-thumbnailer; do
    ln -r -s $PREFIX/opt/blender/$BINARY $PREFIX/bin/$BINARY
done

# Script to set environment variables during activation
mkdir -p $PREFIX/etc/conda/activate.d
cat <<EOF > $PREFIX/etc/conda/activate.d/$PKG_NAME-$PKG_VERSION-vars.sh
export "BLENDER_LOCATION=\$CONDA_PREFIX/opt/blender"
export "BLENDER_VERSION=$BLENDER_VERSION"
export "BLENDER_LIBRARY_PATH=\$BLENDER_LOCATION/lib"
export "BLENDER_SCRIPTS_PATH=\$BLENDER_LOCATION/scripts"
export "BLENDER_PYTHON_PATH=\$BLENDER_LOCATION/python"
export "BLENDER_DATAFILES_PATH=\$BLENDER_LOCATION/datafiles"
EOF

mkdir -p $PREFIX/etc/conda/deactivate.d
cat <<EOF > $PREFIX/etc/conda/deactivate.d/$PKG_NAME-$PKG_VERSION-vars.sh
unset BLENDER_DATAFILES_PATH
unset BLENDER_PYTHON_PATH
unset BLENDER_SCRIPTS_PATH
unset BLENDER_LIBRARY_PATH
unset BLENDER_VERSION
unset BLENDER_LOCATION
EOF
