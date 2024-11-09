#!/bin/env bash
set -euo pipefail

if [ -z "${S3_PROXY_ROOT:-}" ]; then
    echo "No S3 proxy was performed."
    exit 0
fi

set +e
for MOUNTPOINT in "$S3_PROXY_ROOT"/*; do
    echo "Unmounting $MOUNTPOINT"
    fusermount -u $MOUNTPOINT
    rmdir $MOUNTPOINT
done
set -e
