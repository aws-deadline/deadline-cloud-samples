#!/bin/sh
set -xeuo pipefail

# The version without the update number
REDSHIFT_VERSION="$PKG_VERSION"

INSTALLER_DIR="$SRC_DIR/installer"
INSTALLER="$INSTALLER_DIR/redshift_${REDSHIFT_VERSION}_linux_x64.run"
REDSHIFT_UNPACK_DIR="$INSTALLER_DIR/redshift_installer_artifacts"
REDSHIFT_ROOT="$PREFIX/opt/redshift"

# Extract the run file into its accompanying tarball and setup script
chmod u+x "$INSTALLER"
$INSTALLER --target "$REDSHIFT_UNPACK_DIR" --noexec

# Skip superuser check by modifying the setup script in-place
sed -i 's/\[ "$(id -u)" != "0" \]/false/' "$REDSHIFT_UNPACK_DIR/setup.sh"

# Run the setup script
cd "$REDSHIFT_UNPACK_DIR"
./setup.sh --installpath "$REDSHIFT_ROOT"

# Clean up unneeded DCC artifacts
rm -r "$REDSHIFT_ROOT/redshift4c4d"
rm -r "$REDSHIFT_ROOT/redshift4katana"
rm -r "$REDSHIFT_ROOT/redshift4maya"

# Create symlink for redshiftCmdLine
mkdir -p "$PREFIX/bin"
ln -r -s "$REDSHIFT_ROOT/bin/redshiftCmdLine" "$PREFIX/bin/redshiftCmdLine"

# Add rpath into the Houdini installation in the same environment
for so_file in $(find "$REDSHIFT_ROOT"/redshift4houdini/*/dso -iname "redshift4houdini.so"); do
    patchelf --add-rpath '$ORIGIN/../../../../houdini/dsolib' "$so_file"
done

# Create Houdini package file for Redshift plugin and place into Houdini search path
# https://help.maxon.net/r3d/houdini/en-us/Content/html/Houdini+Plugin+Configuration.html
mkdir -p "$PREFIX/opt/houdini/packages"
cat <<EOF > "$PREFIX/opt/houdini/packages/redshift_package.json"
{
    "env":[
        {"HOUDINI_PATH": "\${REDSHIFT_COREDATAPATH}/redshift4houdini/\${RS_PLUGIN_VERSION}"},
        {"PATH": "\${REDSHIFT_COREDATAPATH}/bin"},
    ]
}
EOF

mkdir -p "$PREFIX/etc/conda/activate.d"
cp "$RECIPE_DIR/activate.sh" "$PREFIX/etc/conda/activate.d/houdini-redshift-$PKG_VERSION-vars.sh"

mkdir -p "$PREFIX/etc/conda/deactivate.d"
cp "$RECIPE_DIR/deactivate.sh" "$PREFIX/etc/conda/deactivate.d/houdini-redshift-$PKG_VERSION-vars.sh"
