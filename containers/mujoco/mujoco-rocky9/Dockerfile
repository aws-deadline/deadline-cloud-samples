# MuJoCo on Rocky Linux 9, CPU only, with headless offscreen rendering.
# MuJoCo ships manylinux wheels, so nothing is compiled here.
#
# Build:
#   docker build --platform linux/amd64 -t mujoco-rocky9:3.11.0 .
#
# Smoke test:
#   docker run --rm mujoco-rocky9:3.11.0 mj-hand-sweep --help
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

# Pinned so a rebuild produces the same MuJoCo. Its wheel needs Python 3.11 or later.
ARG MUJOCO_VERSION=3.11.0
RUN python3.12 -m pip install --no-cache-dir \
        "mujoco==${MUJOCO_VERSION}" \
        "numpy" \
        "pillow" \
    # Rocky's /usr/bin/python3 is 3.9. These links make plain `python3` resolve to 3.12.
    && ln -sf /usr/bin/python3.12 /usr/local/bin/python \
    && ln -sf /usr/bin/python3.12 /usr/local/bin/python3

# Models are pinned to commits, so the scene geometry cannot shift under a rebuild.
ARG CUBE_REF=bfd39af77043a3d9e44898c7db4288882a11ea72
ARG MENAGERIE_REF=71f066ad0be9cd271f7ed58c030243ef157af9f4

# A 3x3x3 puzzle cube model. Its core body is welded to the world.
RUN git clone --quiet https://github.com/kevinzakka/mujoco_cube.git /models/mujoco_cube \
    && git -C /models/mujoco_cube checkout --quiet "${CUBE_REF}" \
    && rm -rf /models/mujoco_cube/.git

# MuJoCo Menagerie is large, so take only shadow_hand with a blobless sparse checkout.
RUN git clone --quiet --filter=blob:none --sparse \
        https://github.com/google-deepmind/mujoco_menagerie.git /models/mujoco_menagerie \
    && git -C /models/mujoco_menagerie checkout --quiet "${MENAGERIE_REF}" \
    && git -C /models/mujoco_menagerie sparse-checkout set shadow_hand \
    && rm -rf /models/mujoco_menagerie/.git

# Record what was baked in, for provenance.
RUN printf 'mujoco=%s\ncube=%s\nmenagerie=%s\n' \
        "$(python3.12 -c 'import mujoco; print(mujoco.__version__)')" \
        "${CUBE_REF}" "${MENAGERIE_REF}" > /mujoco-refs.txt

# One sweep point: scale the physics, simulate, render frames and an MP4.
# The job in ../job_bundle/ runs it once per task.
COPY scripts/mj_hand_sweep.py /usr/local/bin/mj-hand-sweep
RUN chmod 0755 /usr/local/bin/mj-hand-sweep

# The right hand holding a sphere. It sits next to the hand model because its
# <include> and meshdir resolve relative to the main model file.
COPY scenes/scene_right_ball.xml /models/mujoco_menagerie/shadow_hand/scene_right_ball.xml

# EGL is the only headless backend on Rocky 9, which has no OSMesa package.
ENV MUJOCO_GL=egl
ENV PYTHONUNBUFFERED=1

# Fail the build if headless rendering is broken: render one cube frame and
# check that the pixels are not all black.
RUN cd /models/mujoco_cube \
    && python3.12 -c "\
import mujoco, sys;\
m = mujoco.MjModel.from_xml_path('cube_3x3x3.xml');\
d = mujoco.MjData(m);\
mujoco.mj_forward(m, d);\
r = mujoco.Renderer(m, 120, 160);\
r.update_scene(d);\
px = r.render();\
sys.exit(0 if px.sum() > 0 else 'offscreen render produced an empty frame')" \
    && echo "build-time render check passed"

# Fail the build if a relative --out-dir doesn't land under the working directory.
# mj-hand-sweep changes into the model's directory to compile it.
RUN cd /tmp \
    && mj-hand-sweep --model /models/mujoco_menagerie/shadow_hand/scene_right_ball.xml \
        --duration 0.1 --fps 10 --width 64 --height 48 --no-video \
        --label out-dir-check --out-dir out-dir-check \
    && test -s /tmp/out-dir-check/metrics.json \
    && rm -rf /tmp/out-dir-check \
    && echo "build-time out-dir check passed"

WORKDIR /models

# No ENTRYPOINT. Deadline Cloud runs each job command as an argv inside a running
# container, so local runs pass the command the same way.
CMD ["cat", "/mujoco-refs.txt"]
