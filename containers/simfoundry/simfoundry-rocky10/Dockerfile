# SimFoundry's four core conda envs (simfoundry, hunyuan, any6d, da3) on Rocky Linux 10 with
# the CUDA 12.8 toolkit. Together they run pipelines A, B and C. The optional
# auto-background (void, nerfstudio_simfoundry, 3dgrut) and articulation envs are left out.
#
# The build needs no GPU. Run verify-simfoundry on a GPU host before you push the image.
#
# Build (several hours):
#   docker build --platform linux/amd64 -t simfoundry:9e34ebe .
#
# Check on a GPU host:
#   docker run --rm --gpus all simfoundry:9e34ebe verify-simfoundry

# Rocky 10 because Isaac Sim 5.1 links hypot@GLIBC_2.35 (omni.usd.libs, lula), and Rocky 9
# has glibc 2.34. NVIDIA publishes Rocky 10 images only for CUDA 13, so this takes the base
# image and installs the 12.8 toolkit the installers need beside it.
FROM nvidia/cuda:13.0.1-base-rockylinux10

SHELL ["/bin/bash", "-o", "pipefail", "-c"]

# Isaac Sim loads the X, GL and Vulkan client libraries even when it runs headless.
# gcc builds the stages' C extensions. ffmpeg comes from conda-forge in the simfoundry env,
# which is where the stages that call it run.
RUN dnf install -y --setopt=install_weak_deps=False \
        bzip2 ca-certificates diffutils findutils gcc gcc-c++ git git-lfs make patch \
        procps-ng tar unzip wget which xz \
        alsa-lib libglvnd-egl libglvnd-glx libglvnd-opengl libgomp libICE libSM libX11 \
        libXcursor libXext libXi libXinerama libXrandr libXrender libXt libxkbcommon \
        mesa-libGLU nss vulkan-loader \
    && dnf clean all \
    && rm -rf /var/cache/dnf

# The installers hard-code CUDA_HOME=/usr/local/cuda-12.8, and torch 2.7.0 is built for
# cu128. NVIDIA's Rocky 10 repository has no 12.x packages, so use the runfile's toolkit
# only, with no driver. The md5 is NVIDIA's published sum for this file.
ARG CUDA_RUNFILE=cuda_12.8.1_570.124.06_linux.run
ARG CUDA_RUNFILE_MD5=e281945bf4ea42788db29457ebc1e6ae
RUN curl -fsSL -o /tmp/cuda.run \
        "https://developer.download.nvidia.com/compute/cuda/12.8.1/local_installers/${CUDA_RUNFILE}" \
    && echo "${CUDA_RUNFILE_MD5}  /tmp/cuda.run" | md5sum -c - \
    && sh /tmp/cuda.run --silent --toolkit --toolkitpath=/usr/local/cuda-12.8 \
        --no-opengl-libs --no-man-page --no-drm --override --tmpdir=/tmp \
    && rm -rf /tmp/cuda.run /tmp/cuda-installer.log /usr/local/cuda-12.8/{nsight*,libnvvp,extras/demo_suite} \
    && ln -sfn /usr/local/cuda-12.8 /usr/local/cuda \
    && /usr/local/cuda-12.8/bin/nvcc --version | tail -1

# The base image advertises CUDA 13, which needs a 580 driver. Everything here is built for
# 12.8, so ask the toolkit for a driver that supports 12.8 instead. The graphics capability
# makes the NVIDIA Container Toolkit mount the driver's EGL and Vulkan libraries and their
# loader manifests, which Isaac Sim's renderer needs. Don't add manifests of your own:
# Isaac Sim sees a second ICD for the same GPU and warns that it may crash.
ENV PATH=/usr/local/cuda-12.8/bin:${PATH} \
    LD_LIBRARY_PATH=/usr/local/nvidia/lib:/usr/local/nvidia/lib64:/usr/local/cuda-12.8/lib64 \
    CUDA_VERSION=12.8.1 \
    NVIDIA_REQUIRE_CUDA="cuda>=12.8" \
    NVIDIA_DRIVER_CAPABILITIES=all

# Every installer calls mamba, and needs mamba 2 for `mamba shell hook`.
ARG MINIFORGE_VERSION=26.9.4-2
RUN curl -fsSL -o /tmp/miniforge.sh \
        "https://github.com/conda-forge/miniforge/releases/download/${MINIFORGE_VERSION}/Miniforge3-${MINIFORGE_VERSION}-Linux-x86_64.sh" \
    && bash /tmp/miniforge.sh -b -p /opt/conda \
    && rm /tmp/miniforge.sh
ENV PATH=/opt/conda/bin:${PATH} \
    MAMBA_ROOT_PREFIX=/opt/conda \
    PIP_NO_CACHE_DIR=1

# SimFoundry is pinned to a commit, and its installers pin every dependency they clone.
# The package derives Data/, checkpoints/ and deps/ from its own location, so it stays at
# one fixed path. Git LFS only holds README images, so they are skipped.
ARG SIMFOUNDRY_REF=9e34ebefcd020583fbb755a8b57268dce78eca26
ENV SIMFOUNDRY_ROOT=/opt/SimFoundry
RUN GIT_LFS_SKIP_SMUDGE=1 git clone --quiet https://github.com/NVlabs/SimFoundry.git "${SIMFOUNDRY_ROOT}" \
    && git -C "${SIMFOUNDRY_ROOT}" checkout --quiet --detach "${SIMFOUNDRY_REF}"

# The installers read compute capabilities from nvidia-smi, which a build doesn't have.
# 8.6 is the A10G (g5). 8.9 is the L4 (g6) and L40S (g6e). CUDA extensions built
# without a matching arch fail at run time with "no kernel image is available".
ARG CUDA_ARCH_LIST="8.6;8.9"
# Parallel nvcc jobs for flash-attn, xformers and the FoundationPose extensions.
# Each one can take 8 GB of RAM or more, so 4 suits a 64 GB build host.
ARG MAX_JOBS=4

# Upstream's FAISS check runs a search on the GPU, so it fails in a build. Swap in a check
# that the GPU symbols exist, then restore the upstream file once the envs are built.
COPY scripts/faiss_gpu_build.sh /tmp/faiss_gpu_build.sh
RUN cd "${SIMFOUNDRY_ROOT}/scripts/installation" \
    && mv faiss_gpu.sh faiss_gpu.upstream.sh \
    && mv /tmp/faiss_gpu_build.sh faiss_gpu.sh

# The installers leave most PyPI requirements unpinned, so a fresh build picks up releases
# newer than the SimFoundry commit. pyarrow 26, for one, refuses the numpy 1.26 that the
# simfoundry env pins. Each env installs against PyPI as it was at the commit, served by a
# local index that hides later uploads. Other indexes, such as PyTorch's, are unaffected.
ARG PYPI_CUTOFF=2026-08-27T02:13:06Z
COPY scripts/pypi_cutoff_proxy.py scripts/with_pypi_cutoff.sh /usr/local/lib/simfoundry-build/
RUN chmod 0755 /usr/local/lib/simfoundry-build/with_pypi_cutoff.sh \
    && ln -s /usr/local/lib/simfoundry-build/with_pypi_cutoff.sh /usr/local/bin/with-pypi-cutoff

# One layer per env, so a failed env rebuilds without the ones before it.
# CONDA_OVERRIDE_CUDA lets mamba solve CUDA packages without a driver.
# simfoundry also installs OmniGibson and Isaac Sim, and accepts the NVIDIA Omniverse
# EULA and the BEHAVIOR-1K dataset terms on your behalf.
#
# evdev generates its constants from /usr/include but compiles with conda's gcc against
# conda's kernel headers. Rocky 10's headers carry backported constants that conda's lack,
# so evdev is built here with the system gcc, and the installer finds it and skips it.
# The installer reuses an existing env, and this one is what it would have created.
RUN mamba create -y -n simfoundry python=3.11 "pip<25.3" \
    && CC=gcc LDSHARED="gcc -shared" mamba run -n simfoundry pip install "evdev==1.9.3" \
    && mamba clean -afy

RUN CONDA_OVERRIDE_CUDA=12.8 MAX_JOBS="${MAX_JOBS}" with-pypi-cutoff "${PYPI_CUTOFF}" \
        bash "${SIMFOUNDRY_ROOT}/scripts/installation/install_simfoundry.sh" \
        --project-root "${SIMFOUNDRY_ROOT}" --env-name simfoundry --default \
        --cuda-arch-list "${CUDA_ARCH_LIST}" \
    && mamba clean -afy && rm -rf /root/.cache/pip

RUN CONDA_OVERRIDE_CUDA=12.8 MAX_JOBS="${MAX_JOBS}" with-pypi-cutoff "${PYPI_CUTOFF}" \
        bash "${SIMFOUNDRY_ROOT}/scripts/installation/install_hunyuan.sh" \
        --project-root "${SIMFOUNDRY_ROOT}" --env-name hunyuan --default \
        --cuda-arch-list "${CUDA_ARCH_LIST}" \
    && mamba clean -afy && rm -rf /root/.cache/pip

RUN CONDA_OVERRIDE_CUDA=12.8 MAX_JOBS="${MAX_JOBS}" with-pypi-cutoff "${PYPI_CUTOFF}" \
        bash "${SIMFOUNDRY_ROOT}/scripts/installation/install_any6d.sh" \
        --project-root "${SIMFOUNDRY_ROOT}" --env-name any6d --default \
        --cuda-arch-list "${CUDA_ARCH_LIST}" \
    && mamba clean -afy && rm -rf /root/.cache/pip

RUN CONDA_OVERRIDE_CUDA=12.8 MAX_JOBS="${MAX_JOBS}" with-pypi-cutoff "${PYPI_CUTOFF}" \
        bash "${SIMFOUNDRY_ROOT}/scripts/installation/install_da3.sh" \
        --project-root "${SIMFOUNDRY_ROOT}" --env-name da3 --default \
        --cuda-arch-list "${CUDA_ARCH_LIST}" \
    && mamba clean -afy && rm -rf /root/.cache/pip

RUN cd "${SIMFOUNDRY_ROOT}/scripts/installation" \
    && mv faiss_gpu.upstream.sh faiss_gpu.sh \
    && git -C "${SIMFOUNDRY_ROOT}" diff --exit-code --stat

# Public checkpoints the core envs read from fixed paths under the repo. HF_HUB_OFFLINE
# stops the script from also pulling the auto-background VOID base model, about 20 GB
# that the core pipeline doesn't use. The script exits non-zero for those skipped VOID
# files, so check the core files directly. Google Drive rate-limits gdown, so retry the
# build if it fails here. Set BAKE_CHECKPOINTS=0 to skip this step.
ARG BAKE_CHECKPOINTS=1
RUN if [[ "${BAKE_CHECKPOINTS}" == 1 ]]; then \
        HF_HUB_OFFLINE=1 bash "${SIMFOUNDRY_ROOT}/scripts/installation/download_checkpoints.sh" \
            --project-root "${SIMFOUNDRY_ROOT}" --env-name simfoundry --default || true; \
        for f in \
            deps/FoundationStereo/pretrained_models/23-51-11/model_best_bp2.pth \
            deps/FoundationPose/weights/2023-10-28-18-33-37/model_best.pth \
            deps/FoundationPose/weights/2024-01-11-20-02-45/model_best.pth \
            checkpoints/sam2.1_hiera_large.pt \
            deps/ml-depth-pro/checkpoints/depth_pro.pt \
            deps/Hunyuan3D-2.1/ckpt/RealESRGAN_x4plus.pth; do \
            test -s "${SIMFOUNDRY_ROOT}/$f" || { echo "missing checkpoint: $f" >&2; exit 1; }; \
        done; \
        rm -rf /root/.cache/pip; \
    fi

# The checks INSTALL.md lists that need no GPU: every env imports simfoundry from this
# checkout, and each pipeline prints its stage plan.
RUN for env in simfoundry hunyuan any6d da3; do \
        mamba run -n "${env}" python -c "import os, torch, simfoundry; \
assert simfoundry.__file__.startswith(os.environ['SIMFOUNDRY_ROOT'] + '/'), simfoundry.__file__; \
print('${env}', torch.__version__)"; \
    done \
    && cd "${SIMFOUNDRY_ROOT}" \
    && bash scripts/pipeline/A_reconstruction/run.sh --dry-run --include 1b,2 \
    && bash scripts/pipeline/B_augmentation/run.sh --dry-run --include 1 \
    && bash scripts/pipeline/C_application/run.sh --dry-run --mode smoke-random

# Gated Hugging Face models (SAM3, RMBG-2.0, DINOv3) and the Hunyuan3D and DA3 weights
# download on first use, into HF_HOME. Mount persistent storage there to reuse them.
ENV HF_HOME=/opt/simfoundry-cache/huggingface \
    OMNI_KIT_ACCEPT_EULA=YES \
    PYTHONUNBUFFERED=1
RUN mkdir -p "${HF_HOME}" && chmod -R a+rwX /opt/simfoundry-cache

COPY scripts/verify.sh /usr/local/bin/verify-simfoundry
RUN chmod 0755 /usr/local/bin/verify-simfoundry

# Record what was baked in, for provenance. The deps/ commits are read from the checkouts
# rather than the installers, so they show what was actually built.
RUN { \
        echo "simfoundry=${SIMFOUNDRY_REF}"; \
        echo "base=nvidia/cuda:13.0.1-base-rockylinux10 cuda_toolkit=${CUDA_VERSION}"; \
        echo "cuda_arch_list=${CUDA_ARCH_LIST}"; \
        echo "pypi_cutoff=${PYPI_CUTOFF}"; \
        echo "checkpoints_baked=${BAKE_CHECKPOINTS}"; \
        for d in "${SIMFOUNDRY_ROOT}"/deps/*/ "${SIMFOUNDRY_ROOT}"/deps/*/extensions/*/; do \
            if [[ -e "${d}.git" ]]; then echo "${d#"${SIMFOUNDRY_ROOT}"/}=$(git -C "${d}" rev-parse HEAD)"; fi; \
        done; \
        echo "isaacsim=$(mamba run -n simfoundry pip show isaacsim 2>/dev/null | awk '/^Version:/{print $2}')"; \
        for env in simfoundry hunyuan any6d da3; do \
            echo "torch_${env}=$(mamba run -n "${env}" python -c 'import torch; print(torch.__version__)')"; \
        done; \
    } > /simfoundry-refs.txt

WORKDIR /opt/SimFoundry

# No ENTRYPOINT. Deadline Cloud runs each job command as an argv inside a running
# container, so local runs pass the command the same way.
CMD ["cat", "/simfoundry-refs.txt"]
