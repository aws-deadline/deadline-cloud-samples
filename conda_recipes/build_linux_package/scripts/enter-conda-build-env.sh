#!/bin/env bash
set -euo pipefail

ENV_DIR=
CONDA_BLD_DIR=

# Parse the CLI arguments
while [ $# -gt 0 ]; do
    case "${1}" in
    --env-dir) ENV_DIR="$2" ; shift 2 ;;
    --conda-bld-dir) CONDA_BLD_DIR="$2" ; shift 2 ;;
    *) echo "Unexpected option: $1" ; exit 1 ;;
  esac
done

if [ -z "$ENV_DIR" ]; then
    echo "ERROR: Option --env-dir is required."
    exit 1
fi
if [ -z "$CONDA_BLD_DIR" ]; then
    echo "ERROR: Option --conda-bld-dir is required."
    exit 1
fi

# Install an error handler to clean the Conda cache
function conda_clean_on_error {
    if [ ! "$1" = "0" ]; then
        echo "Error detected, cleaning the Conda cache."
        conda clean --yes --all
    fi
}
trap 'conda_clean_on_error $?' EXIT

conda create --yes -p "$ENV_DIR" \
    -c conda-forge \
    python=3.11 conda conda-build conda-index boto3 yq

# By default, Conda creates 32-bit .conda packages that are limited to 2GB.
# We patch the file conda_package_handling/conda_fmt.py to change its constructor
# from `conda_file.open(component, "w")` to
# `conda_file.open(component, "w", force_zip64=True)`.
CONDA_FMT_PATH="lib/python3.11/site-packages/conda_package_handling/conda_fmt.py"
sed -i 's/conda_file.open(component, "w")/conda_file.open(component, "w", force_zip64=True)/' "$ENV_DIR/$CONDA_FMT_PATH"
if grep -q force_zip64 "$ENV_DIR/$CONDA_FMT_PATH"; then
    echo "Patching conda_package_handling/conda_fmt.py for 64-bit .conda format succeeded"
else
    echo "Failed to patch conda_package_handling/conda_fmt.py for 64-bit .conda format"
    exit 1
fi

# Create a .condarc to control the package build settings
cat <<EOF > "$ENV_DIR/.condarc"
conda_build:
    # This needs to be version 2 or later for the S3 bucket channel
    # reindexing to be efficient.
    pkg_format: '2'
    root-dir: '$CONDA_BLD_DIR'
EOF

echo "Installing Mountpoint-S3..."
pushd "$ENV_DIR"
curl https://s3.amazonaws.com/mountpoint-s3-release/latest/x86_64/mount-s3.tar.gz \
    -Ls | tar -xvz "./bin/mount-s3"
popd

echo "Capturing the environment variables for the OpenJD environment scope..."
VARS_TMP="$(mktemp vars-capture.tmp.XXXXXXXXXX)"
python "$(dirname $0)/openjd-vars-start.py" "$VARS_TMP"
conda run -p "$ENV_DIR" python "$(dirname $0)/openjd-vars-capture.py" "$VARS_TMP"
rm "$VARS_TMP"
