# MuJoCo hand sweep in a container

Run a [MuJoCo](https://github.com/google-deepmind/mujoco) physics sweep on AWS Deadline Cloud from an
image in Amazon ECR. The job template has no Docker commands. The queue's Docker environment runs
every task inside the container.

## The sweep

The job sweeps three physics parameters on the Shadow Dexterous Hand holding a ball.
Each task runs one combination of damping, stiffness and friction, 24 tasks in all.

Each task simulates 2 seconds and writes 40 PNG frames, an H.264 MP4 and a `metrics.json`.
A final `Summarize` step reads all 24 metrics files and writes `summary.csv`.

## Files

| Path | Contents |
|---|---|
| [`mujoco-rocky9/`](mujoco-rocky9/) | The image: MuJoCo 3.11.0, the hand and cube models, and the `mj-hand-sweep` command |
| [`job_bundle/template.yaml`](job_bundle/template.yaml) | The job. Each step runs a command from the image |
| [`job_bundle/scripts/summarize_metrics.py`](job_bundle/scripts/summarize_metrics.py) | The `Summarize` step's helper, uploaded with the job |

## Prerequisites

Set up your farm for containers as described in
[Container support for fleets](https://docs.aws.amazon.com/deadline-cloud/latest/userguide/fleet-container-support.html).
You need these resources:

- A Linux service-managed fleet with the Docker software add-on.
- A queue with the Docker default queue environment, associated with that fleet.
- A queue role that can pull from Amazon ECR, such as one with `AmazonEC2ContainerRegistryReadOnly`.

To build and submit, you need Docker and the AWS CLI on a `linux/amd64` host.
You also need the [Deadline Cloud CLI](https://docs.aws.amazon.com/deadline-cloud/latest/developerguide/submit-jobs.html).

## Build and push the image

These steps follow
[Building, tagging, and pushing a container image](https://docs.aws.amazon.com/deadline-cloud/latest/developerguide/containers-build-push.html).
Set your account, Region, repository and tag first.

```console
REGION=<region>
ACCOUNT_ID=<account-id>
REPOSITORY=mujoco-rocky9
IMAGE_TAG=3.11.0
REGISTRY="${ACCOUNT_ID}.dkr.ecr.${REGION}.amazonaws.com"
IMAGE_URI="${REGISTRY}/${REPOSITORY}:${IMAGE_TAG}"
```

Build the image and check that the sweep command runs.

```console
cd containers/mujoco/mujoco-rocky9
docker build --platform linux/amd64 --tag "${REPOSITORY}:${IMAGE_TAG}" .
docker run --rm "${REPOSITORY}:${IMAGE_TAG}" mj-hand-sweep --help
```

Create the repository once, then log in, tag and push.

```console
aws ecr create-repository --region "${REGION}" --repository-name "${REPOSITORY}"
aws ecr get-login-password --region "${REGION}" | \
  docker login --username AWS --password-stdin "${REGISTRY}"
docker tag "${REPOSITORY}:${IMAGE_TAG}" "${IMAGE_URI}"
docker push "${IMAGE_URI}"
```

Record the digest with your build output.
Use a version tag or a digest in jobs, not `latest`.
A mutable tag can resolve to a different image in each session.

```console
aws ecr describe-images --region "${REGION}" --repository-name "${REPOSITORY}" \
  --image-ids imageTag="${IMAGE_TAG}" --query 'imageDetails[0].imageDigest' --output text
```

## Submit the job

Submit the bundle from `containers/mujoco`, passing the image you pushed.

```console
cd containers/mujoco
deadline bundle submit job_bundle --farm-id <farm-id> --queue-id <queue-id> \
  -p DockerImage=<account-id>.dkr.ecr.<region>.amazonaws.com/mujoco-rocky9:3.11.0
```

Always pass `DockerImage`. The tasks need your MuJoCo image, not the queue's default.

When the job finishes, download the output into `job_bundle/output/`.

```console
deadline job download-output --farm-id <farm-id> --queue-id <queue-id> --job-id <job-id>
```

## What you get

Each combination gets its own directory, named for its parameters.

```text
job_bundle/output/
├── damp0.25-kp0.5-fr0.25/
│   ├── frames/damp0.25-kp0.5-fr0.25-0000.png ... -0039.png
│   ├── clip.mp4
│   └── metrics.json
├── ... 23 more combinations
└── summary.csv
```

| Parameter | Default | Meaning |
|---|---|---|
| `DockerImage` | none | The image URI. The queue's Docker environment pulls and runs it |
| `Duration` | `2.0` | Simulated seconds per combination, which is also the clip length |
| `Fps` | `20.0` | Rendered frames per simulated second. Rendering sets the cost |
| `VideoBitrate` | `2M` | Target bitrate for each MP4 |
| `Model` | `.../scene_right_ball.xml` | The MJCF scene inside the image |
| `OutputDir` | `./output` | Where the results go. Job attachments upload it |

The task parameters are `DampingScale` (0.25, 0.5, 2.0, 4.0), `StiffnessScale` (0.5, 1.0, 2.0) and
`FrictionScale` (0.25, 4.0). Edit the ranges in `template.yaml` to change the sweep.

Friction has the clearest effect. The `Summarize` step prints the mean for each friction value.

| `FrictionScale` | Mean ball displacement | Mean lowest ball height |
|---|---|---|
| 0.25 | 0.317 m | -0.078 m |
| 4.0 | 0.048 m | 0.045 m |

At low friction the ball rolls off the hand. At high friction it stays in the palm.

## How it works

The template doesn't reference an image or call Docker.
Its commands are plain argv, like `mj-hand-sweep --damping-scale 4.0`.

The queue's `DockerContainer` environment starts one container for each session.
It mounts the session directory at the same path inside the container.

The environment uses the `WRAP_ACTIONS` extension. Its `onWrapTaskRun` hook replaces each task's
`onRun` with a `docker container exec` of the same command and arguments.
Containers run rootless, so files that the job writes belong to the job user on the worker.

`OutputDir` and the uploaded scripts are inside the session directory, so the container can read and
write them. Job attachments then upload `OutputDir` when each task finishes.

The template uses the `EXPR` extension to build each task's label, such as `damp4.0-kp2.0-fr0.25`.
It also joins paths with `/`, as in `Param.OutputDir / label`.

To learn more, see these pages:

- [Docker queue environment](https://docs.aws.amazon.com/deadline-cloud/latest/developerguide/containers-queue-environment.html)
  and [Share the session working directory](https://docs.aws.amazon.com/deadline-cloud/latest/developerguide/containers-share-session-directory.html)
  in the developer guide.
- [RFC 0008: Environment wrap actions](https://github.com/OpenJobDescription/openjd-specifications/blob/mainline/rfcs/0008-environment-wrap-actions.md)
  for the `WRAP_ACTIONS` syntax.
- [RFC 0005: Expression language](https://github.com/OpenJobDescription/openjd-specifications/blob/mainline/rfcs/0005-expression-language.md)
  and [RFC 0006: Expression function library](https://github.com/OpenJobDescription/openjd-specifications/blob/mainline/rfcs/0006-expression-function-library.md)
  for `EXPR`.
- [Template schemas](https://github.com/OpenJobDescription/openjd-specifications/wiki/2023-09-Template-Schemas)
  for the rest of the job template.

## Cost and cleanup

The 24 tasks run in parallel. A spot fleet scales toward its maximum worker count.
On three running 16 vCPU workers, the job took about 2.5 minutes.
Each run writes about 100 MB of output to your job attachments bucket.

Delete image tags you no longer need from Amazon ECR. Job output stays in your job attachments bucket.

## Troubleshooting

| Symptom | Fix |
|---|---|
| `exec: "mj-hand-sweep": executable file not found in $PATH` | The task ran in the wrong image. Pass `-p DockerImage=...` with your MuJoCo image |
| The environment fails with `could not pull` | Check the tag, and that the queue role can pull from Amazon ECR |
| Tasks stay `READY` | Associate the queue with a fleet that has the Docker software add-on |
| You need logs | Session logs are in CloudWatch under `/aws/deadline/<farm-id>/<queue-id>` |

## Tested with

MuJoCo 3.11.0 on Rocky Linux 9, built for `linux/amd64`.
A CPU-only Linux service-managed spot fleet with 16 vCPUs per worker and the Docker software add-on.
Deadline Cloud CLI 0.60.7, in October 2026.

## Related resources

- [Run portable jobs in containers](https://docs.aws.amazon.com/deadline-cloud/latest/developerguide/containers.html)
  in the developer guide.
- [Security and best practices for containers](https://docs.aws.amazon.com/deadline-cloud/latest/developerguide/containers-security.html).
- [`job_bundles/mujoco_sim_to_policy`](../../job_bundles/mujoco_sim_to_policy/), a MuJoCo pipeline that
  uses a Conda queue environment and a GPU fleet.
