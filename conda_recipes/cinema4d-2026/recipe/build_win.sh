# Fail the script if any commands it runs fail
set -euo pipefail

# C4D_VERSION remains major.minor for compatibility with the OpenJD adaptor.
CINEMA_4D_VERSION=${PKG_VERSION%.*}
CINEMA_4D_PLUGIN_SYNC_VERSION=$CINEMA_4D_VERSION

# The conda-build environment is configured for packaging one PyPI package into one conda package.
# Turn off the following defaults for the pip install below.
unset PIP_NO_DEPENDENCIES
unset PIP_IGNORE_INSTALLED
unset PIP_NO_INDEX

# Move all files into the prefix. cmd handles Windows permissions and locking
# more reliably than the POSIX compatibility layer.
cmd <<EOF
move $SRC_DIR\\cinema4d $PREFIX\\
EOF

# The cinema4d-openjd command currently requires pywin32 in Cinema 4D's Python.
"$PREFIX\\cinema4d\\resource\\modules\\python\\libs\\win64\\python.exe" -m ensurepip
"$PREFIX\\cinema4d\\resource\\modules\\python\\libs\\win64\\python.exe" -m pip install \
    --no-deps --require-hashes -r "$RECIPE_DIR/requirements.txt"

mkdir -p "$PREFIX/etc/conda/activate.d"
mkdir -p "$PREFIX/etc/conda/deactivate.d"

# Deadline Cloud queue environments activate Conda with bash on Windows, so
# provide both shell and batch activation scripts.
cat <<EOF > "$PREFIX/etc/conda/activate.d/$PKG_NAME-$PKG_VERSION-vars.sh"
export C4D_VERSION=$CINEMA_4D_VERSION
export C4D_PLUGIN_SYNC_VERSION=$CINEMA_4D_PLUGIN_SYNC_VERSION
export C4D_LOCATION="$PREFIX\\cinema4d"
export C4D_COMMANDLINE_EXECUTABLE="$PREFIX\\cinema4d\\Commandline.exe"
EOF
cat "$PREFIX/etc/conda/activate.d/$PKG_NAME-$PKG_VERSION-vars.sh"

cat <<EOF > "$PREFIX/etc/conda/activate.d/$PKG_NAME-$PKG_VERSION-vars.bat"
set "C4D_VERSION=$CINEMA_4D_VERSION"
set "C4D_PLUGIN_SYNC_VERSION=$CINEMA_4D_PLUGIN_SYNC_VERSION"
set "C4D_LOCATION=$PREFIX\cinema4d"
set "C4D_COMMANDLINE_EXECUTABLE=$PREFIX\cinema4d\Commandline.exe"
EOF
cat "$PREFIX/etc/conda/activate.d/$PKG_NAME-$PKG_VERSION-vars.bat"

cat <<EOF > "$PREFIX/etc/conda/deactivate.d/$PKG_NAME-$PKG_VERSION-vars.sh"
unset C4D_VERSION
unset C4D_PLUGIN_SYNC_VERSION
unset C4D_LOCATION
unset C4D_COMMANDLINE_EXECUTABLE
EOF
cat "$PREFIX/etc/conda/deactivate.d/$PKG_NAME-$PKG_VERSION-vars.sh"

cat <<EOF > "$PREFIX/etc/conda/deactivate.d/$PKG_NAME-$PKG_VERSION-vars.bat"
set C4D_VERSION=
set C4D_PLUGIN_SYNC_VERSION=
set C4D_LOCATION=
set C4D_COMMANDLINE_EXECUTABLE=
EOF
cat "$PREFIX/etc/conda/deactivate.d/$PKG_NAME-$PKG_VERSION-vars.bat"

# Install Plugin Sync hooks after the standard Cinema 4D environment hooks.
cp "$RECIPE_DIR/zzz-cinema4d-plugin-sync-activate.sh" \
    "$PREFIX/etc/conda/activate.d/zzz-$PKG_NAME-$PKG_VERSION-plugin-sync.sh"
cp "$RECIPE_DIR/zzz-cinema4d-plugin-sync-deactivate.sh" \
    "$PREFIX/etc/conda/deactivate.d/zzz-$PKG_NAME-$PKG_VERSION-plugin-sync.sh"
