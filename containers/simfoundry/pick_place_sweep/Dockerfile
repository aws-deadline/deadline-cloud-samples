# Adds what the pick-and-place sweep needs on top of the SimFoundry image:
#   * NVIDIA cuRobo in the simfoundry env, for OmniGibson's StarterSemanticActionPrimitives.
#   * openpi-client in the simfoundry env, which SimFoundry's OpenPI policy client imports.
#   * OpenPI in its own uv environment at /opt/openpi, to serve a pi0.5 DROID checkpoint.
#     It pins JAX, torch and numpy versions of its own, so it stays out of the conda envs.
# No checkpoint is baked in; jobs download it at run time.
#
# Build:
#   docker build --tag simfoundry:9e34ebe-rocky10-pick .
ARG BASE=simfoundry:9e34ebe-rocky10-bedrock
FROM ${BASE}

ARG PYPI_CUTOFF=2026-08-27T02:13:06Z
ARG CUDA_ARCH_LIST="8.6;8.9"
ARG MAX_JOBS=8

# cuRobo, as pinned by OmniGibson's `primitives` extra. It compiles CUDA kernels against the
# env's torch, so build without isolation and for the fleet's GPU architectures.
ARG CUROBO_REF=88f6c617ea2ac73c7efb10449bbae28ed235b6dd
RUN CONDA_OVERRIDE_CUDA=12.8 TORCH_CUDA_ARCH_LIST="${CUDA_ARCH_LIST}" CUDA_HOME=/usr/local/cuda-12.8 \
        MAX_JOBS="${MAX_JOBS}" with-pypi-cutoff "${PYPI_CUTOFF}" \
        bash -c 'set -e; \
            mamba run -n simfoundry pip install "setuptools_scm>=6.2,<9" wheel pybind11 "packaging==25.0"; \
            mamba run -n simfoundry pip install --no-build-isolation \
                "nvidia-curobo @ git+https://github.com/StanfordVL/curobo@${CUROBO_REF}" \
                "numpy==1.26.4" "torch==2.7.0" "packaging==25.0"' \
    && rm -rf /root/.cache/pip

# OpenPI, pinned. The client goes into the simfoundry env; the server gets its own env.
ARG OPENPI_REF=215abfb217dbac7d5f1273282331b9b1866c0479
ARG UV_VERSION=0.13.9
ENV OPENPI_ROOT=/opt/openpi \
    UV_PYTHON_INSTALL_DIR=/opt/uv-python \
    UV_LINK_MODE=copy
RUN curl -fsSL "https://github.com/astral-sh/uv/releases/download/${UV_VERSION}/uv-x86_64-unknown-linux-gnu.tar.gz" \
        | tar -xz -C /usr/local/bin --strip-components=1 \
    && uv --version \
    && GIT_LFS_SKIP_SMUDGE=1 git clone --quiet https://github.com/Physical-Intelligence/openpi.git "${OPENPI_ROOT}" \
    && git -C "${OPENPI_ROOT}" checkout --quiet --detach "${OPENPI_REF}" \
    && GIT_LFS_SKIP_SMUDGE=1 git -C "${OPENPI_ROOT}" submodule update --init --recursive --quiet \
    && cd "${OPENPI_ROOT}" \
    && GIT_LFS_SKIP_SMUDGE=1 UV_CACHE_DIR=/tmp/uv-cache uv sync --frozen \
    && GIT_LFS_SKIP_SMUDGE=1 UV_CACHE_DIR=/tmp/uv-cache uv pip install --no-deps -e . \
    && rm -rf /tmp/uv-cache \
    && chmod -R a+rX "${OPENPI_ROOT}" "${UV_PYTHON_INSTALL_DIR}" \
    && with-pypi-cutoff "${PYPI_CUTOFF}" mamba run -n simfoundry pip install \
        "${OPENPI_ROOT}/packages/openpi-client" \
    && rm -rf /root/.cache/pip

# Checks that need no GPU. cuRobo's kernels load, the primitives module imports (it imports
# cuRobo lazily, so import the curobo wrapper explicitly), and OpenPI resolves the DROID
# joint-position config that SimFoundry's eval stage expects.
RUN mamba run -n simfoundry python -c "\
import torch; \
from curobo.wrap.reacher.motion_gen import MotionGen; \
from curobo.curobolib import kinematics_fused_cu, geom_cu, lbfgs_step_cu, line_search_cu, tensor_step_cu; \
import omnigibson.action_primitives.curobo as ogc; \
import openpi_client; from simfoundry.policies.openpi import OpenPIClient; \
print('curobo + openpi-client OK, torch', torch.__version__)" \
    && cd "${OPENPI_ROOT}" && .venv/bin/python -c "\
import jax, openpi; \
from openpi.training import config; from openpi.policies import policy_config; \
c = config.get_config('pi05_droid_jointpos_polaris'); \
print('openpi OK, jax', jax.__version__, c.name, c.model.action_horizon)" \
    && echo "openpi=${OPENPI_REF}" >> /simfoundry-refs.txt \
    && echo "curobo=${CUROBO_REF}" >> /simfoundry-refs.txt

# OpenPI caches downloaded checkpoints here. Jobs point it at the session directory.
ENV OPENPI_DATA_HOME=/opt/simfoundry-cache/openpi
RUN mkdir -p "${OPENPI_DATA_HOME}" && chmod -R a+rwX "${OPENPI_DATA_HOME}"
