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

# Script to set environment variables during activation
# Environment variables are based on what is needed for portable Redshift installations
# https://help.maxon.net/r3d/houdini/en-us/Content/html/Custom+Install+Locations.html
mkdir -p "$PREFIX/etc/conda/activate.d"
cat <<EOF > "$PREFIX/etc/conda/activate.d/houdini-redshift-$PKG_VERSION-vars.sh"
export REDSHIFT_COREDATAPATH="$REDSHIFT_ROOT"
export REDSHIFT_LOCALDATAPATH="\$REDSHIFT_COREDATAPATH/redshift_local_data"
export REDSHIFT_PROCEDURALSPATH="\$REDSHIFT_COREDATAPATH/procedurals"
export REDSHIFT_PREFSPATH="\$REDSHIFT_LOCALDATAPATH/preferences.xml"
export HOUDINI_DSO_ERROR=2

# Redshift plugins for Houdini are versioned to match the exact patch release
# of the Houdini version. If there is no exact match this package will point
# to the latest plugin version for either the matching MAJOR.MINOR Houdini version.
# Using a plugin version that doesn't match the Houdini version could cause
# instability and failures.

HOU_VERSION_OUTPUT=\$(houdini --version 2>/dev/null)
if [ $? -eq 0 ] && [[ "\$HOU_VERSION_OUTPUT" =~ Houdini\ FX\ ([0-9]+\.[0-9]+\.[0-9]+) ]]; then
  HOU_VERSION="\${BASH_REMATCH[1]}"

  # Get all available plugin versions
  AVAILABLE_VERSIONS=\$(find "\$REDSHIFT_COREDATAPATH/redshift4houdini/" -mindepth 1 -maxdepth 1 -type d -printf "%f\n")

  # Check for exact match first
  if echo "\$AVAILABLE_VERSIONS" | grep -q "^\$HOU_VERSION$"; then
    export RS_PLUGIN_VERSION="\$HOU_VERSION"
  else
    # Extract major.minor from HOU_VERSION (e.g. 21.0 from 21.0.440)
    HOU_MAJOR_MINOR=\${HOU_VERSION%.*}
    
    # Find the latest patch release for a matching major.minor version
    MATCHING_VERSION=\$(echo "\$AVAILABLE_VERSIONS" | grep "^\$HOU_MAJOR_MINOR" | sort -V | tail -1)

    if [ -n "\$MATCHING_VERSION" ]; then
      export RS_PLUGIN_VERSION="\$MATCHING_VERSION"
      echo "Warning: No exact match Redshift plugin found for Houdini \$HOU_VERSION, using \$RS_PLUGIN_VERSION instead"
    else
      # If no matching major.minor version is found fail to load the package
      echo "Error: No matching Redshift plugin found for Houdini \$HOU_MAJOR_MINOR in \$AVAILABLE_VERSIONS"
      exit 1
    fi
  fi
else
  echo "Error: Could not determine Houdini version using 'houdini --version'"
  exit 1
fi

# PXR_PLUGINPATH_NAME should be able to be set for the Solaris plugin in the Redshift package file.
# https://help.maxon.net/r3d/houdini/en-us/Content/html/Houdini+Plugin+Configuration.html
# However, there's a known issue where that doesn't work on Linux.
# Instead we can set it outside the package file as part of the environment as the suggested workaround.

internal_package_add_to_search_path () {
    # Add a path to a new or existing environment variable.
    # Usage: internal_package_add_to_search_path VAR_NAME /search/path/value
    eval "CURRENT_VALUE=\\\${\$1:-}"
    if [ "\$CURRENT_VALUE" = "" ]; then
        eval "export \"\$1=\\\$2\""
    else
        NEW_VALUE="\$CURRENT_VALUE:\$2"
        eval "export \"\$1=\\\$NEW_VALUE\""
    fi
}

internal_package_add_to_search_path PXR_PLUGINPATH_NAME "\$REDSHIFT_COREDATAPATH/redshift4solaris/\$RS_PLUGIN_VERSION"

unset -f internal_package_add_to_search_path
EOF

mkdir -p "$PREFIX/etc/conda/deactivate.d"
cat <<EOF > "$PREFIX/etc/conda/deactivate.d/houdini-redshift-$PKG_VERSION-vars.sh"
internal_package_remove_from_search_path () {
    # Removes the given path from the given environment variable.
    # Usage: internal_package_remove_from_search_path VAR_NAME /search/path/value
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

internal_package_remove_from_search_path PXR_PLUGINPATH_NAME "\$REDSHIFT_COREDATAPATH/redshift4solaris/\$RS_PLUGIN_VERSION"

unset REDSHIFT_COREDATAPATH
unset REDSHIFT_LOCALDATAPATH
unset REDSHIFT_PROCEDURALSPATH
unset REDSHIFT_PREFSPATH
unset HOUDINI_DSO_ERROR
unset -f internal_package_remove_from_search_path
EOF
