#!/usr/bin/env bash
# Install Docker Engine for CPU container jobs on Deadline Cloud Linux
# service-managed fleet workers. Host configuration scripts run as root.
#
# Tested on: Amazon Linux 2023

set -euo pipefail

log() {
    printf '[%s] %s\n' "$(date -u +%FT%TZ)" "$*"
}

if [[ "${EUID}" -ne 0 ]]; then
    echo "ERROR: this host configuration script must run as root" >&2
    exit 1
fi

if ! command -v dnf >/dev/null 2>&1; then
    echo "ERROR: dnf was not found; this sample supports Amazon Linux 2023" >&2
    exit 1
fi

log "Installing Docker Engine and job utilities"
dnf install -y docker curl-minimal tar gzip coreutils python3 util-linux

log "Enabling and starting Docker"
systemctl enable --now docker

if ! id job-user >/dev/null 2>&1; then
    echo "ERROR: Deadline Cloud job user 'job-user' does not exist" >&2
    exit 1
fi

log "Granting job-user access to the Docker daemon"
usermod -aG docker job-user

log "Verifying Docker daemon and job-user access"
systemctl is-active --quiet docker
docker info >/dev/null
runuser -u job-user -- docker info >/dev/null

log "Docker Engine setup complete: $(docker --version)"
