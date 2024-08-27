#!/bin/sh
set -xeuo pipefail

# Copy the Blender installation into the prefix
mkdir -p $PREFIX/opt
cp -r $SRC_DIR/blender $PREFIX/opt/

# The version without the build number
BLENDER_VERSION=${PKG_VERSION%.*}

# See https://docs.conda.io/projects/conda/en/latest/dev-guide/deep-dives/activation.html
# for details on activation. The Deadline Cloud sample queue environments use bash
# to activate environments on Windows, so we recommend always producing both .bat and .sh files.

mkdir -p $PREFIX/etc/conda/activate.d
mkdir -p $PREFIX/etc/conda/deactivate.d

cat <<EOF > "$PREFIX/etc/conda/activate.d/$PKG_NAME-$PKG_VERSION-vars.bat"
export "BLENDER_LOCATION=$PREFIX/opt/blender"
export "BLENDER_VERSION=$BLENDER_VERSION"
export "BLENDER_LIBRARY_PATH=%BLENDER_LOCATION%/lib"
export "BLENDER_SCRIPTS_PATH=%BLENDER_LOCATION%/%BLENDER_VERSION%/scripts"
export "BLENDER_PYTHON_PATH=%BLENDER_LOCATION%/%BLENDER_VERSION%/python"
export "BLENDER_DATAFILES_PATH=%BLENDER_LOCATION%/%BLENDER_VERSION%/datafiles"
set "PATH=$PREFIX/opt/blender;%PATH%"
EOF
cat "$PREFIX/etc/conda/activate.d/$PKG_NAME-$PKG_VERSION-vars.bat"

cat <<EOF > $PREFIX/etc/conda/activate.d/$PKG_NAME-$PKG_VERSION-vars.sh
export "BLENDER_LOCATION=\$CONDA_PREFIX/opt/blender"
export "BLENDER_VERSION=$BLENDER_VERSION"
export "BLENDER_LIBRARY_PATH=\$BLENDER_LOCATION/lib"
export "BLENDER_SCRIPTS_PATH=\$BLENDER_LOCATION/\$BLENDER_VERSION/scripts"
export "BLENDER_PYTHON_PATH=\$BLENDER_LOCATION/\$BLENDER_VERSION/python"
export "BLENDER_DATAFILES_PATH=\$BLENDER_LOCATION/\$BLENDER_VERSION/datafiles"
export PATH="\$(cygpath '$PREFIX/opt/blender'):\$PATH"
EOF
cat $PREFIX/etc/conda/activate.d/$PKG_NAME-$PKG_VERSION-vars.sh

cat <<EOF > "$PREFIX/etc/conda/deactivate.d/$PKG_NAME-$PKG_VERSION-vars.bat"
set "PATH=%PATH:$PREFIX/opt/blender;=%"
set BLENDER_DATAFILES_PATH=
set BLENDER_PYTHON_PATH=
set BLENDER_SCRIPTS_PATH=
set BLENDER_LIBRARY_PATH=
set BLENDER_VERSION=
set BLENDER_LOCATION=
EOF
cat "$PREFIX/etc/conda/deactivate.d/$PKG_NAME-$PKG_VERSION-vars.bat"

cat <<EOF > $PREFIX/etc/conda/deactivate.d/$PKG_NAME-$PKG_VERSION-vars.sh
export PATH="\${PATH/\$(cygpath '$PREFIX/opt/blender'):/}"
unset BLENDER_DATAFILES_PATH
unset BLENDER_PYTHON_PATH
unset BLENDER_SCRIPTS_PATH
unset BLENDER_LIBRARY_PATH
unset BLENDER_VERSION
unset BLENDER_LOCATION
EOF
cat $PREFIX/etc/conda/deactivate.d/$PKG_NAME-$PKG_VERSION-vars.sh
