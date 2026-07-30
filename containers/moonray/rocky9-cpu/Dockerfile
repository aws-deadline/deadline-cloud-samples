# Builds MoonRay from source on Rocky Linux 9, following the official
# container build procedure:
# https://docs.openmoonray.org/getting-started/installation/building-moonray/rocky9_container_build/
#
# The docs run these steps interactively in a rockylinux:9 container and
# `docker commit` the result; this Dockerfile encodes the same steps so the
# image is reproducible with a single command:
#
#   docker build --platform linux/amd64 -t openmoonray-rocky9 .
#
# The build compiles MoonRay's third-party dependencies (OpenEXR, USD, ...)
# and then MoonRay itself — expect it to take on the order of hours and to
# need 8+ GB of RAM available to the Docker VM.
#
# CUDA/GPU (XPU) support is omitted (--nocuda / MOONRAY_USE_OPTIX=NO), per
# the same docs, since GPUs are typically not available in containers.

FROM rockylinux:9

SHELL ["/bin/bash", "-c"]

# The openmoonray repository uses submodules and Git LFS for test data.
RUN dnf install -y git git-lfs \
    && git lfs install

ARG OPENMOONRAY_REPO=https://github.com/dreamworksanimation/openmoonray.git
ARG OPENMOONRAY_REF=main

# The moonray/materialx_shaders submodule points at a repository that is not
# public (404), so deactivate it and fetch the rest of the submodules.
RUN git clone --branch "${OPENMOONRAY_REF}" "${OPENMOONRAY_REPO}" /source \
    && cd /source \
    && git config submodule."moonray/materialx_shaders".update none \
    && git submodule update --init --recursive

# Step 1: install the system packages MoonRay's build needs.
RUN source /source/building/Rocky9/install_packages.sh --nocuda \
    && dnf clean all

# The EPEL cmake links the system libuv and crashes in its SIGCHLD handler
# when the image is built under x86_64 emulation (e.g. on Apple Silicon).
# The pip wheel is the same cmake 3.x with a bundled libuv and works
# everywhere; it installs to /usr/local/bin, which shadows /usr/bin.
RUN pip3 install "cmake<4"

# Step 2: build the remaining dependencies from source (installs under /installs).
RUN mkdir /build \
    && cd /build \
    && cmake /source/building/Rocky9 \
    && cmake --build . -- -j "$(nproc)"

# Step 3: build and install MoonRay itself.
RUN cd /build \
    && rm -rf ./* \
    && cmake /source \
        -DPYTHON_EXECUTABLE=python3 \
        -DBOOST_PYTHON_COMPONENT_NAME=python39 \
        -DABI_VERSION=0 \
        -DMOONRAY_USE_OPTIX=NO \
    && cmake --build . -j "$(nproc)" \
    && mkdir -p /installs/openmoonray \
    && cmake --install /build --prefix /installs/openmoonray \
    && rm -rf /build

# setup.sh puts moonray, moonray_gui, and hd_render on PATH.
RUN echo 'source /installs/openmoonray/scripts/setup.sh' > /etc/profile.d/openmoonray.sh

ENTRYPOINT ["/bin/bash", "-lc"]
CMD ["moonray"]
