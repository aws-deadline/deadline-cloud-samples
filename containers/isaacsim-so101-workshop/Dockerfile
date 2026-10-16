# syntax=docker/dockerfile:1
#
# Isaac Sim / Isaac Lab image for the `isaacsim_so101_sim_to_policy` job bundle.
#
# This is a RECIPE, not a redistributable image. It builds on NVIDIA's
# `nvcr.io/nvidia/isaac-lab` image, which YOU pull under NVIDIA's licence terms;
# nothing NVIDIA-owned is vendored into this repository. Push the result to a
# registry you control (e.g. your own Amazon ECR) and pass that URI to the job
# bundle's `ContainerImage` parameter. Do not redistribute the built image.
#
#   docker build -t isaacsim-so101-workshop:2.3.2 .
#
# See README.md in this directory for the ECR push and the job-bundle wiring.
#
# ---------------------------------------------------------------------------
# Why this file exists at all, given the workshop ships its own Dockerfile
# ---------------------------------------------------------------------------
# The upstream `docker/sim/Dockerfile` in the Sim-to-Real-SO-101-Workshop repo
# deliberately does NOT copy `source/` into the image -- the workshop's own run
# command bind-mounts it from a developer checkout
# (`-v $(pwd)/source:/workspace/Sim-to-Real-SO-101-Workshop/source`). That is
# convenient for a workstation and wrong for a render farm: it would force every
# Deadline Cloud worker to stage the whole workshop repo as a job attachment on
# every task. This recipe clones the workshop at a pinned commit INTO the image
# instead, so a worker needs only the image plus the bundle's own scripts.
#
# The workshop repo is Apache-2.0, so cloning it from a published recipe
# redistributes nothing proprietary. The Omniverse Kit runtime still arrives
# only via the NVIDIA base image that you pull.

ARG BASE_IMAGE=nvcr.io/nvidia/isaac-lab:2.3.2
FROM ${BASE_IMAGE}

# Isaac Lab 2.3.2 declares support for Isaac Sim 4.5.0 / 5.0.0 / 5.1.0 and no
# 6.x. 5.1.0 is the target here: it is the version that has been observed
# working on a Deadline Cloud Linux GPU service-managed fleet, and the SMF
# accelerator runtime tops out at the grid:r580 (driver 580.x) generation that
# 5.1.0 expects. Isaac Lab 3.x pins isaacsim 6.0.1, whose driver floor is above
# that ceiling -- do not bump the base image without re-checking the fleet's
# available accelerator runtimes.

# Pinned so a rebuild is reproducible.
#   WORKSHOP_REF: commit on https://github.com/isaac-sim/Sim-to-Real-SO-101-Workshop
#                 (this is the tip of `main` at tag v1.0 + the calibration-script commit)
#   LEROBOT_REF:  the exact commit the workshop's own Dockerfile checks out.
ARG WORKSHOP_REPO=https://github.com/isaac-sim/Sim-to-Real-SO-101-Workshop.git
ARG WORKSHOP_REF=ce807d99724cb65671abec01f908a2fcb4a6eab7
ARG LEROBOT_REPO=https://github.com/huggingface/lerobot.git
ARG LEROBOT_REF=e670ac5daf9b76cf5c18f632b89a8ff85c727ca6

ENV PYTHON=/workspace/isaaclab/_isaac_sim/python.sh
ENV PATH="/workspace/isaaclab/_isaac_sim/kit/python/bin:$PATH"

# --------------------------------------------------------------------------
# LeRobot, at the workshop's pin.
# --------------------------------------------------------------------------
# `--no-deps` is load-bearing: LeRobot's dependency set would upgrade
# packaging / numpy / torch / lxml, and Isaac Lab's vendored copies of those are
# reached through symlinks that break when pip replaces them. The constraints
# file below then re-pins them while the *missing* deps are installed normally.
# This is the upstream workshop's approach, kept verbatim.
WORKDIR /workspace
RUN git clone --filter=blob:none "${LEROBOT_REPO}" lerobot \
    && git -C lerobot checkout "${LEROBOT_REF}"
WORKDIR /workspace/lerobot
RUN $PYTHON -m pip install --no-deps -e .

RUN printf '%s\n' \
    "packaging==23.0" \
    "numpy==1.26.0" \
    "lxml==4.9.4" \
    "torch==2.7.0" \
    "torchvision==0.22.0" \
    "imageio==2.37.0" \
    > /tmp/constraints.txt

RUN $PYTHON -m pip install -c /tmp/constraints.txt \
    "datasets>=4.0.0,<4.2.0" \
    "diffusers>=0.27.2,<0.36.0" \
    "huggingface-hub[hf-transfer,cli]>=0.34.2,<0.36.0" \
    "accelerate>=1.10.0,<2.0.0" \
    "cmake>=3.29.0.1,<4.2.0" \
    "av>=15.0.0,<16.0.0" \
    "jsonlines>=4.0.0,<5.0.0" \
    "pynput>=1.7.7,<1.9.0" \
    "pyserial>=3.5,<4.0" \
    "wandb>=0.20.0,<0.22.0" \
    "torchcodec>=0.2.1,<0.6.0" \
    "draccus==0.10.0" \
    "deepdiff>=7.0.1,<9.0.0" \
    "feetech-servo-sdk>=1.0.0,<2.0.0"

# torchcodec and the dataset video writer both link against ffmpeg's shared
# libraries, so a static ffmpeg binary is not enough.
#
# Pinned to a DATED BtbN autobuild release, not the rolling `latest` tag.
# `latest` is mutable: it carried ffmpeg-n7.1 when the workshop's Dockerfile was
# written, and by 2026-08 it had rotated to n8.1 / n9.0 / master, so the n7.1
# filename started returning 404 and the build broke. A dated tag plus the exact
# filename is both reproducible and stable.
#
# Stay on the 7.x line: `torchcodec<0.6.0` (pinned above) predates ffmpeg 8, and
# a major-version jump would fail at runtime rather than at build time. Bump
# FFMPEG_RELEASE / FFMPEG_TARBALL together, and only after checking which ffmpeg
# majors the pinned torchcodec supports.
ARG FFMPEG_RELEASE=autobuild-2026-08-16-13-00
ARG FFMPEG_TARBALL=ffmpeg-n7.1.5-16-g9a4bb2c579-linux64-lgpl-shared-7.1.tar.xz
RUN curl --proto "=https" --tlsv1.2 -sSf -L -o /tmp/ffmpeg.tar.xz \
    "https://github.com/BtbN/FFmpeg-Builds/releases/download/${FFMPEG_RELEASE}/${FFMPEG_TARBALL}" && \
    tar -xf /tmp/ffmpeg.tar.xz -C /usr/local --strip-components=1 && \
    ldconfig && \
    ffmpeg -version | head -1 && \
    rm /tmp/ffmpeg.tar.xz

# Kit links these even in headless mode; they are not in the base image.
RUN apt-get update && apt-get install -y --no-install-recommends \
    libx11-6 libxcursor1 libxrandr2 libxi6 libxinerama1 \
    libxkbcommon0 libxkbcommon-x11-0 \
    && rm -rf /var/lib/apt/lists/*

# rerun-sdk's metadata demands numpy>=2 but it works with the pinned 1.26.0.
RUN $PYTHON -m pip install --no-deps "rerun-sdk>=0.24.0,<0.27.0"
RUN $PYTHON -m pip install "pyzmq"

# --------------------------------------------------------------------------
# The workshop itself -- baked in, not bind-mounted (see header).
# --------------------------------------------------------------------------
# git-lfs is REQUIRED, not optional. The workshop's .gitattributes routes
# *.usd, *.usda, *.hdr, *.psd and *.dae through Git LFS, so a plain clone yields
# ~133-byte pointer files instead of geometry. Isaac Sim then fails deep into
# scene construction with:
#
#   FileNotFoundError: Unable to open the usd file at path: .../SO-ARM101-USD.usd
#
# which reads like a missing-file bug rather than a checkout problem. Without
# LFS the repo is ~1 MB on disk; with it, ~150 MB. This is easy to miss locally
# because most developer machines already have git-lfs installed, so a manual
# clone looks fine while the image is silently broken.
RUN apt-get update && apt-get install -y --no-install-recommends git-lfs \
    && rm -rf /var/lib/apt/lists/* \
    && git lfs install --system

WORKDIR /workspace
RUN git clone --filter=blob:none "${WORKSHOP_REPO}" Sim-to-Real-SO-101-Workshop \
    && git -C Sim-to-Real-SO-101-Workshop checkout "${WORKSHOP_REF}" \
    && git -C Sim-to-Real-SO-101-Workshop lfs pull \
    && test -s Sim-to-Real-SO-101-Workshop/source/sim_to_real_so101/assets/usd/SO-ARM101-USD.usd \
    && [ "$(stat -c%s Sim-to-Real-SO-101-Workshop/source/sim_to_real_so101/assets/usd/SO-ARM101-USD.usd)" -gt 1000000 ] \
    || { echo "ERROR: SO-ARM101-USD.usd is still an LFS pointer -- 'git lfs pull' did not fetch it." >&2; exit 1; }

WORKDIR /workspace/Sim-to-Real-SO-101-Workshop
RUN chmod +x docker/sim/entrypoint.sh \
    && mkdir -p outputs datasets

# Pre-install so the entrypoint's `pip install -e` is a metadata no-op and does
# not need the network on a worker with restricted egress.
RUN $PYTHON -m pip install --no-deps -e source/sim_to_real_so101/

# Kit writes a lot of __pycache__; keep it off the read-only layers.
RUN mkdir -p /tmp/pycache && chmod 1777 /tmp/pycache
ENV PYTHONPYCACHEPREFIX=/tmp/pycache

RUN cat docker/utils.sh >> /root/.bashrc

# Headless offscreen rendering. `--headless` alone gives you no cameras;
# ENABLE_CAMERAS is what selects isaaclab.python.headless.rendering.kit.
ENV HEADLESS=1
ENV ENABLE_CAMERAS=1
ENV ACCEPT_EULA=Y
ENV PRIVACY_CONSENT=Y

# The upstream entrypoint runs `set -e` and then:
#
#     source /root/env 2>/dev/null
#
# `source` of a missing file returns non-zero, so under `set -e` the entrypoint
# EXITS THERE -- and because stderr is redirected to /dev/null, it does so with
# no diagnostic whatsoever. The container just exits 1 having printed nothing,
# which looks exactly like a GPU/runtime/mount failure and is not.
#
# The workshop's own run tooling creates /root/env to inject environment
# variables; nothing in a plain `docker run` does. Creating it empty here keeps
# the upstream entrypoint usable unmodified, which is preferable to patching
# their script or overriding ENTRYPOINT (see the note below on why the
# entrypoint must be kept).
RUN touch /root/env

# Keep the upstream entrypoint. It sources setup_python_env.sh, sets
# CARB_APP_PATH / ISAAC_PATH / EXP_PATH, installs the /usr/local/bin/python
# shim that forwards to Isaac Sim's python.sh, and ends in `exec "$@"`.
# Replacing it with `--entrypoint bash` (a workaround needed for the plain
# isaac-sim image, whose entrypoint swallows stdout) would silently drop all of
# that and Isaac Lab imports would fail. This entrypoint does not swallow
# stdout, so the workaround is unnecessary here.
ENTRYPOINT ["/workspace/Sim-to-Real-SO-101-Workshop/docker/sim/entrypoint.sh"]
CMD ["bash"]
