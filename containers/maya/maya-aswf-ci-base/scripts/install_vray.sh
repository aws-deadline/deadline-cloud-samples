#!/usr/bin/env bash
# Install Chaos V-Ray for Maya. No-op unless WITH_VRAY=1.
#
# Follows conda_recipes/maya-vray-2027/recipe/build.sh, the recipe proven on
# Deadline Cloud:
#   * The Chaos installer is run with `-unpackInstall`, which only extracts the
#     payload (vray/, maya_vray/, maya_root/) and performs no interactive setup.
#   * maya_root/modules/VRayForMaya.module is copied to the system-wide module
#     directory /usr/autodesk/modules/maya/<MAYA_VERSION>/ with its relative
#     ../../maya_vray path rewritten to the absolute installation path.
#   * The recipe had to vendor xcb-util-* and libxkbcommon-x11 and put them on
#     LD_LIBRARY_PATH; here the Dockerfile installs those libraries from the
#     distribution instead, so no LD_LIBRARY_PATH manipulation is needed.
set -euo pipefail

# shellcheck source=common.sh
source "$(dirname "${BASH_SOURCE[0]}")/common.sh"

if [[ "${WITH_VRAY:-0}" != "1" ]]; then
    log "WITH_VRAY=${WITH_VRAY:-0}; skipping V-Ray"
    exit 0
fi

MAYA_VERSION=${MAYA_VERSION:?MAYA_VERSION must be set}
INSTALLERS_DIR=${INSTALLERS_DIR:-/installers}
MAYA_LOCATION=${MAYA_LOCATION:-/usr/autodesk/maya${MAYA_VERSION}}
# Chaos's default location for V-Ray for Maya on Linux.
VRAY_ROOT=${VRAY_ROOT:-/usr/ChaosGroup/V-Ray/Maya${MAYA_VERSION}-x64}
MODULES_DIR=/usr/autodesk/modules/maya/${MAYA_VERSION}

installer=$(find_installer "$INSTALLERS_DIR" "$(vray_installer_glob "$MAYA_VERSION")") || die \
    "No V-Ray for Maya installer found. Expected a file matching '$(vray_installer_glob "$MAYA_VERSION")'" \
    "(for example vray_74004_maya${MAYA_VERSION}_dr2_rhel8, the Linux rhel8 build) directly in the" \
    "installers directory or one subdirectory deep. Download it from https://download.chaos.com"
is_elf_file "$installer" || die \
    "$installer is not a Linux executable. Download the Linux (rhel8) build of V-Ray for Maya" \
    "${MAYA_VERSION}, not the Windows or macOS installer."

log "Installing V-Ray for Maya ${MAYA_VERSION} from $installer"

work=$(mktemp -d /tmp/vray-install.XXXXXX)
trap 'rm -rf "$work"' EXIT

# The bind mount is read-only and keeps the host's permission bits, so copy the
# installer to make it executable.
cp "$installer" "$work/vray-installer"
chmod +x "$work/vray-installer"

# --- Unpack -------------------------------------------------------------------
mkdir -p "$VRAY_ROOT"
cd "$VRAY_ROOT"
"$work/vray-installer" -unpackInstall . > "$work/unpack.log" 2>&1 \
    || { tail -n 40 "$work/unpack.log"; die "V-Ray -unpackInstall failed"; }
tail -n 5 "$work/unpack.log" || true
rm -f "$work/vray-installer"

[[ -f "$VRAY_ROOT/maya_vray/plug-ins/vrayformaya.so" ]] \
    || die "maya_vray/plug-ins/vrayformaya.so not found after unpacking; is this a V-Ray for Maya ${MAYA_VERSION} Linux installer?"
module_src=$(find "$VRAY_ROOT/maya_root" -name 'VRayForMaya*.module' -type f | head -n 1)
[[ -n "$module_src" ]] || die "maya_root/modules/VRayForMaya.module not found after unpacking"

# Not needed on a render node.
rm -rf "$VRAY_ROOT/vray/samples" "$VRAY_ROOT/vray/docs" "$VRAY_ROOT/maya_vray/docs"

# Drop any debug information shipped with the binaries (see common.sh).
strip_debug_info "$VRAY_ROOT"

# --- rpaths -----------------------------------------------------------------------
# vrayformaya.so needs libvray.so and friends from vray/lib; the libraries in
# vray/lib and maya_vray/lib need each other. Add $ORIGIN-relative rpaths so they
# resolve without LD_LIBRARY_PATH (same as the conda recipe). Skipped silently
# when patchelf is not installed.
for lib in "$VRAY_ROOT"/maya_vray/lib/*.so*; do
    add_rpath "$lib" '$ORIGIN'
done
for lib in "$VRAY_ROOT"/vray/lib/*.so*; do
    add_rpath "$lib" '$ORIGIN'
done
add_rpath "$VRAY_ROOT/maya_vray/plug-ins/vrayformaya.so" '$ORIGIN/../../vray/lib' '$ORIGIN/../lib' "$MAYA_LOCATION/lib"

# --- Maya module ------------------------------------------------------------------
# The shipped module refers to the plug-in tree as ../../maya_vray, relative to
# maya_root/modules/. Rewrite that to the absolute path so the module can live in
# the system module directory. The pattern is kept generic (any module name /
# version, optional MAYAVERSION:/PLATFORM: qualifiers) and verified afterwards.
mkdir -p "$MODULES_DIR"
module_dst="$MODULES_DIR/VRayForMaya.module"
cp "$module_src" "$module_dst"
sed -E -i "s#^(\+ .*[[:space:]])\.\./\.\./maya_vray[[:space:]]*\$#\1${VRAY_ROOT}/maya_vray#" "$module_dst"
if grep -Eq "^\+ .*[[:space:]]${VRAY_ROOT}/maya_vray\$" "$module_dst"; then
    log "Rewrote the module path in $module_dst to $VRAY_ROOT/maya_vray"
else
    cat "$module_dst"
    die "Could not rewrite the '+ ... ../../maya_vray' line in $(basename "$module_src")"
fi
log "Module file content:"
sed 's/^/    /' "$module_dst"

# Chaos's installer copies the rest of maya_root/ into the Maya installation
# (renderer descriptions and similar). Do the same without overwriting Maya files.
if [[ -d "$VRAY_ROOT/maya_root" ]]; then
    while IFS= read -r -d '' entry; do
        name=$(basename "$entry")
        [[ "$name" == modules ]] && continue
        log "Copying maya_root/$name into $MAYA_LOCATION/"
        cp -a --no-clobber "$entry" "$MAYA_LOCATION/"
    done < <(find "$VRAY_ROOT/maya_root" -mindepth 1 -maxdepth 1 -print0)
fi

# --- Launchers --------------------------------------------------------------------
# The V-Ray Standalone renderer (renders .vrscene files). V-Ray 7 ships it as
# maya_vray/bin/vray, a script that sets LD_LIBRARY_PATH and runs vray.bin next
# to it; older layouts put it in vray/bin, which is checked first.
if [[ -e "$VRAY_ROOT/vray/bin/vray" ]]; then
    install_launcher vray "$VRAY_ROOT/vray/bin/vray"
elif [[ -e "$VRAY_ROOT/maya_vray/bin/vray" ]]; then
    install_launcher vray "$VRAY_ROOT/maya_vray/bin/vray"
else
    warn "No vray standalone executable found under $VRAY_ROOT; only the Maya plug-in is available"
fi

log "V-Ray installed in $VRAY_ROOT ($(du -sh "$VRAY_ROOT" | cut -f1))"
