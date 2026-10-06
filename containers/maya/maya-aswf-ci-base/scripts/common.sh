#!/usr/bin/env bash
# Shared helpers for the Maya container build.
#
# This file is sourced (not executed) by build.sh on the host and by every
# scripts/install_*.sh inside the image, so the installer filename patterns are
# defined in exactly one place and the host-side pre-flight check in build.sh
# agrees with what the container-side scripts look for.

# ---------------------------------------------------------------------------
# Installer filename patterns
#
# Each function prints a shell glob that matches the vendor's download for the
# given Maya version. The installers are located under the directory passed to
# `docker build --build-context installers=DIR`, either directly in that
# directory or exactly one subdirectory deep (for example DIR/Maya2027/...).
# ---------------------------------------------------------------------------

# Autodesk Maya Linux archive, for example Autodesk_Maya_2027_Linux_64bit.tgz or
# Autodesk_Maya_2027_1_Update_Linux_64bit.tgz.
maya_installer_glob() {
    echo "Autodesk_Maya_${1}*_Linux_64bit.tgz"
}

# Arnold for Maya (MtoA) Makeself installer, for example MtoA-5.6.3-linux-2027.run.
# Optional: when absent, install_arnold.sh falls back to the MtoA payload that
# ships inside the Maya archive.
mtoa_installer_glob() {
    echo "MtoA-*-linux-${1}.run"
}

# Chaos V-Ray for Maya Linux installer, for example vray_74004_maya2027_dr2_rhel8.
# Chaos ships the Linux build without a file extension; the Windows build of the
# same release matches this pattern too, so callers check for an ELF file.
vray_installer_glob() {
    echo "vray_*_maya${1}*"
}

# Maxon Redshift Linux Makeself installer, for example
# redshift_2026.8.1_2741261432_linux_x64.run. Not Maya-version specific.
redshift_installer_glob() {
    echo "redshift_*_linux_x64.run"
}

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

log() {
    printf '[%s] %s\n' "$(basename "$0")" "$*"
}

warn() {
    printf '[%s] WARNING: %s\n' "$(basename "$0")" "$*" >&2
}

die() {
    printf '[%s] ERROR: %s\n' "$(basename "$0")" "$*" >&2
    exit 1
}

# ---------------------------------------------------------------------------
# find_installer DIR GLOB
#
# Prints the path of the file matching GLOB directly under DIR or one
# subdirectory deep. When several files match, the highest version (sort -V)
# wins and a warning is printed. Returns 1 when nothing matches.
# ---------------------------------------------------------------------------
find_installer() {
    local dir=$1 pattern=$2 candidate
    local -a matches=()

    [[ -d "$dir" ]] || return 1

    shopt -s nullglob
    # shellcheck disable=SC2086  # $pattern is intentionally expanded as a glob
    for candidate in "$dir"/$pattern "$dir"/*/$pattern; do
        [[ -f "$candidate" ]] && matches+=("$candidate")
    done
    shopt -u nullglob

    [[ ${#matches[@]} -gt 0 ]] || return 1

    if [[ ${#matches[@]} -gt 1 ]]; then
        warn "Several files match '$pattern' under $dir; using the newest:"
        printf '    %s\n' "${matches[@]}" >&2
    fi
    printf '%s\n' "${matches[@]}" | sort -V | tail -n 1
}

# ---------------------------------------------------------------------------
# is_elf_file FILE
#
# Succeeds when FILE starts with the ELF magic number. Used to reject a Windows
# installer that happens to match a Linux installer pattern. Only needs od,
# which is POSIX, so it works on the build host as well as inside the image.
# ---------------------------------------------------------------------------
is_elf_file() {
    [[ -f "$1" ]] || return 1
    [[ "$(head -c 4 "$1" | od -An -tx1 | tr -d ' \n')" == "7f454c46" ]]
}

# ---------------------------------------------------------------------------
# install_launcher NAME TARGET
#
# Writes /usr/local/bin/NAME as a tiny wrapper that exec()s TARGET. A wrapper is
# used instead of a symlink because several Autodesk launchers (maya, mayapy,
# Render) derive the installation root from the path they were invoked through,
# and a symlink in /usr/local/bin would make them look for Maya's libraries in
# /usr/local/lib. The wrappers let `docker exec <id> Render ...` work with no
# shell profile and make the image compatible with queue environments that call
# /usr/local/bin/<command> explicitly. The second line is a marker that
# scripts/verify.sh parses to check that every launcher target exists.
#
# The destination is removed before it is written. The Maya RPM's %post
# scriptlet symlinks /usr/local/bin/maya and /usr/local/bin/Render to the
# scripts in $MAYA_LOCATION/bin; writing through such a symlink would replace
# Autodesk's script with a wrapper that exec()s itself in an endless loop.
# ---------------------------------------------------------------------------
LAUNCHER_MARKER='# maya-container launcher'

# Written by install_maya.sh: one path per line for every file the Autodesk
# Desktop Analytics SDK zip installed into $MAYA_LOCATION/lib. Some of them
# replace files owned by the Maya RPM; verify.sh reads the list so that its
# `rpm -V` integrity check of the licensing libraries can ignore those.
ADP_SDK_MANIFEST=${ADP_SDK_MANIFEST:-/opt/maya-container/adp-sdk-files.txt}

install_launcher() {
    local name=$1 target=$2
    local dest="/usr/local/bin/$name"
    [[ -n "$name" ]] || die "install_launcher: missing launcher name"
    [[ -e "$target" ]] || die "Cannot create launcher $name: $target does not exist"
    if [[ -f "$target" ]] && sed -n '2p' "$target" 2> /dev/null | grep -qF "$LAUNCHER_MARKER"; then
        die "Cannot create launcher $name: $target is itself a launcher (would loop)"
    fi
    rm -f "$dest"
    cat > "$dest" <<EOF
#!/bin/sh
$LAUNCHER_MARKER
exec "$target" "\$@"
EOF
    chmod 755 "$dest"
    log "Installed $dest -> $target"
}

# ---------------------------------------------------------------------------
# is_autodesk_licensing_file FILE
#
# Succeeds when FILE (by its base name, case-insensitively) belongs to the
# Autodesk licensing, identity or desktop analytics (ADP) components. These
# files must be installed exactly as the vendor ships them: their loaders check
# the file contents before use. The Autodesk CLM hub (libAdClmHub) reads the
# whole of libadlmint.so and refuses it when it has been modified; a stripped
# copy made it log "Init() failed to load ADLM", Arnold then reported
# "[clm.v1] error loading a library (4)" and every render on the farm aborted
# before the license server was even contacted. Matches, for example:
#   libadlmint.so*, libadlmPIT.so*, libadlmutil.so*, adlmreg    (AdLM / FlexNet)
#   libAdClmHub.so*                                             (CLM hub)
#   libAdskLicensingSDK.so*, libAdskIdentitySDK.so*             (licensing / identity)
#   AdpSDKCore.so, AdpSDKUI.so, libAdpIPC.so, ADPClientService  (desktop analytics)
#   ProductInformation.pit                                      (not ELF anyway)
# The pattern is deliberately wide (*clm*, *adsk*.so*): skipping a few more
# files costs nothing, modifying one of these costs every render.
# ---------------------------------------------------------------------------
is_autodesk_licensing_file() {
    local name
    name=$(basename "$1" | tr '[:upper:]' '[:lower:]')
    case "$name" in
        *adlm* | *adclm* | *clm* | *adsklicens* | *adskidentity* | *adp* | *adsk*.so* | productinformation.pit)
            return 0 ;;
    esac
    return 1
}

# ---------------------------------------------------------------------------
# strip_debug_info DIR...
#
# Removes the DWARF debug sections from the shared libraries and executables
# below the given directories. Maya ships a number of libraries with full debug
# information (libopenvdb alone is 1.3 GB, of which 1.2 GB is debug data), which
# is of no use on a render node but makes the image several gigabytes larger
# and slower to pull. `strip --strip-debug` only drops the .debug_* sections and
# keeps the dynamic and regular symbol tables, so dlopen/dlsym, ldd and
# backtraces keep working. Only ELF files that `file` reports as carrying
# debug_info are touched; a failure on an individual file is a warning.
#
# The Autodesk licensing, identity and analytics libraries are never touched,
# whatever they contain (see is_autodesk_licensing_file above): stripping
# libadlmint.so broke Arnold licensing on the farm.
# ---------------------------------------------------------------------------
strip_debug_info() {
    if ! command -v strip > /dev/null 2>&1 || ! command -v file > /dev/null 2>&1; then
        warn "strip or file is not available; leaving debug information in place"
        return 0
    fi
    local before after count=0 skipped=0 f
    before=$(du -sb "$@" | awk '{ s += $1 } END { print s }')
    while IFS= read -r -d '' f; do
        is_elf_file "$f" || continue
        if is_autodesk_licensing_file "$f"; then
            # Integrity-checked by its loader; leave the vendor file byte for byte.
            skipped=$((skipped + 1))
            continue
        fi
        file -b "$f" | grep -q 'with debug_info' || continue
        if strip --strip-debug "$f" 2> /dev/null; then
            count=$((count + 1))
        else
            warn "could not strip debug information from $f"
        fi
    done < <(find "$@" -type f -size +1M ! -name '*.a' -print0)
    after=$(du -sb "$@" | awk '{ s += $1 } END { print s }')
    log "Stripped debug information from $count file(s): $(awk -v b="$before" -v a="$after" \
        'BEGIN { printf "%.1f GB -> %.1f GB", b / 1e9, a / 1e9 }') under $*" \
        "(skipped $skipped Autodesk licensing/analytics file(s))"
}

# ---------------------------------------------------------------------------
# add_rpath FILE RPATH...
#
# Appends RPATH entries to an ELF file with patchelf when patchelf is available
# and FILE is a dynamic ELF object. Silently skips anything else so that it can
# be used on globs that may include scripts or data files. Implemented with
# --print-rpath / --set-rpath because the patchelf in Rocky Linux 8 (0.12) has
# no --add-rpath; entries that are already present are not duplicated, and a
# file that already has every entry is not rewritten at all.
# ---------------------------------------------------------------------------
add_rpath() {
    local file=$1
    shift
    command -v patchelf > /dev/null 2>&1 || return 0
    [[ -f "$file" && ! -L "$file" ]] || return 0
    local current rpath original
    current=$(patchelf --print-rpath "$file" 2> /dev/null) || return 0
    original=$current
    for rpath in "$@"; do
        case ":$current:" in
            *":$rpath:"*) ;;
            *) current="${current:+$current:}$rpath" ;;
        esac
    done
    # Leave the file byte for byte as shipped when nothing needs adding.
    [[ "$current" == "$original" ]] && return 0
    patchelf --set-rpath "$current" "$file" || warn "patchelf could not set the rpath of $file"
}
