#!/bin/sh
# Plugin Sync for Houdini - Activate Script
# Downloads customer plugins from S3 and copies package .json files to Houdini's packages directory.
# Skips silently if DEADLINE_JA_S3_BUCKET is not set.

if [ -z "${DEADLINE_JA_S3_BUCKET:-}" ] || [ -z "${OPENJD_SESSION_WORKING_DIR:-}" ]; then
    return 0 2>/dev/null || exit 0
fi

_SP_PREFIX="${DEADLINE_JA_ROOT_PREFIX:+${DEADLINE_JA_ROOT_PREFIX}/}"
_SP_PLUGIN_DIR="${OPENJD_SESSION_WORKING_DIR}/deadline-plugins/houdini"
mkdir -p "$_SP_PLUGIN_DIR"

# Download generic plugins
_SP_GENERIC_DIR="${OPENJD_SESSION_WORKING_DIR}/deadline-plugins/generic"
_SP_GENERIC_SRC="s3://${DEADLINE_JA_S3_BUCKET}/${_SP_PREFIX}plugins/generic/"
if aws s3 ls "$_SP_GENERIC_SRC" >/dev/null 2>&1; then
    echo "Plugin Sync: Downloading generic plugins from $_SP_GENERIC_SRC" >&2
    mkdir -p "$_SP_GENERIC_DIR"
    if ! aws s3 cp "$_SP_GENERIC_SRC" "$_SP_GENERIC_DIR/" --recursive --quiet; then
        echo "Plugin Sync: WARNING — Failed to download generic plugins from $_SP_GENERIC_SRC" >&2
    fi
fi

# Download Houdini-specific plugins for this version
_SP_DCC_SRC="s3://${DEADLINE_JA_S3_BUCKET}/${_SP_PREFIX}plugins/linux/houdini/21.0/"
if aws s3 ls "$_SP_DCC_SRC" >/dev/null 2>&1; then
    echo "Plugin Sync: Downloading Houdini plugins from $_SP_DCC_SRC" >&2
    if ! aws s3 cp "$_SP_DCC_SRC" "$_SP_PLUGIN_DIR/" --recursive --quiet; then
        echo "Plugin Sync: WARNING — Failed to download Houdini plugins from $_SP_DCC_SRC" >&2
    fi
fi

# Copy .json package files from root of plugin directory to Houdini's packages directory
_SP_HOUDINI_PACKAGES_DIR="$HOME/houdini21.0/packages"
mkdir -p "$_SP_HOUDINI_PACKAGES_DIR"
echo "Plugin Sync: Houdini packages directory: $_SP_HOUDINI_PACKAGES_DIR" >&2
echo "Plugin Sync: Plugin directory: $_SP_PLUGIN_DIR" >&2
ls -la "$_SP_PLUGIN_DIR"/*.json >&2 || echo "Plugin Sync: No .json files found at root of plugin directory" >&2

_SP_MANIFEST_FILE="$_SP_PLUGIN_DIR/.copied_packages_manifest"
: > "$_SP_MANIFEST_FILE"

for _sp_json_file in "$_SP_PLUGIN_DIR"/*.json; do
    [ -f "$_sp_json_file" ] || continue
    echo "Plugin Sync: Copying $_sp_json_file to $_SP_HOUDINI_PACKAGES_DIR/" >&2
    cp "$_sp_json_file" "$_SP_HOUDINI_PACKAGES_DIR/"
    basename "$_sp_json_file" >> "$_SP_MANIFEST_FILE"
done

echo "Plugin Sync: Copied $(wc -l < "$_SP_MANIFEST_FILE") package file(s) to $_SP_HOUDINI_PACKAGES_DIR" >&2

export DEADLINE_CLOUD_HOUDINI_PLUGIN_SYNC_DIR="$_SP_PLUGIN_DIR"
unset _SP_PREFIX _SP_PLUGIN_DIR _SP_GENERIC_DIR _SP_GENERIC_SRC _SP_DCC_SRC _SP_HOUDINI_PACKAGES_DIR _SP_MANIFEST_FILE _sp_json_file
