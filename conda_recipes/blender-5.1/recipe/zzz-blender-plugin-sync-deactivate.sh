#!/bin/bash
# Plugin Sync cleanup for Blender
# Removes downloaded plugin files and unsets env vars.

if [ -n "${_SP_PLUGIN_DIR:-}" ] && [ -d "$_SP_PLUGIN_DIR" ]; then
    echo "Plugin Sync: Cleaning up $_SP_PLUGIN_DIR"
    rm -rf "$_SP_PLUGIN_DIR"
fi

# Clean up the generic plugins directory too
_SP_GENERIC_DIR="${OPENJD_SESSION_WORKING_DIR:-${TMPDIR:-/tmp}}/deadline-plugins/generic"
if [ -d "$_SP_GENERIC_DIR" ]; then
    rm -rf "$_SP_GENERIC_DIR"
fi

# Remove the parent if empty
_SP_PARENT="${OPENJD_SESSION_WORKING_DIR:-${TMPDIR:-/tmp}}/deadline-plugins"
rmdir "$_SP_PARENT" 2>/dev/null || true

unset BLENDER_USER_SCRIPTS
unset _SP_PLUGIN_DIR _SP_GENERIC_DIR _SP_PARENT
