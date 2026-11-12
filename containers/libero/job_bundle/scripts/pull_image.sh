#!/usr/bin/env bash
# Pull a private Amazon ECR image with the queue role's credentials.
#
# Always pull, even when the image is already on the worker: service-managed workers
# are reused across jobs, and a rebuilt image pushed under the same tag must not be
# silently skipped. When nothing changed, the pull only checks the manifest.
set -euo pipefail
IMAGE="$1"
REGISTRY="${IMAGE%%/*}"
if [[ ! "$REGISTRY" =~ ^[0-9]{12}\.dkr\.ecr\.[a-z0-9-]+\.amazonaws\.com$ ]]; then
  echo "ERROR: expected a private Amazon ECR image URI such as" >&2
  echo "  <account-id>.dkr.ecr.<region>.amazonaws.com/<repository>:<tag>, got: $IMAGE" >&2
  exit 1
fi
REGION=$(echo "$REGISTRY" | cut -d. -f4)
aws ecr get-login-password --region "$REGION" | docker login --username AWS --password-stdin "$REGISTRY"
docker pull -q "$IMAGE"
