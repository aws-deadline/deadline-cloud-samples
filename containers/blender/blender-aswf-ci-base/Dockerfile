# Blender Docker image for AWS Deadline Cloud container rendering
# Base: ASWF ci-base (Rocky Linux 8, VFX Platform compliant, CUDA included)
#
# This uses the Academy Software Foundation's Docker base image which includes:
# - Rocky Linux 8 (industry standard for VFX)
# - CUDA runtime (GPU rendering)
# - VFX Platform libraries (Python, TBB, Boost, OpenEXR, etc.)
# - OpenGL/Mesa pre-configured

ARG VFX_PLATFORM_YEAR=2026
FROM aswf/ci-base:${VFX_PLATFORM_YEAR}

ARG BLENDER_VERSION=4.5.0
ARG ADAPTOR_VERSION=0.6.3

ENV NVIDIA_VISIBLE_DEVICES=all
ENV NVIDIA_DRIVER_CAPABILITIES=compute,utility,graphics

# --- Install Blender ---
# ASWF base already has most deps (OpenGL, X11, Python, etc.)
# We just need wget/xz to download and a few extra libs Blender needs
RUN yum install -y wget xz libXxf86vm libXi libXrender libSM libICE \
    libXext libXfixes libgomp mesa-libEGL alsa-lib libXpm libtiff \
    && yum clean all

RUN BLENDER_MAJOR=$(echo ${BLENDER_VERSION} | cut -d. -f1,2) \
    && wget -q https://download.blender.org/release/Blender${BLENDER_MAJOR}/blender-${BLENDER_VERSION}-linux-x64.tar.xz \
    && tar -xf blender-${BLENDER_VERSION}-linux-x64.tar.xz -C /opt/ \
    && mv /opt/blender-${BLENDER_VERSION}-linux-x64 /opt/blender \
    && rm blender-${BLENDER_VERSION}-linux-x64.tar.xz \
    && ln -s /opt/blender/blender /usr/local/bin/blender \
    && yum remove -y wget xz \
    && yum clean all

# --- Install the Deadline Cloud Blender adaptor ---
RUN pip3 install --no-cache-dir deadline-cloud-for-blender==${ADAPTOR_VERSION}

# --- Install and enable user-supplied plugins (optional) ---
COPY plugins/ /tmp/plugins/
COPY scripts/ /opt/blender-scripts/

ENV BLENDER_USER_SCRIPTS=/opt/blender-plugins
ENV BLENDER_USER_CONFIG=/opt/blender-config
RUN mkdir -p /opt/blender-plugins/addons /opt/blender-plugins/startup /opt/blender-config \
    && chmod -R 777 /opt/blender-plugins /opt/blender-config

# Extract plugins using the shared script
RUN python3 /opt/blender-scripts/extract_plugins.py \
    && rm -rf /tmp/plugins \
    && chmod -R 777 /opt/blender-plugins/addons

# Bootstrap: install and enable addons via headless Blender
RUN blender -b --python /opt/blender-scripts/bootstrap.py \
    && chmod -R 777 /opt/blender-config

# Install log_addons.py as a Blender startup script so it runs on every launch
RUN cp /opt/blender-scripts/log_addons.py /opt/blender-plugins/startup/log_addons.py

# --- Verify installations ---
RUN blender --version && blender-openjd --help > /dev/null 2>&1

# --- UID handling ---
ARG JOB_USER_UID=1001
RUN useradd --uid ${JOB_USER_UID} --create-home --shell /bin/bash jobuser
USER jobuser

CMD ["bash", "-c", "sleep infinity"]
