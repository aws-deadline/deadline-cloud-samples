# Minimal NVIDIA Isaac Sim container for Replicator SDG

A short recipe that builds the image the
[`isaacsim_replicator_sdg` job bundle](../../job_bundles/isaacsim_replicator_sdg/README.md)
runs on, over NVIDIA's NGC base image.

**This directory contains a recipe, not an image.** You pull
`nvcr.io/nvidia/isaac-sim` under NVIDIA's licence terms and push the result to a
registry you control. Nothing NVIDIA-owned is vendored into this repository, and
you should not redistribute what you build.

## Why this is small

The [`isaacsim-so101-workshop`](../isaacsim-so101-workshop/README.md) image
serves a different bundle and adds LeRobot, a shared-library ffmpeg build, and
the Sim-to-Real-SO-101-Workshop repository through Git LFS. The SDG bundle's
`primitives` and `usd` scene sources need none of that — between them they
import only `isaacsim.SimulationApp`, `omni.replicator.core`, `numpy` and `pxr`,
all present in the base image.

So this Dockerfile adds exactly two things: the X11 and xkbcommon libraries that
Kit links even with no display attached and which are absent from the base
image, and a writable `__pycache__` location.

Use the workshop image instead if, and only if, you want `SceneSource=workshop`,
which loads USD files that ship inside it.

## Prerequisites

* Docker with `buildx`.
* An [NVIDIA NGC account](https://ngc.nvidia.com/signin) and an
  [API key](https://ngc.nvidia.com/setup/api-key), to pull the base image.
* An Amazon ECR repository in the same account and Region as your farm.

## Build and push

```bash
export AWS_REGION=us-west-2
ACCOUNT=$(aws sts get-caller-identity --query Account --output text)
REPO=isaacsim-replicator
TAG=5.1.0
REGISTRY="${ACCOUNT}.dkr.ecr.${AWS_REGION}.amazonaws.com"

# 1. Authenticate to NGC. Username is the literal string $oauthtoken.
echo "$NGC_API_KEY" | docker login nvcr.io -u '$oauthtoken' --password-stdin

# 2. Create the ECR repository, if you have not already.
aws ecr create-repository --repository-name "$REPO" --region "$AWS_REGION" || true

# 3. Authenticate to ECR.
aws ecr get-login-password --region "$AWS_REGION" \
  | docker login --username AWS --password-stdin "$REGISTRY"

# 4. Build for the fleet's architecture, not your laptop's. Service-managed
#    fleets are x86_64; an arm64 image built on an Apple Silicon Mac will push
#    successfully and then fail to start on a worker.
docker buildx build --platform linux/amd64 -t "${REPO}:${TAG}" --load .

# 5. Push.
docker tag "${REPO}:${TAG}" "${REGISTRY}/${REPO}:${TAG}"
docker push "${REGISTRY}/${REPO}:${TAG}"

echo "Image URI: ${REGISTRY}/${REPO}:${TAG}"
```

Give that image URI to the Docker queue environment's image parameter. If you
deployed the
[isaacsim_farm CloudFormation template](../../cloudformation/farm_templates/isaacsim_farm/README.md),
keep `$REPO` equal to its `EcrRepositoryName` parameter, which is what scopes
the queue role's pull permission.

## Version pinning

The base image tag is `ARG BASE_IMAGE=nvcr.io/nvidia/isaac-sim:5.1.0`, and 5.1.0
is deliberate. Service-managed fleet accelerator runtimes currently top out at
`grid:r580` (driver 580.x), which is the branch Isaac Sim 5.1.0 expects. Isaac
Sim 6.x raises its driver floor above that ceiling. Check the fleet's available
accelerator runtimes before bumping:

```bash
aws deadline get-fleet --farm-id <FARM_ID> --fleet-id <FLEET_ID> \
  --query 'configuration.serviceManagedEc2.instanceCapabilities.acceleratorCapabilities'
```

To pin by digest instead of tag, so the tag cannot be re-pushed underneath you:

```bash
docker buildx build --platform linux/amd64 \
  --build-arg BASE_IMAGE=nvcr.io/nvidia/isaac-sim@sha256:<DIGEST> \
  -t "${REPO}:${TAG}" --load .
```

## Notes

* **The image's `ENTRYPOINT` never runs.** The Docker queue environment starts a
  session container and uses `docker container exec` for each task, so anything
  the base entrypoint would set — `EXP_PATH`, `CARB_APP_PATH`, the
  `/usr/local/bin/python` shim — is absent. Job scripts must not rely on it.
  `generate_sdg.py` passes its Kit experience file explicitly for this reason.
* **Build on a machine with disk to spare.** The base image is roughly 9 GB
  compressed and expands well beyond that.
* **`ACCEPT_EULA=Y` and `PRIVACY_CONSENT=Y` are set in the Dockerfile.** Review
  [NVIDIA's licence terms](https://docs.isaacsim.omniverse.nvidia.com/latest/common/NVIDIA_Omniverse_License_Agreement.html)
  before building.
