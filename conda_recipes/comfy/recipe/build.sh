#!/bin/env bash
set -xeuo pipefail

# Let pip resolve and install dependencies, which the conda build defaults turn off.
unset PIP_NO_DEPENDENCIES
unset PIP_IGNORE_INSTALLED
unset PIP_NO_INDEX
export PIP_NO_CACHE_DIR=1
export COMFY_NO_TELEMETRY=1
# Make comfy-cli install into this prefix instead of creating its own .venv.
export CONDA_PREFIX="$PREFIX"
unset VIRTUAL_ENV

pip_install() {
    set +e
    rm -f "$SRC_DIR/pip_install_result.log"
    pip install "$@" --log "$SRC_DIR/pip_install_result.log"
    INSTALL_RESULT="$?"
    set -e
    if [ "$INSTALL_RESULT" != "0" ]; then
        cat "$SRC_DIR/pip_install_result.log"
        echo "openjd_status: Failed to pip install $@"
        exit 1
    fi
}

echo "openjd_status: Installing comfy-cli $COMFY_CLI_VERSION"
pip_install "comfy-cli==$COMFY_CLI_VERSION"

# ComfyUI-Manager is skipped: it can't install nodes into a shared conda env.
echo "openjd_status: Installing ComfyUI $COMFYUI_VERSION with comfy-cli (CUDA $CUDA_VERSION)"
mkdir -p "$PREFIX/opt"
comfy --skip-prompt --workspace "$PREFIX/opt/comfyui" install \
    --version "$COMFYUI_VERSION" \
    --nvidia --cuda-version "$CUDA_VERSION" \
    --skip-manager

if [ -d "$PREFIX/opt/comfyui/.venv" ]; then
    echo "openjd_status: comfy-cli created its own .venv instead of using the conda environment"
    exit 1
fi
test -f "$PREFIX/opt/comfyui/main.py"
pip check

pip freeze > "$PREFIX/opt/comfyui/pip-freeze.txt"
grep -E "^(torch|torchvision|torchaudio|comfy-cli)==" "$PREFIX/opt/comfyui/pip-freeze.txt"

mkdir -p "$PREFIX/etc/conda/env_vars.d"
cat > "$PREFIX/etc/conda/env_vars.d/$PKG_NAME-$PKG_VERSION.json" << EOF
{
  "COMFYUI_LOCATION": "$PREFIX/opt/comfyui",
  "COMFYUI_VERSION": "$PKG_VERSION",
  "COMFY_CLI_VERSION": "$COMFY_CLI_VERSION",
  "COMFY_NO_TELEMETRY": "1",
  "PYTHONUNBUFFERED": "1"
}
EOF

echo "openjd_status: Finished comfy package build"
