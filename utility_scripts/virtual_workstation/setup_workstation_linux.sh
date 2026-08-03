#!/usr/bin/env bash
# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0
#
# Example: pre-configure a Linux workstation for AWS Deadline Cloud submission.
#
# Installs Blender, the Deadline Cloud submitter, and Deadline Cloud monitor,
# then creates a monitor profile so an artist only has to sign in.
#
# This is a worked example rather than a general-purpose tool. It targets Ubuntu
# 22.04 on x86-64, which is the last release carrying the libwebkit2gtk-4.0-37
# that Deadline Cloud monitor needs. Edit the constants below for your
# environment. Run as root during provisioning (EC2 user data, an AMI bake, or by
# hand).
#
# Usage: setup_workstation_linux.sh MONITOR_URL [WORKSTATION_USER]
#
#   MONITOR_URL       https://<subdomain>.<region>.deadlinecloud.amazonaws.com/
#   WORKSTATION_USER  Account that signs in to the monitor. The profile is written
#                     to this user's home directory. Defaults to SUDO_USER when
#                     run under sudo. Required otherwise, including under EC2 user
#                     data and in an AMI bake, where there is no account to infer.

set -euo pipefail

# ---------------------------------------------------------------------------
# Edit these for your environment
# ---------------------------------------------------------------------------

BLENDER_VERSION="4.5.0"

# The submitter's installer components for this DCC: the submitter plug-in itself,
# and the specific DCC version it integrates with. Both change together when you
# switch DCC; see "Adapting to another DCC".
SUBMITTER_COMPONENT="deadline_cloud_for_blender"
BLENDER_COMPONENT="blender_45"

# download.blender.org rejects some automated clients, so this points at
# Blender's official mirror redirector, which forwards to a nearby mirror.
# Point it at an internal mirror if you host the archives yourself.
BLENDER_MIRROR="https://mirror.blender.org/release"

BLENDER_PREFIX="/opt/blender"
SUBMITTER_PREFIX="/opt/DeadlineCloudSubmitter"

DOWNLOADS_BASE="https://downloads.deadlinecloud.amazonaws.com"

# Deadline Cloud monitor links against OpenSSL 1.1, which no current Ubuntu
# release provides. Ubuntu 20.04 is the last release to carry libssl1.1, so
# install that package here. Pinned to a specific build and checksum: it is not
# published with a .sha256 alongside it, so the expected hash lives here. Take a
# newer hash from the "SHA256:" field for libssl1.1 in
# https://archive.ubuntu.com/ubuntu/dists/focal-updates/main/binary-amd64/Packages.gz
LIBSSL_DEB="libssl1.1_1.1.1f-1ubuntu2.24_amd64.deb"
LIBSSL_DEB_SHA256="7cf39d70a639017d1dd7c8d36daa2258063608688e449fddf40ffdd46f992a78"

# ---------------------------------------------------------------------------
# Adapting to another DCC
# ---------------------------------------------------------------------------
#
# Blender stands in for whichever DCC you run. It is used here because it
# installs unattended from a public archive with no license server, which keeps
# this example runnable as-is. Everything Deadline Cloud does is identical for
# every DCC, so switching to Maya, Nuke, Houdini, 3ds Max, Cinema 4D, After
# Effects, or VRED means changing three things:
#
#   1. SUBMITTER_COMPONENT and BLENDER_COMPONENT above, for example
#      deadline_cloud_for_houdini plus houdini_20_5. Run "<installer> --help" for
#      the current --enable-components values. The --<dcc>-path flag is derived
#      from BLENDER_COMPONENT, so it follows automatically.
#   2. The "Install Blender" step. Commercial DCCs need a vendor installer and
#      usually a license server, so replace that block entirely.
#   3. The "Enable the add-on in Blender" step. It is Blender-specific. Other
#      DCCs are wired up by the installer itself or by an environment variable
#      such as MAYA_MODULE_PATH or NUKE_PATH, so you can often delete it.

log() { printf '[setup-workstation] %s\n' "$*"; }
die() { printf '[setup-workstation] ERROR: %s\n' "$*" >&2; exit 1; }

# ---------------------------------------------------------------------------
# Arguments
# ---------------------------------------------------------------------------

MONITOR_URL="${1:-}"
[[ -n "$MONITOR_URL" ]] || die "usage: $0 MONITOR_URL [WORKSTATION_USER]"

[[ $EUID -eq 0 ]] || die "run as root: this installs system packages"

# The profile and Blender's add-on preferences are per user, so pass the artist's
# account when there is no SUDO_USER to infer, as under EC2 user data. Configuring
# root instead produces a workstation where the artist finds nothing set up.
WORKSTATION_USER="${2:-${SUDO_USER:-root}}"

# The URL must carry its Region segment: the monitor accepts one without it and
# then writes a profile with the wrong region.
[[ "$MONITOR_URL" =~ ^https://([a-z0-9-]+)\.([a-z0-9-]+)\.deadlinecloud\.amazonaws\.com/?$ ]] \
    || die "monitor URL must be https://<subdomain>.<region>.deadlinecloud.amazonaws.com/ (got: $MONITOR_URL)"
MONITOR_REGION="${BASH_REMATCH[2]}"
PROFILE_NAME="${BASH_REMATCH[1]}-${MONITOR_REGION}"

USER_HOME="$(getent passwd "$WORKSTATION_USER" | cut -d: -f6)"
[[ -n "$USER_HOME" ]] || die "user does not exist: $WORKSTATION_USER"

log "workstation user: $WORKSTATION_USER ($USER_HOME)"
log "monitor profile: $PROFILE_NAME"

# ---------------------------------------------------------------------------
# Prerequisites
# ---------------------------------------------------------------------------

DEBIAN_FRONTEND=noninteractive apt-get update -qq

# Deadline Cloud monitor's .deb needs libwebkit2gtk-4.0-37, which Ubuntu dropped
# after 22.04 in favor of the 4.1 build. Check before installing anything, since
# otherwise this fails at apt dependency resolution after a 1 GB download.
# apt-cache policy, not show, which also succeeds for a virtual package. Capture
# first: piping into grep -q kills apt-cache with SIGPIPE, and under pipefail a
# package that is present looks missing.
webkit_policy="$(apt-cache policy libwebkit2gtk-4.0-37 2>/dev/null)"
if ! grep -q 'Candidate: [0-9]' <<<"$webkit_policy"; then
    die "Deadline Cloud monitor needs libwebkit2gtk-4.0-37, which this image does not provide. Use Ubuntu 22.04."
fi

DEBIAN_FRONTEND=noninteractive apt-get install -y -qq ca-certificates curl xz-utils

WORK_DIR="$(mktemp -d)"

# Remove the ~1 GB of downloads on success, keep them on failure so the installer
# logs survive for diagnosis.
cleanup() {
    local status=$?
    if [[ $status -eq 0 ]]; then
        rm -rf "$WORK_DIR"
    else
        printf '[setup-workstation] downloads left in %s\n' "$WORK_DIR" >&2
    fi
}
trap cleanup EXIT

# Download a file and verify it against a published sha256. Verification is not
# optional: an unreachable checksum is an error, not a reason to skip the check.
# Pass a filename to select one line from a multi-file checksum manifest.
download_verified() {
    local url="$1" dest="$2" checksum_url="$3" match_name="${4:-}" body expected actual

    log "downloading ${url##*/}"
    curl -fsSL --retry 3 --retry-delay 2 -o "$dest" "$url" \
        || die "cannot download ${dest##*/} from $url"

    body="$(curl -fsSL --retry 3 --retry-delay 2 "$checksum_url")" \
        || die "cannot fetch the checksum for ${dest##*/} from $checksum_url"

    if [[ -n "$match_name" ]]; then
        expected="$(awk -v w="$match_name" '$2 == w || $2 == "./" w {print $1; exit}' <<<"$body")"
    else
        expected="$(awk 'NR==1 {print $1}' <<<"$body")"
    fi
    [[ "$expected" =~ ^[0-9a-fA-F]{64}$ ]] || die "no usable sha256 for ${dest##*/} in $checksum_url"

    actual="$(sha256sum "$dest" | awk '{print $1}')"
    [[ "${actual,,}" == "${expected,,}" ]] \
        || die "checksum mismatch for ${dest##*/} (expected $expected, got $actual)"
    log "verified ${dest##*/}"
}

# Verify a file against a checksum given directly, for artifacts published
# without a .sha256 of their own.
verify_sha256() {
    local path="$1" expected="$2" actual
    actual="$(sha256sum "$path" | awk '{print $1}')"
    [[ "${actual,,}" == "${expected,,}" ]] \
        || die "checksum mismatch for ${path##*/} (expected $expected, got $actual)"
    log "verified ${path##*/}"
}

# Install OpenSSL 1.1 for Deadline Cloud monitor. The monitor's .deb declares no
# SSL dependency, so a missing libssl.so.1.1 installs fine and then cannot start.
# Capture first rather than piping into grep -q: under pipefail, grep -q exits on
# the first match and ldconfig dies with SIGPIPE, so a library that is present
# looks missing.
ldconfig_libs="$(ldconfig -p)"
if ! grep -qF 'libssl.so.1.1' <<<"$ldconfig_libs"; then
    log "installing libssl1.1 for Deadline Cloud monitor"
    curl -fsSL --retry 3 --retry-delay 2 -o "$WORK_DIR/$LIBSSL_DEB" \
        "https://archive.ubuntu.com/ubuntu/pool/main/o/openssl/$LIBSSL_DEB"
    verify_sha256 "$WORK_DIR/$LIBSSL_DEB" "$LIBSSL_DEB_SHA256"
    DEBIAN_FRONTEND=noninteractive apt-get install -y -qq "$WORK_DIR/$LIBSSL_DEB"
fi

# ---------------------------------------------------------------------------
# Install Blender
# ---------------------------------------------------------------------------

blender_series="${BLENDER_VERSION%.*}"
blender_archive="blender-${BLENDER_VERSION}-linux-x64.tar.xz"

download_verified \
    "${BLENDER_MIRROR}/Blender${blender_series}/${blender_archive}" \
    "$WORK_DIR/$blender_archive" \
    "${BLENDER_MIRROR}/Blender${blender_series}/blender-${BLENDER_VERSION}.sha256" \
    "$blender_archive"

# Unpack into a staging directory beside the prefix and move it into place, so an
# interrupted run cannot leave a half-extracted prefix behind.
#
# Only delete a prefix that looks like one of ours: BLENDER_PREFIX is a constant
# you are meant to edit, and rm -rf as root on whatever it names is unforgiving.
if [[ -e "$BLENDER_PREFIX" && ! -x "$BLENDER_PREFIX/blender" ]]; then
    die "$BLENDER_PREFIX exists but holds no blender executable. Refusing to delete it; check BLENDER_PREFIX."
fi
rm -rf "$BLENDER_PREFIX" "${BLENDER_PREFIX}.staging"
mkdir -p "${BLENDER_PREFIX}.staging"
tar -xJf "$WORK_DIR/$blender_archive" -C "${BLENDER_PREFIX}.staging" --strip-components=1
chmod 755 "${BLENDER_PREFIX}.staging"
mv "${BLENDER_PREFIX}.staging" "$BLENDER_PREFIX"
ln -sf "$BLENDER_PREFIX/blender" /usr/local/bin/blender

# Run Blender rather than only testing for the file, so one that unpacked but
# cannot start fails here. Capture the output before taking a line: piping into
# head closes the pipe early and Blender's SIGPIPE would make a working Blender
# look broken. A real failure usually means the image lacks Blender's X11 and GL
# libraries, so report those.
if ! blender_output="$("$BLENDER_PREFIX/blender" --version 2>&1)"; then
    # "|| true" on the ldd: it exits non-zero for a binary it cannot recognize as
    # dynamic, and set -e would then exit before either message is printed.
    missing="$( { ldd "$BLENDER_PREFIX/blender" || true; } 2>/dev/null \
        | awk '/not found/ {print $1}' | paste -sd' ' - )"
    [[ -n "$missing" ]] \
        && die "Blender cannot start, missing shared libraries: $missing. This image needs a desktop environment or Blender's dependencies."
    die "Blender installed to $BLENDER_PREFIX but will not run: $(head -1 <<<"$blender_output")"
fi
log "Blender installed: $(head -1 <<<"$blender_output")"

# ---------------------------------------------------------------------------
# Install the Deadline Cloud submitter
# ---------------------------------------------------------------------------

# The "latest" path always serves the current release, and its .sha256 alongside.
SUBMITTER_URL="${DOWNLOADS_BASE}/submitters/latest/linux/DeadlineCloudSubmitter-linux-x64-installer.run"

installer="$WORK_DIR/submitter-installer.run"
download_verified "$SUBMITTER_URL" "$installer" "${SUBMITTER_URL}.sha256"
chmod +x "$installer"

# --mode unattended runs without a GUI. deadline_client (the Deadline Cloud CLI
# and libraries) is always installed; enable only the DCC components needed here.
log "installing the submitter (unattended)"
"$installer" \
    --mode unattended \
    --unattendedmodeui none \
    --installscope system \
    --prefix "$SUBMITTER_PREFIX" \
    --enable-components "${SUBMITTER_COMPONENT},${BLENDER_COMPONENT}" \
    --"${BLENDER_COMPONENT//_/-}-path" "$BLENDER_PREFIX"
log "submitter installed at $SUBMITTER_PREFIX"

# ---------------------------------------------------------------------------
# Enable the add-on in Blender
# ---------------------------------------------------------------------------

# The unattended install stages the add-on but cannot enable it, because add-ons
# live in Blender's per-user preferences while the install runs at system scope.
# Run the installer's own script as the workstation user to register it.
addon_script="$SUBMITTER_PREFIX/Submitters/Blender/add_submitter_to_pref.py"
addon_path="$SUBMITTER_PREFIX/Submitters/Blender/python"

# Report Blender's own output on failure, which is where the cause actually is.
log "enabling the Blender add-on for $WORKSTATION_USER"
addon_output="$(
    runuser -u "$WORKSTATION_USER" -- env HOME="$USER_HOME" \
        "$BLENDER_PREFIX/blender" --background --python "$addon_script" \
        -- --deadline_cloud_install_path "$addon_path" 2>&1
)" || die "failed to enable the Blender add-on: $addon_output"

# Confirm from Blender's preferences rather than trusting the exit code.
verify_output="$(
    runuser -u "$WORKSTATION_USER" -- env HOME="$USER_HOME" \
        "$BLENDER_PREFIX/blender" --background --python-expr \
        'import bpy, sys; sys.exit(0 if "deadline_cloud_blender_submitter" in bpy.context.preferences.addons.keys() else 1)' 2>&1
)" || die "the Blender add-on did not register in $WORKSTATION_USER's preferences: $verify_output"
log "Blender add-on enabled"

# ---------------------------------------------------------------------------
# Install Deadline Cloud monitor and create the profile
# ---------------------------------------------------------------------------

MONITOR_BIN="/usr/bin/deadline-cloud-monitor"
MONITOR_BASE="${DOWNLOADS_BASE}/dcm/latest"

download_verified "${MONITOR_BASE}/deadline-cloud-monitor_amd64.deb" \
    "$WORK_DIR/dcm.deb" "${MONITOR_BASE}/deadline-cloud-monitor_amd64.deb.sha256"
DEBIAN_FRONTEND=noninteractive apt-get install -y -qq "$WORK_DIR/dcm.deb"

# Run it, so a monitor that installs but cannot start fails here.
monitor_version="$("$MONITOR_BIN" --version)" || die "the monitor at $MONITOR_BIN will not run"
log "monitor installed: $monitor_version"

# create-profile needs no display. Run it as the workstation user, so the profile
# and the credential cache path baked into it land in that user's home directory.
#
# --monitor-id is required but need not be correct: the real ID cannot be found
# without AWS credentials, and the monitor overwrites it, along with the user and
# identity store IDs, at first sign-in. It must be non-empty though -- an empty
# value makes the monitor drop the profile from its picker and ask for the URL
# instead. It shows verbatim until first sign-in, so make it self-explanatory.
MONITOR_ID_PLACEHOLDER="pending-first-login"

log "creating monitor profile '$PROFILE_NAME'"
profile_output="$(
    runuser -u "$WORKSTATION_USER" -- env HOME="$USER_HOME" "$MONITOR_BIN" create-profile \
        --profile "$PROFILE_NAME" \
        --monitor-id "$MONITOR_ID_PLACEHOLDER" \
        --monitor-url "$MONITOR_URL" \
        --enable-auto-login \
        --set-as-deadline-default 2>&1
)" || true

# create-profile exits 0 even when it fails, so check its output and the file.
grep -qF "Created profile ${PROFILE_NAME}" <<<"$profile_output" \
    || die "failed to create the monitor profile: $profile_output"
grep -qF "[profile ${PROFILE_NAME}]" "$USER_HOME/.aws/config" \
    || die "profile $PROFILE_NAME is missing from $USER_HOME/.aws/config"
log "profile created and verified in $USER_HOME/.aws/config"

cat <<SUMMARY

[setup-workstation] Done.

  Blender:    $BLENDER_PREFIX ($BLENDER_VERSION)
  Submitter:  $SUBMITTER_PREFIX
  Monitor:    $MONITOR_BIN
  Profile:    $PROFILE_NAME ($MONITOR_URL)

$WORKSTATION_USER can now open Deadline Cloud monitor, sign in to the
'$PROFILE_NAME' profile, and submit from Blender.

SUMMARY
