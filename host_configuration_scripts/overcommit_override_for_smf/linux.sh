#!/bin/bash
# Override memory overcommit on Deadline Cloud service managed fleet workers.
# Run this as a host configuration script (runs as root).
#
# The default SMF worker AMI sets vm.overcommit_memory=2 (strict accounting),
# which limits total memory reservations to: CommitLimit = swap + RAM.
# This can cause malloc failures for memory-intensive workloads with large
# job attachments (e.g. Blender, Houdini) even when physical RAM is free.
#
# This script switches to heuristic overcommit (vm.overcommit_memory=1),
# which allows allocations as long as physical RAM is available.

set -e

OVERCOMMIT_MODE="1"  # 0=heuristic, 1=always allow, 2=strict (default on SMF)

echo "[$(date)] Configuring vm.overcommit_memory=${OVERCOMMIT_MODE}..."

sysctl -w vm.overcommit_memory=${OVERCOMMIT_MODE}

# Persist across reboots (SMF instances are currently ephemeral and don't reboot,
# but this ensures the setting survives if worker restart becomes available)
if ! grep -q "vm.overcommit_memory" /etc/sysctl.d/99-overcommit.conf 2>/dev/null; then
    echo "vm.overcommit_memory=${OVERCOMMIT_MODE}" | tee /etc/sysctl.d/99-overcommit.conf
    echo "Persisted to /etc/sysctl.d/99-overcommit.conf"
fi

echo "vm.overcommit_memory=$(sysctl -n vm.overcommit_memory)"
echo "[$(date)] Overcommit configuration complete."
