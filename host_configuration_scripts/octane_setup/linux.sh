#!/usr/bin/env bash
set -e

# TODO - update this for your environment
S3_CREDENTIAL_URI="s3://amzn-s3-demo-bucket/octane/otoy_unattended_credentials"

# TODO - set the cuDNN archive for your OctaneRender release. See
# "6. Set the cuDNN archive" in README.md for how to find this URL.
CUDNN_URL="https://render.otoy.com/downloads/<path>/cudnn_<version>_linux.zip"

# OctaneRender reads its unattended auth file from this exact path. The filename matters.
CREDENTIAL_DIR="/etc/OctaneRender"
CREDENTIAL_PATH="$CREDENTIAL_DIR/otoy_unattended_credentials"

# OctaneRender loads cuDNN from a directory named after the archive,
# for example thirdparty/cudnn_9_7_0 for cudnn_9_7_0_linux.zip.
CUDNN_DIR="$CREDENTIAL_DIR/thirdparty/$(basename "$CUDNN_URL" _linux.zip)"

install -d -m 0755 "$CREDENTIAL_DIR"

echo "Downloading the OctaneRender auth file from $S3_CREDENTIAL_URI"
if ! aws s3 cp "$S3_CREDENTIAL_URI" "$CREDENTIAL_PATH"; then
    echo "ERROR: Failed to download the auth file. Ensure the fleet role has read access" >&2
    echo "to $S3_CREDENTIAL_URI" >&2
    exit 1
fi

# Readable by the user that renders, which is not root.
chmod 0644 "$CREDENTIAL_PATH"

echo "OctaneRender licensing configured at $CREDENTIAL_PATH"

echo "Downloading the OctaneRender cuDNN runtime from $CUDNN_URL"
CUDNN_ARCHIVE="$(mktemp --suffix=.zip)"
curl --fail --location --silent --show-error --output "$CUDNN_ARCHIVE" "$CUDNN_URL"
install -d -m 0755 "$CUDNN_DIR"
unzip -oq "$CUDNN_ARCHIVE" -d "$CUDNN_DIR"
rm -f "$CUDNN_ARCHIVE"

# Readable by the user that renders, which is typically not root.
chmod -R a+rX "$CUDNN_DIR"

echo "OctaneRender cuDNN configured at $CUDNN_DIR"
