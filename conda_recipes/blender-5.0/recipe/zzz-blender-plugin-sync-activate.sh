#!/bin/bash
# Plugin Sync for Blender
# Downloads plugin files from S3, configures BLENDER_USER_SCRIPTS, then
# installs and enables addons via a one-shot headless Blender call so the
# enabled state persists into userpref.blend for subsequent Blender
# invocations in the same session.
#
# Why one-shot install at activate time (not a startup script):
#   On Blender 5.0.x, scripts in BLENDER_USER_SCRIPTS/startup/ run with
#   bpy.context set to _RestrictContext. From that context:
#     - bpy.ops.preferences.addon_install raises AttributeError on
#       view_layer/scene attributes.
#     - addon_utils.enable() can't import the addon module because the
#       addon hasn't been registered in Blender's preferences yet.
#   Running install + enable from --python-expr bypasses the restricted
#   context. save_userpref() then persists enabled-addon state so all
#   later `blender` calls in the session pick it up automatically.
#
# Runs after standard Blender env vars are set (zzz- prefix).
#
# S3 convention: s3://<bucket>/<prefix>/plugins/<os>/blender/<version>/
# Generic path:  s3://<bucket>/<prefix>/plugins/generic/
#
# Required environment variables (set by the worker agent):
#   DEADLINE_JA_S3_BUCKET      - Job attachment S3 bucket name
#   DEADLINE_JA_ROOT_PREFIX    - Job attachment root prefix in the bucket
#   OPENJD_SESSION_WORKING_DIR - Session working directory path

# Skip if the required env vars aren't available.
if [ -z "${DEADLINE_JA_S3_BUCKET:-}" ] || [ -z "${BLENDER_VERSION:-}" ]; then
    echo "Plugin Sync: Skipping — DEADLINE_JA_S3_BUCKET or BLENDER_VERSION not set." >&2
    return 0 2>/dev/null || exit 0
fi

_SP_PREFIX="${DEADLINE_JA_ROOT_PREFIX:+${DEADLINE_JA_ROOT_PREFIX}/}"
_SP_OS="linux"
case "$(uname -s)" in
    MINGW*|MSYS*|CYGWIN*) _SP_OS="windows" ;;
esac

_SP_SESSION_ROOT="${OPENJD_SESSION_WORKING_DIR:-${TMPDIR:-/tmp}}"
_SP_PLUGIN_DIR="$_SP_SESSION_ROOT/deadline-plugins/blender"
mkdir -p "$_SP_PLUGIN_DIR"

# Generic plugins
_SP_GENERIC_DIR="$_SP_SESSION_ROOT/deadline-plugins/generic"
_SP_GENERIC_SRC="s3://${DEADLINE_JA_S3_BUCKET}/${_SP_PREFIX}plugins/generic/"
if aws s3 ls "$_SP_GENERIC_SRC" >/dev/null 2>&1; then
    mkdir -p "$_SP_GENERIC_DIR"
    echo "Plugin Sync: Downloading generic plugins from $_SP_GENERIC_SRC" >&2
    aws s3 cp "$_SP_GENERIC_SRC" "$_SP_GENERIC_DIR/" --recursive --quiet 2>/dev/null || true
fi

# Blender-specific plugins
_SP_DCC_SRC="s3://${DEADLINE_JA_S3_BUCKET}/${_SP_PREFIX}plugins/${_SP_OS}/blender/${BLENDER_VERSION}/"
if aws s3 ls "$_SP_DCC_SRC" >/dev/null 2>&1; then
    echo "Plugin Sync: Downloading Blender plugins from $_SP_DCC_SRC" >&2
    aws s3 cp "$_SP_DCC_SRC" "$_SP_PLUGIN_DIR/" --recursive --quiet 2>/dev/null || true
fi

if [ ! -d "$_SP_PLUGIN_DIR" ] || [ -z "$(ls -A "$_SP_PLUGIN_DIR" 2>/dev/null)" ]; then
    echo "Plugin Sync: No Blender plugins found, skipping." >&2
    unset _SP_PREFIX _SP_OS _SP_SESSION_ROOT _SP_GENERIC_DIR _SP_GENERIC_SRC _SP_DCC_SRC _SP_PLUGIN_DIR
    return 0 2>/dev/null || exit 0
fi

# Reorganize into addons/. Top-level dirs become addon packages.
mkdir -p "$_SP_PLUGIN_DIR/addons"
find "$_SP_PLUGIN_DIR" -maxdepth 1 -type f \( -name '*.py' -o -name '*.zip' \) | while read -r f; do
    mv "$f" "$_SP_PLUGIN_DIR/addons/"
done
find "$_SP_PLUGIN_DIR" -maxdepth 1 -mindepth 1 -type d ! -name addons | while read -r d; do
    _target="$_SP_PLUGIN_DIR/addons/$(basename "$d")"
    if [ -d "$_target" ]; then
        cp -rf "$d"/* "$_target"/ 2>/dev/null || true
        rm -rf "$d"
    else
        mv "$d" "$_SP_PLUGIN_DIR/addons/"
    fi
done

export BLENDER_USER_SCRIPTS="$_SP_PLUGIN_DIR"

# Use a session-scoped user-config dir so the userpref.blend we write
# below doesn't leak across sessions or interfere with the worker user's
# own Blender config.
_SP_USER_CONFIG="$_SP_SESSION_ROOT/deadline-plugins/blender-config"
mkdir -p "$_SP_USER_CONFIG"
export BLENDER_USER_CONFIG="$_SP_USER_CONFIG"

echo "Plugin Sync: BLENDER_USER_SCRIPTS=$_SP_PLUGIN_DIR" >&2
echo "Plugin Sync: BLENDER_USER_CONFIG=$_SP_USER_CONFIG" >&2

# Debug log we can inspect from the task script. Lets us verify the
# activate-time bootstrap actually ran end-to-end since stderr from
# activate.d/*.sh is dropped by conda-queue-env-enter.
_SP_DEBUG_LOG="$_SP_SESSION_ROOT/plugin-sync-activate.log"
{
    echo "=== Plugin Sync activate ($(date -u +%Y-%m-%dT%H:%M:%SZ)) ==="
    echo "BLENDER_USER_SCRIPTS=$_SP_PLUGIN_DIR"
    echo "BLENDER_USER_CONFIG=$_SP_USER_CONFIG"
    echo "addons/:"
    ls -la "$_SP_PLUGIN_DIR/addons/"
} > "$_SP_DEBUG_LOG"

# Run the bootstrap. The bootstrap script lives in the conda env at
# $CONDA_PREFIX/share/blender-plugin-sync/ — see build.sh.
_SP_BOOTSTRAP_PY="$CONDA_PREFIX/share/blender-plugin-sync/plugin_sync_bootstrap.py"
if [ ! -f "$_SP_BOOTSTRAP_PY" ]; then
    echo "Plugin Sync: WARNING - bootstrap script not found at $_SP_BOOTSTRAP_PY" >&2
    unset _SP_PREFIX _SP_OS _SP_SESSION_ROOT _SP_GENERIC_DIR _SP_GENERIC_SRC \
          _SP_DCC_SRC _SP_PLUGIN_DIR _SP_USER_CONFIG _SP_BOOTSTRAP_PY _SP_DEBUG_LOG
    return 0 2>/dev/null || exit 0
fi

echo "Plugin Sync: Bootstrapping addons via headless Blender..." >&2
"$BLENDER_LOCATION/blender" -b --python "$_SP_BOOTSTRAP_PY" 2>&1 | tee -a "$_SP_DEBUG_LOG" >&2
_BOOTSTRAP_RC=${PIPESTATUS[0]}
echo "=== bootstrap exit code: $_BOOTSTRAP_RC ===" >> "$_SP_DEBUG_LOG"
if [ "$_BOOTSTRAP_RC" -ne 0 ]; then
    echo "Plugin Sync: WARNING - bootstrap blender call exited $_BOOTSTRAP_RC" >&2
fi

unset _SP_PREFIX _SP_OS _SP_SESSION_ROOT _SP_GENERIC_DIR _SP_GENERIC_SRC \
      _SP_DCC_SRC _SP_PLUGIN_DIR _SP_USER_CONFIG _SP_BOOTSTRAP_PY \
      _SP_DEBUG_LOG _BOOTSTRAP_RC
