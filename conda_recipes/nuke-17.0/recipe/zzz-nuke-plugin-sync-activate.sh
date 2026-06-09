#!/bin/bash
# Simple Plugin Delivery for Nuke
# Downloads plugin files from S3 and configures NUKE_PATH.
# Adds the plugin directory (for .gizmo files) and each subdirectory
# (for folder-based plugins with init.py) to NUKE_PATH.
#
# S3 convention: s3://<bucket>/<prefix>/plugins/<os>/nuke/<version>/
#
# Required environment variables (set by the worker agent):
#   DEADLINE_JA_S3_BUCKET      - Job attachment S3 bucket name
#   DEADLINE_JA_ROOT_PREFIX    - Job attachment root prefix in the bucket
#   OPENJD_SESSION_WORKING_DIR - Session working directory path

if [ -z "${DEADLINE_JA_S3_BUCKET:-}" ] || [ -z "${NUKE_VERSION:-}" ]; then
        echo "Plugin Sync: Skipping — DEADLINE_JA_S3_BUCKET or NUKE_VERSION not set."
    return 0 2>/dev/null || exit 0
fi

_SP_PREFIX="${DEADLINE_JA_ROOT_PREFIX:+${DEADLINE_JA_ROOT_PREFIX}/}"
_SP_OS="linux"
if [[ "$(uname -s)" == MINGW* ]] || [[ "$(uname -s)" == MSYS* ]] || [ -n "${OS:-}" ]; then
    _SP_OS="windows"
fi

_SP_PLUGIN_DIR="${OPENJD_SESSION_WORKING_DIR:-${TMPDIR:-/tmp}}/deadline-plugins/nuke"
mkdir -p "$_SP_PLUGIN_DIR"

# Download generic plugins
_SP_GENERIC_DIR="${OPENJD_SESSION_WORKING_DIR:-${TMPDIR:-/tmp}}/deadline-plugins/generic"
_SP_GENERIC_SRC="s3://${DEADLINE_JA_S3_BUCKET}/${_SP_PREFIX}plugins/generic/"
if aws s3 ls "$_SP_GENERIC_SRC" >/dev/null 2>&1; then
    mkdir -p "$_SP_GENERIC_DIR"
    echo "Plugin Sync: Downloading generic plugins from $_SP_GENERIC_SRC" >&2
    aws s3 cp "$_SP_GENERIC_SRC" "$_SP_GENERIC_DIR/" --recursive --quiet 2>/dev/null || true
fi

# Download Nuke-specific plugins
_SP_DCC_SRC="s3://${DEADLINE_JA_S3_BUCKET}/${_SP_PREFIX}plugins/${_SP_OS}/nuke/${NUKE_VERSION}/"
if aws s3 ls "$_SP_DCC_SRC" >/dev/null 2>&1; then
    echo "Plugin Sync: Downloading Nuke plugins from $_SP_DCC_SRC"
    aws s3 cp "$_SP_DCC_SRC" "$_SP_PLUGIN_DIR/" --recursive --quiet 2>/dev/null || true
fi

# Build NUKE_PATH: parent dir (for .gizmo files) + each subdir (for folder plugins)
if [ -d "$_SP_PLUGIN_DIR" ] && [ "$(ls -A "$_SP_PLUGIN_DIR" 2>/dev/null)" ]; then
    _SP_SEP=":"
    [[ "$_SP_OS" == "windows" ]] && _SP_SEP=";"

    _SP_PATHS="$_SP_PLUGIN_DIR"
    for _d in "$_SP_PLUGIN_DIR"/*/; do
        [ -d "$_d" ] && _SP_PATHS="${_SP_PATHS}${_SP_SEP}${_d%/}"
    done

    export NUKE_PATH="${NUKE_PATH:+${NUKE_PATH}${_SP_SEP}}${_SP_PATHS}"
    export _SP_PLUGIN_DIR
    echo "Plugin Sync: NUKE_PATH=$NUKE_PATH"
else
    echo "Plugin Sync: No Nuke plugins found, skipping."
fi

unset _SP_PREFIX _SP_OS _SP_DCC_SRC _SP_SEP _SP_PATHS _d
