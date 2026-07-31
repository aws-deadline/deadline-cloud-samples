#!/bin/bash
# Download Cinema 4D plugins from the job attachments bucket and add their
# session directory to g_additionalModulePath.

if [ -z "${DEADLINE_JA_S3_BUCKET:-}" ] || [ -z "${C4D_PLUGIN_SYNC_VERSION:-}" ]; then
    echo "Plugin Sync: Skipping; DEADLINE_JA_S3_BUCKET or C4D_PLUGIN_SYNC_VERSION is not set." >&2
    return 0 2>/dev/null || exit 0
fi

_SP_PREFIX="${DEADLINE_JA_ROOT_PREFIX:+${DEADLINE_JA_ROOT_PREFIX}/}"
_SP_OS="linux"
case "$(uname -s)" in
    MINGW*|MSYS*|CYGWIN*) _SP_OS="windows" ;;
esac

_SP_SESSION_ROOT="${OPENJD_SESSION_WORKING_DIR:-${TMPDIR:-/tmp}}"
_SP_PLUGIN_DIR="$_SP_SESSION_ROOT/deadline-plugins/cinema4d"
mkdir -p "$_SP_PLUGIN_DIR"

_SP_GENERIC_DIR="$_SP_SESSION_ROOT/deadline-plugins/generic"
_SP_GENERIC_SRC="s3://${DEADLINE_JA_S3_BUCKET}/${_SP_PREFIX}plugins/generic/"
if aws s3 ls "$_SP_GENERIC_SRC" >/dev/null 2>&1; then
    mkdir -p "$_SP_GENERIC_DIR"
    echo "Plugin Sync: Downloading generic plugins from $_SP_GENERIC_SRC" >&2
    aws s3 cp "$_SP_GENERIC_SRC" "$_SP_GENERIC_DIR/" --recursive --quiet 2>/dev/null || true
fi

_SP_DCC_SRC="s3://${DEADLINE_JA_S3_BUCKET}/${_SP_PREFIX}plugins/${_SP_OS}/cinema4d/${C4D_PLUGIN_SYNC_VERSION}/"
if aws s3 ls "$_SP_DCC_SRC" >/dev/null 2>&1; then
    echo "Plugin Sync: Downloading Cinema 4D plugins from $_SP_DCC_SRC" >&2
    aws s3 cp "$_SP_DCC_SRC" "$_SP_PLUGIN_DIR/" --recursive --quiet 2>/dev/null || true
fi

_SP_MODULE_PATHS=""
if [ -d "$_SP_PLUGIN_DIR" ] && [ -n "$(ls -A "$_SP_PLUGIN_DIR" 2>/dev/null)" ]; then
    _SP_MODULE_PATHS="$_SP_PLUGIN_DIR"
fi
if [ -d "$_SP_GENERIC_DIR" ] && [ -n "$(ls -A "$_SP_GENERIC_DIR" 2>/dev/null)" ]; then
    if [ -n "$_SP_MODULE_PATHS" ]; then
        _SP_MODULE_PATHS="$_SP_MODULE_PATHS;$_SP_GENERIC_DIR"
    else
        _SP_MODULE_PATHS="$_SP_GENERIC_DIR"
    fi
fi

if [ -n "$_SP_MODULE_PATHS" ]; then
    if [ "${g_additionalModulePath+x}" = x ]; then
        export _CINEMA4D_PLUGIN_SYNC_HAD_MODULE_PATH=1
        export _CINEMA4D_PLUGIN_SYNC_PREVIOUS_MODULE_PATH="$g_additionalModulePath"
    else
        export _CINEMA4D_PLUGIN_SYNC_HAD_MODULE_PATH=0
        unset _CINEMA4D_PLUGIN_SYNC_PREVIOUS_MODULE_PATH
    fi
    export g_additionalModulePath="${_SP_MODULE_PATHS}${g_additionalModulePath:+;${g_additionalModulePath}}"
    echo "Plugin Sync: Added $_SP_MODULE_PATHS to g_additionalModulePath" >&2
else
    echo "Plugin Sync: No Cinema 4D plugins found." >&2
fi

unset _SP_PREFIX _SP_OS _SP_SESSION_ROOT _SP_PLUGIN_DIR _SP_MODULE_PATHS
unset _SP_GENERIC_DIR _SP_GENERIC_SRC _SP_DCC_SRC
