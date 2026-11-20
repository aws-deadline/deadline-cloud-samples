# SimFoundry real-to-sim in a container

Run [SimFoundry](https://github.com/NVlabs/SimFoundry) on AWS Deadline Cloud from an image in Amazon
ECR. SimFoundry turns a short tabletop video into an OmniGibson simulation scene. The job template
has no Docker commands. The queue's Docker environment runs every task inside the container.

## The job

The job has two steps, and they run in parallel on GPU workers.

| Step | Tasks | What it does |
|---|---|---|
| `Reconstruct` | 1 | Runs stages 1b and 2 of SimFoundry's pipeline A on a video. Depth Anything 3 estimates depth on 15 sampled frames, and a helper writes a depth preview and a coloured point cloud |
| `Simulate` | 5 | Loads one of SimFoundry's published DROID desk scenes in OmniGibson and Isaac Sim. A Franka arm takes 60 random actions while 3 cameras record an MP4 |

You can run both steps without an API key or access to a gated model. The rest of pipeline A calls Gemini and loads gated
Hugging Face models. See [Run the full pipeline](#run-the-full-pipeline).

## Files

| Path | Contents |
|---|---|
| [`simfoundry-rocky10/`](simfoundry-rocky10/) | The image: SimFoundry's four core conda envs, with OmniGibson 3.8.0 and Isaac Sim 5.1, on Rocky Linux 10 |
| [`job_bundle/template.yaml`](job_bundle/template.yaml) | The job. Each step runs SimFoundry's own scripts from the image |
| [`job_bundle/scripts/depth_preview.py`](job_bundle/scripts/depth_preview.py) | The `Reconstruct` step's helper, uploaded with the job |

## Prerequisites

Set up your farm for containers as described in
[Container support for fleets](https://docs.aws.amazon.com/deadline-cloud/latest/userguide/fleet-container-support.html).
You need these resources:

- A Linux service-managed fleet with the Docker software add-on, one NVIDIA A10G or L4 GPU per
  worker, at least 64 GiB of memory, and a root volume of at least 500 GiB.
- **The fleet's GPU runtime set to `grid:r580`.** Isaac Sim 5.1 crashes at startup on the
  595-series driver that `latest` gives. See the [image README](simfoundry-rocky10/README.md#run-on-deadline-cloud).
- A queue with the Docker default queue environment, associated with that fleet.
- A queue role that can pull from Amazon ECR, such as one with `AmazonEC2ContainerRegistryReadOnly`.

To build and submit, you need Docker and the AWS CLI on a `linux/amd64` host with 250 GB free.
You also need the [Deadline Cloud CLI](https://docs.aws.amazon.com/deadline-cloud/latest/developerguide/submit-jobs.html).
The build doesn't need a GPU.

## Build and push the image

Build the image as described in [`simfoundry-rocky10/README.md`](simfoundry-rocky10/README.md).
The build takes about 2 hours, and the image is 49.4 GiB compressed. These steps follow
[Building, tagging, and pushing a container image](https://docs.aws.amazon.com/deadline-cloud/latest/developerguide/containers-build-push.html).

```console
REGION=<region>
ACCOUNT_ID=<account-id>
REPOSITORY=simfoundry
IMAGE_TAG=9e34ebe-rocky10
REGISTRY="${ACCOUNT_ID}.dkr.ecr.${REGION}.amazonaws.com"
IMAGE_URI="${REGISTRY}/${REPOSITORY}:${IMAGE_TAG}"

cd containers/simfoundry/simfoundry-rocky10
docker build --platform linux/amd64 --tag "${REPOSITORY}:${IMAGE_TAG}" .

aws ecr create-repository --region "${REGION}" --repository-name "${REPOSITORY}"
aws ecr get-login-password --region "${REGION}" | \
  docker login --username AWS --password-stdin "${REGISTRY}"
docker tag "${REPOSITORY}:${IMAGE_TAG}" "${IMAGE_URI}"
docker push "${IMAGE_URI}"
```

Use a version tag or a digest in jobs, not `latest`.

## Submit the job

Submit the bundle from `containers/simfoundry`, passing the image you pushed.

```console
cd containers/simfoundry
deadline bundle submit job_bundle --farm-id <farm-id> --queue-id <queue-id> \
  -p DockerImage=<account-id>.dkr.ecr.<region>.amazonaws.com/simfoundry:9e34ebe-rocky10
```

Always pass `DockerImage`. The tasks need the SimFoundry image, not the queue's default.

When the job finishes, download the output into `job_bundle/output/`.

```console
deadline job download-output --farm-id <farm-id> --queue-id <queue-id> --job-id <job-id>
```

## What you get

```text
job_bundle/output/
├── fruits/
│   ├── s1_video/frames_subsampled_15/   the 15 frames depth was estimated from
│   ├── s2_da/
│   │   ├── da/exports/npz/results.npz   Depth Anything 3 depth, confidence and camera poses
│   │   ├── depth_preview.png            8 frames above their depth maps
│   │   ├── point_cloud.ply              all 15 frames back-projected into one point cloud
│   │   └── depth_summary.json
│   └── pipeline_run_report.json
└── simulate/
    ├── droid_desk_serve_fruits.mp4      3 cameras side by side, 3840x720
    └── ... 4 more scenes
```

| Parameter | Default | Meaning |
|---|---|---|
| `DockerImage` | none | The image URI. The queue's Docker environment pulls and runs it |
| `Video` | `.../example_videos/Fruits.mp4` | The video to reconstruct, as a path inside the image. SimFoundry includes six examples |
| `SceneName` | `fruits` | The output directory for the reconstruction |
| `Frames` | `15` | Frames sampled from the video for depth |
| `SimSteps` | `60` | Random actions per scene, at 15 a second. 60 gives a 6-second clip |
| `AssetsRevision` | `beac75a...` | The commit of the [`nadunRanawaka1/simfoundry-assets`](https://huggingface.co/datasets/nadunRanawaka1/simfoundry-assets) dataset the scenes come from |
| `OutputDir` | `./output` | Where the results go. Job attachments upload it |

On the default video, the depth step produced 15 frames at 448x252 and a point cloud of about
1.2 million points. The median depth was 1.05 m, which matches a camera held about a metre from
the desk. Each rollout video is 61 frames from the wrist camera and two external cameras.

## How it works

The template doesn't reference an image or call Docker. Its commands are plain argv, run inside
the container by the queue's `DockerContainer` environment through its `onWrapTaskRun` hook. The
container mounts the session directory at the same path, so the uploaded script and `OutputDir`
are where the template names them.

`Simulate` has a step environment that downloads the example scenes, about 345 MB, from Hugging
Face. The queue environment's `onWrapEnvEnter` hook runs it inside the container once per session,
and every task in that session reuses it.

The `Reconstruct` step deletes `s1_video/frames_all`, every decoded frame of the video, after
depth finishes. For the default video that is 430 MB that nothing in the job reads.

Isaac Sim's shutdown exits with status 0 even after an error, so each `Simulate` task fails
explicitly when its video is missing.

To learn more, see these pages:

- [Docker queue environment](https://docs.aws.amazon.com/deadline-cloud/latest/developerguide/containers-queue-environment.html)
  and [Share the session working directory](https://docs.aws.amazon.com/deadline-cloud/latest/developerguide/containers-share-session-directory.html)
  in the developer guide.
- [RFC 0008: Environment wrap actions](https://github.com/OpenJobDescription/openjd-specifications/blob/mainline/rfcs/0008-environment-wrap-actions.md)
  for the `WRAP_ACTIONS` syntax.
- [RFC 0005: Expression language](https://github.com/OpenJobDescription/openjd-specifications/blob/mainline/rfcs/0005-expression-language.md)
  for the `EXPR` syntax the template uses to build paths and quote shell arguments.

## Run the full pipeline

This job runs the stages that don't need credentials. To run all of pipeline A with Claude on Amazon
Bedrock and FLUX, with your Hugging Face token passed at submission, see
[`full_pipeline/`](full_pipeline/README.md).

## Cost and cleanup

The job ran in 35 minutes on two on-demand GPU workers that both started cold. About 19 minutes of
that was the workers starting and pulling the image. A second run took 25 minutes, because one
worker still held the image. The tasks took 3 to 6 minutes for `Reconstruct`, 5 minutes for the
first scene in a session and 1.5 minutes for each scene after it. The output is about 60 MB.

Delete image tags you no longer need from Amazon ECR. Each is about 50 GiB.

## Troubleshooting

| Symptom | Fix |
|---|---|
| `Crash detected` in `librtx.scenedb.plugin.so` | The worker has a 595-series driver. Set the fleet's GPU runtime to `grid:r580` and let running workers drain |
| `No rollout video at ...` | The `Simulate` task's scene failed to load. The lines above it name the cause |
| `no kernel image is available` | The GPU isn't in the image's `CUDA_ARCH_LIST`. Rebuild with its compute capability |
| The environment fails with `could not pull`, or with no space left | Check the tag and that the queue role can pull from Amazon ECR. Give the fleet a root volume of at least 500 GiB |
| Tasks stay `READY` | Associate the queue with a fleet that has the Docker software add-on |
| `No rollout video at ...` on a 32 GiB worker | `Simulate` needs at least 64 GiB. On 32 GiB, starting ffmpeg fails with `OSError: [Errno 12] Cannot allocate memory`, and Isaac Sim's shutdown hides the traceback |
| The job is `NOT_COMPATIBLE` | Both steps require a GPU, and `Simulate` requires 60,000 MiB of memory. Associate the queue with a fleet that has both |
| You need logs | Session logs are in CloudWatch under `/aws/deadline/<farm-id>/<queue-id>` |

## Tested with

SimFoundry `9e34ebe` in the [`simfoundry-rocky10`](simfoundry-rocky10/) image, in November 2026.
A Linux service-managed fleet of on-demand workers with 8 to 16 vCPUs, 64 to 128 GiB of memory,
one NVIDIA A10G or L4, a 500 GiB root volume, the Docker software add-on and the `grid:r580` GPU runtime (driver
580.178.04). The default Docker queue environment, unchanged. Deadline Cloud CLI 0.60.11.

## Licences

SimFoundry is Apache 2.0, but the image also contains components with non-commercial and
regional restrictions, and building it accepts the NVIDIA Omniverse License Agreement. See the
[image README](simfoundry-rocky10/README.md#licences). The example scenes come from a Hugging
Face dataset published by a SimFoundry author. Check its terms before you redistribute output.
