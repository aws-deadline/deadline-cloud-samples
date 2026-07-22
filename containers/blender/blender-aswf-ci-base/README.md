# Blender container for AWS Deadline Cloud

This example builds a Docker image that packages Blender with the [deadline-cloud-for-blender](https://github.com/aws-deadline/deadline-cloud-for-blender) adaptor and GPU support for rendering on AWS Deadline Cloud.

## Use cases

- Run Blender Cycles GPU renders (CUDA/OptiX) on Deadline Cloud service-managed fleets.
- Bundle third-party Blender addons into the image at build time.

## What's included

| Component | Description |
|-----------|-------------|
| Base image | `aswf/ci-base:2026` (Rocky Linux 8 with CUDA 12.9 and VFX Platform 2026, an industry standard) |
| Blender | Configurable version (default 4.5.0), downloaded from blender.org |
| Adaptor | `deadline-cloud-for-blender`: the OpenJD adaptor that Deadline Cloud invokes to drive renders |
| Plugins | Optional addon `.zip` files placed in `plugins/` are installed and enabled at build time |
| CloudFormation | `cloudformation.yaml`: deploys the queue, fleet, and queue environment in one stack |

## Project structure

```
blender-aswf-ci-base/
├── Dockerfile
├── cloudformation.yaml           # One-click deploy (queue + fleet + queue env)
├── scripts/
│   ├── extract_plugins.py        # Extracts addon zips at build time
│   ├── bootstrap.py              # Installs/enables addons via headless Blender
│   └── log_addons.py             # Startup script that logs enabled addons
└── plugins/                      # Place addon .zip files here before building
```

## Prerequisites

- **Docker** installed locally ([Get Docker](https://docs.docker.com/get-docker/))
- **AWS CLI** configured with credentials ([Install AWS CLI](https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html))
- **An ECR repository** to store the built image ([Creating an ECR repository](https://docs.aws.amazon.com/AmazonECR/latest/userguide/repository-create.html))
- **An S3 bucket** for job attachments ([Job attachments storage](https://docs.aws.amazon.com/deadline-cloud/latest/userguide/storage-job-attachments.html))
- **A Deadline Cloud farm** ([Getting started with Deadline Cloud](https://docs.aws.amazon.com/deadline-cloud/latest/userguide/getting-started.html))
- **IAM roles** for the queue and fleet ([Deadline Cloud IAM roles](https://docs.aws.amazon.com/deadline-cloud/latest/userguide/security-iam.html))

## Building the image

Place any addon `.zip` files in `plugins/`, then build:

```bash
# Basic build (Blender 4.5.0, VFX Platform 2026)
docker build -t blender-aswf:4.5.0 .

# Custom Blender version
docker build --build-arg BLENDER_VERSION=4.3.1 -t blender-aswf:4.3.1 .

# Custom VFX Platform year
docker build --build-arg VFX_PLATFORM_YEAR=2025 -t blender-aswf:4.5.0 .
```

### Push to ECR

```bash
ECR_REPO=<your-account-id>.dkr.ecr.<region>.amazonaws.com/<your-repo-name>
ECR_REGISTRY=$(echo $ECR_REPO | cut -d/ -f1)
aws ecr get-login-password --region <region> | docker login --username AWS --password-stdin $ECR_REGISTRY
docker tag blender-aswf:4.5.0 $ECR_REPO:4.5.0
docker push $ECR_REPO:4.5.0
```

## IAM permissions for ECR access

The queue role must have permission to pull images from the ECR repository used for the container image. At minimum, the role needs these statements for ECR:

```json
        {
            "Effect": "Allow",
            "Action": "ecr:GetAuthorizationToken",
            "Resource": "*"
        },
        {
            "Effect": "Allow",
            "Action": [
                "ecr:BatchGetImage",
                "ecr:GetDownloadUrlForLayer"
            ],
            "Resource": "arn:aws:ecr:<REGION>:<ACCOUNT>:repository/<REPOSITORY>"
        }
```

If the ECR repository is in a different account, you also need a repository policy granting cross-account access.

See [Private repository policies](https://docs.aws.amazon.com/AmazonECR/latest/userguide/repository-policies.html) and [Using Amazon ECR images with Amazon ECS](https://docs.aws.amazon.com/AmazonECR/latest/userguide/ECR_on_ECS.html) for details on configuring ECR access.

## Deploying to Deadline Cloud

Use the provided CloudFormation template to deploy everything in one command:

```bash
aws cloudformation deploy \
    --template-file cloudformation.yaml \
    --stack-name blender-aswf-ci-base-stack \
    --parameter-overrides \
        FarmId=farm-... \
        ECRImageURI=$ECR_REPO:4.5.0 \
        FleetRoleArn=arn:aws:iam::...:role/FleetRole \
        QueueRoleArn=arn:aws:iam::...:role/QueueRole \
        JobAttachmentsBucket=my-deadline-bucket
```

The stack creates:
- A **queue** with job attachment settings and the container queue environment attached
- A **fleet** with GPU instances, Docker host configuration, and NVIDIA Container Toolkit
- A **queue-fleet association** connecting the two

### Updating the container image

After pushing a new image tag to ECR, update the stack so the queue environment's default `ContainerImage` parameter points to the new tag. This way users submitting jobs don't have to manually change the image URI in the submitter dialog.

```bash
aws cloudformation deploy \
    --template-file cloudformation.yaml \
    --stack-name blender-aswf-ci-base-stack \
    --parameter-overrides \
        FarmId=farm-... \
        ECRImageURI=$ECR_REPO:4.5.1 \
        FleetRoleArn=arn:aws:iam::...:role/FleetRole \
        QueueRoleArn=arn:aws:iam::...:role/QueueRole \
        JobAttachmentsBucket=my-deadline-bucket
```

### Tearing down

```bash
aws cloudformation delete-stack --stack-name blender-aswf-ci-base-stack
```

## How it works

1. **Build**: The Dockerfile installs Blender and the adaptor (plus any plugins) into an ASWF VFX Platform base image with CUDA.
2. **Host config**: When a fleet instance launches, the host configuration script installs Docker and the NVIDIA Container Toolkit.
3. **Queue environment**: On each session, the enter script pulls the image and starts the container. It then installs a `blender-openjd` wrapper that forwards adaptor calls into the container via `docker exec`.
4. **Render**: The Deadline Cloud worker invokes `blender-openjd` as usual. The wrapper runs it inside the container with GPU access.

## Adding plugins

1. Download addon `.zip` files from the vendor
2. Place them in the `plugins/` directory
3. Rebuild the image. The build process extracts, installs, and enables them automatically

Do not redistribute proprietary plugins in public images. Users must supply their own licensed copies.

## GPU support

GPU rendering is automatic when the fleet has GPU instances. The queue environment conditionally adds `--gpus all --runtime=nvidia` based on whether the host has an NVIDIA GPU (detected via `nvidia-smi`). CPU-only instances fall back to Cycles CPU rendering.

