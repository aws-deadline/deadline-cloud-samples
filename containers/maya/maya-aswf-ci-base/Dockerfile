# syntax=docker/dockerfile:1
# Autodesk Maya Docker image for AWS Deadline Cloud container rendering
# Base: ASWF ci-base (Rocky Linux 8, VFX Platform compliant, CUDA included)
#
# This uses the Academy Software Foundation's Docker base image which includes:
# - Rocky Linux 8 (industry standard for VFX, and what Maya's Linux build targets)
# - CUDA runtime (GPU rendering with V-Ray GPU and Redshift)
# - VFX Platform libraries (Python, TBB, Boost, OpenEXR, etc.)
# - OpenGL/Mesa pre-configured
#
# Build with build.sh. It supplies the two named build contexts this file needs,
# so a plain `docker build .` does not work:
#   installers  directory with the customer-supplied Maya, MtoA, V-Ray and
#               Redshift installers. It is bind mounted read-only while each
#               component installs, so the multi-GB archives never enter a layer.
#   plugins     directory with optional Maya modules, plug-ins and scripts.
#
# Each ARG is declared right before the first RUN that uses it, and each script
# is copied right before the RUN that uses it, so the Maya layer is shared by
# every renderer variant and changing one renderer flag or script only rebuilds
# the layers after it.

ARG VFX_PLATFORM_YEAR=2026
FROM aswf/ci-base:${VFX_PLATFORM_YEAR}

ARG MAYA_VERSION=2027

# --- System libraries ---
# The base image already ships most of the X11, Mesa and xcb libraries Maya and
# the renderers load; this adds the missing ones and pins the rest as explicit
# dependencies. binutils provides strip, used to drop the debug information the
# installers ship with. scripts/verify.sh runs ldd over the installed binaries
# later and fails the build if anything is still unresolved.
RUN dnf install -y epel-release dnf-plugins-core \
    && dnf config-manager --set-enabled powertools \
    && dnf install -y --setopt=install_weak_deps=False \
        unzip tar gzip xz bzip2 which patchelf binutils file \
        libva libvdpau pciutils-libs openjpeg2 libatomic libgomp \
        alsa-lib pulseaudio-libs libsndfile \
        freetype fontconfig harfbuzz graphite2 brotli \
        libxkbfile libxkbcommon libxkbcommon-x11 libxcb \
        xcb-util xcb-util-image xcb-util-keysyms xcb-util-renderutil xcb-util-wm xcb-util-cursor \
        mesa-libGL mesa-libGLU mesa-libEGL libglvnd-glx libglvnd-egl libglvnd-opengl \
        libX11 libXext libXfixes libXi libXrender libXxf86vm libXpm libXcursor libXrandr \
        libXinerama libXcomposite libXdamage libXtst libXScrnSaver libXmu libXt libSM libICE \
        libtiff libjpeg-turbo libpng dbus-libs nss nspr cups-libs libxslt libxml2 \
    && dnf clean all \
    && rm -rf /var/cache/dnf

# --- Install Maya ---
# Installs the Maya RPM, the ADP SDK (Maya 2027 exits 255 without it) and the
# legacy thin-client licensing configuration. See scripts/install_maya.sh.
COPY --chmod=0755 scripts/common.sh scripts/install_maya.sh /opt/maya-container/scripts/
RUN --mount=type=bind,from=installers,target=/installers,ro \
    bash /opt/maya-container/scripts/install_maya.sh

# --- Install the Deadline Cloud Maya adaptor ---
# Provides the maya-openjd and MayaAdaptor entry points in /usr/local/bin.
ARG ADAPTOR_VERSION=0.15.13
RUN pip3 install --no-cache-dir deadline-cloud-for-maya==${ADAPTOR_VERSION} \
    && for cmd in maya-openjd MayaAdaptor; do \
        [ -e "/usr/local/bin/$cmd" ] || ln -s "$(command -v "$cmd")" "/usr/local/bin/$cmd"; \
    done

# --- Optional renderers ---
# Each script is a no-op when its WITH_* argument is 0.
ARG WITH_ARNOLD=0
COPY --chmod=0755 scripts/install_arnold.sh /opt/maya-container/scripts/
RUN --mount=type=bind,from=installers,target=/installers,ro \
    bash /opt/maya-container/scripts/install_arnold.sh

ARG WITH_VRAY=0
COPY --chmod=0755 scripts/install_vray.sh /opt/maya-container/scripts/
RUN --mount=type=bind,from=installers,target=/installers,ro \
    bash /opt/maya-container/scripts/install_vray.sh

ARG WITH_REDSHIFT=0
COPY --chmod=0755 scripts/install_redshift.sh /opt/maya-container/scripts/
RUN --mount=type=bind,from=installers,target=/installers,ro \
    bash /opt/maya-container/scripts/install_redshift.sh

# --- Install user-supplied Maya modules, plug-ins and scripts (optional) ---
# Copies the plugins build context to /opt/maya-plugins, which is on the Maya
# search paths set below. A no-op when the directory only holds .gitkeep.
COPY --chmod=0755 scripts/install_plugins.sh /opt/maya-container/scripts/
RUN --mount=type=bind,from=plugins,target=/plugins,ro \
    bash /opt/maya-container/scripts/install_plugins.sh

# --- Environment ---
# `docker exec` starts from a clean environment, so everything a render needs
# has to be set here. Maya's own bin directory goes at the END of PATH: it
# contains python3 and pip3, which must not shadow the interpreter the adaptor
# runs under. The launchers in /usr/local/bin (maya, mayapy, Render, kick, vray,
# redshiftCmdLine) are found first.
ENV MAYA_VERSION=${MAYA_VERSION}
ENV MAYA_LOCATION=/usr/autodesk/maya${MAYA_VERSION}
ENV PATH=${PATH}:/usr/autodesk/maya${MAYA_VERSION}/bin:/usr/autodesk/arnold/maya${MAYA_VERSION}/bin:/usr/ChaosGroup/V-Ray/Maya${MAYA_VERSION}-x64/vray/bin:/usr/ChaosGroup/V-Ray/Maya${MAYA_VERSION}-x64/maya_vray/bin:/usr/redshift/bin

# Legacy thin-client licensing, configured by scripts/install_maya.sh. License
# server addresses (ADSKFLEX_LICENSE_FILE, redshift_LICENSE, VRAY_AUTH_CLIENT_*)
# are deliberately NOT set in the image: Deadline Cloud usage-based licensing or
# your queue environment supplies them at run time.
ENV AUTODESK_ADLM_THINCLIENT_ENV=/usr/autodesk/maya${MAYA_VERSION}/AdlmThinClientCustomEnv.xml \
    MAYA_LEGACY_THINCLIENT=1 \
    MAYA_NO_HOME=1 \
    MAYA_DISABLE_ADP=1 \
    MAYA_DISABLE_CIP=1 \
    MAYA_DISABLE_CER=1 \
    ARNOLD_ADP_DISABLE=1

# Writable locations that do not depend on $HOME. The container may run as root
# or as an arbitrary host UID with no passwd entry and HOME=/, so Maya's
# preferences and Redshift's local data go to world-writable directories.
ENV MAYA_APP_DIR=/var/tmp/maya-app-dir \
    REDSHIFT_LOCALDATAPATH=/var/tmp/redshift-cache

# Search paths: the renderer modules in /usr/autodesk/modules/maya/<version>
# and the user-supplied content in /opt/maya-plugins (see install_plugins.sh).
ENV MAYA_MODULE_PATH=/opt/maya-plugins:/usr/autodesk/maya${MAYA_VERSION}/modules:/usr/autodesk/modules/maya/${MAYA_VERSION}:/usr/autodesk/modules/maya \
    MAYA_PLUG_IN_PATH=/opt/maya-plugins/plug-ins \
    MAYA_SCRIPT_PATH=/opt/maya-plugins/scripts \
    PYTHONPATH=/opt/maya-plugins/scripts

ENV NVIDIA_VISIBLE_DEVICES=all
ENV NVIDIA_DRIVER_CAPABILITIES=compute,utility,graphics

# Maya's Qt and the adaptor's Python expect a UTF-8 locale; without one Maya
# prints a locale warning at every start.
ENV LANG=C.UTF-8

RUN mkdir -p /var/tmp/maya-app-dir /var/tmp/redshift-cache \
    && chmod 1777 /var/tmp/maya-app-dir /var/tmp/redshift-cache

# --- Verify installations ---
# License-free checks: mayapy imports Maya and renders a frame to PNG, the
# adaptor and renderer executables answer --help/--version, the Autodesk
# licensing libraries are unmodified, and an ldd scan fails the build when a
# shared library is missing. See scripts/verify.sh.
COPY --chmod=0755 scripts/verify.sh /opt/maya-container/scripts/
RUN bash /opt/maya-container/scripts/verify.sh

# --- UID handling ---
ARG JOB_USER_UID=1001
RUN useradd --uid ${JOB_USER_UID} --create-home --shell /bin/bash jobuser
USER jobuser

CMD ["bash", "-c", "sleep infinity"]
