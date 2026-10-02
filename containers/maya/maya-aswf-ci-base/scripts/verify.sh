#!/usr/bin/env bash
# Build-time verification of the Maya image. None of these checks needs a
# license: Maya is imported and initialized in mayapy only to render one frame
# with the software renderer, which is license-free, and the renderer
# executables are only asked for their version. A command that does try to
# check out a license is given 60 seconds and a license failure is reported
# as a warning, not an error. The one deliberate license attempt, kick against
# a server that does not exist, is a check of the licensing library itself.
#
# Hard failures (exit 1):
#   * a required executable or launcher is missing
#   * mayapy cannot import the maya package
#   * maya-openjd / MayaAdaptor --help fail
#   * the ADP SDK libraries, thin-client XML or ProductInformation.pit are missing
#   * ldd reports "not found" for maya.bin, mayapy.bin, render.bin, AdpSDKCore.so,
#     or any installed renderer plug-in / executable
#   * a /usr/local/bin symlink or launcher points at something that does not exist
#   * an Autodesk licensing library differs from the Maya RPM, or Arnold's CLM
#     hub rejects libadlmint.so ("failed to load ADLM")
#   * a mayapy render to PNG fails, hangs or hits "libpng error: Invalid IHDR data"
set -uo pipefail

# shellcheck source=common.sh
source "$(dirname "${BASH_SOURCE[0]}")/common.sh"

MAYA_VERSION=${MAYA_VERSION:?MAYA_VERSION must be set}
MAYA_LOCATION=${MAYA_LOCATION:-/usr/autodesk/maya${MAYA_VERSION}}
ARNOLD_ROOT=${ARNOLD_ROOT:-/usr/autodesk/arnold/maya${MAYA_VERSION}}
VRAY_ROOT=${VRAY_ROOT:-/usr/ChaosGroup/V-Ray/Maya${MAYA_VERSION}-x64}
REDSHIFT_ROOT=${REDSHIFT_ROOT:-/usr/redshift}
MODULES_DIR=/usr/autodesk/modules/maya/${MAYA_VERSION}

# Anything the checks below leave in the temporary directory (Maya scratch
# files, licensing logs) would be root-owned in the image; everything newer
# than this marker is removed at the end.
TMP_ROOT=${TMPDIR:-/tmp}
tmp_marker=$(mktemp "$TMP_ROOT/verify-marker.XXXXXX")
sleep 1

failures=0
fail() {
    printf '[verify] FAIL: %s\n' "$*" >&2
    failures=$((failures + 1))
}
pass() {
    printf '[verify] ok:   %s\n' "$*"
}
section() {
    printf '\n[verify] === %s ===\n' "$*"
}

# run_check [--tolerant] NAME TIMEOUT COMMAND...
# Runs COMMAND with a timeout and prints the first lines of its output. A
# license-related message in the output or a timeout is a warning; any other
# non-zero status is a failure, or a warning with --tolerant (used for renderer
# executables whose help/version switches may exit non-zero or probe a license
# server). Status 255 with no output is Maya's symptom for a missing ADP SDK and
# is always a failure.
run_check() {
    local tolerant=0
    if [[ $1 == --tolerant ]]; then
        tolerant=1
        shift
    fi
    local name=$1 limit=$2 output status
    shift 2
    output=$(timeout "$limit" "$@" 2>&1)
    status=$?
    if [[ $status -eq 0 ]]; then
        pass "$name"
        [[ -n "$output" ]] && head -n 3 <<< "$output" | sed 's/^/        /'
        return 0
    fi
    if [[ $status -eq 255 && -z "$output" ]]; then
        fail "$name exited with status 255 and printed nothing (Maya does this when AdpSDKCore.so cannot be loaded)"
        return 1
    fi
    if [[ $status -eq 124 ]]; then
        warn "$name timed out after ${limit}s (usually a license check waiting for a server); continuing"
        return 0
    fi
    if grep -qi -E 'licen[cs]e|flexnet|flexlm|adskflex|rlm' <<< "$output"; then
        warn "$name exited with status $status with a license-related message; this is expected without a license server:"
        head -n 5 <<< "$output" | sed 's/^/        /' >&2
        return 0
    fi
    if [[ $tolerant -eq 1 ]]; then
        warn "$name exited with status $status; continuing because this check is informational:"
        head -n 5 <<< "$output" | sed 's/^/        /' >&2
        return 0
    fi
    fail "$name exited with status $status:"
    head -n 20 <<< "$output" | sed 's/^/        /' >&2
    return 1
}

is_installed_arnold()   { [[ -f "$ARNOLD_ROOT/plug-ins/mtoa.so" ]]; }
is_installed_vray()     { [[ -f "$VRAY_ROOT/maya_vray/plug-ins/vrayformaya.so" ]]; }
is_installed_redshift() { [[ -f "$REDSHIFT_ROOT/redshift4maya/${MAYA_VERSION}/redshift4maya.so" ]]; }

# --- Required files ------------------------------------------------------------------
section "Maya installation"
for f in bin/maya.bin bin/mayapy.bin bin/Render bin/maya bin/mayapy; do
    [[ -e "$MAYA_LOCATION/$f" ]] && pass "$MAYA_LOCATION/$f exists" || fail "$MAYA_LOCATION/$f is missing"
done

section "ADP SDK (Maya ${MAYA_VERSION} exits 255 at startup without it)"
adp_names=$(find "$MAYA_LOCATION/lib" -maxdepth 1 -name 'AdpSDK*.so*' -type f -printf '%f ' | sort)
if [[ -n "$adp_names" ]]; then
    pass "ADP SDK libraries present in $MAYA_LOCATION/lib: $adp_names"
else
    fail "No AdpSDK*.so found in $MAYA_LOCATION/lib"
fi

section "Thin-client licensing configuration"
xml="$MAYA_LOCATION/AdlmThinClientCustomEnv.xml"
[[ -f "$xml" ]] && pass "$xml exists" || fail "$xml is missing"
[[ "${AUTODESK_ADLM_THINCLIENT_ENV:-}" == "$xml" ]] \
    && pass "AUTODESK_ADLM_THINCLIENT_ENV points at it" \
    || fail "AUTODESK_ADLM_THINCLIENT_ENV is '${AUTODESK_ADLM_THINCLIENT_ENV:-unset}', expected $xml"
pit_dir=$(sed -n 's#.*<STRING>\(.*\)</STRING>.*#\1#p' "$xml" 2> /dev/null | head -n 1)
if [[ -n "$pit_dir" && -f "$pit_dir/ProductInformation.pit" ]]; then
    pass "$pit_dir/ProductInformation.pit exists"
else
    fail "ProductInformation.pit not found in the ADLM_PIT_FILE_LOCATION '${pit_dir:-?}' from $xml"
fi
[[ "${MAYA_LEGACY_THINCLIENT:-}" == "1" ]] && pass "MAYA_LEGACY_THINCLIENT=1" || fail "MAYA_LEGACY_THINCLIENT is not 1"
for var in ADSKFLEX_LICENSE_FILE redshift_LICENSE VRAY_AUTH_CLIENT_SETTINGS VRAY_AUTH_CLIENT_FILE_PATH; do
    if [[ -n "${!var:-}" ]]; then
        fail "$var is set in the image; license variables must come from the queue environment"
    fi
done
pass "no license server variables baked into the image"

section "Runtime-writable directories"
for d in "${MAYA_APP_DIR:-/var/tmp/maya-app-dir}" /var/flexlm /opt/maya-plugins /opt/maya-plugins/scripts /opt/maya-plugins/plug-ins; do
    [[ -d "$d" ]] && pass "$d exists" || fail "$d is missing"
done
app_dir_mode=$(stat -c %a "${MAYA_APP_DIR:-/var/tmp/maya-app-dir}" 2> /dev/null || echo "")
[[ "$app_dir_mode" == "1777" ]] && pass "MAYA_APP_DIR is world-writable (1777)" || fail "MAYA_APP_DIR mode is '$app_dir_mode', expected 1777"

# --- /usr/local/bin ---------------------------------------------------------------------
section "/usr/local/bin symlinks and launchers"
for entry in /usr/local/bin/*; do
    if [[ -L "$entry" ]]; then
        target=$(readlink -f "$entry" || true)
        if [[ -n "$target" && -e "$target" ]]; then
            pass "$(basename "$entry") -> $target"
        else
            fail "$entry is a dangling symlink (-> $(readlink "$entry"))"
        fi
    elif [[ -f "$entry" ]] && sed -n '2p' "$entry" 2> /dev/null | grep -qF "$LAUNCHER_MARKER"; then
        target=$(sed -n 's/^exec "\(.*\)" "\$@"$/\1/p' "$entry" | head -n 1)
        if [[ -z "$target" || ! -e "$target" ]]; then
            fail "$entry launcher target '${target:-?}' does not exist"
        elif [[ -f "$target" ]] && sed -n '2p' "$target" 2> /dev/null | grep -qF "$LAUNCHER_MARKER"; then
            # A launcher whose target is a launcher exec()s forever; happens when a
            # wrapper is written through a pre-existing symlink onto Autodesk's script.
            fail "$entry launcher target $target is itself a launcher (exec loop)"
        else
            pass "$(basename "$entry") launcher -> $target"
        fi
    fi
done
for cmd in maya mayapy Render maya-openjd MayaAdaptor; do
    command -v "$cmd" > /dev/null 2>&1 && pass "$cmd is on PATH ($(command -v "$cmd"))" || fail "$cmd is not on PATH"
done

# Maya's own launcher scripts must be the ones from the RPM. `rpm -V` lists files
# whose contents differ from the package; ELF files are skipped because
# install_maya.sh strips their debug information on purpose.
if rpm -q "Maya${MAYA_VERSION}_64" > /dev/null 2>&1; then
    modified=""
    while IFS= read -r path; do
        is_elf_file "$path" || modified+="$path"$'\n'
    done < <(rpm -V "Maya${MAYA_VERSION}_64" 2> /dev/null | awk '$1 ~ /5/ { print $NF }' | grep "^$MAYA_LOCATION/bin/" || true)
    if [[ -n "$modified" ]]; then
        fail "scripts in $MAYA_LOCATION/bin differ from the Maya RPM (overwritten during the build):"
        sed 's/^/        /' <<< "$modified" >&2
    else
        pass "scripts in $MAYA_LOCATION/bin are unmodified from the RPM"
    fi
fi

# --- Smoke tests ------------------------------------------------------------------------
section "Smoke tests (no license required)"
run_check "mayapy -c 'import maya'" 120 mayapy -c "import maya; print('mayapy import ok')"
run_check --tolerant "Render -help" 60 Render -help
run_check "maya-openjd --help" 60 bash -c 'maya-openjd --help > /dev/null'
run_check "MayaAdaptor --help" 60 bash -c 'MayaAdaptor --help > /dev/null'

# --- Autodesk licensing libraries ----------------------------------------------------------
# The CLM hub (libAdClmHub) checks the contents of libadlmint.so before using
# it. A build step that modifies the file (the debug-information stripping did,
# once) makes every Arnold render abort with "[clm.v1] error loading a library
# (4)" before a license server is contacted - a failure that only shows up on a
# licensed farm. Two checks catch it at build time:
#   1. `rpm -V` must not report a changed licensing, CLM, identity or analytics
#      file of the Maya RPM. Files the ADP SDK drop replaced on purpose (listed
#      in $ADP_SDK_MANIFEST by install_maya.sh) are the only exception.
#   2. With Arnold installed, kick renders a two-node scene against a license
#      server that does not exist (127.0.0.1). The expected outcome is a
#      checkout error, which proves the hub accepted libadlmint.so and went on
#      to FlexNet; "failed to load ADLM" or "error loading a library" means the
#      library was rejected. Nothing else about kick's output or exit status
#      matters here, and ADCLMHUB_LOG_LEVEL=DEBUG makes the hub log the reason.
#      TMPDIR points the licensing components' logs (AdClmHub-*.log, AdlSdk-*.log,
#      Adlm.log ...) into a scratch directory that is deleted afterwards, so no
#      root-owned files are left in the image's /tmp.
section "Autodesk licensing libraries"
if rpm -q "Maya${MAYA_VERSION}_64" > /dev/null 2>&1; then
    changed=""
    while IFS= read -r line; do
        path=${line##* }
        if [[ -s "$ADP_SDK_MANIFEST" ]] && grep -qxF "$path" "$ADP_SDK_MANIFEST"; then
            continue
        fi
        changed+="        $line"$'\n'
    done < <(rpm -V "Maya${MAYA_VERSION}_64" 2> /dev/null | grep -E -i 'adlm|adclm|adsk' || true)
    if [[ -n "$changed" ]]; then
        fail "Autodesk licensing files differ from the Maya RPM (S = size, 5 = checksum); they must not be stripped or patched:"
        printf '%s' "$changed" >&2
    else
        pass "rpm -V: licensing, CLM, identity and analytics files of the Maya RPM are unmodified"
    fi
fi

if is_installed_arnold; then
    adlm_dir=$(mktemp -d "${TMPDIR:-/tmp}/verify-adlm.XXXXXX")
    cat > "$adlm_dir/scene.ass" <<'EOF'
options { xres 8 yres 8 camera "cam" }
persp_camera { name "cam" }
EOF
    kick_check() {
        (cd "$adlm_dir" && TMPDIR=$adlm_dir ADSKFLEX_LICENSE_FILE=2702@127.0.0.1 ADCLMHUB_LOG_LEVEL=DEBUG \
            timeout 90 kick -dw -dp -v 1 -nostdin -nokeypress "$@" 2>&1) || true
    }
    kick_out=$(kick_check scene.ass)
    if ! grep -qi 'authoriz' <<< "$kick_out"; then
        # The scene did not get as far as licensing; an empty input does.
        kick_out=$(kick_check -i /dev/null)
    fi
    hub_logs=$(find "$adlm_dir" -maxdepth 1 -name 'AdClmHub-*.log' 2> /dev/null || true)
    [[ -n "$hub_logs" ]] && kick_out+=$'\n'$(cat $hub_logs)
    if grep -q -E 'failed to load ADLM|error loading a library' <<< "$kick_out"; then
        fail "Arnold's CLM hub rejected the licensing library (libadlmint.so was modified during the build):"
        grep -E 'clm|ADLM|loading a library' <<< "$kick_out" | head -n 8 | sed 's/^/        /' >&2
    elif grep -q -E 'clm' <<< "$kick_out"; then
        pass "Arnold's CLM hub loads the licensing library and attempts a FlexNet checkout (no server at 127.0.0.1, so it fails):"
        grep -E '\[clm\.v1\]|CHECKOUT' <<< "$kick_out" | head -n 4 | sed 's/^/        /'
    else
        warn "kick produced no licensing diagnostics; cannot confirm the licensing library check:"
        tail -n 8 <<< "$kick_out" | sed 's/^/        /' >&2
    fi
    rm -rf "$adlm_dir"
fi

# --- mayapy PNG render --------------------------------------------------------------------
# The maya-openjd adaptor renders through mayapy. Maya's bundled FreeType exports
# libpng symbols that, under mayapy, interpose the system libpng used by the PNG
# image plug-in: the render then prints "libpng error: Invalid IHDR data" and
# "double free or corruption", and the process hangs. install_maya.sh replaces
# that FreeType; this renders one 64x64 frame of a sphere to PNG with the Maya
# software renderer (which needs no license) the way the adaptor does and fails
# on those messages, on a missing or empty image, or on a hang.
section "mayapy PNG render (adaptor path)"
png_dir=$(mktemp -d "${TMPDIR:-/tmp}/verify-png.XXXXXX")
png_out=$(cd "$png_dir" && timeout 240 mayapy -c "
import maya.standalone
maya.standalone.initialize(name='python')
import maya.cmds as cmds
cmds.polySphere()
cmds.setAttr('defaultRenderGlobals.imageFormat', 32)
cmds.setAttr('defaultResolution.width', 64)
cmds.setAttr('defaultResolution.height', 64)
cmds.setAttr('defaultRenderGlobals.imageFilePrefix', '$png_dir/img', type='string')
print('render:', cmds.render('persp'))
maya.standalone.uninitialize()
" 2>&1)
png_status=$?
png_file=$(find "$png_dir" -name '*.png' -size +0 -type f | head -n 1)
if grep -q -E 'Invalid IHDR|double free|libpng error' <<< "$png_out"; then
    fail "mayapy PNG render hit the libpng interposition problem (is lib/libfreetype.so.6 still Maya's own copy?):"
    grep -E 'libpng|double free' <<< "$png_out" | head -n 5 | sed 's/^/        /' >&2
elif [[ $png_status -eq 124 ]]; then
    fail "mayapy PNG render timed out after 240 s"
    tail -n 10 <<< "$png_out" | sed 's/^/        /' >&2
elif [[ -z "$png_file" ]]; then
    fail "mayapy PNG render (exit status $png_status) produced no PNG file:"
    tail -n 10 <<< "$png_out" | sed 's/^/        /' >&2
elif [[ "$(head -c 8 "$png_file" | od -An -tx1 | tr -d ' \n')" != "89504e470d0a1a0a" ]]; then
    fail "mayapy wrote $(basename "$png_file") but it does not start with the PNG signature"
else
    pass "mayapy rendered $(basename "$png_file") ($(stat -c %s "$png_file") bytes, valid PNG signature) with the software renderer"
fi
rm -rf "$png_dir"

if is_installed_arnold; then
    section "Arnold"
    [[ -f "$MODULES_DIR/mtoa.mod" ]] && pass "$MODULES_DIR/mtoa.mod exists" || fail "$MODULES_DIR/mtoa.mod is missing"
    command -v kick > /dev/null 2>&1 && pass "kick is on PATH" || fail "kick is not on PATH"
    run_check --tolerant "kick --version" 60 kick --version
fi
if is_installed_vray; then
    section "V-Ray"
    mod=$(find "$MODULES_DIR" -maxdepth 1 -name 'VRayForMaya*' -type f | head -n 1)
    [[ -n "$mod" ]] && pass "$mod exists" || fail "$MODULES_DIR/VRayForMaya.module is missing"
    if command -v vray > /dev/null 2>&1; then
        pass "vray is on PATH"
        run_check --tolerant "vray -version" 60 vray -version
    else
        warn "vray standalone is not on PATH; only the Maya plug-in is available"
    fi
fi
if is_installed_redshift; then
    section "Redshift"
    [[ -f "$MODULES_DIR/redshift4maya.mod" ]] && pass "$MODULES_DIR/redshift4maya.mod exists" || fail "$MODULES_DIR/redshift4maya.mod is missing"
    command -v redshiftCmdLine > /dev/null 2>&1 && pass "redshiftCmdLine is on PATH" || fail "redshiftCmdLine is not on PATH"
    run_check --tolerant "redshiftCmdLine --version" 60 redshiftCmdLine --version
fi

# --- ldd scan -----------------------------------------------------------------------------
# Emulates the library search path of a running Maya: the launcher scripts
# prepend $MAYA_LOCATION/lib and the plug-in library directories to
# LD_LIBRARY_PATH. Renderer library directories are added so that libraries the
# renderers ship themselves are found; anything still "not found" is a missing
# system library and fails the build.
section "ldd scan"
ld_dirs=("$MAYA_LOCATION/lib")
for d in "$MAYA_LOCATION"/plug-ins/*/lib; do
    [[ -d "$d" ]] && ld_dirs+=("$d")
done
is_installed_arnold && ld_dirs+=("$ARNOLD_ROOT/bin")
is_installed_vray && ld_dirs+=("$VRAY_ROOT/vray/lib" "$VRAY_ROOT/maya_vray/lib")
is_installed_redshift && ld_dirs+=("$REDSHIFT_ROOT/bin")
scan_ld_path=$(IFS=:; echo "${ld_dirs[*]}")${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}

scan_targets=("$MAYA_LOCATION/bin/maya.bin" "$MAYA_LOCATION/bin/mayapy.bin" "$MAYA_LOCATION/bin/render.bin" "$MAYA_LOCATION/bin/Render")
# Only AdpSDKCore is dlopen()ed at startup. AdpSDKUI (the analytics consent
# dialog) links GTK and WebKitGTK, which are not installed and not needed for
# batch rendering; it is reported below but does not fail the build.
while IFS= read -r lib; do
    scan_targets+=("$lib")
done < <(find "$MAYA_LOCATION/lib" -maxdepth 1 -name 'AdpSDKCore*.so*' -type f | sort)
is_installed_arnold && scan_targets+=("$ARNOLD_ROOT/plug-ins/mtoa.so" "$ARNOLD_ROOT/bin/kick")
# The V-Ray Standalone executable is maya_vray/bin/vray.bin (vray is a shell
# script around it) in V-Ray 7; older layouts had it in vray/bin. Missing
# targets are skipped below.
is_installed_vray && scan_targets+=("$VRAY_ROOT/maya_vray/plug-ins/vrayformaya.so" "$VRAY_ROOT/maya_vray/bin/vray.bin" "$VRAY_ROOT/vray/bin/vray")
is_installed_redshift && scan_targets+=("$REDSHIFT_ROOT/redshift4maya/${MAYA_VERSION}/redshift4maya.so" "$REDSHIFT_ROOT/bin/redshiftCmdLine")

scanned=0
for target in "${scan_targets[@]}"; do
    [[ -e "$target" ]] || continue
    if ! is_elf_file "$target"; then
        printf '[verify]       skipping %s (not an ELF file)\n' "$target"
        continue
    fi
    scanned=$((scanned + 1))
    missing=$(LD_LIBRARY_PATH="$scan_ld_path" ldd "$target" 2>&1 | grep -E 'not found' || true)
    if [[ -n "$missing" ]]; then
        fail "$target has unresolved shared libraries:"
        sed 's/^/        /' <<< "$missing" >&2
    else
        pass "ldd $target"
    fi
done
[[ $scanned -gt 0 ]] || fail "ldd scan found nothing to scan"

while IFS= read -r lib; do
    missing=$(LD_LIBRARY_PATH="$scan_ld_path" ldd "$lib" 2>&1 | grep -E 'not found' | awk '{ print $1 }' | tr '\n' ' ' || true)
    if [[ -n "$missing" ]]; then
        printf '[verify]       info: %s is not loadable (UI-only library): %s\n' "$(basename "$lib")" "$missing"
    fi
done < <(find "$MAYA_LOCATION/lib" -maxdepth 1 -name 'AdpSDK*.so*' ! -name 'AdpSDKCore*' -type f | sort)

# --- Clean up ---------------------------------------------------------------------------------
# The checks above write logs and preferences into the runtime-writable
# directories (Redshift creates REDSHIFT_LOCALDATAPATH/log, mayapy its prefs in
# MAYA_APP_DIR) and may leave scratch files in the temporary directory. Those
# files would be owned by root in the image and could block a container that runs
# as another UID, so leave the directories empty and remove what appeared in
# $TMP_ROOT since the marker was created.
for d in "${MAYA_APP_DIR:-}" "${REDSHIFT_LOCALDATAPATH:-}"; do
    [[ -n "$d" && -d "$d" ]] && find "$d" -mindepth 1 -delete
done
leftovers=$(find "$TMP_ROOT" -mindepth 1 -maxdepth 1 -newer "$tmp_marker" 2> /dev/null || true)
if [[ -n "$leftovers" ]]; then
    printf '[verify]       removing temporary files left by the checks: %s\n' "$(tr '\n' ' ' <<< "$leftovers")"
    # shellcheck disable=SC2086  # one path per line, none with spaces
    rm -rf $leftovers
fi
rm -f "$tmp_marker"

# --- Result ---------------------------------------------------------------------------------
printf '\n'
if [[ $failures -gt 0 ]]; then
    printf '[verify] %d check(s) FAILED\n' "$failures" >&2
    exit 1
fi
log "All checks passed"
