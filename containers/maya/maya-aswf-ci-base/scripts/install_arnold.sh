#!/usr/bin/env bash
# Install Arnold for Maya (MtoA). No-op unless WITH_ARNOLD=1.
#
# Payload selection:
#   * Preferred: a standalone MtoA Makeself installer (MtoA-*-linux-<MAYA_VERSION>.run)
#     downloaded from Autodesk Account. `sh <run> --noexec --target DIR` extracts
#     it without running anything.
#   * Fallback: the MtoA payload bundled inside the Maya installer archive
#     (Packages/package.tgz + Packages/unix_installer.py).
#
# Both payloads are the same shape: a package.tgz plus Autodesk's
# unix_installer.py. That installer, when run as `python3 unix_installer.py
# <MAYA_VERSION> linux silent`, extracts package.tgz to
# /usr/autodesk/arnold/maya<MAYA_VERSION>, writes mtoa.mod there and copies it to
# /usr/autodesk/modules/maya/<MAYA_VERSION>/ ... and then runs the bundled
# Autodesk CLM licensing installer (license/ArnoldLicensing-*.run --silent) and
# LicensingUpdater. Those licensing components are not wanted in a container
# that uses thin-client licensing (see install_maya.sh), so this script performs
# the same extraction and module setup itself and skips the licensing step. The
# mtoa.mod content below is exactly what unix_installer.py writes. This also
# matches the proven Deadline Cloud recipe conda_recipes/maya-mtoa-2027.
set -euo pipefail

# shellcheck source=common.sh
source "$(dirname "${BASH_SOURCE[0]}")/common.sh"

if [[ "${WITH_ARNOLD:-0}" != "1" ]]; then
    log "WITH_ARNOLD=${WITH_ARNOLD:-0}; skipping Arnold"
    exit 0
fi

MAYA_VERSION=${MAYA_VERSION:?MAYA_VERSION must be set}
INSTALLERS_DIR=${INSTALLERS_DIR:-/installers}
MAYA_LOCATION=${MAYA_LOCATION:-/usr/autodesk/maya${MAYA_VERSION}}
ARNOLD_ROOT=${ARNOLD_ROOT:-/usr/autodesk/arnold/maya${MAYA_VERSION}}
MODULES_DIR=/usr/autodesk/modules/maya/${MAYA_VERSION}

work=$(mktemp -d /tmp/arnold-install.XXXXXX)
trap 'rm -rf "$work"' EXIT

# --- Locate the payload ---------------------------------------------------------
if mtoa_run=$(find_installer "$INSTALLERS_DIR" "$(mtoa_installer_glob "$MAYA_VERSION")"); then
    log "Using the MtoA installer $mtoa_run"
    # Makeself: extract only, do not run the embedded unix_installer.sh.
    sh "$mtoa_run" --noexec --target "$work/mtoa" > "$work/extract.log" 2>&1 \
        || { cat "$work/extract.log"; die "Extracting $mtoa_run failed"; }
    payload=$(find "$work/mtoa" -name package.tgz -type f | head -n 1)
    [[ -n "$payload" ]] || die "package.tgz not found inside $mtoa_run"
else
    maya_archive=$(find_installer "$INSTALLERS_DIR" "$(maya_installer_glob "$MAYA_VERSION")") || die \
        "No MtoA installer matching '$(mtoa_installer_glob "$MAYA_VERSION")' and no Maya archive" \
        "matching '$(maya_installer_glob "$MAYA_VERSION")' found under $INSTALLERS_DIR"
    log "No MtoA-*.run supplied; using the MtoA payload bundled in $(basename "$maya_archive")"
    tar -xzf "$maya_archive" -C "$work" --wildcards "*Packages/package.tgz"
    payload=$(find "$work" -path "*Packages/package.tgz" -type f | head -n 1)
    [[ -n "$payload" ]] || die "Packages/package.tgz not found inside $maya_archive"
fi

# --- Extract --------------------------------------------------------------------
log "Extracting MtoA into $ARNOLD_ROOT"
mkdir -p "$ARNOLD_ROOT"
tar -xzf "$payload" -C "$ARNOLD_ROOT"
rm -f "$payload"

[[ -f "$ARNOLD_ROOT/plug-ins/mtoa.so" ]] || die "plug-ins/mtoa.so is missing from the MtoA payload"
[[ -f "$ARNOLD_ROOT/bin/kick" ]] || die "bin/kick is missing from the MtoA payload"

# Not needed on a render node: documentation and the Autodesk licensing installers.
rm -rf "$ARNOLD_ROOT/docs" \
    "$ARNOLD_ROOT/license/installer" \
    "$ARNOLD_ROOT/license/LicensingUpdater"
find "$ARNOLD_ROOT/license" -maxdepth 1 -name 'ArnoldLicensing-*.run' -delete 2> /dev/null || true

# unix_installer.py marks these executable explicitly; tar normally preserves the
# bits, but do it anyway so a repacked payload still works.
for tool in kick maketx noice oslc oslinfo lmutil rlmutil ArnoldLicenseManager; do
    [[ -f "$ARNOLD_ROOT/bin/$tool" ]] && chmod +x "$ARNOLD_ROOT/bin/$tool"
done

# Drop any debug information shipped with the binaries (see common.sh).
strip_debug_info "$ARNOLD_ROOT"

# Arnold procedurals link against libAdskSeExpr.so from Maya's XGen plug-in, and
# the render view library against Maya's own libraries. Give them rpaths so they
# resolve outside a Maya process as well (what the conda recipe does).
add_rpath "$ARNOLD_ROOT/bin/libai_renderview.so" "$MAYA_LOCATION/lib"
for lib in "$ARNOLD_ROOT"/procedurals/*.so; do
    add_rpath "$lib" "$MAYA_LOCATION/plug-ins/xgen/lib" "$MAYA_LOCATION/lib"
done

# --- Maya module ----------------------------------------------------------------
# Identical to the module written by Autodesk's unix_installer.py.
log "Writing $MODULES_DIR/mtoa.mod"
mkdir -p "$MODULES_DIR"
cat > "$ARNOLD_ROOT/mtoa.mod" <<EOF
+ mtoa any $ARNOLD_ROOT
PATH +:= bin
MAYA_CUSTOM_TEMPLATE_PATH +:= scripts/mtoa/ui/templates
MAYA_SCRIPT_PATH +:= scripts/mtoa/mel
MAYA_RENDER_DESC_PATH += $ARNOLD_ROOT
MAYA_PXR_PLUGINPATH_NAME += $ARNOLD_ROOT/usd
MATERIALX_SEARCH_PATH +:= materialx/arnold
MATERIALX_SEARCH_PATH +:= materialx/targets
PXR_MTLX_PLUGIN_SEARCH_PATHS +:= usd/materialx
EOF
cp "$ARNOLD_ROOT/mtoa.mod" "$MODULES_DIR/mtoa.mod"

# unix_installer.py also registers the package with Autodesk's ApplicationPlugins.
if [[ -f "$ARNOLD_ROOT/PackageContents.xml" ]]; then
    mkdir -p /usr/autodesk/ApplicationPlugins/mtoa
    cp "$ARNOLD_ROOT/PackageContents.xml" /usr/autodesk/ApplicationPlugins/mtoa/PackageContents.xml
fi

# --- Launchers ------------------------------------------------------------------
install_launcher kick "$ARNOLD_ROOT/bin/kick"
for tool in noice oslc oslinfo maketx; do
    # Do not shadow tools the base image may already provide (for example OIIO's maketx).
    if [[ -f "$ARNOLD_ROOT/bin/$tool" && ! -e "/usr/local/bin/$tool" ]]; then
        install_launcher "$tool" "$ARNOLD_ROOT/bin/$tool"
    fi
done

log "Arnold installed in $ARNOLD_ROOT ($(du -sh "$ARNOLD_ROOT" | cut -f1))"
