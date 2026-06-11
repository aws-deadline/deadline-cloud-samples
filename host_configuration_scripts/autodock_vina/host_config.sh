#!/bin/bash
# Host configuration script for AutoDock VINA.
#
# NOTE: Prefer using the conda recipe at conda_recipes/autodock-vina-1.2.5/
# with your queue's Conda environment instead of this host config.
# This script is provided as a fallback for fleets without a Conda queue environment.
set -euo pipefail

echo "=== Installing AutoDock VINA ==="

# VINA is a single static binary (not available on conda-forge upstream).
VINA_URL="https://github.com/ccsb-scripps/AutoDock-Vina/releases/download/v1.2.5/vina_1.2.5_linux_x86_64"
curl -sL "${VINA_URL}" -o /usr/local/bin/vina
chmod 755 /usr/local/bin/vina

vina --version
echo "=== AutoDock VINA Installed ==="
