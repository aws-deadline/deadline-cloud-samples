#!/bin/bash
# Install Docker and NVIDIA Container Toolkit on Deadline Cloud service managed fleet workers.
# Run this as a host configuration script (runs as root).
#
# Tested on: Amazon Linux 2023 with NVIDIA GPU drivers pre-installed
# Requires: GPU instance type (g6, g6e, p4d, etc.)

set -e

echo "[$(date)] Installing Docker and NVIDIA Container Toolkit..."

# --- Docker ---
echo "Installing Docker..."
dnf install -y docker
systemctl enable docker
systemctl start docker

# Allow job-user to run docker without sudo
if id "job-user" &>/dev/null; then
    usermod -aG docker job-user
    echo "job-user added to docker group."
else
    echo "WARNING: job-user does not exist yet. Add job-user to the docker group after the worker agent starts."
fi

# --- NVIDIA Container Toolkit ---
echo "Installing NVIDIA Container Toolkit..."
curl -s -L https://nvidia.github.io/libnvidia-container/stable/rpm/nvidia-container-toolkit.repo | \
    tee /etc/yum.repos.d/nvidia-container-toolkit.repo

dnf install -y nvidia-container-toolkit

# Configure Docker to use NVIDIA runtime
nvidia-ctk runtime configure --runtime=docker

# Generate CDI spec (required for --runtime=nvidia on newer drivers)
mkdir -p /etc/cdi
nvidia-ctk cdi generate --output=/etc/cdi/nvidia.yaml

# Restart Docker to pick up NVIDIA runtime
systemctl restart docker

# --- Verify ---
echo ""
echo "=== Verification ==="
echo "Docker: $(docker --version)"
echo "NVIDIA driver: $(nvidia-smi --query-gpu=driver_version --format=csv,noheader 2>/dev/null || echo 'not found')"
echo "GPU: $(nvidia-smi --query-gpu=name,memory.total --format=csv,noheader 2>/dev/null || echo 'not found')"
echo "NVIDIA runtime: $(grep -c nvidia /etc/docker/daemon.json 2>/dev/null || echo '0') references in daemon.json"

echo "[$(date)] Docker and NVIDIA Container Toolkit setup complete."
