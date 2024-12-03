#!/bin/sh
set -xeuo pipefail

# The location within $PREFIX where AE will be installed
mkdir -p $PREFIX/opt
cp -r $SRC_DIR/aftereffects $PREFIX/opt/

# The version without the update number
AE_VERSION=${PKG_VERSION%.*}

# See https://docs.conda.io/projects/conda/en/latest/dev-guide/deep-dives/activation.html
# for details on activation. The Deadline Cloud sample queue environments use bash
# to activate environments on Windows, so we recommend always producing both .bat and .sh files.

mkdir -p "$PREFIX/etc/conda/activate.d"
mkdir -p "$PREFIX/etc/conda/deactivate.d"

cat <<EOF > "$PREFIX/etc/conda/activate.d/$PKG_NAME-$PKG_VERSION-vars.bat"
set "AE_LOCATION=$PREFIX/opt/aftereffects"
set "AE_VERSION=$AE_VERSION"
set "PATH=$PREFIX/opt/aftereffects;%PATH%"
EOF
cat "$PREFIX/etc/conda/activate.d/$PKG_NAME-$PKG_VERSION-vars.bat"

cat <<EOF > $PREFIX/etc/conda/activate.d/$PKG_NAME-$PKG_VERSION-vars.sh
export "AE_VERSION=$AE_VERSION"
export "AE_LOCATION=\$CONDA_PREFIX/opt/aftereffects"
export PATH="\$(cygpath '$PREFIX/opt/aftereffects'):\$PATH"
EOF
cat $PREFIX/etc/conda/activate.d/$PKG_NAME-$PKG_VERSION-vars.sh


cat <<EOF > "$PREFIX/etc/conda/deactivate.d/$PKG_NAME-$PKG_VERSION-vars.bat"
set "PATH=%PATH:$PREFIX/opt/aftereffects;=%"
set AE_VERSION=
set AE_LOCATION=
EOF
cat "$PREFIX/etc/conda/deactivate.d/$PKG_NAME-$PKG_VERSION-vars.bat"

cat <<EOF > $PREFIX/etc/conda/deactivate.d/$PKG_NAME-$PKG_VERSION-vars.sh
export PATH="\${PATH/\$(cygpath '$PREFIX/opt/aftereffects'):/}"
unset AE_VERSION
unset AE_LOCATION
EOF
cat $PREFIX/etc/conda/deactivate.d/$PKG_NAME-$PKG_VERSION-vars.sh