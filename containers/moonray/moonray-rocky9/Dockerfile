# Builds MoonRay from source on Rocky Linux 9, following the official steps:
# https://docs.openmoonray.org/getting-started/installation/building-moonray/rocky9_container_build/
# CPU only (--nocuda, MOONRAY_USE_OPTIX=NO). See README.md for build time and options.
FROM rockylinux:9

SHELL ["/bin/bash", "-c"]

# The openmoonray repository uses submodules and Git LFS for test data.
RUN dnf install -y git git-lfs \
    && git lfs install

ARG OPENMOONRAY_REPO=https://github.com/dreamworksanimation/openmoonray.git
# A released tag, so a rebuild produces the same MoonRay. Passed to `git clone --branch`.
ARG OPENMOONRAY_REF=v2026.29.1

# The moonray/materialx_shaders submodule points at a private repository (404).
RUN git clone --branch "${OPENMOONRAY_REF}" "${OPENMOONRAY_REPO}" /source \
    && cd /source \
    && git config submodule."moonray/materialx_shaders".update none \
    && git submodule update --init --recursive \
    && echo "${OPENMOONRAY_REF} $(git rev-parse HEAD)" > /openmoonray-ref.txt

# Step 1: install the system packages MoonRay's build needs.
RUN source /source/building/Rocky9/install_packages.sh --nocuda \
    && dnf clean all

# The EPEL cmake crashes in libuv under x86_64 emulation; the pip wheel bundles its own.
RUN pip3 install "cmake<4"

# Step 2: build the remaining dependencies. Removing /build in the same layer
# keeps the dependency build tree out of the image.
RUN mkdir /build \
    && cd /build \
    && cmake /source/building/Rocky9 \
    && cmake --build . -- -j "$(nproc)" \
    && rm -rf /build

# Step 3: build and install MoonRay. The rocky9-release preset points CMake at
# the step 2 dependencies and installs to /installs/openmoonray.
RUN cd /source \
    && cmake --preset rocky9-release -DMOONRAY_USE_OPTIX=NO \
    && cmake --build --preset rocky9-release -- -j "$(nproc)" \
    && rm -rf /build

# The Docker queue environment runs commands without a login shell, so set what
# scripts/setup.sh would export. Mirrors setup.sh at OPENMOONRAY_REF; re-check when bumping it.
ENV PATH=/installs/openmoonray/bin:${PATH} \
    PYTHONPATH=/installs/lib/python:/usr/local/lib/python:/installs/lib64/python3.9/site-packages/ \
    RDL2_DSO_PATH=/installs/openmoonray/rdl2dso \
    REZ_MOONRAY_ROOT=/installs/openmoonray \
    ARRAS_SESSION_PATH=/installs/openmoonray/sessions \
    MOONRAY_CLASS_PATH=/installs/openmoonray/shader_json \
    PXR_PLUGINPATH_NAME=/installs/openmoonray/plugin/pxr \
    PXR_PLUGIN_PATH=/installs/openmoonray/plugin/pxr

# setup.sh builds the shader descriptions on first use; build them once here.
RUN rdl2_json_exporter --out /installs/openmoonray/shader_json/ --sparse

# Smoke test with the job's flags. -auto_affinity off: no CAP_SYS_NICE in containers.
RUN cd /source/testdata \
    && moonray -in rectangle.rdla -auto_affinity off -res 8 -out /tmp/smoke.exr \
    && test -s /tmp/smoke.exr \
    && rm -f /tmp/smoke.exr

CMD ["moonray", "-help"]
