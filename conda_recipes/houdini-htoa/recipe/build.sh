#!/bin/sh
set -xeuo pipefail

# Version info
HTOA_PACKAGING_VERSION="$PKG_VERSION"
UPSTREAM_VERSION="$HTOA_PACKAGING_VERSION"
BUILD_ID="rd99f711"
HOUDINI_VERSION="20.0.896"

INSTALLER_DIR="$SRC_DIR/installer"
EXPECTED_INSTALLER="htoa-${UPSTREAM_VERSION}_${BUILD_ID}_houdini-${HOUDINI_VERSION}_gcc11.2_linux.run"
INSTALLER="$INSTALLER_DIR/$EXPECTED_INSTALLER"
HTOA_UNPACK_DIR="$INSTALLER_DIR/htoa_installer_artifacts"

if [ ! -f "$INSTALLER" ]; then
    echo "Expected installer $EXPECTED_INSTALLER not found in $INSTALLER_DIR" >&2
    echo "Discovering available installers..." >&2
    FOUND_INSTALLER=$(find "$INSTALLER_DIR" -maxdepth 1 -type f -name "htoa-*_houdini-${HOUDINI_VERSION}_gcc11.2_linux.run" | sort | head -n 1 || true)
    if [ -z "${FOUND_INSTALLER:-}" ]; then
        echo "ERROR: No HtoA installer archives were found in $INSTALLER_DIR" >&2
        ls -l "$INSTALLER_DIR" || true
        exit 1
    fi
    INSTALLER="$FOUND_INSTALLER"
    INSTALLER_BASENAME=$(basename "$INSTALLER")
    UPSTREAM_VERSION=$(printf "%s" "$INSTALLER_BASENAME" | sed -E 's/^htoa-([0-9.]+)_.*/\1/')
    echo "Using installer $INSTALLER_BASENAME (upstream version $UPSTREAM_VERSION)"
fi
HTOA_ROOT="$PREFIX/opt/htoa"

# Extract the self-extracting installer using makeself flags
# Following the same pattern as maya-redshift
echo "Extracting HtoA installer..."
mkdir -p "$HTOA_UNPACK_DIR"

# Make installer executable
chmod u+x "$INSTALLER"

# Set environment for Qt Installer Framework
# The installer needs Qt libraries and plugins
export LD_LIBRARY_PATH="$BUILD_PREFIX/lib:${LD_LIBRARY_PATH:-}"
export QT_QPA_PLUGIN_PATH="$BUILD_PREFIX/plugins"

# Extract using Qt Installer Framework flags
echo "Extracting installer contents using --extract-to (silent, license accepted)..."
if "$INSTALLER" --accept-license --silent --extract-to "$HTOA_UNPACK_DIR"; then
    echo "Successfully extracted installer contents"
    ls -lh "$HTOA_UNPACK_DIR"
else
    echo "ERROR: Extraction failed"
    exit 1
fi

# The extracted contents should include the HtoA files
# Inspect the unpacked directory to see the structure
echo "Contents of unpacked directory:"
ls -la "$HTOA_UNPACK_DIR"

# Install HtoA to the prefix
mkdir -p "$HTOA_ROOT"

# Copy HtoA files to the installation directory
# Adjust the source path based on actual extracted structure
if [ -d "$HTOA_UNPACK_DIR/htoa" ]; then
    cp -r "$HTOA_UNPACK_DIR/htoa"/* "$HTOA_ROOT/"
elif [ -d "$HTOA_UNPACK_DIR" ]; then
    # If files are directly in the unpack dir
    cp -r "$HTOA_UNPACK_DIR"/* "$HTOA_ROOT/"
fi

# Create symlinks for Arnold command-line tools
mkdir -p "$PREFIX/bin"
for BINARY in kick maketx noice oslc oslinfo; do
    if [ -f "$HTOA_ROOT/bin/$BINARY" ]; then
        chmod u+x "$HTOA_ROOT/bin/$BINARY"
        ln -r -s "$HTOA_ROOT/bin/$BINARY" "$PREFIX/bin/$BINARY"
    fi
done

# Add rpath to shared libraries to find Houdini's libraries
# This ensures the plugin can find Houdini's DSOs at runtime
for so_file in $(find "$HTOA_ROOT" -name "*.so" -o -name "*.so.*"); do
    if [ -f "$so_file" ]; then
        patchelf --add-rpath '$ORIGIN:$ORIGIN/../lib:$ORIGIN/../../houdini/dsolib' "$so_file" || true
    fi
done

# Create Houdini package file for HtoA plugin
# This tells Houdini where to find the Arnold plugin
# https://www.sidefx.com/docs/houdini/ref/plugins.html
mkdir -p "$PREFIX/opt/houdini/packages"
cat <<'EOF' > "$PREFIX/opt/houdini/packages/htoa.json"
{
    "env": [
        {
            "HTOA": "$HTOA_ROOT"
        },
        {
            "ARNOLD_LOCATION": "$HTOA_ROOT"
        },
        {
            "PATH": {
                "value": "$HTOA_ROOT/bin",
                "method": "prepend"
            }
        },
        {
            "HOUDINI_PATH": {
                "value": "$HTOA_ROOT:&",
                "method": "prepend"
            }
        },
        {
            "PYTHONPATH": {
                "value": "$HTOA_ROOT/python",
                "method": "prepend"
            }
        }
    ]
}
EOF

# Replace $HTOA_ROOT with actual path in the JSON file
sed -i "s|\$HTOA_ROOT|$HTOA_ROOT|g" "$PREFIX/opt/houdini/packages/htoa.json"

# Script to set environment variables during conda activation
mkdir -p "$PREFIX/etc/conda/activate.d"
cat <<EOF > "$PREFIX/etc/conda/activate.d/houdini-htoa-$PKG_VERSION-vars.sh"
export HTOA="$HTOA_ROOT"
export ARNOLD_LOCATION="$HTOA_ROOT"
export HOUDINI_DSO_ERROR=2

# Add Arnold's Python module path
if [ -d "$HTOA_ROOT/python" ]; then
    export PYTHONPATH="$HTOA_ROOT/python:\${PYTHONPATH:-}"
fi

# Version detection similar to Redshift pattern
HOU_VERSION_OUTPUT=\$(houdini --version 2>/dev/null)
if [ \$? -eq 0 ] && [[ "\$HOU_VERSION_OUTPUT" =~ Houdini\ (FX|Core)?\ ?([0-9]+\.[0-9]+\.[0-9]+) ]]; then
  HOU_VERSION="\${BASH_REMATCH[2]}"
  export HOUDINI_VERSION="\$HOU_VERSION"
  echo "Detected Houdini version: \$HOU_VERSION"
else
  echo "Warning: Could not determine Houdini version"
fi
EOF

mkdir -p "$PREFIX/etc/conda/deactivate.d"
cat <<EOF > "$PREFIX/etc/conda/deactivate.d/houdini-htoa-$PKG_VERSION-vars.sh"
unset HTOA
unset ARNOLD_LOCATION
unset HOUDINI_DSO_ERROR
unset HOUDINI_VERSION

# Remove Arnold Python path from PYTHONPATH
if [ -n "\${PYTHONPATH:-}" ]; then
    export PYTHONPATH=\$(echo "\$PYTHONPATH" | sed "s|$HTOA_ROOT/python:||g")
fi
EOF