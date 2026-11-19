# MuJoCo 4.0.0 on Rocky Linux 9, CPU only, with headless offscreen rendering.
# MuJoCo ships manylinux wheels, so nothing is compiled here.
#
# Build:
#   docker build --platform linux/amd64 -t mujoco4-rocky9:4.0.0 .
#
# Smoke test:
#   docker run --rm mujoco4-rocky9:4.0.0 mj4-sweep --help
FROM rockylinux:9

# mesa-dri-drivers provides the llvmpipe software rasterizer, and the EGL packages
# provide the offscreen context. PyOpenGL also dlopens libOpenGL and libGL, so
# mesa-libGL and libglvnd-opengl are required.
# Rocky 9 has no ffmpeg, so ffmpeg-free comes from EPEL. Its H.264 encoder needs
# the separate openh264 package.
RUN dnf install -y epel-release \
    && dnf install -y --enablerepo=crb --setopt=install_weak_deps=False \
        openh264 \
        python3.12 \
        python3.12-pip \
        git \
        mesa-libEGL \
        mesa-libGL \
        mesa-dri-drivers \
        libglvnd-egl \
        libglvnd-opengl \
        ffmpeg-free \
    && dnf clean all \
    && rm -rf /var/cache/dnf

# MuJoCo 4.0 splits the wheel. mujoco-core is the C library and Python bindings;
# its [rendering] extra adds PyOpenGL and glfw for mujoco.Renderer. The default `mujoco`
# package also installs mujoco-studio, the Filament renderer and Studio viewer,
# which a headless sweep does not use.
# Every Python package is pinned to the tested version, transitive ones included, so a
# rebuild gets the same Python stack. The base image and dnf packages are not pinned.
ARG MUJOCO_VERSION=4.0.0
RUN python3.12 -m pip install --no-cache-dir \
        "mujoco-core[rendering]==${MUJOCO_VERSION}" \
        "numpy==2.5.5" \
        "PyOpenGL==3.1.10" \
        "glfw==2.11.0" \
        "pillow==13.0.0" \
    # Rocky's /usr/bin/python3 is 3.9. These links make plain `python3` resolve to 3.12.
    && ln -sf /usr/bin/python3.12 /usr/local/bin/python \
    && ln -sf /usr/bin/python3.12 /usr/local/bin/python3

# The plastic/ and speculative/ example models ship in the MuJoCo source tree, not
# the wheel. Take only those two directories with a blobless sparse checkout of
# MUJOCO_REF, the commit the 4.0.0 tag points to. Checking out the commit rather than
# the tag means a moved tag cannot change the scenes.
ARG MUJOCO_REF=ac60eae30fa7e0d31315c38d9476752fb81be67e
RUN git clone --quiet --filter=blob:none --sparse --no-checkout \
        https://github.com/google-deepmind/mujoco.git /models/mujoco \
    && git -C /models/mujoco sparse-checkout set model/plastic model/speculative \
    && git -C /models/mujoco checkout --quiet "${MUJOCO_REF}" \
    && rm -rf /models/mujoco/.git

# Record what was baked in, for provenance.
RUN printf 'mujoco=%s\nmodels=%s\n' \
        "$(python3.12 -c 'import mujoco; print(mujoco.__version__)')" \
        "${MUJOCO_REF}" > /mujoco-refs.txt

# One sweep point: set the physics, simulate, render frames and an MP4.
# mj4-summarize turns a directory of their metrics.json files into one table.
# The jobs in ../ run each once per task, then summarize once.
COPY scripts/mj4_sweep.py /usr/local/bin/mj4-sweep
COPY scripts/mj4_summarize.py /usr/local/bin/mj4-summarize
RUN chmod 0755 /usr/local/bin/mj4-sweep /usr/local/bin/mj4-summarize

# EGL is the only headless backend on Rocky 9, which has no OSMesa package.
ENV MUJOCO_GL=egl
ENV PYTHONUNBUFFERED=1

# Fail the build if headless rendering, MP4 encoding or either sweep is broken: run
# each for a fraction of a second from /tmp, so a relative --out-dir must land there.
RUN cd /tmp \
    && mj4-sweep torsion --yield-strain 0.025 --duration 0.05 --fps 20 --width 64 --height 48 \
        --no-video --label torsion-check --out-dir torsion-check \
    && mj4-sweep cradle --timestep-ms 4 --speculative enable --duration 0.25 --fps 20 \
        --width 64 --height 48 --label cradle-check --out-dir cradle-check \
    && test -s /tmp/torsion-check/metrics.json \
    && test -s /tmp/cradle-check/metrics.json \
    && test -s /tmp/cradle-check/clip.mp4 \
    && mj4-summarize /tmp/torsion-check /tmp/cradle-check \
    && rm -rf /tmp/torsion-check /tmp/cradle-check \
    && echo "build-time sweep check passed"

WORKDIR /models

# No ENTRYPOINT. Deadline Cloud runs each job command as an argv inside a running
# container, so local runs pass the command the same way.
CMD ["cat", "/mujoco-refs.txt"]
