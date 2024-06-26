#!/bin/env bash
set -euo pipefail

CONDA_BLD_DIR=
CONDA_PLATFORM=
CONDA_CHANNELS=
S3_CHANNEL=
OVERRIDE_PREFIX_LENGTH=0
RECIPE_DIR=
OVERRIDE_PACKAGE_NAME=
OVERRIDE_SOURCE_ARCHIVE=

# Parse the CLI arguments
while [ $# -gt 0 ]; do
    case "${1}" in
    --conda-bld-dir) CONDA_BLD_DIR="$2" ; shift 2 ;;
    --conda-platform) CONDA_PLATFORM="$2" ; shift 2 ;;
    --conda-channels) CONDA_CHANNELS="$2" ; shift 2 ;;
    --s3-conda-channel) S3_CHANNEL="$2" ; shift 2 ;;
    --override-prefix-length) OVERRIDE_PREFIX_LENGTH="$2" ; shift 2 ;;
    --recipe-dir) RECIPE_DIR="$2" ; shift 2 ;;
    --override-package-name) OVERRIDE_PACKAGE_NAME="$2" ; shift 2 ;;
    --override-source-archive) OVERRIDE_SOURCE_ARCHIVE="$2" ; shift 2 ;;
    *) echo "Unexpected option: $1" ; exit 1 ;;
  esac
done

if [ -z "$CONDA_BLD_DIR" ]; then
    echo "ERROR: Option --conda-bld-dir is required."
    exit 1
fi
if [ -z "$CONDA_PLATFORM" ]; then
    echo "ERROR: Option --conda-platform is required."
    exit 1
fi
if [ -z "$S3_CHANNEL" ]; then
    echo "ERROR: Option --s3-conda-channel is required."
    exit 1
fi
if [ -z "$RECIPE_DIR" ]; then
    echo "ERROR: Option --recipe-dir is required."
    exit 1
fi

# Trim the trailing '/' from the S3 channel URL if necessary
S3_CHANNEL=${S3_CHANNEL%/}

if [[ "$S3_CHANNEL" =~ ^s3://([^/]+)/(.*)/?$ ]]; then
    S3_CHANNEL_BUCKET=${BASH_REMATCH[1]}
    S3_CHANNEL_PREFIX=${BASH_REMATCH[2]}
else
    echo "ERROR: The value for --s3-conda-channel does not match s3://<bucket-name>/prefix."
    exit 1
fi

# Print information about the package building environment
conda info

# Make sure the package build starts with a clean conda-bld directory
conda build purge

# Convert the space-separated list into consecutive channel options
CHANNEL_OPTIONS="$(echo $CONDA_CHANNELS | sed -r 's/(\s+|^)(\S)/ -c \2/g')"

# If the S3 channel already has an index, include it in the list of input channels
if aws s3api head-object --bucket $S3_CHANNEL_BUCKET --key $S3_CHANNEL_PREFIX/noarch/repodata.json.zst; then
    CHANNEL_OPTIONS="-c $S3_CHANNEL $CHANNEL_OPTIONS"
fi

conda render \
    --no-source \
    -f rendered_meta.yaml \
    $CHANNEL_OPTIONS \
    "$RECIPE_DIR"
echo "The recipe's rendered meta.yaml file:"
cat rendered_meta.yaml

# Get the next available build number for this package version
PACKAGE_NAME=$(yq .package.name rendered_meta.yaml -r)
if [ ! -z "$OVERRIDE_PACKAGE_NAME" ]; then
    PACKAGE_NAME="$OVERRIDE_PACKAGE_NAME"
fi
PACKAGE_VERSION=$(yq .package.version rendered_meta.yaml -r)
if conda search \
        $CHANNEL_OPTIONS \
        --platform $CONDA_PLATFORM \
        --json \
        --spec "$PACKAGE_NAME==$PACKAGE_VERSION" > package-search.json; then
    BUILD_NUMBER=$(jq ".\"$PACKAGE_NAME\" | max_by(.build_number) | .build_number + 1" package-search.json)
else
    # If it's not a package not found error, fail the build
    if grep -qv PackagesNotFoundError; then
        cat package-search.json
        exit 1
    fi
    BUILD_NUMBER=0
fi

echo "Selected build number $BUILD_NUMBER"

# Create a clobber file that replaces the build number
cat rendered_meta.yaml | yq ".build.number = $BUILD_NUMBER | {package,source,build}" > recipe_clobber.yaml

# If the source archive is provided directly, add it to the clobber file
if [ ! -z "$OVERRIDE_SOURCE_ARCHIVE" ]; then
    mv recipe_clobber.yaml recipe_clobber.yaml.bak
    yq '.source.url = "'$OVERRIDE_SOURCE_ARCHIVE'"' recipe_clobber.yaml.bak > recipe_clobber.yaml
fi

# If there's a name override, add it to the clobber file
if [ ! -z "$OVERRIDE_PACKAGE_NAME" ]; then
    mv recipe_clobber.yaml recipe_clobber.yaml.bak
    yq '.package.name = "'$OVERRIDE_PACKAGE_NAME'"' recipe_clobber.yaml.bak > recipe_clobber.yaml
fi

echo "The clobber file we will use to modify properties of meta.yaml:"
cat recipe_clobber.yaml

PREFIX_LENGTH_OPTION=
if [ $OVERRIDE_PREFIX_LENGTH -ne 0 ]; then
    PREFIX_LENGTH_OPTION="--prefix-length $OVERRIDE_PREFIX_LENGTH"
fi

echo "Build the package(s)..."
conda build --no-anaconda-upload \
    --clobber-file recipe_clobber.yaml \
    $PREFIX_LENGTH_OPTION \
    $CHANNEL_OPTIONS \
    "$RECIPE_DIR"

echo "Uploading the package(s) to the S3 Conda channel..."
for SUBDIR in $CONDA_PLATFORM noarch; do
    aws s3 sync --no-progress \
        "$CONDA_BLD_DIR/$SUBDIR" \
        "$S3_CHANNEL/$SUBDIR" \
        --exclude "*" \
        --include "*.conda"
done

echo "All done"
