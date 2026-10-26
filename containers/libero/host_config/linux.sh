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

# CDI spec. Jobs in this sample use `docker run --runtime=nvidia`, which works on
# these workers; the spec is kept so CDI-based tools also find the GPU.
# NVIDIA Container Toolkit >= 1.18 generates /var/run/cdi/nvidia.yaml at boot
# (nvidia-cdi-refresh). A second spec in /etc/cdi defines the same devices and
# makes them unresolvable, so (re)generate only the /var/run/cdi spec.
rm -f /etc/cdi/nvidia.yaml
mkdir -p /var/run/cdi
nvidia-ctk cdi generate --output=/var/run/cdi/nvidia.yaml
nvidia-ctk cdi list

# Restart Docker to pick up NVIDIA runtime
systemctl restart docker

# --- Verify ---
echo ""
echo "=== Verification ==="
echo "Docker: $(docker --version)"
echo "NVIDIA driver: $(nvidia-smi --query-gpu=driver_version --format=csv,noheader 2>/dev/null || echo 'not found')"
echo "GPU: $(nvidia-smi --query-gpu=name,memory.total --format=csv,noheader 2>/dev/null || echo 'not found')"
echo "NVIDIA runtime: $(grep -c nvidia /etc/docker/daemon.json 2>/dev/null || echo '0') references in daemon.json"

echo "[$(date)] Docker and NVIDIA Container Toolkit installed."

# --- Enable Docker's CDI feature ---
# Not used by this sample's jobs: on Docker 25 with NVIDIA Container Toolkit 1.20,
# `--device nvidia.com/gpu=all` still reports unresolvable devices, so the jobs use
# `--runtime=nvidia`. Kept because this exact script was the one verified end to end.
python3 - <<'PY'
import json, pathlib
p = pathlib.Path("/etc/docker/daemon.json")
d = json.loads(p.read_text()) if p.exists() and p.read_text().strip() else {}
d.setdefault("features", {})["cdi"] = True
p.write_text(json.dumps(d, indent=2))
PY
systemctl restart docker
ls /etc/cdi /var/run/cdi 2>/dev/null || true

# --- Memory overcommit (from overcommit_override_for_smf) ---
# SMF workers default to vm.overcommit_memory=2; PyTorch plus many simulator
# processes reserve far more virtual memory than they use, causing MemoryError.
sysctl -w vm.overcommit_memory=1
echo "vm.overcommit_memory=1" > /etc/sysctl.d/99-overcommit.conf

echo "[$(date)] Host configuration complete."
