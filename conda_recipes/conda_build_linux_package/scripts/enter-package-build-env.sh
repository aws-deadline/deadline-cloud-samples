#!/bin/env bash
set -euo pipefail

ENV_NAME=
CONDA_BLD_DIR=
REUSE_ENV=1

# Parse the CLI arguments
while [ $# -gt 0 ]; do
    case "${1}" in
    --reuse-env) REUSE_ENV="$2" ; shift 2 ;;
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
        for ENVS_DIR in $(conda info --json | python -c "import json, sys; v = json.load(sys.stdin); print('\n'.join(v['envs_dirs']))"); do
            if [ -d $ENVS_DIR/$ENV_NAME ]; then
                echo "Removing directory $ENVS_DIR/$ENV_NAME for the environment"
                rm -rf $ENVS_DIR/$ENV_NAME
                if [ -d $ENVS_DIR/$ENV_NAME ]; then
                    echo "WARNING: Could not remove the directory. Possibly a permissions error or a process holding a lock."
                fi
            fi
        done
        conda clean --yes --all || true
    fi
}
trap 'conda_clean_on_error $?' EXIT

if [ "$REUSE_ENV" == "0" ]; then
    echo "Removing any existing environment called $ENV_NAME"
    for ENVS_DIR in $(conda info --json | python -c "import json, sys; v = json.load(sys.stdin); print('\n'.join(v['envs_dirs']))"); do
        if [ -d $ENVS_DIR/$ENV_NAME ]; then
            echo "Removing directory $ENVS_DIR/$ENV_NAME for the environment"
            rm -rf $ENVS_DIR/$ENV_NAME
            if [ -d $ENVS_DIR/$ENV_NAME ]; then
                echo "ERROR: Could not remove the directory. Possibly a permissions error or a process holding a lock."
                exit 1
            fi
        fi
    done
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
        python=3.12 conda conda-build rattler-build conda-index boto3 pyyaml

    # Activate the Conda environment, capturing the environment variables for the session to use
    python "$(dirname "$0")/openjd-vars-start.py" .vars
    conda activate "$ENV_NAME"
    python "$(dirname "$0")/openjd-vars-capture.py" .vars

    # By default, Conda creates 32-bit .conda packages that are limited to 2GB.
    # We patch the file conda_package_handling/conda_fmt.py to change its constructor
    # from `conda_file.open(component, "w")` to
    # `conda_file.open(component, "w", force_zip64=True)`.
    for CFP in "lib/python3.12/site-packages/conda_package_handling/conda_fmt.py" "lib/site-packages/conda_package_handling/conda_fmt.py"; do
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

if [[ "$(uname -s)" == MINGW* || "$(uname -s)" == MSYS_NT* ]]; then
    # Remove ripgrep because conda-build gives it an arguments list that is too long when building some package recipes.
    # See https://github.com/conda/conda-build/issues/4357
    #   FileNotFoundError: [WinError 206] The filename or extension is too long
    rm -f $CONDA_PREFIX/bin/rg.exe || true
    rm -f $CONDA_PREFIX/Library/bin/rg.exe || true
fi

# Create a .condarc to control the package build settings
cat <<EOF > "$CONDA_PREFIX/.condarc"
# Default to no channels. Specify channels in the conda build recipe's deadline-cloud.yaml file.
channels: []
conda_build:
    # Build in the .conda package format
    pkg_format: '2'
    root-dir: '$CONDA_BLD_DIR'
    debug: false
EOF

conda info
