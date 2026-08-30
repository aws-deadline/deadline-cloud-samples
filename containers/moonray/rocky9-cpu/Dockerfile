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

# Which MoonRay version to build. Defaults to a released tag rather than a
# branch so that rebuilding this Dockerfile later produces the same MoonRay.
# Pick another version from the tag list:
#   https://github.com/dreamworksanimation/openmoonray/tags
# Upstream publishes two tag series: the older openmoonray-<major>.<minor>.0.0
# scheme (up to openmoonray-3.6.0.1) and the current date-based v<year>.<week>.<n>
# scheme. Override with, for example:
#   docker build --platform linux/amd64 \
#       --build-arg OPENMOONRAY_REF=openmoonray-3.6.0.1 \
#       -t openmoonray-rocky9 .
# This is passed to `git clone --branch`, so it accepts a tag or a branch name
# ("main" for the tip of development) but not a bare commit sha.
ARG OPENMOONRAY_REF=v2026.29.1

# The moonray/materialx_shaders submodule points at a repository that is not
# public (404), so deactivate it and fetch the rest of the submodules.
RUN git clone --branch "${OPENMOONRAY_REF}" "${OPENMOONRAY_REPO}" /source \
    && cd /source \
    && git config submodule."moonray/materialx_shaders".update none \
    && git submodule update --init --recursive \
    && echo "${OPENMOONRAY_REF} $(git rev-parse HEAD)" > /openmoonray-ref.txt

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
#
# This goes through the rocky9-release CMake preset (CMakeLinuxPresets.json),
# as the official docs do, rather than a hand-written cmake invocation. The
# preset is what connects this step to step 2: the dependencies install to
# /opt/MoonRay/installs (the InstallRoot default in
# building/Rocky9/CMakeLists.txt), and the preset sets CMAKE_PREFIX_PATH and
# the per-dependency *_ROOT variables that point there. Configuring without
# it fails immediately at the first dependency lookup:
#   CMake Error ... Could NOT find JsonCpp (missing: JsonCpp_LIBRARIES)
# The preset also sets the build directory to /build, the install prefix to
# /installs/openmoonray, and PYTHON_EXECUTABLE / BOOST_PYTHON_COMPONENT_NAME /
# ABI_VERSION; its build preset runs the `install` target, so there is no
# separate `cmake --install`.
RUN rm -rf /build/* \
    && cd /source \
    && cmake --preset rocky9-release -DMOONRAY_USE_OPTIX=NO \
    && cmake --build --preset rocky9-release -- -j "$(nproc)" \
    && rm -rf /build

# setup.sh puts moonray, moonray_gui, and hd_render on PATH.
RUN echo 'source /installs/openmoonray/scripts/setup.sh' > /etc/profile.d/openmoonray.sh

ENTRYPOINT ["/bin/bash", "-lc"]
CMD ["moonray"]
