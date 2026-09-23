#!/usr/bin/env bash
set -e

# TODO - update this for your environment
S3_CREDENTIAL_URI="s3://amzn-s3-demo-bucket/octane/otoy_unattended_credentials"

# OctaneRender reads its unattended auth file from this exact path. The filename matters.
CREDENTIAL_DIR="/etc/OctaneRender"
CREDENTIAL_PATH="$CREDENTIAL_DIR/otoy_unattended_credentials"

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
