# MuJoCo 4.0.0 on Rocky Linux 9 for NVIDIA GPU workers, with headless EGL rendering
# on the GPU. The CPU image in ../mujoco4-rocky9/ installs the same MuJoCo stack.
#
# Build from containers/mujoco-4, so the image can copy the scripts it shares with
# the CPU image:
#   docker build --platform linux/amd64 -f mujoco4-rocky9-gpu/Dockerfile \
#     -t mujoco4-rocky9-gpu:4.0.0 .
#
# Smoke test on a GPU host (the classic NVIDIA runtime or CDI):
#   docker run --rm --gpus all mujoco4-rocky9-gpu:4.0.0 nvidia-smi -L
#
# The CUDA base supplies the CUDA runtime and the NVIDIA container settings. The
# rendering driver itself (libEGL_nvidia and its glvnd vendor file) comes from the
# host when the container starts with --gpus all, so the image holds no driver.
# CUDA 13.0 needs driver 580 or later. The tested workers ran driver 595.
FROM nvidia/cuda:13.0.3-base-rockylinux9

# The NVIDIA runtime only mounts the driver libraries for the capabilities listed
# here. The base image lists compute and utility; EGL rendering also needs graphics.
ENV NVIDIA_DRIVER_CAPABILITIES=graphics,compute,utility

# libglvnd-egl is the EGL loader that dispatches to the NVIDIA vendor library.
# Mesa stays installed so the build-time check below can render on a builder with
# no GPU; at run time mj4-sweep fails rather than fall back to it (MJ4_RENDERER).
# PyOpenGL also dlopens libOpenGL and libGL, so mesa-libGL and libglvnd-opengl are
# required. Rocky 9 has no ffmpeg, so ffmpeg-free comes from EPEL. Its H.264
# encoder needs the separate openh264 package.
RUN dnf install -y epel-release \
    && dnf install -y --enablerepo=crb --setopt=install_weak_deps=False \
        openh264 \
        python3.12 \
        python3.12-pip \
        git \
        libglvnd-egl \
        libglvnd-opengl \
        mesa-libEGL \
        mesa-libGL \
        mesa-dri-drivers \
        ffmpeg-free \
    && dnf clean all \
    && rm -rf /var/cache/dnf

# The same pinned Python stack as the CPU image. See ../mujoco4-rocky9/Dockerfile.
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

# The plastic/ and speculative/ example models, from the commit the 4.0.0 tag
# points to. A moved tag cannot change the scenes.
ARG MUJOCO_REF=ac60eae30fa7e0d31315c38d9476752fb81be67e
RUN git clone --quiet --filter=blob:none --sparse --no-checkout \
        https://github.com/google-deepmind/mujoco.git /models/mujoco \
    && git -C /models/mujoco sparse-checkout set model/plastic model/speculative \
    && git -C /models/mujoco checkout --quiet "${MUJOCO_REF}" \
    && rm -rf /models/mujoco/.git

RUN printf 'mujoco=%s\nmodels=%s\ncuda=%s\n' \
        "$(python3.12 -c 'import mujoco; print(mujoco.__version__)')" \
        "${MUJOCO_REF}" "${CUDA_VERSION}" > /mujoco-refs.txt

# The same commands as the CPU image, so both produce the same metrics.json.
COPY mujoco4-rocky9/scripts/mj4_sweep.py /usr/local/bin/mj4-sweep
COPY mujoco4-rocky9/scripts/mj4_summarize.py /usr/local/bin/mj4-summarize
RUN chmod 0755 /usr/local/bin/mj4-sweep /usr/local/bin/mj4-summarize

# MuJoCo's EGL backend lists CUDA-backed EGL devices first, so it picks the GPU
# when the NVIDIA driver is present.
ENV MUJOCO_GL=egl
ENV PYTHONUNBUFFERED=1

# Fail the build if rendering, MP4 encoding or either sweep is broken. A builder
# usually has no GPU, so this check renders on Mesa with --renderer any.
RUN cd /tmp \
    && mj4-sweep torsion --yield-strain 0.025 --duration 0.05 --fps 20 --width 64 --height 48 \
        --no-video --renderer any --label torsion-check --out-dir torsion-check \
    && mj4-sweep cradle --timestep-ms 4 --speculative enable --duration 0.25 --fps 20 \
        --width 64 --height 48 --renderer any --label cradle-check --out-dir cradle-check \
    && test -s /tmp/torsion-check/metrics.json \
    && test -s /tmp/cradle-check/metrics.json \
    && test -s /tmp/cradle-check/clip.mp4 \
    && mj4-summarize /tmp/torsion-check /tmp/cradle-check \
    && rm -rf /tmp/torsion-check /tmp/cradle-check \
    && echo "build-time sweep check passed"

# Set after the check above: from here on, mj4-sweep fails any task that renders on
# the CPU rasterizer, so a missing GPU or driver can't pass as a slow success.
ENV MJ4_RENDERER=gpu

WORKDIR /models

# No ENTRYPOINT. Deadline Cloud runs each job command as an argv inside a running
# container, so local runs pass the command the same way.
CMD ["cat", "/mujoco-refs.txt"]
