#!/bin/sh

# Echo all the commands so debugging from log output is simpler
set -x
# Fail the script if any commands it runs fail
set -euo pipefail

# The version without the update number
MAYA_VERSION=${PKG_VERSION%.*}
# The location within $PREFIX where the RPM file extracts Maya
AUTODESK_ROOT="usr/autodesk"
MAYA_ROOT="$AUTODESK_ROOT/maya$MAYA_VERSION"
INSTALL_DIR="$PREFIX/$MAYA_ROOT"

cd "$PREFIX"

# Extract the Maya RPM
rpm2cpio "$SRC_DIR/installer/Packages"/Maya${MAYA_VERSION}_64-$PKG_VERSION-*.x86_64.rpm | cpio -idm

# Remove examples, they're not needed on the farm
rm -r "$MAYA_ROOT"/Examples

# Maya needs this symlink that rpm2cpio did not create
ln -r -s "$INSTALL_DIR/bin/maya$MAYA_VERSION" "$INSTALL_DIR/bin/maya"

# Install dependencies not available on Deadline Cloud service-managed fleets
# from the system package manager, dnf.
mkdir -p "$SRC_DIR/download"
cd "$SRC_DIR/download"
dnf download --resolve -y freetype alsa-lib fontconfig harfbuzz libbrotli graphite2 libxkbfile
for RPM_FILE in *.rpm; do
    rpm2cpio "$RPM_FILE" | cpio -idm
done

# Use patchelf to add relative RPATHs to the .so files where necessary.
# This is to follow the recommendation of https://docs.conda.io/projects/conda-build/en/latest/resources/use-shared-libraries.html
# to never use LD_LIBRARY_PATH in Conda environments.

# Copy the .so libraries to the Maya lib directory, adding to their RPATHs so they see each other
find . -type f,l -iname "*.so.*" -exec patchelf --add-rpath '$ORIGIN/.' {} \;
find . -type f,l -iname "*.so.*" -exec cp -P {} "$INSTALL_DIR/lib/" \;

# The Maya RPM has libraries in both $MAYA_ROOT/lib and $MAYA_ROOT/lib/el9
patchelf --add-rpath '$ORIGIN/../..' "$INSTALL_DIR"/lib/python*/site-packages/*.so
patchelf --add-rpath '$ORIGIN/../..' "$INSTALL_DIR"/lib/python*/site-packages/*/*.so
patchelf --add-rpath '$ORIGIN/../..' "$INSTALL_DIR"/lib/python*/lib-dynload/*.so
patchelf --add-rpath '$ORIGIN/../../el9' "$INSTALL_DIR"/lib/python*/lib-dynload/*.so

# Work around rattler-build issue https://github.com/prefix-dev/rattler-build/issues/1191 that it excludes intentional .pyc files without corresponding .py.
# Rename every .pyc file to .pyc2.
for PYC in "$INSTALL_DIR"/lib/python*/site-packages/maya/*.pyc; do
    mv "$PYC" "${PYC}2"
done

# Use thin client licensing configuration to use the ProductInformation.pit from the Arnold installation.
#
# To learn more, see the Autodesk article "Thin Client Licensing for Maya and MotionBuilder"
# at https://www.autodesk.com/support/technical/article/caas/tsarticles/ts/2zqRBCuGDrcPZDzULJQ27p.html
# and the Arnold support tip "error: (44) Product key not found"
# at https://arnoldsupport.com/2022/02/02/error-44-product-key-not-found/.

# Use the ProductInformation.pit from the included Arnold
unzip -j "$SRC_DIR/installer/Packages/package.zip" bin/ProductInformation.pit -d "$INSTALL_DIR"

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
# for details on activation.

# Activation scripts to set/unset environment variables
mkdir -p "$PREFIX/etc/conda/activate.d"
cat <<EOF > "$PREFIX/etc/conda/activate.d/$PKG_NAME-$PKG_VERSION-vars.sh"
export MAYA_LOCATION="\$CONDA_PREFIX/$MAYA_ROOT"
export MAYA_VERSION="$MAYA_VERSION"

# Turn off the Maya application home for the render farm
export MAYA_NO_HOME=1

# Set the Maya module path to include the virtual environment equivalent of the default system module paths
export MAYA_MODULE_PATH="\$CONDA_PREFIX/usr/autodesk/maya$MAYA_VERSION/modules:\$CONDA_PREFIX/usr/autodesk/modules/maya/$MAYA_VERSION:\$CONDA_PREFIX/usr/autodesk/modules/maya"
export PATH="\$MAYA_LOCATION/bin:\$PATH"

# Set thin client mode to use the correct ProductInformation.pit file
export AUTODESK_ADLM_THINCLIENT_ENV='$INSTALL_DIR/AdlmThinClientCustomEnv.xml'
export MAYA_LEGACY_THINCLIENT=1

# Work around rattler-build issue https://github.com/prefix-dev/rattler-build/issues/1191 that it excludes intentional .pyc files without corresponding .py.
# Rename every .pyc2 file back to .pyc.
if [ -f "\$MAYA_LOCATION"/lib/python*/site-packages/maya/OpenMaya.pyc2 ]; then
    for PYC2 in "\$MAYA_LOCATION"/lib/python*/site-packages/maya/*.pyc2; do
        mv "\$PYC2" "\${PYC2%2}"
    done
fi

EOF
cat "$PREFIX/etc/conda/activate.d/$PKG_NAME-$PKG_VERSION-vars.sh"

mkdir -p "$PREFIX/etc/conda/deactivate.d"
cat <<EOF > "$PREFIX/etc/conda/deactivate.d/$PKG_NAME-$PKG_VERSION-vars.sh"
unset MAYA_LEGACY_THINCLIENT
unset AUTODESK_ADLM_THINCLIENT_ENV
unset MAYA_MODULE_PATH
export PATH="\${PATH/\$MAYA_LOCATION\\/bin:/}"
unset MAYA_NO_HOME
unset MAYA_VERSION
unset MAYA_LOCATION
EOF
cat "$PREFIX/etc/conda/deactivate.d/$PKG_NAME-$PKG_VERSION-vars.sh"
