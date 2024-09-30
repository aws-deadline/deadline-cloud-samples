#!/bin/env bash
set -euo pipefail

ENV_NAME=
CONDA_BLD_DIR=
REUSE_ENV=1

# Parse the CLI arguments
while [ $# -gt 0 ]; do
    case "${1}" in
    --reuse-env) REUSE_ENV=1 ; shift 1 ;;
    --no-reuse-env) REUSE_ENV=0 ; shift 1 ;;
    --env-name) ENV_NAME="$2" ; shift 2 ;;
    --conda-bld-dir) CONDA_BLD_DIR="$2" ; shift 2 ;;
    *) echo "Unexpected option: $1" ; exit 1 ;;
  esac
done

if [ -z "$ENV_NAME" ]; then
    echo "ERROR: Option --env-name is required."
    exit 1
fi
if [ -z "$CONDA_BLD_DIR" ]; then
    echo "ERROR: Option --conda-bld-dir is required."
    exit 1
fi

# Install an error handler to clean the Conda cache
function conda_clean_on_error {
    if [ ! "$1" = "0" ]; then
        echo "Error detected, removing the $ENV_NAME environment and cleaning the Conda cache."
        conda remove --yes --name "$ENV_NAME" --all || true
        conda clean --yes --all || true
    fi
}
trap 'conda_clean_on_error $?' EXIT

if [ "$REUSE_ENV" = "0" ]; then
    conda env remove --yes -q -n $ENV_NAME
fi

if conda env list | grep -q "^$ENV_NAME "; then
    echo "Reusing the existing named Conda environment $ENV_NAME."

    # Activate the Conda environment, capturing the environment variables for the session to use
    python "$(dirname "$0")/openjd-vars-start.py" .vars
    conda activate "$ENV_NAME"
    python "$(dirname "$0")/openjd-vars-capture.py" .vars
else
    echo "Creating the named Conda environment $ENV_NAME for running conda-build."

    conda create --yes -n "$ENV_NAME" \
        -c conda-forge \
        python=3.11 conda conda-build conda-index boto3 pyyaml

    # Activate the Conda environment, capturing the environment variables for the session to use
    python "$(dirname "$0")/openjd-vars-start.py" .vars
    conda activate "$ENV_NAME"
    python "$(dirname "$0")/openjd-vars-capture.py" .vars

    # By default, Conda creates 32-bit .conda packages that are limited to 2GB.
    # We patch the file conda_package_handling/conda_fmt.py to change its constructor
    # from `conda_file.open(component, "w")` to
    # `conda_file.open(component, "w", force_zip64=True)`.
    for CFP in "lib/python3.11/site-packages/conda_package_handling/conda_fmt.py" "lib/site-packages/conda_package_handling/conda_fmt.py"; do
        if [ -f "$CONDA_PREFIX/$CFP" ]; then
            CONDA_FMT_PATH=$CFP
        fi
    done
    sed -i 's/conda_file.open(component, "w")/conda_file.open(component, "w", force_zip64=True)/' "$CONDA_PREFIX/$CONDA_FMT_PATH"
    if grep -q force_zip64 "$CONDA_PREFIX/$CONDA_FMT_PATH"; then
        echo "Patching conda_package_handling/conda_fmt.py for 64-bit .conda format succeeded"
    else
        echo "Failed to patch conda_package_handling/conda_fmt.py for 64-bit .conda format"
        exit 1
    fi

    if [ "$(uname)" = Linux ]; then
        echo "Installing Mountpoint-S3..."
        ARCH=$(uname -m)
        ARCH=${ARCH/aarch64/arm64}
        pushd "$CONDA_PREFIX"
        curl https://s3.amazonaws.com/mountpoint-s3-release/latest/$ARCH/mount-s3.tar.gz \
            -Ls | tar -xvz "./bin/mount-s3"
        popd
    else
        echo "Skipping Mountpoint-S3 installation, it is only for Linux."
    fi

fi

if [[ "$(uname -s)" == MINGW* ]]; then
    # Remove ripgrep because conda-build gives it an arguments list that is too long when building some package recipes.
    # See https://github.com/conda/conda-build/issues/4357
    #   FileNotFoundError: [WinError 206] The filename or extension is too long
    rm -f $CONDA_PREFIX/bin/rg.exe || true
    rm -f $CONDA_PREFIX/Library/bin/rg.exe || true
fi

# Create a .condarc to control the package build settings
cat <<EOF > "$CONDA_PREFIX/.condarc"
conda_build:
    # Build in the .conda package format
    pkg_format: '2'
    root-dir: '$CONDA_BLD_DIR'
    debug: false
EOF
