#!/bin/sh
set -xeuo pipefail

# The location within $PREFIX where AE will be installed
mkdir -p $PREFIX
cp -r $SRC_DIR/aftereffects $PREFIX

# The version without the update number
AE_VERSION=${PKG_VERSION%.*}
# The Plugin Sync S3 folder name, such as 25.1
AE_PLUGIN_SYNC_VERSION=$PKG_VERSION

# See https://docs.conda.io/projects/conda/en/latest/dev-guide/deep-dives/activation.html
# for details on activation. The Deadline Cloud sample queue environments use bash
# to activate environments on Windows, so we recommend always producing both .bat and .sh files.

mkdir -p "$PREFIX/etc/conda/activate.d"
mkdir -p "$PREFIX/etc/conda/deactivate.d"

cat <<EOF > "$PREFIX/etc/conda/activate.d/$PKG_NAME-$PKG_VERSION-vars.bat"
set "AE_LOCATION=$PREFIX/aftereffects"
set "AE_VERSION=$AE_VERSION"
set "AE_PLUGIN_SYNC_VERSION=$AE_PLUGIN_SYNC_VERSION"
set "PATH=$PREFIX/aftereffects;%PATH%"
EOF
cat "$PREFIX/etc/conda/activate.d/$PKG_NAME-$PKG_VERSION-vars.bat"

cat <<EOF > $PREFIX/etc/conda/activate.d/$PKG_NAME-$PKG_VERSION-vars.sh
export "AE_VERSION=$AE_VERSION"
export "AE_PLUGIN_SYNC_VERSION=$AE_PLUGIN_SYNC_VERSION"
export "AE_LOCATION=\$CONDA_PREFIX/aftereffects"
export PATH="\$(cygpath '$PREFIX/aftereffects'):\$PATH"
EOF
cat $PREFIX/etc/conda/activate.d/$PKG_NAME-$PKG_VERSION-vars.sh


cat <<EOF > "$PREFIX/etc/conda/deactivate.d/$PKG_NAME-$PKG_VERSION-vars.bat"
set "PATH=%PATH:$PREFIX/aftereffects;=%"
set AE_VERSION=
set AE_PLUGIN_SYNC_VERSION=
set AE_LOCATION=
EOF
cat "$PREFIX/etc/conda/deactivate.d/$PKG_NAME-$PKG_VERSION-vars.bat"

cat <<EOF > $PREFIX/etc/conda/deactivate.d/$PKG_NAME-$PKG_VERSION-vars.sh
export PATH="\${PATH/\$(cygpath '$PREFIX/aftereffects'):/}"
unset AE_VERSION
unset AE_PLUGIN_SYNC_VERSION
unset AE_LOCATION
EOF
cat $PREFIX/etc/conda/deactivate.d/$PKG_NAME-$PKG_VERSION-vars.sh

# Install Plugin Sync hooks after the standard After Effects environment hooks.
# Deadline Cloud queue environments activate Conda with bash, so only .sh hooks are provided.
cp "$RECIPE_DIR/zzz-aftereffects-plugin-sync-activate.sh" \
    "$PREFIX/etc/conda/activate.d/zzz-$PKG_NAME-$PKG_VERSION-plugin-sync.sh"
cp "$RECIPE_DIR/zzz-aftereffects-plugin-sync-deactivate.sh" \
    "$PREFIX/etc/conda/deactivate.d/zzz-$PKG_NAME-$PKG_VERSION-plugin-sync.sh"