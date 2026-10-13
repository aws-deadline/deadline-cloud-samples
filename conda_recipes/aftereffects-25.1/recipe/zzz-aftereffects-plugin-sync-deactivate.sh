#!/bin/bash
# Remove the plugins that the Plugin Sync activate hook copied into the
# After Effects installation.
#
# The activate hook records the directory in _AE_PLUGIN_SYNC_DIR because the
# After Effects variables hook unsets AE_LOCATION before this hook runs.

if [ -n "${_AE_PLUGIN_SYNC_DIR:-}" ] && [ -d "$_AE_PLUGIN_SYNC_DIR" ]; then
    # Only remove the directory that the activate hook owns.
    if [ "$(basename "$_AE_PLUGIN_SYNC_DIR")" = "deadline-plugin-sync" ]; then
        if rm -rf "$_AE_PLUGIN_SYNC_DIR" 2>/dev/null; then
            echo "Plugin Sync: Removed $_AE_PLUGIN_SYNC_DIR" >&2
        else
            # A process that After Effects started can keep a plugin file open
            # after aerender exits. Session cleanup removes the environment later.
            echo "Plugin Sync: WARNING: Could not fully remove $_AE_PLUGIN_SYNC_DIR; a process might still have a plugin open." >&2
        fi
    fi
fi

unset _AE_PLUGIN_SYNC_DIR
