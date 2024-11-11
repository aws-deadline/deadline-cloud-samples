# Echo all the commands so debugging from log output is simpler
set -x
# Fail the script if any commands it runs fail
set -euo pipefail

# The location within $PREFIX where Maya will be installed
# The value of $MAYA_VERSION comes from the maya package dependency
AUTODESK_ROOT="opt/Autodesk"
MTOA_ROOT="opt/Autodesk/Arnold/maya$MAYA_VERSION"
INSTALL_DIR="$PREFIX/$MTOA_ROOT"

mkdir -p "$PREFIX/$AUTODESK_ROOT"

ls "$SRC_DIR/installer"

# Move all the files into the prefix. Using cmd to move the files as it works
# more reliably with permissions and locking.
cmd <<EOF
move $SRC_DIR\\installer\\Arnold "$PREFIX\\$AUTODESK_ROOT"
EOF

## You can uncomment this to get a verbose listing of all the files
# pushd $PREFIX
# find .
# popd

# Remove installers, they're not needed on the farm
rm -r "$INSTALL_DIR"/license/installer

# Remove docs, they're not needed on the farm
rm -r "$INSTALL_DIR"/docs

# Create the mtoa.mod file so Maya loads the plugin.
#
# The maya package has set the Maya module path to include virtual environment-equivalents of
# the system module paths, so this is the usual installation location after the virtual environment
# prefix.
mkdir -p "$PREFIX/usr/Autodesk/modules/maya/$MAYA_VERSION"
cat <<EOF > "$PREFIX/usr/Autodesk/modules/maya/$MAYA_VERSION/mtoa.mod"
+ mtoa any $PREFIX/$MTOA_ROOT
PATH +:= bin
MAYA_CUSTOM_TEMPLATE_PATH +:= scripts/mtoa/ui/templates
MAYA_SCRIPT_PATH +:= scripts/mtoa/mel
MAYA_RENDER_DESC_PATH += $PREFIX/$MTOA_ROOT
MAYA_PXR_PLUGINPATH_NAME += $PREFIX/$MTOA_ROOT/usd
EOF

# See https://docs.conda.io/projects/conda/en/latest/dev-guide/deep-dives/activation.html
# for details on activation. The Deadline Cloud sample queue environments use bash
# to activate environments on Windows, so we recommend always producing both .bat and .sh files.

mkdir -p "$PREFIX/etc/conda/activate.d"
mkdir -p "$PREFIX/etc/conda/deactivate.d"

cat <<EOF > "$PREFIX/etc/conda/activate.d/$PKG_NAME-$PKG_VERSION-vars.sh"
export MTOA_VERSION=$MAYA_VERSION
export MTOA_LOCATION='$INSTALL_DIR'
export PATH="\$(cygpath '$INSTALL_DIR/bin'):\$PATH"
EOF
cat "$PREFIX/etc/conda/activate.d/$PKG_NAME-$PKG_VERSION-vars.sh"

cat <<EOF > "$PREFIX/etc/conda/activate.d/$PKG_NAME-$PKG_VERSION-vars.bat"
set "MTOA_LOCATION=$INSTALL_DIR"
set "MTOA_VERSION=$MAYA_VERSION"
set "PATH=$INSTALL_DIR/bin;%PATH%"
EOF
cat "$PREFIX/etc/conda/activate.d/$PKG_NAME-$PKG_VERSION-vars.bat"

cat <<EOF > "$PREFIX/etc/conda/deactivate.d/$PKG_NAME-$PKG_VERSION-vars.sh"
export PATH="\${PATH/\$(cygpath '$INSTALL_DIR/bin'):/}"
unset MTOA_LOCATION
unset MTOA_VERSION
EOF
cat "$PREFIX/etc/conda/deactivate.d/$PKG_NAME-$PKG_VERSION-vars.sh"

cat <<EOF > "$PREFIX/etc/conda/deactivate.d/$PKG_NAME-$PKG_VERSION-vars.bat"
set "PATH=%PATH:$INSTALL_DIR/bin;=%"
set MTOA_LOCATION=
set MTOA_VERSION=
EOF
cat "$PREFIX/etc/conda/deactivate.d/$PKG_NAME-$PKG_VERSION-vars.bat"
