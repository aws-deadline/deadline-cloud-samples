#!/bin/bash
# Enable swap on Deadline Cloud service managed fleet workers.
# Run this as a host configuration script (runs as root).
#
# Useful for memory-intensive workloads (e.g. ComfyUI, large diffusion models)
# that temporarily exceed physical RAM during model loading.

set -e

SWAP_SIZE="32G"

echo "[$(date)] Configuring ${SWAP_SIZE} swap..."

if [ -f /swapfile ]; then
    echo "Swap file already exists."
    swapon /swapfile 2>/dev/null || true
else
    echo "Creating ${SWAP_SIZE} swap file..."
    fallocate -l "${SWAP_SIZE}" /swapfile
    chmod 600 /swapfile
    mkswap /swapfile
    swapon /swapfile

    # Persist across reboots
    echo "/swapfile swap swap defaults 0 0" | tee -a /etc/fstab
    echo "Swap file created and enabled."
fi

echo "Swap: $(free -h | grep Swap | awk '{print $2}')"
echo "[$(date)] Swap configuration complete."
