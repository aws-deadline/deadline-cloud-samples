#!/bin/bash
# Install Docker and the NVIDIA Container Toolkit on Deadline Cloud
# service-managed fleet workers, so a Docker queue environment can start
# containers with GPU access.
#
# Run this as a host configuration script. It runs as root, once per worker,
# before the worker takes any session.
#
# PREFER THE DOCKER SOFTWARE ADD-ON INSTEAD, for a new fleet. Setting fleet
# `instanceCapabilities.softwareAddOns: [{name: "docker"}]` makes the service
# install rootless Docker, the NVIDIA Container Toolkit and a CDI spec, with no
# privileged script to maintain. See
# cloudformation/farm_templates/gpu_docker_persistent_farm/.
#
# This script remains for fleets that already use a host configuration script,
# or that need the rootful daemon. The two fleet types are NOT interchangeable.
# A queue environment gating on `docker info` reporting an `nvidia` runtime
# passes no GPU flags at all on an add-on fleet, and the container runs CPU-only
# in silence. Match the queue environment to the fleet.
#
# Tested on: Amazon Linux 2023 with the NVIDIA GPU driver pre-installed
# (driver 580.178.04), on g6e instances.
# Requires: a GPU instance type (g6, g6e, p4d and similar).
#
# This sets up the ROOTFUL Docker daemon and the legacy `nvidia` runtime:
#
#     docker container run --runtime=nvidia --gpus all ...
#
# `queue_environments/docker_queue_env.yaml` is NOT compatible with this script.
# That environment targets the `docker` software add-on: it starts a rootless
# daemon from /opt/deadline/docker-rootless and gates GPU injection on
# /etc/cdi/nvidia.yaml. Pairing it with this script fails in onEnter with
# "rootless docker daemon not available", because this script leaves no rootless
# daemon to start. Using this script means writing a queue environment that
# talks to the rootful daemon and passes --runtime=nvidia.
#
# It deliberately does NOT enable CDI device injection
# (`--device=nvidia.com/gpu=all`). CDI is the newer and generally preferred
# mechanism, but mixing the two on a service-managed fleet produces failures
# that point away from their cause, so pick one and keep the queue environment
# matched to it. If you switch to CDI, enable `features.cdi` in
# /etc/docker/daemon.json as well: generating a spec is not sufficient on
# Docker 25 and 26, where CDI is experimental and off by default, and the
# failure is `could not select device driver "cdi" with capabilities: []`
# despite a valid spec and a working host nvidia-smi.

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

# Register the `nvidia` runtime in /etc/docker/daemon.json. This is the line the
# queue environment depends on: it gates on `docker info` reporting an nvidia
# runtime before it passes --runtime=nvidia.
nvidia-ctk runtime configure --runtime=docker

# Generate a CDI spec. Not needed by the legacy runtime path above, and kept
# only so a queue environment that prefers CDI has a spec to resolve against.
# Any spec the AMI already ships under /var/run/cdi is left alone: removing it
# was tried as a fix for a device-resolution failure and changed nothing.
mkdir -p /etc/cdi
nvidia-ctk cdi generate --output=/etc/cdi/nvidia.yaml

# Restart Docker to pick up the NVIDIA runtime
systemctl restart docker

# --- Verify ---
echo ""
echo "=== Verification ==="
echo "Docker: $(docker --version)"
echo "NVIDIA driver: $(nvidia-smi --query-gpu=driver_version --format=csv,noheader 2>/dev/null || echo 'not found')"
echo "GPU: $(nvidia-smi --query-gpu=name,memory.total --format=csv,noheader 2>/dev/null || echo 'not found')"
echo "NVIDIA runtime registered: $(docker info 2>/dev/null | grep -ci 'Runtimes:.*nvidia' || echo '0')"

# Prove a container can actually reach the GPU, using the same flags the queue
# environment uses.
#
# This check exists because the failure it catches is silent and expensive. A
# driver, a runtime and a spec can all be present and a container still get no
# GPU: `--gpus all` is ACCEPTED, the container starts, nvidia-smi is simply
# absent inside it, and the application fails much later with a CUDA error that
# names nothing relevant. On a GPU fleet that is a 35 GB model download and
# several minutes of billed instance time before anyone learns the truth.
#
# Reported rather than fatal. A worker that cannot reach the GPU should still
# come up, so the session log shows the real reason instead of the fleet
# refusing to start workers with nothing to read.
echo "GPU-in-container smoke test:"
docker pull -q public.ecr.aws/amazonlinux/amazonlinux:2023 >/dev/null 2>&1 || true
SMOKE=$(docker run --rm --runtime=nvidia --gpus all \
    --entrypoint nvidia-smi public.ecr.aws/amazonlinux/amazonlinux:2023 \
    --query-gpu=name --format=csv,noheader 2>&1 | tail -2 | tr '\n' ' ')
echo "  --runtime=nvidia --gpus all -> ${SMOKE}"
case "$SMOKE" in
    *NVIDIA*) echo "  OK: the container sees a GPU." ;;
    *) echo "  WARNING: the container did NOT see a GPU. A Docker queue environment will start normally and the workload will fail later with a CUDA error." ;;
esac

echo "[$(date)] Docker and NVIDIA Container Toolkit setup complete."
