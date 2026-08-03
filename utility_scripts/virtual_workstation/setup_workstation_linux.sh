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

# Refuse an implicitly-resolved root, for the same reason the Windows script
# refuses SYSTEM: the monitor profile and Blender's add-on preferences are both
# per user, and every check below reads the invoking user's own state. Under EC2
# user data SUDO_USER is unset, so this would resolve to root, write everything
# into /root, pass every check, and report success while the artist finds nothing
# configured. An explicit root is allowed, since naming it makes it a choice --
# a root-login container or an AMI bake for a single-user image is a real case.
if [[ -n "${2:-}" ]]; then
    WORKSTATION_USER="$2"
else
    WORKSTATION_USER="${SUDO_USER:-$(id -un)}"
    [[ "$WORKSTATION_USER" != "root" ]] || die \
        "no workstation user given and none could be inferred (SUDO_USER is unset, as under EC2 user data or in an AMI bake). The monitor profile and Blender preferences are per user, so they would be written to root's home directory, where no artist signs in. Pass the artist's account: $0 MONITOR_URL ARTIST_USER"
fi

# The Region segment is required. The monitor accepts a URL without it and then
# writes a profile with a wrong region, so reject that here instead. Hostnames and
# schemes are case-insensitive, so compare in lowercase.
monitor_url_lc="${MONITOR_URL,,}"
[[ "$monitor_url_lc" == https://* ]] \
    || die "monitor URL must use https (got: $MONITOR_URL)"
monitor_host="${monitor_url_lc#https://}"
monitor_host="${monitor_host%%/*}"
[[ "$monitor_host" =~ ^([a-z0-9-]+)\.([a-z0-9-]+)\.deadlinecloud\.amazonaws\.com$ ]] \
    || die "monitor URL must be https://<subdomain>.<region>.deadlinecloud.amazonaws.com/ (got: $MONITOR_URL)"
MONITOR_SUBDOMAIN="${BASH_REMATCH[1]}"
MONITOR_REGION="${BASH_REMATCH[2]}"
PROFILE_NAME="${MONITOR_SUBDOMAIN}-${MONITOR_REGION}"

id "$WORKSTATION_USER" >/dev/null 2>&1 || die "user does not exist: $WORKSTATION_USER"
USER_HOME="$(getent passwd "$WORKSTATION_USER" | cut -d: -f6)"
[[ -n "$USER_HOME" ]] || die "cannot determine the home directory for $WORKSTATION_USER"

log "workstation user: $WORKSTATION_USER ($USER_HOME)"
log "monitor: $MONITOR_SUBDOMAIN in $MONITOR_REGION, profile '$PROFILE_NAME'"

# ---------------------------------------------------------------------------
# Prerequisites
# ---------------------------------------------------------------------------

# This example was written and tested against Ubuntu 22.04. Adapting it to a
# non-Debian distribution means replacing apt-get below and installing the monitor
# from the .rpm instead of the .deb.
command -v apt-get >/dev/null 2>&1 \
    || die "this example expects Ubuntu 22.04 (apt-get was not found)"

# Blender's archive, the monitor's .deb, and libssl1.1 are all pinned to x86-64
# below. On another architecture every download and checksum still succeeds and
# the binaries then fail to exec, so refuse here rather than after the downloads.
host_arch="$(uname -m)"
[[ "$host_arch" == "x86_64" ]] \
    || die "this example installs x86-64 artifacts only (this host is $host_arch). Substitute your architecture's Blender archive, monitor .deb, and OpenSSL 1.1 package."

# Refresh the package index only, so the checks below can read it. Nothing is
# installed until every up-front check has passed.
DEBIAN_FRONTEND=noninteractive apt-get update -qq

# Deadline Cloud monitor's .deb depends on libwebkit2gtk-4.0-37, which was
# dropped after Ubuntu 22.04 in favor of the 4.1 build. Installing
# it elsewhere fails at dependency resolution, so say so here rather than partway
# through. Check before anything is installed.
# apt-cache policy reports a candidate version only for a package apt can
# actually install, unlike apt-cache show, which also succeeds for a virtual one.
webkit_candidate="$(apt-cache policy libwebkit2gtk-4.0-37 2>/dev/null | awk '/Candidate:/ {print $2}')"
if [[ -z "$webkit_candidate" || "$webkit_candidate" == "(none)" ]]; then
    die "Deadline Cloud monitor needs libwebkit2gtk-4.0-37, which this image's repositories do not provide. Ubuntu 22.04 carries it; 24.04 replaced it with libwebkit2gtk-4.1-0 and no official repository offers the 4.0 build. Use Ubuntu 22.04, or see the README for installing the submitter without the monitor."
fi

DEBIAN_FRONTEND=noninteractive apt-get install -y -qq ca-certificates curl xz-utils python3

WORK_DIR="$(mktemp -d)"

# Keep the downloads and any installer logs when a run fails, so the failure can
# be diagnosed, and remove them on success: they total roughly 1 GB. The Windows
# script does the same.
# blender_staging is set later and may not exist yet, so test before removing it:
# "rm -rf" on an empty string is an error on GNU coreutils, and this runs under
# set -e.
cleanup() {
    local status=$?
    [[ -z "${blender_staging:-}" ]] || rm -rf "$blender_staging"
    if [[ $status -eq 0 ]]; then
        rm -rf "$WORK_DIR"
    else
        printf '[setup-workstation] downloads and installer logs left in %s\n' "$WORK_DIR" >&2
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

# Install OpenSSL 1.1 for Deadline Cloud monitor. Its .deb declares no SSL
# dependency, so a missing libssl.so.1.1 does not fail the install: the monitor
# installs and then cannot start. Check for the library rather than for a
# package name, since it may already be present from another source.
# Capture first rather than piping into grep -q: under pipefail, grep -q exits on
# the first match and ldconfig dies with SIGPIPE, so the pipeline reports 141 and a
# library that is present looks missing.
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

# Extract to a staging directory and move it into place, so BLENDER_PREFIX only
# ever exists complete. Extracting into it directly means a run interrupted
# partway leaves a prefix with no ./blender in it, which the guard below then
# refuses to delete on every later run, and the script cannot proceed without
# someone removing the directory by hand.
#
# Stage beside the prefix rather than in WORK_DIR, which is under /tmp and may be
# a different filesystem: then the mv would copy rather than rename, reopening the
# same window.
blender_staging="$(mktemp -d "${BLENDER_PREFIX}.staging.XXXXXX")"
tar -xJf "$WORK_DIR/$blender_archive" -C "$blender_staging" --strip-components=1
[[ -x "$blender_staging/blender" ]] \
    || die "the Blender archive did not contain a blender executable"

# mktemp -d creates the directory 0700 and mv preserves that, which would leave
# every account but root unable to even traverse the prefix -- so the artist's
# add-on step would fail with "Permission denied". Blender is a system-wide
# install that every user runs, so widen it to the 0755 that mkdir would have
# produced under the usual umask.
chmod 755 "$blender_staging"

# Replace any previous install so re-runs are clean. Only ever delete a directory
# this script created: BLENDER_PREFIX is a constant an administrator edits, and
# removing it unconditionally as root would destroy whatever it names.
if [[ -e "$BLENDER_PREFIX" ]]; then
    [[ -x "$BLENDER_PREFIX/blender" ]] \
        || die "$BLENDER_PREFIX exists but holds no blender executable. Refusing to delete it; check BLENDER_PREFIX, and see Troubleshooting in the README if a previous run was interrupted."
    rm -rf "$BLENDER_PREFIX"
fi
mv "$blender_staging" "$BLENDER_PREFIX"
blender_staging=""
ln -sf "$BLENDER_PREFIX/blender" /usr/local/bin/blender

# Run Blender rather than only testing for the file, so one that unpacked but
# cannot start fails here. Capture the whole output before taking a line: piping
# into head closes the pipe early, and under pipefail Blender's SIGPIPE would make
# a working Blender look broken. Assign rather than interpolate, because a command
# substitution inside an argument cannot abort under set -e. The usual cause of a
# real failure is a server image lacking Blender's X11 and GL libraries.
if ! blender_output="$("$BLENDER_PREFIX/blender" --version 2>&1)"; then
    # "|| true" on the ldd itself, not on the whole assignment: ldd exits non-zero
    # for a binary it cannot even recognize as dynamic, which is exactly the case
    # this diagnostic exists for -- a wrong-architecture build. Without it, that
    # status propagates and set -e exits here, before either message is printed.
    # Keeping the "|| true" narrow leaves a genuine awk or paste failure visible.
    missing="$( { ldd "$BLENDER_PREFIX/blender" || true; } 2>/dev/null \
        | awk '/not found/ {print $1}' | paste -sd' ' - )"
    [[ -n "$missing" ]] \
        && die "Blender cannot start: missing shared libraries: $missing. This image has no desktop environment, which this example requires. Install one, or add Blender's dependencies."
    die "Blender installed to $BLENDER_PREFIX but will not run: $(head -1 <<<"$blender_output")"
fi
log "Blender installed: $(head -1 <<<"$blender_output")"

# ---------------------------------------------------------------------------
# Install the Deadline Cloud submitter
# ---------------------------------------------------------------------------

# The manifest maps "latest" to a concrete version, so the download is a pinned,
# checksummed artifact rather than a moving target.
log "resolving the latest submitter from the manifest"
curl -fsSL --retry 3 -o "$WORK_DIR/manifest.json" "${DOWNLOADS_BASE}/submitters/manifest.json"

read -r submitter_version installer_path checksum_path < <(
    python3 - "$WORK_DIR/manifest.json" <<'PY'
import json
import sys

with open(sys.argv[1]) as handle:
    root = json.load(handle)["DeadlineCloudSubmitter"]
version = root["latest"]["linux"]
node = root["versions"]
for part in version.split("."):
    node = node[part]
node = node["linux"]
print(version, node["installer"], node["sha256"])
PY
)
log "submitter version: $submitter_version"

installer="$WORK_DIR/submitter-installer.run"
download_verified \
    "${DOWNLOADS_BASE}/submitters${installer_path}" "$installer" \
    "${DOWNLOADS_BASE}/submitters${checksum_path}"
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

# Capture the output and report it on failure. Discarding it leaves the operator
# with "failed to enable the Blender add-on" and nothing to act on, when the
# actual cause is in the message -- a prefix the artist cannot execute, say.
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

# Run the monitor rather than only testing for the file, so one that installs but
# cannot start fails here instead of silently later.
monitor_version="$("$MONITOR_BIN" --version)" || die "the monitor at $MONITOR_BIN will not run"
log "monitor installed: $monitor_version"

# create-profile is a non-GUI subcommand: it writes the profile and exits without
# needing a display. Run it as the workstation user so the profile and the
# credential cache path baked into it land in that user's home directory.
#
# --monitor-id is required, but the real ID is not needed and cannot be discovered
# without AWS credentials, so pass a placeholder. The monitor replaces it, along
# with the user and identity store IDs, using authoritative values from the portal
# on the artist's first sign-in.
#
# The placeholder must be non-empty. An empty value makes the monitor drop the
# profile from its picker and fall back to asking for the monitor URL, which
# defeats the point of pre-configuring it. The value is shown verbatim in the
# monitor's profile list until first sign-in, so use something self-explanatory.
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

# create-profile exits 0 even when it fails, so confirm from its output and then
# from the file it should have written. -F because the name is data, not a regex.
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
