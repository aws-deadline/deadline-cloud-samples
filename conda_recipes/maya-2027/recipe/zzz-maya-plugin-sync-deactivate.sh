#!/bin/bash
# Plugin Sync for Maya — deactivate script
# Cleans up downloaded plugin files.

if [ -n "${_MAYA_PLUGIN_SYNC_DIR:-}" ] && [ -d "$_MAYA_PLUGIN_SYNC_DIR" ]; then
    rm -rf "$_MAYA_PLUGIN_SYNC_DIR"
fi
unset _MAYA_PLUGIN_SYNC_DIR
