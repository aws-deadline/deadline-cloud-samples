#!/usr/bin/env bash
# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0
#
# Pre-configure a Linux virtual workstation for AWS Deadline Cloud submission.
#
# Installs Blender, the Deadline Cloud submitter for Blender, and Deadline Cloud
# monitor, then creates a monitor profile so an artist only has to sign in.
#
# Run as root during instance provisioning (user data, AMI bake, or by hand).

set -euo pipefail

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

MONITOR_URL=""
PROFILE_NAME=""
MONITOR_ID=""
BLENDER_VERSION="4.5.0"
BLENDER_MIRROR="https://download.blender.org/release"
WORKSTATION_USER=""
SKIP_BLENDER="no"
SKIP_SUBMITTER="no"
SKIP_MONITOR="no"

DOWNLOADS_BASE="https://downloads.deadlinecloud.amazonaws.com"
SUBMITTER_MANIFEST="${DOWNLOADS_BASE}/submitters/manifest.json"
MONITOR_BASE="${DOWNLOADS_BASE}/dcm/latest"

# Where Blender is unpacked. The submitter installer needs this path so it can
# drop its add-on into the matching Blender version's scripts directory.
BLENDER_PREFIX="/opt/blender"

# Where the submitter installer puts the Deadline Cloud CLI and the add-on files.
SUBMITTER_PREFIX="/opt/DeadlineCloudSubmitter"

# ---------------------------------------------------------------------------
# ADAPTING THIS SCRIPT TO A DIFFERENT DCC
# ---------------------------------------------------------------------------
#
# Blender is used here because it installs unattended from a public archive with
# no license server, which makes the sample runnable as-is. The Deadline Cloud
# parts (submitter, monitor, profile) are identical for every DCC. To target
# Maya, Nuke, Houdini, 3ds Max, Cinema 4D, After Effects, or VRED, change these
# five places, each marked with a "DCC:" comment below:
#
#   1. The version-to-component map. Run
#      "<installer> --help" for the current --enable-components values, for
#      example deadline_cloud_for_maya, deadline_cloud_for_nuke, or
#      deadline_cloud_for_houdini plus a version component like houdini_20_5.
#   2. The DCC install step. Most commercial DCCs use a vendor installer and a
#      license server rather than a tarball, so replace this block entirely.
#   3. The --enable-components list and the --<dcc>-path flag passed to the
#      submitter installer.
#   4. The add-on enable step. It is Blender-specific: other DCCs are wired up
#      by the installer itself or by environment variables such as
#      MAYA_MODULE_PATH or NUKE_PATH, so this step is often unnecessary.
#   5. The closing summary text.
#
# To install more than one DCC, pass a comma-separated --enable-components list
# with every DCC and version component you need, plus one --<dcc>-path flag per
# DCC, and repeat step 2 for each.

log() { printf '[setup-workstation] %s\n' "$*"; }
err() { printf '[setup-workstation] ERROR: %s\n' "$*" >&2; }
die() { err "$*"; exit 1; }

usage() {
    cat <<'USAGE'
Usage: setup_workstation_linux.sh --monitor-url URL [options]

Required:
  --monitor-url URL        Monitor URL, for example
                           https://mymonitor.us-west-2.deadlinecloud.amazonaws.com/

Options:
  --profile-name NAME      AWS profile name to create.
                           Default: <subdomain>-<region> from the monitor URL.
  --monitor-id ID          Monitor ID (monitor-<32 hex characters>). When omitted,
                           the script calls deadline:ListMonitors to discover it.
                           See "Monitor ID discovery" in the README.
  --workstation-user USER  Local user who signs in to the monitor. The profile is
                           written to this user's home directory.
                           Default: the invoking user, or SUDO_USER under sudo.
  --blender-version VER    Blender version to install. Default: 4.5.0
  --blender-mirror URL     Base URL for Blender downloads. Default:
                           https://download.blender.org/release
  --skip-blender           Do not install Blender.
  --skip-submitter         Do not install the Deadline Cloud submitter.
  --skip-monitor           Do not install Deadline Cloud monitor or create a profile.
  -h, --help               Show this message.
USAGE
}

# Require a value for flags that take one. Without this a trailing flag makes
# "shift 2" fail, which under set -e exits with no message at all.
need_value() {
    [[ $# -ge 2 && -n "$2" ]] || die "$1 requires a value"
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --monitor-url)       need_value "$@"; MONITOR_URL="$2"; shift 2 ;;
        --profile-name)      need_value "$@"; PROFILE_NAME="$2"; shift 2 ;;
        --monitor-id)        need_value "$@"; MONITOR_ID="$2"; shift 2 ;;
        --workstation-user)  need_value "$@"; WORKSTATION_USER="$2"; shift 2 ;;
        --blender-version)   need_value "$@"; BLENDER_VERSION="$2"; shift 2 ;;
        --blender-mirror)    need_value "$@"; BLENDER_MIRROR="$2"; shift 2 ;;
        --skip-blender)      SKIP_BLENDER="yes"; shift ;;
        --skip-submitter)    SKIP_SUBMITTER="yes"; shift ;;
        --skip-monitor)      SKIP_MONITOR="yes"; shift ;;
        -h|--help)           usage; exit 0 ;;
        *)                   usage >&2; die "unknown argument: $1" ;;
    esac
done

[[ $EUID -eq 0 ]] || die "run this script as root (installs system packages)"

if [[ "$SKIP_MONITOR" == "no" && -z "$MONITOR_URL" ]]; then
    usage >&2
    die "--monitor-url is required unless --skip-monitor is given"
fi

# The submitter needs a Blender install to point its add-on at. Skipping Blender
# while still installing the submitter would target a path that does not exist.
if [[ "$SKIP_BLENDER" == "yes" && "$SKIP_SUBMITTER" == "no" ]]; then
    die "--skip-blender also requires --skip-submitter, because the submitter installer needs the Blender install path. To use a Blender that is already installed, set BLENDER_PREFIX in this script to its location and drop --skip-blender"
fi

# ---------------------------------------------------------------------------
# Resolve the workstation user and their home directory
# ---------------------------------------------------------------------------

if [[ -z "$WORKSTATION_USER" ]]; then
    WORKSTATION_USER="${SUDO_USER:-$(id -un)}"
fi
id "$WORKSTATION_USER" >/dev/null 2>&1 || die "user does not exist: $WORKSTATION_USER"
USER_HOME="$(getent passwd "$WORKSTATION_USER" | cut -d: -f6)"
[[ -n "$USER_HOME" ]] || die "cannot determine home directory for $WORKSTATION_USER"

log "workstation user: $WORKSTATION_USER (home: $USER_HOME)"

# ---------------------------------------------------------------------------
# Parse the monitor URL into subdomain and region
# ---------------------------------------------------------------------------

MONITOR_SUBDOMAIN=""
MONITOR_REGION=""

if [[ -n "$MONITOR_URL" ]]; then
    # Monitor URLs are https://<subdomain>.<region>.deadlinecloud.amazonaws.com/
    monitor_host="${MONITOR_URL#*://}"
    monitor_host="${monitor_host%%/*}"
    if [[ "$monitor_host" =~ ^([a-z0-9-]+)\.([a-z0-9-]+)\.deadlinecloud\.amazonaws\.com$ ]]; then
        MONITOR_SUBDOMAIN="${BASH_REMATCH[1]}"
        MONITOR_REGION="${BASH_REMATCH[2]}"
    else
        die "monitor URL must look like https://<subdomain>.<region>.deadlinecloud.amazonaws.com/ (got: $MONITOR_URL)"
    fi
    : "${PROFILE_NAME:=${MONITOR_SUBDOMAIN}-${MONITOR_REGION}}"
    log "monitor: subdomain=$MONITOR_SUBDOMAIN region=$MONITOR_REGION profile=$PROFILE_NAME"
fi

# ---------------------------------------------------------------------------
# Distribution detection and package installation
# ---------------------------------------------------------------------------

# shellcheck disable=SC1091
. /etc/os-release
DISTRO_ID="${ID:-unknown}"
DISTRO_LIKE="${ID_LIKE:-}"
DISTRO_VERSION="${VERSION_ID:-}"

case "$DISTRO_ID $DISTRO_LIKE" in
    *debian*|ubuntu*) PKG_FAMILY="debian" ;;
    *rhel*|*fedora*|amzn*|rocky*|almalinux*) PKG_FAMILY="rhel" ;;
    *) die "unsupported distribution: $DISTRO_ID (expected a Debian- or RHEL-family system)" ;;
esac
log "detected $DISTRO_ID $DISTRO_VERSION (package family: $PKG_FAMILY)"

pkg_install() {
    case "$PKG_FAMILY" in
        debian) DEBIAN_FRONTEND=noninteractive apt-get install -y -qq "$@" ;;
        rhel)   dnf install -y -q "$@" ;;
    esac
}

pkg_refresh() {
    case "$PKG_FAMILY" in
        debian) DEBIAN_FRONTEND=noninteractive apt-get update -qq ;;
        rhel)   : ;;
    esac
}

log "installing base packages"
pkg_refresh
case "$PKG_FAMILY" in
    # python3 parses the submitter manifest. Minimal images omit it.
    debian) pkg_install curl ca-certificates xz-utils python3 ;;
    # Do not ask for "curl" here: Amazon Linux 2023 and RHEL 9 derivatives ship
    # curl-minimal, which provides /usr/bin/curl but conflicts with the full
    # curl package, so installing it fails. Require the binary instead.
    rhel)   pkg_install ca-certificates xz python3 ;;
esac

for tool in curl python3 tar; do
    command -v "$tool" >/dev/null 2>&1 || die "$tool is required but was not found on PATH"
done

WORK_DIR="$(mktemp -d)"
trap 'rm -rf "$WORK_DIR"' EXIT

# Download a URL and verify it against a sha256 checksum file when one exists.
# The submitter publishes "<sha256>  <filename>" alongside each installer.
download() {
    local url="$1" dest="$2"
    log "downloading ${url##*/}"
    curl -fsSL --retry 3 --retry-delay 2 -o "$dest" "$url"
}

# Verify a downloaded file against its published sha256. Fatal on any failure,
# including an unreachable checksum file: silently downgrading to "no
# verification" on a transient network error would defeat the point. Pass a
# filename to pick one line out of a multi-file checksum manifest.
verify_sha256() {
    local file="$1" checksum_url="$2" match_name="${3:-}" checksum_body expected actual

    checksum_body="$(curl -fsSL --retry 3 --retry-delay 2 "$checksum_url")" \
        || die "cannot fetch the checksum for ${file##*/} from $checksum_url"

    if [[ -n "$match_name" ]]; then
        # Manifests list one "<sha256>  <filename>" line per artifact.
        expected="$(awk -v want="$match_name" '$2 == want || $2 == "./" want {print $1; exit}' <<<"$checksum_body")"
    else
        expected="$(awk 'NR==1 {print $1}' <<<"$checksum_body")"
    fi

    [[ "$expected" =~ ^[0-9a-fA-F]{64}$ ]] \
        || die "no usable sha256 for ${file##*/} in $checksum_url"

    actual="$(sha256sum "$file" | awk '{print $1}')"
    [[ "${actual,,}" == "${expected,,}" ]] \
        || die "checksum mismatch for $file (expected $expected, got $actual)"
    log "checksum verified: ${file##*/}"
}

# ---------------------------------------------------------------------------
# Blender
# ---------------------------------------------------------------------------

# DCC (1 of 5): version-to-component map.
# The submitter installer expects a DCC install path per version, and only
# supports specific versions. Map "4.5.0" to the installer's blender-45 flags.
BLENDER_SERIES=""
BLENDER_COMPONENT=""
if [[ "$SKIP_BLENDER" == "no" || "$SKIP_SUBMITTER" == "no" ]]; then
    blender_major="${BLENDER_VERSION%%.*}"
    blender_rest="${BLENDER_VERSION#*.}"
    blender_minor="${blender_rest%%.*}"
    BLENDER_SERIES="${blender_major}.${blender_minor}"
    case "$BLENDER_SERIES" in
        3.6) BLENDER_COMPONENT="blender_36" ;;
        4.0) BLENDER_COMPONENT="blender_4" ;;
        4.1) BLENDER_COMPONENT="blender_41" ;;
        4.2) BLENDER_COMPONENT="blender_42" ;;
        4.3) BLENDER_COMPONENT="blender_43" ;;
        4.4) BLENDER_COMPONENT="blender_44" ;;
        4.5) BLENDER_COMPONENT="blender_45" ;;
        5.0) BLENDER_COMPONENT="blender_5" ;;
        5.1) BLENDER_COMPONENT="blender_51" ;;
        *)   die "the Deadline Cloud submitter does not support Blender $BLENDER_SERIES" ;;
    esac
fi

# DCC (2 of 5): install the DCC itself.
# Blender ships a relocatable tarball. A commercial DCC will instead need its
# vendor installer and probably a license server, so replace this whole block.
if [[ "$SKIP_BLENDER" == "no" ]]; then
    log "installing Blender $BLENDER_VERSION"
    blender_archive="blender-${BLENDER_VERSION}-linux-x64.tar.xz"
    blender_url="${BLENDER_MIRROR}/Blender${BLENDER_SERIES}/${blender_archive}"
    download "$blender_url" "$WORK_DIR/$blender_archive"
    # Blender publishes one checksum manifest per release covering every platform
    # artifact, so select the line for this archive. Verifying matters most when
    # --blender-mirror points at a third-party mirror.
    verify_sha256 "$WORK_DIR/$blender_archive" \
        "${BLENDER_MIRROR}/Blender${BLENDER_SERIES}/blender-${BLENDER_VERSION}.sha256" \
        "$blender_archive"

    rm -rf "$BLENDER_PREFIX"
    mkdir -p "$BLENDER_PREFIX"
    # The archive contains a single blender-<version>-linux-x64/ directory.
    tar -xJf "$WORK_DIR/$blender_archive" -C "$BLENDER_PREFIX" --strip-components=1
    ln -sf "$BLENDER_PREFIX/blender" /usr/local/bin/blender
    log "Blender installed at $BLENDER_PREFIX ($("$BLENDER_PREFIX/blender" --version 2>/dev/null | head -1 || echo 'version check skipped'))"
fi

# ---------------------------------------------------------------------------
# Deadline Cloud submitter
# ---------------------------------------------------------------------------

if [[ "$SKIP_SUBMITTER" == "no" ]]; then
    log "resolving the latest submitter installer from the manifest"
    # The manifest records the latest version per platform and the installer path
    # under each version. Resolve both so the download is a pinned, checksummed
    # artifact rather than a moving "latest" URL.
    manifest="$WORK_DIR/manifest.json"
    download "$SUBMITTER_MANIFEST" "$manifest"

    read -r submitter_version installer_path checksum_path < <(
        python3 - "$manifest" <<'PY'
import json
import sys

with open(sys.argv[1]) as handle:
    root = json.load(handle)["DeadlineCloudSubmitter"]

version = root["latest"]["linux"]
node = root["versions"]
for part in version.split("."):
    node = node[part]
node = node["linux"]
print(version, node["installer"], node.get("sha256", ""))
PY
    )
    log "submitter version: $submitter_version"

    installer="$WORK_DIR/DeadlineCloudSubmitter-linux-x64-installer.run"
    download "${DOWNLOADS_BASE}/submitters${installer_path}" "$installer"
    [[ -n "$checksum_path" ]] || die "the manifest does not publish a sha256 for the submitter installer"
    verify_sha256 "$installer" "${DOWNLOADS_BASE}/submitters${checksum_path}"
    chmod +x "$installer"

    log "installing the submitter for Blender $BLENDER_SERIES (unattended)"
    # DCC (3 of 5): the enabled components and the --<dcc>-path flag.
    # --mode unattended runs without a GUI. Enabling only the Blender components
    # keeps the install to the submitter this workstation needs; deadline_client
    # (the Deadline Cloud CLI and libraries) is always installed.
    "$installer" \
        --mode unattended \
        --unattendedmodeui none \
        --installscope system \
        --prefix "$SUBMITTER_PREFIX" \
        --enable-components "deadline_cloud_for_blender,${BLENDER_COMPONENT}" \
        --"${BLENDER_COMPONENT//_/-}-path" "$BLENDER_PREFIX"

    log "submitter installed at $SUBMITTER_PREFIX"

    # DCC (4 of 5): enable the add-on. Blender-specific; most other DCCs are
    # wired up by the installer or by an environment variable, so this step can
    # often be deleted outright.
    # The unattended install stages the add-on under the submitter prefix but does
    # not enable it: the add-on lives in Blender's per-user preferences, which the
    # system-scope installer cannot write. Register it for the workstation user by
    # running the installer's own script through Blender in background mode.
    if [[ "$SKIP_BLENDER" == "no" ]]; then
        blender_addon_script="$SUBMITTER_PREFIX/Submitters/Blender/add_submitter_to_pref.py"
        blender_addon_path="$SUBMITTER_PREFIX/Submitters/Blender/python"
        if [[ -f "$blender_addon_script" ]]; then
            log "enabling the Blender add-on for $WORKSTATION_USER"
            runuser -u "$WORKSTATION_USER" -- env HOME="$USER_HOME" \
                "$BLENDER_PREFIX/blender" --background \
                --python "$blender_addon_script" \
                -- --deadline_cloud_install_path "$blender_addon_path" \
                || die "failed to enable the Blender add-on"

            # Confirm the add-on is enabled rather than trusting the exit code.
            if ! runuser -u "$WORKSTATION_USER" -- env HOME="$USER_HOME" \
                "$BLENDER_PREFIX/blender" --background --python-expr \
                'import bpy, sys; sys.exit(0 if "deadline_cloud_blender_submitter" in bpy.context.preferences.addons.keys() else 1)' \
                >/dev/null 2>&1; then
                die "the Blender add-on did not register in $WORKSTATION_USER's preferences"
            fi
            log "Blender add-on enabled in $USER_HOME/.config/blender"
        else
            log "WARNING: $blender_addon_script not found; enable the add-on manually"
        fi
    else
        log "WARNING: Blender was skipped, so the add-on was not enabled in Blender preferences"
    fi
fi

# ---------------------------------------------------------------------------
# Deadline Cloud monitor
# ---------------------------------------------------------------------------

MONITOR_BIN="/usr/bin/deadline-cloud-monitor"

if [[ "$SKIP_MONITOR" == "no" ]]; then
    log "installing Deadline Cloud monitor"
    case "$PKG_FAMILY" in
        debian)
            # The monitor links against libssl.so.1.1, which Ubuntu 22.04 and
            # later no longer ship. Install the compatibility package first.
            if ! ldconfig -p | grep -q 'libssl\.so\.1\.1'; then
                log "installing libssl1.1 for the monitor"
                libssl_deb="libssl1.1_1.1.1f-1ubuntu2_amd64.deb"
                download "https://archive.ubuntu.com/ubuntu/pool/main/o/openssl/${libssl_deb}" \
                    "$WORK_DIR/$libssl_deb"
                pkg_install "$WORK_DIR/$libssl_deb"
            fi
            download "${MONITOR_BASE}/deadline-cloud-monitor_amd64.deb" "$WORK_DIR/dcm.deb"
            verify_sha256 "$WORK_DIR/dcm.deb" "${MONITOR_BASE}/deadline-cloud-monitor_amd64.deb.sha256"
            pkg_install "$WORK_DIR/dcm.deb"
            ;;
        rhel)
            # The monitor links against libssl.so.1.1, which OpenSSL 3 systems no
            # longer ship. Test for the library rather than matching on a version
            # number: Amazon Linux 2023 reports VERSION_ID=2023, so a "== 9" check
            # skips this and the monitor then fails at first launch. The monitor
            # RPM declares no OpenSSL dependency, so the install itself succeeds
            # either way and cannot be relied on to catch this.
            if ! ldconfig -p | grep -q 'libssl\.so\.1\.1'; then
                log "installing compat-openssl11 for the monitor"
                pkg_install epel-release || log "WARNING: could not install epel-release"
                pkg_install compat-openssl11 || die \
                    "the monitor needs libssl.so.1.1 and compat-openssl11 is not available for $DISTRO_ID $DISTRO_VERSION. Amazon Linux 2023 does not package it; use a RHEL 8/9, Rocky, or Alma image, or install OpenSSL 1.1 yourself"
            fi
            download "${MONITOR_BASE}/deadline-cloud-monitor.x86_64.rpm" "$WORK_DIR/dcm.rpm"
            verify_sha256 "$WORK_DIR/dcm.rpm" "${MONITOR_BASE}/deadline-cloud-monitor.x86_64.rpm.sha256"
            pkg_install "$WORK_DIR/dcm.rpm"
            ;;
    esac

    [[ -x "$MONITOR_BIN" ]] || die "expected the monitor at $MONITOR_BIN after install"

    # Run the monitor rather than only testing for the file. A command
    # substitution inside a log argument cannot abort the script under set -e, so
    # capture it in an assignment: a monitor that installs but cannot start (a
    # missing shared library, for example) must fail here rather than later.
    monitor_version="$("$MONITOR_BIN" --version)" \
        || die "the monitor at $MONITOR_BIN will not run. If this reports a missing libssl.so.1.1, see Troubleshooting in the README"
    log "monitor installed: $monitor_version"

    # -----------------------------------------------------------------------
    # Monitor ID discovery
    # -----------------------------------------------------------------------
    # create-profile requires a monitor ID. It stores whatever it is given and
    # replaces it with the authoritative value on the artist's first sign-in, so
    # a placeholder still produces a working profile. Prefer the real ID when
    # credentials are available so the profile is correct before anyone signs in.
    if [[ -z "$MONITOR_ID" ]]; then
        if command -v aws >/dev/null 2>&1; then
            log "looking up the monitor ID with deadline:ListMonitors"
            # Keep stderr so a permissions or credentials problem is visible
            # rather than silently becoming a placeholder ID.
            if aws_output="$(
                aws deadline list-monitors --region "$MONITOR_REGION" \
                    --query "monitors[?subdomain=='${MONITOR_SUBDOMAIN}'].monitorId | [0]" \
                    --output text 2>&1
            )"; then
                MONITOR_ID="$aws_output"
                [[ "$MONITOR_ID" == "None" ]] && MONITOR_ID=""
                [[ -z "$MONITOR_ID" ]] && log "WARNING: no monitor with subdomain '${MONITOR_SUBDOMAIN}' in $MONITOR_REGION"
            else
                log "WARNING: deadline:ListMonitors failed: $aws_output"
            fi
        else
            log "the AWS CLI is not installed, so the monitor ID cannot be discovered"
        fi
    fi
    if [[ -z "$MONITOR_ID" ]]; then
        # 32 zeros is a syntactically valid placeholder that first sign-in replaces.
        MONITOR_ID="monitor-00000000000000000000000000000000"
        log "WARNING: monitor ID not discovered; using a placeholder"
        log "WARNING: the artist's first sign-in replaces it with the real monitor ID"
    fi
    log "monitor ID: $MONITOR_ID"

    # -----------------------------------------------------------------------
    # Create the profile
    # -----------------------------------------------------------------------
    # create-profile is a non-GUI subcommand: it writes the profile and exits
    # without needing a display. Run it as the workstation user so the profile,
    # the Deadline Cloud config, and the credential cache path that
    # credential_process reads all land in that user's home directory.
    log "creating monitor profile '$PROFILE_NAME' for $WORKSTATION_USER"
    profile_output="$(
        runuser -u "$WORKSTATION_USER" -- env HOME="$USER_HOME" "$MONITOR_BIN" create-profile \
            --profile "$PROFILE_NAME" \
            --monitor-id "$MONITOR_ID" \
            --monitor-url "$MONITOR_URL" \
            --enable-auto-login \
            --set-as-deadline-default 2>&1
    )" || true

    # create-profile exits 0 even when it fails, so confirm from its output.
    # -F: the profile name is data, not a pattern. A name containing "." would
    # otherwise match text the monitor never printed, and one containing "["
    # would make grep fail outright.
    if ! grep -qF "Created profile ${PROFILE_NAME}" <<<"$profile_output"; then
        err "failed to create the monitor profile"
        printf '%s\n' "$profile_output" >&2
        exit 1
    fi
    log "$profile_output"

    [[ -f "$USER_HOME/.aws/config" ]] || die "expected $USER_HOME/.aws/config after create-profile"
    grep -qF "[profile ${PROFILE_NAME}]" "$USER_HOME/.aws/config" \
        || die "profile $PROFILE_NAME missing from $USER_HOME/.aws/config"
    log "verified the profile in $USER_HOME/.aws/config"
fi

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------

# DCC (5 of 5): summary text.
cat <<SUMMARY

[setup-workstation] Workstation setup complete.

  Blender:    $([[ "$SKIP_BLENDER" == "no" ]] && echo "$BLENDER_PREFIX (blender $BLENDER_VERSION)" || echo "skipped")
  Submitter:  $([[ "$SKIP_SUBMITTER" == "no" ]] && echo "$SUBMITTER_PREFIX (Blender $BLENDER_SERIES)" || echo "skipped")
  Monitor:    $([[ "$SKIP_MONITOR" == "no" ]] && echo "$MONITOR_BIN" || echo "skipped")
  Profile:    $([[ "$SKIP_MONITOR" == "no" ]] && echo "$PROFILE_NAME ($MONITOR_URL)" || echo "skipped")
SUMMARY

if [[ "$SKIP_MONITOR" == "no" ]]; then
    cat <<NEXT_STEPS

What the artist does next:
  1. Open Deadline Cloud monitor and sign in to the '$PROFILE_NAME' profile.
  2. Open Blender. The Deadline Cloud add-on submits to the farm using that profile.

NEXT_STEPS
else
    cat <<NEXT_STEPS

No monitor profile was created. Re-run without --skip-monitor, passing
--monitor-url, before the artist can submit jobs.

NEXT_STEPS
fi
