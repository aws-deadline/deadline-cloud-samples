#!/bin/bash
# Plugin Sync for Cinema 4D
# Downloads plugin files from S3 and prepends to g_additionalModulePath.
# Runs after all standard Cinema 4D env vars are set via activate.d.
#
# S3 convention: s3://<bucket>/<prefix>/plugins/<os>/cinema4d/<version>/
# Generic path:  s3://<bucket>/<prefix>/plugins/generic/
#
# Required environment variables (set by the worker agent):
#   DEADLINE_JA_S3_BUCKET       - Job attachment S3 bucket name
#   DEADLINE_JA_ROOT_PREFIX     - Job attachment root prefix in the bucket
#   OPENJD_SESSION_WORKING_DIR  - Session working directory path

# Skip if the required env vars aren't available (e.g. local testing without
# the worker agent, or the worker agent hasn't been updated yet).
if [ -z "${DEADLINE_JA_S3_BUCKET:-}" ] || [ -z "${C4D_VERSION:-}" ] || [ -z "${OPENJD_SESSION_WORKING_DIR:-}" ]; then
    echo "Plugin Sync: Skipping — DEADLINE_JA_S3_BUCKET, C4D_VERSION, or OPENJD_SESSION_WORKING_DIR not set."
    return 0 2>/dev/null || exit 0
fi

_SP_PREFIX="${DEADLINE_JA_ROOT_PREFIX:+${DEADLINE_JA_ROOT_PREFIX}/}"
_SP_OS="linux"
case "$(uname -s)" in
    MINGW*|MSYS*) _SP_OS="windows" ;;
esac

# Determine plugin download directory
_SP_PLUGIN_DIR="${OPENJD_SESSION_WORKING_DIR}/deadline-plugins/cinema4d"
mkdir -p "$_SP_PLUGIN_DIR"

# Download generic plugins (shared across DCCs, not added to g_additionalModulePath —
# these are scripts or data consumed by job templates directly, not Cinema 4D modules).
_SP_GENERIC_DIR="${OPENJD_SESSION_WORKING_DIR}/deadline-plugins/generic"
_SP_GENERIC_SRC="s3://${DEADLINE_JA_S3_BUCKET}/${_SP_PREFIX}plugins/generic/"
if aws s3 ls "$_SP_GENERIC_SRC" >/dev/null 2>&1; then
    echo "Plugin Sync: Downloading generic plugins from $_SP_GENERIC_SRC"
    mkdir -p "$_SP_GENERIC_DIR"
    if ! aws s3 cp "$_SP_GENERIC_SRC" "$_SP_GENERIC_DIR/" --recursive --quiet; then
        echo "Plugin Sync: WARNING — Failed to download generic plugins from $_SP_GENERIC_SRC" >&2
    fi
fi

# Download Cinema4D-specific plugins
_SP_DCC_SRC="s3://${DEADLINE_JA_S3_BUCKET}/${_SP_PREFIX}plugins/${_SP_OS}/cinema4d/${C4D_VERSION}/"
if aws s3 ls "$_SP_DCC_SRC" >/dev/null 2>&1; then
    echo "Plugin Sync: Downloading Cinema 4D plugins from $_SP_DCC_SRC"
    if ! aws s3 cp "$_SP_DCC_SRC" "$_SP_PLUGIN_DIR/" --recursive --quiet; then
        echo "Plugin Sync: WARNING — Failed to download Cinema 4D plugins from $_SP_DCC_SRC" >&2
    fi
fi

# Prepend to g_additionalModulePath if we downloaded any files
# Cinema 4D uses ; as path separator (even on Linux)
if [ -d "$_SP_PLUGIN_DIR" ] && [ -n "$(ls -A "$_SP_PLUGIN_DIR" 2>/dev/null)" ]; then
    export g_additionalModulePath="${_SP_PLUGIN_DIR};${g_additionalModulePath:-}"
    echo "Plugin Sync: g_additionalModulePath updated with $_SP_PLUGIN_DIR"
else
    echo "Plugin Sync: No Cinema 4D plugins found, skipping."
fi

# Clean up temp variables
unset _SP_PREFIX _SP_OS _SP_PLUGIN_DIR _SP_GENERIC_DIR _SP_GENERIC_SRC _SP_DCC_SRC
