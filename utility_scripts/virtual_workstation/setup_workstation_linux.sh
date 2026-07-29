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

while [[ $# -gt 0 ]]; do
    case "$1" in
        --monitor-url)       MONITOR_URL="${2:-}"; shift 2 ;;
        --profile-name)      PROFILE_NAME="${2:-}"; shift 2 ;;
        --monitor-id)        MONITOR_ID="${2:-}"; shift 2 ;;
        --workstation-user)  WORKSTATION_USER="${2:-}"; shift 2 ;;
        --blender-version)   BLENDER_VERSION="${2:-}"; shift 2 ;;
        --blender-mirror)    BLENDER_MIRROR="${2:-}"; shift 2 ;;
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
DISTRO_VERSION_MAJOR="${VERSION_ID%%.*}"

case "$DISTRO_ID $DISTRO_LIKE" in
    *debian*|ubuntu*) PKG_FAMILY="debian" ;;
    *rhel*|*fedora*|amzn*|rocky*|almalinux*) PKG_FAMILY="rhel" ;;
    *) die "unsupported distribution: $DISTRO_ID (expected a Debian- or RHEL-family system)" ;;
esac
log "detected $DISTRO_ID ${VERSION_ID:-} (package family: $PKG_FAMILY)"

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
    debian) pkg_install curl ca-certificates xz-utils ;;
    rhel)   pkg_install curl ca-certificates xz ;;
esac

WORK_DIR="$(mktemp -d)"
trap 'rm -rf "$WORK_DIR"' EXIT

# Download a URL and verify it against a sha256 checksum file when one exists.
# The submitter publishes "<sha256>  <filename>" alongside each installer.
download() {
    local url="$1" dest="$2"
    log "downloading ${url##*/}"
    curl -fsSL --retry 3 --retry-delay 2 -o "$dest" "$url"
}

verify_sha256() {
    local file="$1" checksum_url="$2" expected
    expected="$(curl -fsSL --retry 3 "$checksum_url" 2>/dev/null | awk 'NR==1 {print $1}')" || true
    if [[ -z "$expected" ]]; then
        log "WARNING: no checksum published at $checksum_url, skipping verification"
        return 0
    fi
    local actual
    actual="$(sha256sum "$file" | awk '{print $1}')"
    [[ "$actual" == "$expected" ]] || die "checksum mismatch for $file (expected $expected, got $actual)"
    log "checksum verified: ${file##*/}"
}

# ---------------------------------------------------------------------------
# Blender
# ---------------------------------------------------------------------------

# The submitter installer expects a Blender install path per version, and only
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

if [[ "$SKIP_BLENDER" == "no" ]]; then
    log "installing Blender $BLENDER_VERSION"
    blender_archive="blender-${BLENDER_VERSION}-linux-x64.tar.xz"
    blender_url="${BLENDER_MIRROR}/Blender${BLENDER_SERIES}/${blender_archive}"
    download "$blender_url" "$WORK_DIR/$blender_archive"

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
    if [[ -n "$checksum_path" ]]; then
        verify_sha256 "$installer" "${DOWNLOADS_BASE}/submitters${checksum_path}"
    fi
    chmod +x "$installer"

    log "installing the submitter for Blender $BLENDER_SERIES (unattended)"
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
            pkg_install "$WORK_DIR/dcm.deb"
            ;;
        rhel)
            # RHEL 9 derivatives default to OpenSSL 3 and need compat-openssl11
            # from EPEL for the monitor's libssl.so.1.1 dependency.
            if [[ "$DISTRO_VERSION_MAJOR" == "9" ]]; then
                pkg_install epel-release || log "WARNING: could not install epel-release"
                pkg_install compat-openssl11 || die "compat-openssl11 is required on this distribution"
            fi
            download "${MONITOR_BASE}/deadline-cloud-monitor.x86_64.rpm" "$WORK_DIR/dcm.rpm"
            pkg_install "$WORK_DIR/dcm.rpm"
            ;;
    esac

    [[ -x "$MONITOR_BIN" ]] || die "expected the monitor at $MONITOR_BIN after install"
    log "monitor installed: $("$MONITOR_BIN" --version)"

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
            MONITOR_ID="$(
                aws deadline list-monitors --region "$MONITOR_REGION" \
                    --query "monitors[?subdomain=='${MONITOR_SUBDOMAIN}'].monitorId | [0]" \
                    --output text 2>/dev/null || true
            )"
            [[ "$MONITOR_ID" == "None" ]] && MONITOR_ID=""
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
    if ! grep -q "Created profile ${PROFILE_NAME}" <<<"$profile_output"; then
        err "failed to create the monitor profile"
        printf '%s\n' "$profile_output" >&2
        exit 1
    fi
    log "$profile_output"

    [[ -f "$USER_HOME/.aws/config" ]] || die "expected $USER_HOME/.aws/config after create-profile"
    grep -q "\[profile ${PROFILE_NAME}\]" "$USER_HOME/.aws/config" \
        || die "profile $PROFILE_NAME missing from $USER_HOME/.aws/config"
    log "verified the profile in $USER_HOME/.aws/config"
fi

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------

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
