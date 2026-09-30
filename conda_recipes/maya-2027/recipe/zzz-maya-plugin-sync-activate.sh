#!/bin/bash
# Plugin Sync for Maya
# Downloads plugin files from S3 and configures MAYA_MODULE_PATH.
# Runs after all standard Maya env vars are set via env_vars.d.
#
# S3 convention: s3://<bucket>/<prefix>/plugins/<os>/maya/<version>/
# Generic path:  s3://<bucket>/<prefix>/plugins/generic/
#
# Required environment variables (set by the worker agent):
#   DEADLINE_JA_S3_BUCKET      - Job attachment S3 bucket name
#   DEADLINE_JA_ROOT_PREFIX    - Job attachment root prefix in the bucket
#   OPENJD_SESSION_WORKING_DIR - Session working directory path

# Skip if the required env vars aren't available (e.g. local testing without
# the worker agent, or the worker agent hasn't been updated yet).
if [ -z "${DEADLINE_JA_S3_BUCKET:-}" ] || [ -z "${MAYA_VERSION:-}" ]; then
    echo "Plugin Sync: Skipping — DEADLINE_JA_S3_BUCKET or MAYA_VERSION not set."
    return 0 2>/dev/null || exit 0
fi

_SP_PREFIX="${DEADLINE_JA_ROOT_PREFIX:+${DEADLINE_JA_ROOT_PREFIX}/}"
_SP_OS="linux"
if [ "$(uname -s)" = "MINGW"* ] || [ "$(uname -s)" = "MSYS"* ] || [ -n "${OS:-}" ]; then
    _SP_OS="windows"
fi

# Determine plugin download directory
_SP_PLUGIN_DIR="${OPENJD_SESSION_WORKING_DIR:-${TMPDIR:-/tmp}}/deadline-plugins/maya"
mkdir -p "$_SP_PLUGIN_DIR"

# Download generic plugins to the session working directory
_SP_GENERIC_DIR="${OPENJD_SESSION_WORKING_DIR:-${TMPDIR:-/tmp}}/deadline-plugins/generic"
_SP_GENERIC_SRC="s3://${DEADLINE_JA_S3_BUCKET}/${_SP_PREFIX}plugins/generic/"
if [ -n "${OPENJD_SESSION_WORKING_DIR:-}" ]; then
    if aws s3 ls "$_SP_GENERIC_SRC" >/dev/null 2>&1; then
        echo "Plugin Sync: Downloading plugins from $_SP_GENERIC_SRC"
        aws s3 cp "$_SP_GENERIC_SRC" "$_SP_GENERIC_DIR" --recursive --quiet 2>/dev/null || true
    fi
fi

# Download Maya-specific plugins
_SP_DCC_SRC="s3://${DEADLINE_JA_S3_BUCKET}/${_SP_PREFIX}plugins/${_SP_OS}/maya/${MAYA_VERSION}/"

if aws s3 ls "$_SP_DCC_SRC" >/dev/null 2>&1; then
    echo "Plugin Sync: Downloading Maya plugins from $_SP_DCC_SRC"
    aws s3 cp "$_SP_DCC_SRC" "$_SP_PLUGIN_DIR/" --recursive --quiet 2>/dev/null || true
fi

# Append to MAYA_MODULE_PATH if we downloaded any files
if [ -d "$_SP_PLUGIN_DIR" ] && [ -n "$(ls -A "$_SP_PLUGIN_DIR" 2>/dev/null)" ]; then
    export MAYA_MODULE_PATH="${_SP_PLUGIN_DIR}:${MAYA_MODULE_PATH:-}"
    echo "Plugin Sync: MAYA_MODULE_PATH updated with $_SP_PLUGIN_DIR"
else
    echo "Plugin Sync: No Maya plugins found, skipping."
fi

# Export for deactivate script cleanup
export _MAYA_PLUGIN_SYNC_DIR="$_SP_PLUGIN_DIR"

# Clean up temp variables
unset _SP_PREFIX _SP_OS _SP_PLUGIN_DIR _SP_GENERIC_SRC _SP_DCC_SRC
