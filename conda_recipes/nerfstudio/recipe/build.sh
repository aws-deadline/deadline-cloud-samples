#!/bin/env bash
set -xeuo pipefail

## Turn off "pip install" customizations from the conda build environment.
#
# This package incorporates NeRF Studio together with dependencies that conda-forge
# doesn't provide as of writing. To do this, pip install must work like normal, so
# this code turns off the conda build defaults for pip.
unset PIP_NO_DEPENDENCIES
unset PIP_IGNORE_INSTALLED
unset PIP_NO_INDEX

## Set the number of processes C++/CUDA will use, to balance memory/parallelism.
#
# C++/CUDA extensions often use the MAX_JOBS environment variable to determine how many
# different compiler processes to run at the same time. This sets it to use one process
# per 3GB of available RAM, so that hosts with more memory can compile faster, and hosts
# with less memory don't run out of memory.
free -g
export MAX_JOBS=$(free -g | awk '/^Mem:/{max_jobs=int($7/3); if (max_jobs == 0) {print 1} else {print max_jobs}}')

## Set CUDA compute capabilities based on the GPUs available in Deadline Cloud service-managed fleets.
# * https://docs.aws.amazon.com/deadline-cloud/latest/userguide/smf-gpu.html
# * https://developer.nvidia.com/cuda-gpus
#
# As of writing, GPU types include T4 (7.5), A10G (8.6), L4 (8.9), and L40S (8.9).
# The gsplat package requires compute capability >= 7.0, and uses the NVCC_FLAGS environment
# variable to provide additional flags to NVCC.
export NVCC_FLAGS="--gpu-architecture=compute_75 --gpu-code=sm_75,sm_86,sm_89"
# The tinycudann package uses the TCNN_CUDA_ARCHITECTURES environment variable.
export TCNN_CUDA_ARCHITECTURES="75,86,89"
# The pytorch models use the TORCH_CUDA_ARCH_LIST environment variable.
export TORCH_CUDA_ARCH_LIST="7.5 8.6 8.9"

pip_install() {
    # Run pip install with --log, to print out detailed info about the build process
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

cd "$SRC_DIR"

# The PyPI ninja package installs both a ninja binary and a Python module to help work with it.
# The conda-forge ninja package does not include the latter, and as of writing there is no python-ninja
# or similar package.
pip install ninja

echo "openjd_status: Installing tiny-cuda-nn"
pip_install  ./tinycudann/bindings/torch

# Install gsplat from source to produce compiled CUDA binaries instead of JIT compiling them later.
echo "openjd_status: Installing gsplat"
pip_install ./gsplat

# Copy the examples so simple_trainer.py is in the package.
mkdir -p "$PREFIX/opt/gsplat_examples"
cp -r gsplat/examples/* "$PREFIX/opt/gsplat_examples/"

# Make a script to run simple_trainer.py
cat <<EOF > "$PREFIX/bin/gsplat_simple_trainer"
#!/bin/env bash
"$PREFIX/bin/python" "$PREFIX/opt/gsplat_examples/simple_trainer.py" "\$@"
EOF
chmod +x "$PREFIX/bin/gsplat_simple_trainer"

# Edit the nerfstudio dependencies to allow versions from conda-forge that we found were working
sed -i 's/"protobuf[^"]*"/"protobuf"/' "nerfstudio/pyproject.toml"
sed -i 's/"opencv-python-headless[^"]*"/"opencv-python-headless"/' "nerfstudio/pyproject.toml"
sed -i 's/"splines[^"]*"/"splines"/' "nerfstudio/pyproject.toml"
sed -i 's/"timm[^"]*"/"timm"/' "nerfstudio/pyproject.toml"
sed -i 's/"everett[^"]*"/"everett"/' "nerfstudio/pyproject.toml"
sed -i 's/"comet_ml[^"]*"/"comet_ml"/' "nerfstudio/pyproject.toml"
# Drop the open3d dependency because pip always replaces conda-forge's open3d package
sed -i 's/"open3d[^"]*",//' "nerfstudio/pyproject.toml"

# Patch nerfstudio to account for the following pytorch change:
# > (1) In PyTorch 2.6, we changed the default value of the `weights_only` argument in `torch.load` from
# > `False` to `True`. Re-running `torch.load` with `weights_only` set to `False` will likely succeed, but
# > it can result in arbitrary code execution. Do it only if you got the file from a trusted source.
for FILE in nerfstudio/nerfstudio/engine/trainer.py \
            nerfstudio/nerfstudio/scripts/downloads/download_data.py \
            nerfstudio/nerfstudio/utils/eval_utils.py; do
    sed -i 's/torch\.load(\(.*\))/torch.load(\1, weights_only=False)/' $FILE
done

echo "openjd_status: Installing NeRF Studio"
pip_install ./nerfstudio

# simple_trainer.py from the gsplat package depends on these additional packages
echo "openjd_status: Installing NeRFView"
pip_install ./nerfview
echo "openjd_status: Installing FusedSSIM"
pip_install ./fusedssim
echo "openjd_status: Installing PyCOLMAP"
pip_install ./pycolmap

# Install the Splatfacto in the Wild model
echo "openjd_status: Installing splatfacto-w"
pip_install ./splatfacto-w

# Copy the splatfacto-w export script
mkdir -p "$PREFIX/opt/splatfacto-w"
cp -r splatfacto-w/export_script.py "$PREFIX/opt/splatfacto-w/"

# Make a script to run the splatfacto-w export_script.py
cat <<EOF > "$PREFIX/bin/splatfactow_export"
#!/bin/env bash
"$PREFIX/bin/python" "$PREFIX/opt/splatfacto-w/export_script.py" "\$@"
EOF
chmod +x "$PREFIX/bin/splatfactow_export"

echo "openjd_status: Finished nerfstudio package build"
