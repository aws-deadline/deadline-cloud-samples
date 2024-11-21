#!/bin/env bash
set -euo pipefail

# The rattler-build tool does not support S3 conda channels. Therefore,
# this job uses s3-mountpoint to mount any conda channels that start with s3://.
#
# Publishes the environment variables CONDA_CHANNELS and S3_CONDA_CHANNEL
# with the s3:// channels rewritten to file://. Also publishes S3_PROXY_ROOT
# for the exit-proxy-s3-conda-channels.sh script to use for clean-up.

CONDA_CHANNELS=
S3_CONDA_CHANNEL=
BUILD_TOOL=

# Parse the CLI arguments
while [ $# -gt 0 ]; do
    case "${1}" in
    --conda-channels) CONDA_CHANNELS="$2" ; shift 2 ;;
    --s3-conda-channel) S3_CONDA_CHANNEL="$2" ; shift 2 ;;
    --build-tool) BUILD_TOOL="$2" ; shift 2 ;;
    *) echo "Unexpected option: $1" ; exit 1 ;;
  esac
done

if [ -z "$S3_CONDA_CHANNEL" ]; then
    echo "ERROR: Option --s3-conda-channel is required."
    exit 1
fi

if [ -z "$BUILD_TOOL" ]; then
    echo "ERROR: Option --build-tool is required."
    exit 1
fi

if [ "$BUILD_TOOL" != "conda-build" ] && [ "$BUILD_TOOL" != "rattler-build" ]; then
    echo "ERROR: Option --build-tool must be either conda-build or rattler-build."
    exit 1
fi

if [ "$BUILD_TOOL" == "conda-build" ]; then
    echo "The conda-build tool support s3:// channels, no proxy is required."
    echo "openjd_env: CONDA_CHANNELS=$CONDA_CHANNELS"
    echo "openjd_env: S3_CONDA_CHANNEL=$S3_CONDA_CHANNEL"
    exit 0
fi

# Choose a root directory for mounting the S3 channels
if [[ "$(uname)" == Linux ]]; then
    mkdir -p proxy-s3
    S3_PROXY_ROOT=$(pwd)/proxy-s3
else
    echo "ERROR: The S3 conda channel proxy is based on s3-mountpoint, only available on Linux."
    exit 1
fi
echo "openjd_env: S3_PROXY_ROOT=$S3_PROXY_ROOT"
mkdir -p "$S3_PROXY_ROOT"

# Install an error handler to unmount any mounted drives
function unmount_s3_proxy_on_error {
    if [ ! "$1" = "0" ]; then
        set +e
        for MOUNTPOINT in "$S3_PROXY_ROOT"/*; do
            fusermount -u $MOUNTPOINT
            rmdir $MOUNTPOINT
        done
        set -e
    fi
}
trap 'unmount_s3_proxy_on_error $?' EXIT

function mount_s3_proxy {
    # Checks if the channel is s3:// and mounts it with s3-mountpoint if so.
    # Outputs new channel name to UPDATED_CHANNEL.
    local CHANNEL=$1

    if [[ "$CHANNEL" =~ ^s3://([^/]+)/(.*)/?$ ]]; then
        local S3_CHANNEL_BUCKET=${BASH_REMATCH[1]}
        local S3_CHANNEL_PREFIX=${BASH_REMATCH[2]}
        local CHANNEL_DIR="${S3_CHANNEL_BUCKET}_${S3_CHANNEL_PREFIX//\//_}"
        mkdir -p "$S3_PROXY_ROOT/$CHANNEL_DIR"
        mount-s3 --prefix $S3_CHANNEL_PREFIX/ \
            --read-only \
            $S3_CHANNEL_BUCKET "$S3_PROXY_ROOT/$CHANNEL_DIR"
        UPDATED_CHANNEL="file://$S3_PROXY_ROOT/$CHANNEL_DIR"
    else
        UPDATED_CHANNEL="$CHANNEL"
    fi
}

# Mount all the S3 conda channels, and rewrite the channel names
RESULT_CONDA_CHANNELS=
for CHANNEL in $CONDA_CHANNELS; do
    mount_s3_proxy "$CHANNEL"
    RESULT_CONDA_CHANNELS="$RESULT_CONDA_CHANNELS $UPDATED_CHANNEL"
done
echo "openjd_env: CONDA_CHANNELS=$RESULT_CONDA_CHANNELS"

# Mount the S3 conda channel and rewrite its name
mount_s3_proxy $S3_CONDA_CHANNEL
echo "openjd_env: S3_CONDA_CHANNEL=$UPDATED_CHANNEL"