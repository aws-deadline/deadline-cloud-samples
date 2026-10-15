#!/bin/env bash
set -xeuo pipefail

# Let pip resolve and install dependencies, which the conda build defaults turn off.
unset PIP_NO_DEPENDENCIES
unset PIP_IGNORE_INSTALLED
unset PIP_NO_INDEX
export PIP_NO_CACHE_DIR=1

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

mkdir -p "$PREFIX/opt"
cp -r "$SRC_DIR/comfyui" "$PREFIX/opt/"

# Without the constraints, the second install can replace the CUDA torch build.
printf 'torch==%s\ntorchvision==%s\n' "$TORCH_VERSION" "$TORCHVISION_VERSION" > "$SRC_DIR/constraints.txt"

echo "openjd_status: Installing PyTorch $TORCH_VERSION ($TORCH_CUDA_INDEX)"
pip_install -c "$SRC_DIR/constraints.txt" torch torchvision \
    --index-url "https://download.pytorch.org/whl/$TORCH_CUDA_INDEX"

# manager_requirements.txt is skipped: ComfyUI-Manager can't install nodes into a shared conda env.
echo "openjd_status: Installing ComfyUI $PKG_VERSION requirements"
pip_install -c "$SRC_DIR/constraints.txt" -r "$PREFIX/opt/comfyui/requirements.txt"
pip check

pip freeze > "$PREFIX/opt/comfyui/pip-freeze.txt"

install -m 0755 "$RECIPE_DIR/comfyui-launcher.sh" "$PREFIX/bin/comfyui"

mkdir -p "$PREFIX/etc/conda/env_vars.d"
cat > "$PREFIX/etc/conda/env_vars.d/$PKG_NAME-$PKG_VERSION.json" << EOF
{
  "COMFYUI_LOCATION": "$PREFIX/opt/comfyui",
  "COMFYUI_VERSION": "$PKG_VERSION",
  "PYTHONUNBUFFERED": "1"
}
EOF

echo "openjd_status: Finished comfyui package build"
