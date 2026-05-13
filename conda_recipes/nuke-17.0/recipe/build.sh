#!/bin/sh
set -xeuo pipefail

mkdir -p $PREFIX/opt
cd $PREFIX/opt

# Install Nuke into $PREFIX/opt
INSTALLER=$SRC_DIR/installer/*.run
env -u SRC_DIR -u PREFIX $INSTALLER --prefix $PREFIX/opt --accept-foundry-eula

NUKE_DIR=$PREFIX/opt/Nuke*
NUKE_BIN=$(basename $NUKE_DIR/Nuke*)
NUKE_VERSION=${NUKE_BIN#Nuke}

# Remove the documentation, it's not needed on the farm
rm -r $NUKE_DIR/Documentation

# Create symlinks
mkdir -p $PREFIX/bin
ln -r -s $NUKE_DIR/$NUKE_BIN $PREFIX/bin/$NUKE_BIN
ln -r -s $NUKE_DIR/$NUKE_BIN $PREFIX/bin/nuke

# Install Nuke dependencies from local package manager
mkdir -p $SRC_DIR/download
cd $SRC_DIR/download
yumdownloader --resolve --destdir=$SRC_DIR/download alsa-lib libglvnd-opengl
for rpm_file in $(realpath $SRC_DIR/download/*.rpm); do
    rpm2cpio "$rpm_file" | cpio -idm
done

# Copy .so's to Nuke installation
for so_file in $(find . -iname "*.so.*"); do
    cp $so_file $NUKE_DIR/.
done

# Script to set environment variables during activation
mkdir -p $PREFIX/etc/conda/activate.d
cat <<EOF > $PREFIX/etc/conda/activate.d/nuke-$NUKE_VERSION-vars.sh
internal_package_add_to_search_path () {
    # Add a path to a new or existing environment variable.
    # For example, we use this to add a plugin path to the NUKE_PATH 
    # Usage: internal_package_add_to_search_path VAR_NAME /seach/path/value
    eval "CURRENT_VALUE=\\\${\$1:-}"
    if [ "\$CURRENT_VALUE" = "" ]; then
        eval "export \"\$1=\\\$2\""
    else
        NEW_VALUE="\$CURRENT_VALUE:\$2"
        eval "export \"\$1=\\\$NEW_VALUE\""
    fi
}

export "NUKE_LOCATION=\$CONDA_PREFIX/opt/$(basename $NUKE_DIR)"
export "NUKE_VERSION=$NUKE_VERSION"
export "NUKE_BINARY_PATH=\$NUKE_LOCATION/bin"
export "NUKE_INCLUDE_PATH=\$NUKE_LOCATION/include"
export "NUKE_LIBRARY_PATH=\$NUKE_LOCATION/lib"
internal_package_add_to_search_path NUKE_PATH "\$NUKE_LOCATION/plugins"

unset -f internal_package_add_to_search_path
EOF

mkdir -p $PREFIX/etc/conda/deactivate.d
cat <<EOF > $PREFIX/etc/conda/deactivate.d/nuke-$NUKE_VERSION-vars.sh
internal_package_remove_from_search_path () {
    # Removes the given path from the given environment variable.
    # For example, we use this to clean up the NUKE_PATH we changed in the activate script.
    # Usage: internal_package_remove_from_search_path VAR_NAME /seach/path/value
    eval "CURRENT_VALUE=\\\$\$1"
    if [ "\$CURRENT_VALUE" = "\$2" ]; then
        eval "unset \$1"
    else
        NEW_VALUE="\$(echo ":\$CURRENT_VALUE:" | sed -e "s|:\$2:|:|")"
        NEW_VALUE="\${NEW_VALUE%:}"
        NEW_VALUE="\${NEW_VALUE#:}"
        eval "export \"\$1=\\\$NEW_VALUE\""
    fi
}

internal_package_remove_from_search_path NUKE_PATH "\$NUKE_LOCATION/plugins"
unset NUKE_LIBRARY_PATH
unset NUKE_INCLUDE_PATH
unset NUKE_BINARY_PATH
unset NUKE_VERSION
unset NUKE_LOCATION

unset -f internal_package_remove_from_search_path
EOF

# --- Simple Plugin Delivery (Option D: per-DCC recipe activate script) ---
# Copies the plugin delivery scripts into the conda activate.d/deactivate.d
# directories. These run AFTER the main nuke env vars are set (zzz- prefix
# ensures lexicographic ordering).

mkdir -p $PREFIX/etc/conda/activate.d
cp $RECIPE_DIR/zzz-nuke-plugin-sync-activate.sh \
   $PREFIX/etc/conda/activate.d/zzz-$PKG_NAME-$PKG_VERSION-plugin-sync.sh

mkdir -p $PREFIX/etc/conda/deactivate.d
cp $RECIPE_DIR/zzz-nuke-plugin-sync-deactivate.sh \
   $PREFIX/etc/conda/deactivate.d/zzz-$PKG_NAME-$PKG_VERSION-plugin-sync.sh
