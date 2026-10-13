#!/bin/bash
# Plugin Sync for Adobe After Effects.
#
# After Effects has no plugin search path environment variable. It scans the
# Plug-ins directory next to aerender.exe at launch, so this hook copies the
# plugins from the job attachments bucket into
# $AE_LOCATION/Plug-ins/deadline-plugin-sync. The matching deactivate hook
# removes that directory so plugins do not persist between sessions.
#
# S3 convention: s3://<bucket>/<root-prefix>/plugins/windows/aftereffects/<version>/
#
# Required environment variables:
#   DEADLINE_JA_S3_BUCKET   - Job attachments bucket, set by the worker agent
#   AE_PLUGIN_SYNC_VERSION  - S3 version folder, set by this package
#   AE_LOCATION             - After Effects installation, set by this package
# Optional:
#   DEADLINE_JA_ROOT_PREFIX - Job attachments root prefix, set by the worker agent

if [ -z "${DEADLINE_JA_S3_BUCKET:-}" ] || [ -z "${AE_PLUGIN_SYNC_VERSION:-}" ] || [ -z "${AE_LOCATION:-}" ]; then
    echo "Plugin Sync: Skipping; DEADLINE_JA_S3_BUCKET, AE_PLUGIN_SYNC_VERSION, or AE_LOCATION is not set." >&2
    return 0 2>/dev/null || exit 0
fi

# Queue environments can start this hook with a PATH that does not resolve the
# AWS CLI, so fall back to its default Windows installation.
_SP_AWS="aws"
if ! command -v aws >/dev/null 2>&1 && [ -x "/c/Program Files/Amazon/AWSCLIV2/aws.exe" ]; then
    _SP_AWS="/c/Program Files/Amazon/AWSCLIV2/aws.exe"
fi

_SP_PREFIX="${DEADLINE_JA_ROOT_PREFIX:+${DEADLINE_JA_ROOT_PREFIX}/}"
_SP_DCC_SRC="s3://${DEADLINE_JA_S3_BUCKET}/${_SP_PREFIX}plugins/windows/aftereffects/${AE_PLUGIN_SYNC_VERSION}/"
_SP_AE_LOCATION="${AE_LOCATION//\\//}"
_SP_PLUGIN_DIR="${_SP_AE_LOCATION%/}/Plug-ins/deadline-plugin-sync"

# Remove any directory left behind by an earlier session in this environment,
# such as one whose deactivate hook could not remove a locked plugin.
rm -rf "$_SP_PLUGIN_DIR" 2>/dev/null

if "$_SP_AWS" s3 ls "$_SP_DCC_SRC" >/dev/null 2>&1; then
    mkdir -p "$_SP_PLUGIN_DIR"
    export _AE_PLUGIN_SYNC_DIR="$_SP_PLUGIN_DIR"
    echo "Plugin Sync: Downloading After Effects plugins from $_SP_DCC_SRC" >&2
    # Skip a startup/ subfolder. Scripts are not plugins and do not belong in Plug-ins.
    if "$_SP_AWS" s3 cp "$_SP_DCC_SRC" "$_SP_PLUGIN_DIR/" --recursive --quiet --exclude "startup/*"; then
        _SP_COUNT=$(find "$_SP_PLUGIN_DIR" -type f | wc -l | tr -d ' ')
        echo "Plugin Sync: Installed plugins into $_SP_PLUGIN_DIR; file count: $_SP_COUNT" >&2
    else
        echo "Plugin Sync: WARNING: Failed to download plugins from $_SP_DCC_SRC; continuing without them." >&2
    fi
else
    echo "Plugin Sync: No After Effects plugins found at $_SP_DCC_SRC" >&2
fi

unset _SP_AWS _SP_PREFIX _SP_DCC_SRC _SP_AE_LOCATION _SP_PLUGIN_DIR _SP_COUNT
