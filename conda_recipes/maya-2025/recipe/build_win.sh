# Echo all the commands so debugging from log output is simpler
set -x
# Fail the script if any commands it runs fail
set -euo pipefail

# The version without the update number
MAYA_VERSION=${PKG_VERSION%.*}
# The location within $PREFIX where Maya will be installed
AUTODESK_ROOT="usr/Autodesk"
MAYA_ROOT="$AUTODESK_ROOT/Maya$MAYA_VERSION"
INSTALL_DIR="$PREFIX/$MAYA_ROOT"

mkdir -p "$PREFIX/$AUTODESK_ROOT"

pushd $SRC_DIR
find .
popd

# Move all the files into the prefix. Use cmd to move the files as it works
# more reliably with permissions and locking.
cmd <<EOF
move $SRC_DIR\\installer\\Maya$MAYA_VERSION "$PREFIX\\$AUTODESK_ROOT\\"
move $SRC_DIR\\installer\\ProductInformation.pit "$INSTALL_DIR\\"
EOF

# See https://www.autodesk.com/support/technical/article/caas/tsarticles/ts/75wD5ycdkRVPHQtG4eUwBL.html
# titled "Deploying Maya Batch on the Cloud" about making Maya for Windows cloud compliant.
cd "$INSTALL_DIR"
./bin/mayapy.exe "$SRC_DIR/cleanMayaForCloud.py"

# The conda-build environment is configured for packaging one pypi package into one conda package.
# We turn off the following defaults for the below mayapy.exe pip install.
unset PIP_NO_DEPENDENCIES
unset PIP_IGNORE_INSTALLED
unset PIP_NO_INDEX

# Currently, the maya-openjd command from the deadline-cloud-for-maya package requires that
# pywin32 be installed inside Maya's Python. This command adds it to the Maya package.
./bin/mayapy.exe -m pip install pywin32

## You can uncomment this to get a verbose listing of all the files
# pushd $PREFIX
# find .
# popd

# Remove docs, they're not needed on the farm
rm -r "$INSTALL_DIR"/docs

# Remove examples, they're not needed on the farm
rm -r "$INSTALL_DIR"/Examples

# Use thin client licensing configuration to use the ProductInformation.pit from the Arnold installation.
#
# To learn more, see the Autodesk article "Thin Client Licensing for Maya and MotionBuilder"
# at https://www.autodesk.com/support/technical/article/caas/tsarticles/ts/2zqRBCuGDrcPZDzULJQ27p.html
# and the Arnold support tip "error: (44) Product key not found"
# at https://arnoldsupport.com/2022/02/02/error-44-product-key-not-found/.

cat <<EOF > "$INSTALL_DIR"/AdlmThinClientCustomEnv.xml
<?xml version="1.0"encoding="utf-8"?>
<ADLMCUSTOMENV VERSION="1.0.0.0">
    <PLATFORM OS="Linux">
        <KEY ID="ADLM_PIT_FILE_LOCATION">
        <!--Path to the ProductInformation.pit file-->
        <!--Default: /var/opt/Autodesk/Adlm/.config-->
        <STRING>$INSTALL_DIR</STRING>
        </KEY>
    </PLATFORM>
</ADLMCUSTOMENV>
EOF

# See https://docs.conda.io/projects/conda/en/latest/dev-guide/deep-dives/activation.html
# for details on activation. The Deadline Cloud sample queue environments use bash
# to activate environments on Windows, so we recommend always producing both .bat and .sh files.

mkdir -p "$PREFIX/etc/conda/activate.d"
mkdir -p "$PREFIX/etc/conda/deactivate.d"

cat <<EOF > "$PREFIX/etc/conda/activate.d/$PKG_NAME-$PKG_VERSION-vars.sh"
export MAYA_VERSION=$MAYA_VERSION
export MAYA_LOCATION='$INSTALL_DIR'
export PATH="\$(cygpath '$INSTALL_DIR/bin'):\$PATH"

# Turn off the Maya application home for the render farm
export MAYA_NO_HOME=1

# Set the Maya module path to include the virtual environment equivalent of a system default path
export MAYA_MODULE_PATH='$PREFIX/usr/autodesk/maya$MAYA_VERSION/modules;$PREFIX/usr/autodesk/modules/maya/$MAYA_VERSION;$PREFIX/usr/autodesk/modules/maya'

# Set thin client mode to use the correct ProductInformation.pit file
export AUTODESK_ADLM_THINCLIENT_ENV='$INSTALL_DIR/AdlmThinClientCustomEnv.xml'
export MAYA_LEGACY_THINCLIENT=1
EOF
cat "$PREFIX/etc/conda/activate.d/$PKG_NAME-$PKG_VERSION-vars.sh"

cat <<EOF > "$PREFIX/etc/conda/activate.d/$PKG_NAME-$PKG_VERSION-vars.bat"
set "MAYA_LOCATION=$INSTALL_DIR"
set "MAYA_VERSION=$MAYA_VERSION"
set "PATH=$INSTALL_DIR/bin;%PATH%"
set MAYA_NO_HOME=1
set MAYA_MODULE_PATH="$PREFIX/usr/autodesk/maya$MAYA_VERSION/modules;$PREFIX/usr/autodesk/modules/maya/$MAYA_VERSION;$PREFIX/usr/autodesk/modules/maya"
set "AUTODESK_ADLM_THINCLIENT_ENV=$INSTALL_DIR/AdlmThinClientCustomEnv.xml"
set MAYA_LEGACY_THINCLIENT=1
EOF
cat "$PREFIX/etc/conda/activate.d/$PKG_NAME-$PKG_VERSION-vars.bat"

cat <<EOF > "$PREFIX/etc/conda/deactivate.d/$PKG_NAME-$PKG_VERSION-vars.sh"
unset MAYA_LEGACY_THINCLIENT
unset AUTODESK_ADLM_THINCLIENT_ENV
unset MAYA_MODULE_PATH
unset MAYA_NO_HOME
export PATH="\${PATH/\$(cygpath '$INSTALL_DIR/bin'):/}"
unset MAYA_LOCATION
unset MAYA_VERSION
EOF
cat "$PREFIX/etc/conda/deactivate.d/$PKG_NAME-$PKG_VERSION-vars.sh"

cat <<EOF > "$PREFIX/etc/conda/deactivate.d/$PKG_NAME-$PKG_VERSION-vars.bat"
set "PATH=%PATH:$INSTALL_DIR/bin;=%"
set MAYA_LEGACY_THINCLIENT=
set AUTODESK_ADLM_THINCLIENT_ENV=
set MAYA_MODULE_PATH=
set MAYA_NO_HOME=
set MAYA_LOCATION=
set MAYA_VERSION=
EOF
cat "$PREFIX/etc/conda/deactivate.d/$PKG_NAME-$PKG_VERSION-vars.bat"
