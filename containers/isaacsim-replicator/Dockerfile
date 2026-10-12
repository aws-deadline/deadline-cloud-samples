# syntax=docker/dockerfile:1
#
# Minimal NVIDIA Isaac Sim image for the `isaacsim_replicator_sdg` job bundle.
#
# This is a RECIPE, not a redistributable image. You pull NVIDIA's
# `nvcr.io/nvidia/isaac-sim` base under NVIDIA's licence terms; nothing
# NVIDIA-owned is vendored into this repository. Push the result to a registry
# you control (your own Amazon ECR) and pass that URI to the Docker queue
# environment's image parameter. Do not redistribute the built image.
#
#   docker build -t isaacsim-replicator:5.1.0 .
#
# See README.md in this directory for the NGC pull and the ECR push.
#
# ---------------------------------------------------------------------------
# Why this is five lines when containers/isaacsim-so101-workshop is a hundred
# ---------------------------------------------------------------------------
# That image serves `isaacsim_so101_sim_to_policy`, which needs LeRobot, a
# shared-library ffmpeg build, and the workshop repository checked out through
# Git LFS. The SDG bundle's `primitives` and `usd` scene sources need none of
# it: between them they import only `isaacsim.SimulationApp`,
# `omni.replicator.core`, `numpy` and `pxr`, all of which are in the base image.
#
# Use the workshop image instead if, and only if, you want
# `SceneSource=workshop`, which loads USD files that ship inside it.

ARG BASE_IMAGE=nvcr.io/nvidia/isaac-sim:5.1.0
FROM ${BASE_IMAGE}

# Isaac Sim 5.1.0 is deliberate, not incidental. It is the version observed
# working on a Deadline Cloud Linux GPU service-managed fleet, and the SMF
# accelerator runtime currently tops out at grid:r580 (driver 580.x), which is
# what 5.1.0 expects. Isaac Sim 6.x raises that driver floor above the ceiling
# SMF offers. Check the fleet's available accelerator runtimes before bumping.

# Kit dynamically links these even with no display attached. They are absent
# from the base image, and without them Kit fails during startup rather than at
# render time, which reads like a GPU problem and is not.
RUN apt-get update && apt-get install -y --no-install-recommends \
        libx11-6 \
        libxcursor1 \
        libxrandr2 \
        libxi6 \
        libxinerama1 \
        libxkbcommon0 \
        libxkbcommon-x11-0 \
    && rm -rf /var/lib/apt/lists/*

# Kit writes a lot of __pycache__. Keep it off the read-only image layers.
RUN mkdir -p /tmp/pycache && chmod 1777 /tmp/pycache
ENV PYTHONPYCACHEPREFIX=/tmp/pycache

# Accepted on your behalf when you build this image. Review NVIDIA's terms
# first: https://docs.isaacsim.omniverse.nvidia.com/latest/common/NVIDIA_Omniverse_License_Agreement.html
ENV ACCEPT_EULA=Y
ENV PRIVACY_CONSENT=Y

# No ENTRYPOINT override is set, and none is needed. The Docker queue
# environment never runs the image's ENTRYPOINT: it starts a session container
# and uses `docker container exec` to run each task's command inside it. That is
# also why `generate_sdg.py` passes its Kit experience file explicitly instead
# of relying on EXP_PATH, which the base image's entrypoint would otherwise set.
