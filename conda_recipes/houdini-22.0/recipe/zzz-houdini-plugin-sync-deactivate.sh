#!/bin/sh
# Plugin Sync for Houdini - Deactivate Script
# Cleans up copied package .json files and downloaded plugins.

if [ -z "${DEADLINE_CLOUD_HOUDINI_PLUGIN_SYNC_DIR:-}" ]; then
    return 0 2>/dev/null || exit 0
fi

# Remove copied .json files from Houdini's packages directory
_SP_HOUDINI_PACKAGES_DIR="$HOME/houdini22.0/packages"
_SP_MANIFEST_FILE="$DEADLINE_CLOUD_HOUDINI_PLUGIN_SYNC_DIR/.copied_packages_manifest"

if [ -f "$_SP_MANIFEST_FILE" ]; then
    while IFS= read -r _sp_filename; do
        rm -f "$_SP_HOUDINI_PACKAGES_DIR/$_sp_filename"
    done < "$_SP_MANIFEST_FILE"
fi

# Remove downloaded plugins
rm -rf "$DEADLINE_CLOUD_HOUDINI_PLUGIN_SYNC_DIR"

unset DEADLINE_CLOUD_HOUDINI_PLUGIN_SYNC_DIR _SP_HOUDINI_PACKAGES_DIR _SP_MANIFEST_FILE _sp_filename
