#!/bin/sh

# Echo all the commands so debugging from log output is simpler
set -x
# Fail the script if any commands it runs fail
set -euo pipefail

# The version without the update number
REDSHIFT_VERSION=${PKG_VERSION%.*}

# Redshift supports the following maya versions 
MAYA_VERSIONS="2022 2023 2024 2025 2026"

INSTALLER_DIR="$SRC_DIR/installer"
REDSHIFT_UNPACK_DIR="$INSTALLER_DIR/redshift_installer_artifacts"
REDSHIFT_ROOT="usr/maxon/redshift_${REDSHIFT_VERSION}"

# Extract the run file into its accompanying tarball and setup script
chmod u+x "$INSTALLER_DIR"/redshift_"${REDSHIFT_VERSION}"*_linux_x64.run
"$INSTALLER_DIR"/redshift_${REDSHIFT_VERSION}*_linux_x64.run --target "$REDSHIFT_UNPACK_DIR" --noexec

# Skip superuser check by modifying the setup script in-place
sed -i 's/\[ "$(id -u)" != "0" \]/false/' "$REDSHIFT_UNPACK_DIR/setup.sh"

# Run the setup script
cd "$REDSHIFT_UNPACK_DIR"
./setup.sh --installpath "${PREFIX}/${REDSHIFT_ROOT}"

# clear the installer artifacts
rm setup.sh
rm package.tar.gz

# clean up unneeded DCC artifacts
# Note: redshift4blender is not included in Redshift 2026+ (Maxon paused Blender development)
rm -r "${PREFIX}/${REDSHIFT_ROOT}"/redshift4c4d
rm -r "${PREFIX}/${REDSHIFT_ROOT}"/redshift4houdini
rm -r "${PREFIX}/${REDSHIFT_ROOT}"/redshift4katana
rm -r "${PREFIX}/${REDSHIFT_ROOT}"/redshift4solaris

# Create the redshift4maya.mod file for multiple Maya versions
#
# The maya package has set the Maya module path to include virtual environment-equivalents of
# the system module paths, so this is the usual installation location after the virtual environment
# prefix.

for MAYA_VERSION in $MAYA_VERSIONS; do

  # Add a relative RPATH from Redshift into Maya using patchelf, which is part of
  # the conda-build virtual environment. This is so we can follow the recommendation
  # of https://docs.conda.io/projects/conda-build/en/latest/resources/use-shared-libraries.html
  # to never use LD_LIBRARY_PATH in Conda environments.

  patchelf --add-rpath "\$ORIGIN/../../../../autodesk/maya${MAYA_VERSION}/lib" "${PREFIX}/${REDSHIFT_ROOT}/redshift4maya/${MAYA_VERSION}"/redshift4maya.so
  patchelf --add-rpath "\$ORIGIN/../../../../autodesk/maya${MAYA_VERSION}/plug-ins/xgen/lib" "${PREFIX}/${REDSHIFT_ROOT}/redshift4maya/${MAYA_VERSION}"/redshift4maya.so

  # Generate the .mod file for this specific version
  mkdir -p "$PREFIX/usr/autodesk/modules/maya/$MAYA_VERSION"
  cat <<EOF > "$PREFIX/usr/autodesk/modules/maya/$MAYA_VERSION/redshift4maya.mod"
+ redshift4maya any $PREFIX/$REDSHIFT_ROOT/redshift4maya
scripts: common/scripts
icons: common/icons
plug-ins: $MAYA_VERSION
REDSHIFT_COREDATAPATH = $PREFIX/$REDSHIFT_ROOT
MAYA_CUSTOM_TEMPLATE_PATH +:= common/scripts/NETemplates
MAYA_RENDER_DESC_PATH +:=  common/rendererDesc
REDSHIFT_MAYAEXTENSIONSPATH +:= $MAYA_VERSION/extensions
REDSHIFT_PROCEDURALSPATH += "\$REDSHIFT_COREDATAPATH/procedurals/usd/USD_24.08"
REDSHIFT_PROCEDURALSPATH += "\$REDSHIFT_COREDATAPATH/procedurals/alembic"
EOF

done

