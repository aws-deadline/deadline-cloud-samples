#!/bin/sh
set -xeuo pipefail

# Copy the Blender installation into the prefix
mkdir -p $PREFIX/opt
cp -r $SRC_DIR/blender $PREFIX/opt/

# The version without the build number
BLENDER_VERSION=${PKG_VERSION%.*}

# Set environment variables using the JSON env_vars.d mechanism.
# See https://rattler-build.prefix.dev/latest/special_files/ for details.
# This is more portable than activation scripts and works with pixi trampolines.
mkdir -p $PREFIX/etc/conda/env_vars.d
cat > $PREFIX/etc/conda/env_vars.d/$PKG_NAME-$PKG_VERSION.json << EOF
{
  "BLENDER_LOCATION": "$PREFIX/opt/blender",
  "BLENDER_VERSION": "$BLENDER_VERSION",
  "BLENDER_LIBRARY_PATH": "$PREFIX/opt/blender/lib",
  "BLENDER_SCRIPTS_PATH": "$PREFIX/opt/blender/$BLENDER_VERSION/scripts",
  "BLENDER_PYTHON_PATH": "$PREFIX/opt/blender/$BLENDER_VERSION/python",
  "BLENDER_DATAFILES_PATH": "$PREFIX/opt/blender/$BLENDER_VERSION/datafiles"
}
EOF
cat $PREFIX/etc/conda/env_vars.d/$PKG_NAME-$PKG_VERSION.json

# Add blender to PATH via activation scripts.
# The Deadline Cloud sample queue environments use bash to activate environments
# on Windows, so we produce both .bat and .sh files.
mkdir -p $PREFIX/etc/conda/activate.d
mkdir -p $PREFIX/etc/conda/deactivate.d

cat <<EOF > "$PREFIX/etc/conda/activate.d/$PKG_NAME-$PKG_VERSION-vars.bat"
set "PATH=$PREFIX/opt/blender;%PATH%"
EOF
cat "$PREFIX/etc/conda/activate.d/$PKG_NAME-$PKG_VERSION-vars.bat"

cat <<EOF > $PREFIX/etc/conda/activate.d/$PKG_NAME-$PKG_VERSION-vars.sh
export PATH="\$(cygpath '$PREFIX/opt/blender'):\$PATH"
EOF
cat $PREFIX/etc/conda/activate.d/$PKG_NAME-$PKG_VERSION-vars.sh

cat <<EOF > "$PREFIX/etc/conda/deactivate.d/$PKG_NAME-$PKG_VERSION-vars.bat"
set "PATH=%PATH:$PREFIX/opt/blender;=%"
EOF
cat "$PREFIX/etc/conda/deactivate.d/$PKG_NAME-$PKG_VERSION-vars.bat"

cat <<EOF > $PREFIX/etc/conda/deactivate.d/$PKG_NAME-$PKG_VERSION-vars.sh
export PATH="\${PATH/\$(cygpath '$PREFIX/opt/blender'):/}"
EOF
cat $PREFIX/etc/conda/deactivate.d/$PKG_NAME-$PKG_VERSION-vars.sh
