# MoonRay on AWS Deadline Cloud with the Docker queue environment

This sample renders a [MoonRay](https://openmoonray.org/) scene in a container that you build from source.
The job template only runs `moonray`. The queue's Docker queue environment runs it inside the container.

## Sample contents

* [`moonray-rocky9/`](moonray-rocky9/) builds a CPU-only MoonRay image on Rocky Linux 9.
* [`job_bundle/`](job_bundle/) is a one-step job that renders one scene folder to an OpenEXR image.

## Prerequisites

* A farm with a Linux service-managed fleet that has the Docker software add-on.
* A queue associated with that fleet that uses the Docker default queue environment.
  See [Container support for service-managed fleets](https://docs.aws.amazon.com/deadline-cloud/latest/userguide/fleet-container-support.html).
* A queue role that can pull from Amazon ECR. The console attaches `AmazonEC2ContainerRegistryReadOnly`.
* A private Amazon ECR repository named `moonray-rocky9` in the farm's Region.
* Docker, the AWS CLI, and the Deadline Cloud CLI (`pip install deadline`) on your workstation.
* An x86_64 build machine with 8 GB of RAM or more and about 20 GB of free disk.

## Build and push the image

The build compiles MoonRay and its dependencies. It took about 45 minutes on 16 x86_64 cores, so start it first.
The steps follow [Building, tagging, and pushing a container image](https://docs.aws.amazon.com/deadline-cloud/latest/developerguide/containers-build-push.html).

```console
REGION=<region>
ACCOUNT_ID=<account-id>
REPOSITORY=moonray-rocky9
IMAGE_TAG=v2026.29.1
REGISTRY="${ACCOUNT_ID}.dkr.ecr.${REGION}.amazonaws.com"

cd moonray-rocky9
docker build --platform linux/amd64 -t "${REPOSITORY}:${IMAGE_TAG}" .
```

Test the image before you push it. The command renders a bundled test scene and exits 0.

```console
docker run --rm "${REPOSITORY}:${IMAGE_TAG}" \
    moonray -in /source/testdata/rectangle.rdla -auto_affinity off -out /tmp/rectangle.exr
```

Log in to Amazon ECR, then tag and push the image.

```console
aws ecr get-login-password --region "${REGION}" \
    | docker login --username AWS --password-stdin "${REGISTRY}"
docker tag "${REPOSITORY}:${IMAGE_TAG}" "${REGISTRY}/${REPOSITORY}:${IMAGE_TAG}"
docker push "${REGISTRY}/${REPOSITORY}:${IMAGE_TAG}"
```

Record the image digest. It identifies the exact image that your jobs run.

```console
aws ecr describe-images --region "${REGION}" --repository-name "${REPOSITORY}" \
    --image-ids imageTag="${IMAGE_TAG}" --query 'imageDetails[0].imageDigest' --output text
```

To build another MoonRay version, see [moonray-rocky9/README.md](moonray-rocky9/README.md).

## Submit the job

Run these commands from `containers/moonray/`.
Download the MoonRay example scenes and unpack one scene into the job bundle.

```console
curl -LO https://docs.openmoonray.org/assets/test-scenes/example_scenes.zip
unzip -q example_scenes.zip 'veach-mis/*' -d job_bundle/scenes
```

Submit the bundle with the image URI that you pushed.

```console
deadline bundle submit job_bundle --farm-id <farm-id> --queue-id <queue-id> \
    -p DockerImage=<account-id>.dkr.ecr.<region>.amazonaws.com/moonray-rocky9:v2026.29.1
```

Wait for the job, then download the rendered image.

```console
deadline job wait --farm-id <farm-id> --queue-id <queue-id> --job-id <job-id>
deadline job download-output --farm-id <farm-id> --queue-id <queue-id> --job-id <job-id>
```

| Parameter | Default | Description |
|---|---|---|
| `DockerImage` | None | ECR URI of the MoonRay image. Without it, the job runs the queue's default image. |
| `SceneDir` | `./scenes/veach-mis` | Folder with `scene.rdlb`, `scene.rdla`, and textures. Job attachments upload it. |
| `OutputDir` | `./output` | Folder for the rendered EXR. Job attachments return it. |
| `ExecMode` | `scalar` | MoonRay CPU execution mode, `scalar` or `vectorized`. |
| `ResolutionDivisor` | `1.0` | Divides the scene's image size. Use `4` for a quick preview. |

To render another example scene, unzip it the same way and pass `-p SceneDir=job_bundle/scenes/<name>`.

## What you get

The download writes `job_bundle/output/veach-mis.exr`, a 1280x720 OpenEXR image of about 5.8 MB.
On a 16 vCPU Linux fleet worker with the default parameters, the render took about 2 minutes.
Pulling the image added about 75 seconds to the session on a worker that had not cached it.

## How it works

The job's only step is a bash script that runs `moonray`.
The template doesn't declare the `WRAP_ACTIONS` extension and doesn't call container tools.

The queue's Docker queue environment does the container work with the `WRAP_ACTIONS` and `EXPR` extensions.
Its `onEnter` action pulls `DockerImage` and starts one container for the session.

The container mounts the session directory at the same path.
Job attachments put `SceneDir` and `OutputDir` there. The job's paths are the same inside the container.

The `onWrapTaskRun` hook replaces the task's command.
It runs the same command in the session container with `docker container exec`.
The worker uploads `OutputDir` after the task. The `onExit` action then stops the container.

The job declares `DockerImage`. Its value replaces the queue environment's default image.
Keep the definition identical to the queue environment's. The Deadline Cloud CLI rejects a submission when they differ.

The script passes `-auto_affinity off` to `moonray`.
Containers don't get `CAP_SYS_NICE`, which MoonRay's NUMA memory binding needs.

Read more in the Deadline Cloud developer guide:

* [Docker queue environment overview](https://docs.aws.amazon.com/deadline-cloud/latest/developerguide/containers-queue-environment.html)
  and its [Customize a Docker queue environment](https://docs.aws.amazon.com/deadline-cloud/latest/developerguide/containers-queue-environment.html#containers-queue-customize) section
* [Run portable jobs in containers](https://docs.aws.amazon.com/deadline-cloud/latest/developerguide/containers.html)
* [Share the session working directory](https://docs.aws.amazon.com/deadline-cloud/latest/developerguide/containers-share-session-directory.html)
* [Security and best practices for container jobs](https://docs.aws.amazon.com/deadline-cloud/latest/developerguide/containers-security.html)

The template syntax comes from these Open Job Description specifications:

* [RFC 0008: Environment wrap actions](https://github.com/OpenJobDescription/openjd-specifications/blob/mainline/rfcs/0008-environment-wrap-actions.md) (`WRAP_ACTIONS`)
* [RFC 0005: Expression language](https://github.com/OpenJobDescription/openjd-specifications/blob/mainline/rfcs/0005-expression-language.md) (`EXPR`)
* [RFC 0006: Expression function library](https://github.com/OpenJobDescription/openjd-specifications/blob/mainline/rfcs/0006-expression-function-library.md) (`repr_sh`, `flatten`)
* [RFC 0004: Enhanced limits and capabilities](https://github.com/OpenJobDescription/openjd-specifications/blob/mainline/rfcs/0004-enhanced-limits-and-capabilities.md) (`FEATURE_BUNDLE_1`, the `bash:` step)
* [2023-09 template schemas](https://github.com/OpenJobDescription/openjd-specifications/wiki/2023-09-Template-Schemas)

## Troubleshooting

* `numaNodeMBInd() sysCallMBind() failed`: the render ran without `-auto_affinity off`. Restore the flag.
* `openjd_fail: could not pull`: check the image URI and the queue role's Amazon ECR permissions.
* `moonray: command not found`: the session ran an image without MoonRay on `PATH`.
  Check that you passed `DockerImage`, and that the image was built from this sample's Dockerfile.
* Session logs are in the Deadline Cloud monitor and in CloudWatch Logs under `/aws/deadline/<farm-id>/<queue-id>`.

## Cost and cleanup

Fleet workers bill while they run. Amazon ECR bills for image storage, about 1.9 GB for this image.
Delete the repository when you no longer need it.

```console
aws ecr delete-repository --region <region> --repository-name moonray-rocky9 --force
```
