# LIBERO policy evaluation with LeRobot, for NVIDIA GPU workers.
#
# The LIBERO benchmark assets and the policy weights are downloaded when you build
# the image, from the Hugging Face Hub. The LIBERO asset collection does not state a
# license, so do not publish an image built from this file. Push it only to your own
# private Amazon ECR repository.
FROM python:3.12-slim

ARG LEROBOT_VERSION=0.6.1
# LIBERO's stored initial states don't settle correctly on MuJoCo 3.4 or later
# (https://github.com/huggingface/lerobot/issues/4390), so stay on 3.3.x.
ARG MUJOCO_VERSION=3.3.7
# CUDA 12.8 builds of PyTorch work with NVIDIA drivers 525 and later. The default
# PyPI build targets CUDA 13, which needs driver 580 or later.
ARG TORCH_INDEX=https://download.pytorch.org/whl/cu128
# Space-separated Hugging Face policy repositories to bake into the image.
ARG POLICIES="lerobot/xvla-libero lerobot/smolvla_libero"

ENV DEBIAN_FRONTEND=noninteractive \
    PIP_NO_CACHE_DIR=1 \
    MUJOCO_GL=egl \
    PYOPENGL_PLATFORM=egl \
    NVIDIA_DRIVER_CAPABILITIES=all \
    HF_HOME=/opt/hf \
    LIBERO_CONFIG_PATH=/opt/libero

RUN apt-get update && apt-get install -y --no-install-recommends \
        libegl1 libgl1 libglib2.0-0 ffmpeg git build-essential cmake \
    && rm -rf /var/lib/apt/lists/*

# Install PyTorch first from the CUDA 12.8 index, then pin it so the LeRobot
# install can't replace it with a different build.
RUN pip install --index-url "${TORCH_INDEX}" "torch>=2.7,<2.12" torchvision \
    && python -c "import torch; print('torch==' + torch.__version__.split('+')[0])" > /tmp/constraints.txt \
    && pip install --extra-index-url "${TORCH_INDEX}" -c /tmp/constraints.txt \
        "lerobot[libero,smolvla,xvla]==${LEROBOT_VERSION}" "mujoco==${MUJOCO_VERSION}" tensorboard \
    && rm -rf /root/.cache

# Download the assets and weights, write LIBERO's config, and fix permissions in a
# single step: a chmod in a later layer would store a second copy of every file.
# LIBERO prompts for input when its config file is missing, which would hang a
# headless job. hf-libero also ignores the config's "assets" entry and looks inside
# its own package, so the assets are linked there.
COPY fetch_models.py /tmp/fetch_models.py
RUN mkdir -p "${LIBERO_CONFIG_PATH}" \
    && POLICIES="${POLICIES}" python /tmp/fetch_models.py \
    && LIBERO_DIR=$(python -c "import importlib.util, os; s=importlib.util.find_spec('libero'); print(os.path.join(os.path.dirname(s.origin), 'libero'))") \
    && printf "assets: /opt/libero/assets\nbddl_files: %s/bddl_files\ndatasets: %s/../datasets\ninit_states: %s/init_files\n" \
        "${LIBERO_DIR}" "${LIBERO_DIR}" "${LIBERO_DIR}" > "${LIBERO_CONFIG_PATH}/config.yaml" \
    && ln -s /opt/libero/assets "${LIBERO_DIR}/assets" \
    && chmod -R a+rX /opt/hf /opt/libero

# Tasks run without network access, from the files baked in above.
ENV HF_HUB_OFFLINE=1
WORKDIR /work
CMD ["lerobot-eval", "--help"]
