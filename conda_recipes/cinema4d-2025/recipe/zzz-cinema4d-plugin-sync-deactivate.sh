#!/bin/bash
# Restore the Cinema 4D module path changed by Plugin Sync.

if [ -n "${_CINEMA4D_PLUGIN_SYNC_HAD_MODULE_PATH+x}" ]; then
    if [ "$_CINEMA4D_PLUGIN_SYNC_HAD_MODULE_PATH" = 1 ]; then
        export g_additionalModulePath="${_CINEMA4D_PLUGIN_SYNC_PREVIOUS_MODULE_PATH:-}"
    else
        unset g_additionalModulePath
    fi
fi

unset _CINEMA4D_PLUGIN_SYNC_HAD_MODULE_PATH
unset _CINEMA4D_PLUGIN_SYNC_PREVIOUS_MODULE_PATH
