#!/usr/bin/env bash
# Install Maxon Redshift and its Maya plug-in. No-op unless WITH_REDSHIFT=1.
#
# Follows conda_recipes/maya-redshift-2026/recipe/build.sh, the recipe proven on
# Deadline Cloud:
#   * The Makeself .run is extracted with `--target DIR --noexec`, which yields
#     Maxon's setup.sh and package.tar.gz.
#   * setup.sh --installpath /usr/redshift (Maxon's default location) extracts the
#     payload. When the package ships a single GPU kernel file, setup.sh also runs
#     `redshiftCmdLine -downloadkernels` to fetch the others, which needs network
#     access during the build.
#   * Plug-ins for the other DCCs are removed and a redshift4maya.mod for this
#     Maya version only is written to /usr/autodesk/modules/maya/<MAYA_VERSION>/.
set -euo pipefail

# shellcheck source=common.sh
source "$(dirname "${BASH_SOURCE[0]}")/common.sh"

if [[ "${WITH_REDSHIFT:-0}" != "1" ]]; then
    log "WITH_REDSHIFT=${WITH_REDSHIFT:-0}; skipping Redshift"
    exit 0
fi

MAYA_VERSION=${MAYA_VERSION:?MAYA_VERSION must be set}
INSTALLERS_DIR=${INSTALLERS_DIR:-/installers}
MAYA_LOCATION=${MAYA_LOCATION:-/usr/autodesk/maya${MAYA_VERSION}}
REDSHIFT_ROOT=${REDSHIFT_ROOT:-/usr/redshift}
MODULES_DIR=/usr/autodesk/modules/maya/${MAYA_VERSION}

installer=$(find_installer "$INSTALLERS_DIR" "$(redshift_installer_glob)") || die \
    "No Redshift installer found. Expected a file matching '$(redshift_installer_glob)'" \
    "(for example redshift_2026.8.1_2741261432_linux_x64.run) directly in the installers" \
    "directory or one subdirectory deep. Download it from https://www.maxon.net/en/downloads"

log "Installing Redshift from $installer"

work=$(mktemp -d /tmp/redshift-install.XXXXXX)
trap 'rm -rf "$work"' EXIT

# --- Extract the Makeself archive (setup.sh + package.tar.gz) -------------------------
sh "$installer" --target "$work/unpack" --noexec > "$work/extract.log" 2>&1 \
    || { cat "$work/extract.log"; die "Extracting $installer failed"; }
[[ -f "$work/unpack/setup.sh" && -f "$work/unpack/package.tar.gz" ]] \
    || die "setup.sh / package.tar.gz not found inside $installer"

# --- Run Maxon's setup.sh ---------------------------------------------------------------
# setup.sh requires root (we are), extracts verbosely and ends with `clear`, so
# capture its output in a log and show only the tail.
log "Running setup.sh --installpath $REDSHIFT_ROOT (this extracts about 3 GB)"
cd "$work/unpack"
if ! TERM=dumb ./setup.sh --installpath "$REDSHIFT_ROOT" > "$work/setup.log" 2>&1; then
    tail -n 40 "$work/setup.log"
    die "Redshift setup.sh failed"
fi
grep -v '^x \|^redshift' "$work/setup.log" | tail -n 15 || true
cd /
rm -rf "$work/unpack"

[[ -x "$REDSHIFT_ROOT/bin/redshiftCmdLine" ]] || die "$REDSHIFT_ROOT/bin/redshiftCmdLine is missing after setup"
plugin_dir="$REDSHIFT_ROOT/redshift4maya/${MAYA_VERSION}"
[[ -f "$plugin_dir/redshift4maya.so" ]] || die \
    "$plugin_dir/redshift4maya.so is missing: this Redshift release does not include a plug-in for Maya ${MAYA_VERSION}." \
    "Available: $(ls "$REDSHIFT_ROOT/redshift4maya" 2> /dev/null | tr '\n' ' ')"

# --- Trim the installation ---------------------------------------------------------------
# Plug-ins for other DCCs and other Maya versions are not needed in this image.
for other in redshift4c4d redshift4houdini redshift4katana redshift4solaris redshift4blender redshift4hydra; do
    if [[ -d "$REDSHIFT_ROOT/$other" ]]; then
        log "Removing $REDSHIFT_ROOT/$other"
        rm -rf "${REDSHIFT_ROOT:?}/$other"
    fi
done
for version_dir in "$REDSHIFT_ROOT"/redshift4maya/20*; do
    [[ -d "$version_dir" && "$(basename "$version_dir")" != "$MAYA_VERSION" ]] || continue
    log "Removing plug-in for Maya $(basename "$version_dir")"
    rm -rf "$version_dir"
done

# Drop any debug information shipped with the binaries (see common.sh).
strip_debug_info "$REDSHIFT_ROOT"

# Redshift's Maya plug-in links against Maya's libraries and the XGen plug-in's
# libAdskSeExpr.so; give it rpaths so it resolves outside a Maya process too.
add_rpath "$plugin_dir/redshift4maya.so" "$MAYA_LOCATION/lib" "$MAYA_LOCATION/plug-ins/xgen/lib"

# --- Maya module ------------------------------------------------------------------------------
# Based on Maxon's redshift4maya.mod.template (kept at $REDSHIFT_ROOT/redshift4maya/
# for reference) and the Deadline Cloud conda recipe, for this Maya version only.
mkdir -p "$MODULES_DIR"
module_dst="$MODULES_DIR/redshift4maya.mod"
log "Writing $module_dst"
{
    echo "+ redshift4maya any $REDSHIFT_ROOT/redshift4maya"
    echo "scripts: common/scripts"
    echo "icons: common/icons"
    echo "plug-ins: $MAYA_VERSION"
    echo "REDSHIFT_COREDATAPATH = $REDSHIFT_ROOT"
    echo "MAYA_CUSTOM_TEMPLATE_PATH +:= common/scripts/NETemplates"
    echo "MAYA_RENDER_DESC_PATH +:= common/rendererDesc"
    echo "REDSHIFT_MAYAEXTENSIONSPATH +:= $MAYA_VERSION/extensions"
    # One procedurals entry per shipped USD build plus the Alembic procedural.
    for usd_dir in "$REDSHIFT_ROOT"/procedurals/usd/*/; do
        [[ -d "$usd_dir" ]] || continue
        echo "REDSHIFT_PROCEDURALSPATH += \"\$REDSHIFT_COREDATAPATH/procedurals/usd/$(basename "$usd_dir")\""
    done
    if [[ -d "$REDSHIFT_ROOT/procedurals/alembic" ]]; then
        echo "REDSHIFT_PROCEDURALSPATH += \"\$REDSHIFT_COREDATAPATH/procedurals/alembic\""
    fi
} > "$module_dst"
sed 's/^/    /' "$module_dst"

# --- Launchers --------------------------------------------------------------------------------
install_launcher redshiftCmdLine "$REDSHIFT_ROOT/bin/redshiftCmdLine"

log "Redshift installed in $REDSHIFT_ROOT ($(du -sh "$REDSHIFT_ROOT" | cut -f1))"
