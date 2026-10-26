# LIBERO policy evaluation on GPU workers

Evaluate a robot policy on the [LIBERO](https://github.com/Lifelong-Robot-Learning/LIBERO) benchmark
with [LeRobot](https://huggingface.co/docs/lerobot/en/libero), spread across AWS Deadline Cloud GPU
workers. Choose this sample when one benchmark run takes too long on one machine, or when you want
to compare checkpoints or settings in parallel.

## Results and features

LIBERO runs in [MuJoCo](https://github.com/google-deepmind/mujoco) through robosuite. The standard
protocol is 4 suites × 10 tasks × 10 episodes, which is 400 episodes per policy. This sample runs each
suite-and-task pair as its own Deadline Cloud task, so the 40 tasks run in parallel across the fleet.
A final `Aggregate` step combines them into one scorecard.

Measured on a service-managed fleet of up to 8 spot GPU workers (NVIDIA A10G and L4), full protocol
(400 episodes):

| Policy | Success | Task time, one GPU back to back | Submit to finish on 8 workers | Worker time |
|---|---|---|---|---|
| `lerobot/xvla-libero` (defaults) | **98.5%** (Spatial 96, Object 100, Goal 100, Long 98) | 40 min | **14 min** | about 1.4 GPU worker-hours |
| `lerobot/smolvla_libero` (re-plan every action) | 72.8% (Spatial 89, Object 68, Goal 74, Long 60) | 102 min | 23 min | about 2.4 GPU worker-hours |

Submit-to-finish times include each new worker pulling the image once (about 9 GB compressed).
Worker time excludes worker start-up.

Other things the sample shows:

- **Portable results.** Each task writes LeRobot's `eval_info.json` and rollout videos. The `Aggregate`
  step writes `scorecard.json`, `scorecard.csv`, and TensorBoard scalars, and it can fail the job when
  success drops below a threshold. Use the threshold as a regression gate.
- **Repeatable environments.** The image pins LeRobot, MuJoCo, and PyTorch, and it includes the
  benchmark assets and policy weights. Tasks don't use the network.
- **Fast experiments.** To test a different checkpoint or setting, submit the same bundle again with
  different parameters. Each job is independent, so you can test hypotheses in parallel.

## Prerequisites

- A Deadline Cloud farm, plus a queue with job attachments.
- A Linux service-managed fleet with:
  - NVIDIA GPU instances, at least 48 GiB of memory, and a 150 GiB root volume. One task with 10
    episodes in parallel peaks at about 27 GiB.
  - The host configuration script in [`host_config/linux.sh`](host_config/linux.sh), with a timeout
    of at least 900 seconds.
  - A custom attribute `attr.DockerEngine` with the value `available`.
- A fleet role with CloudWatch Logs permissions for the farm's log groups, as the console creates.
  Without it, workers start and are replaced repeatedly with no logs.
- A queue role that can pull from your Amazon ECR repository, such as one with
  `AmazonEC2ContainerRegistryReadOnly`.
- Spot G-instance GPU quota for Deadline Cloud in your Region, at least as many GPUs as the fleet's
  maximum worker count.
- Docker and the AWS CLI on a `linux/amd64` host to build and push the image, and the
  [Deadline Cloud CLI](https://docs.aws.amazon.com/deadline-cloud/latest/developerguide/submit-jobs.html)
  to submit.

## How it works

1. The host configuration script installs Docker and the NVIDIA Container Toolkit on each new worker.
   It also sets `vm.overcommit_memory=1`, because the default strict accounting makes PyTorch with
   many simulator processes fail with `MemoryError` while memory is still free.
2. Each `Eval` task pulls the image; only the first pull on a worker downloads layers, and later pulls just check the manifest. It then runs `lerobot-eval` for one LIBERO task
   with `docker run --runtime=nvidia` and writes its results under `OutputDir/tasks/`.
3. The `Aggregate` step runs after every `Eval` task finishes. It reads all the results and writes the
   scorecard to `OutputDir`.

The tasks start containers themselves, like the
[Blender GPU container](../blender/blender-aswf-ci-base/) sample, rather than through the Docker queue
environment that the [MuJoCo hand sweep](../mujoco/) uses. The Docker queue environment runs CPU jobs.
This sample needs the NVIDIA runtime on GPU workers.

## Setup

Build the image and push it to a private repository. The build downloads about 1 GB of LIBERO assets
and the policy weights from the Hugging Face Hub.

```console
REGION=<region>
ACCOUNT_ID=<account-id>
REPOSITORY=libero-eval-gpu
IMAGE_TAG=0.6.1-mj3.3.7
REGISTRY="${ACCOUNT_ID}.dkr.ecr.${REGION}.amazonaws.com"

cd containers/libero/libero-eval-gpu
docker build --platform linux/amd64 --tag "${REPOSITORY}:${IMAGE_TAG}" .

aws ecr create-repository --region "${REGION}" --repository-name "${REPOSITORY}"
aws ecr get-login-password --region "${REGION}" | \
  docker login --username AWS --password-stdin "${REGISTRY}"
docker tag "${REPOSITORY}:${IMAGE_TAG}" "${REGISTRY}/${REPOSITORY}:${IMAGE_TAG}"
docker push "${REGISTRY}/${REPOSITORY}:${IMAGE_TAG}"
```

Push a new tag, or submit by digest, for every rebuild. Each task re-pulls the image, so a rebuilt
image under the same tag is also picked up, but distinct tags keep results traceable to one build.

To include other LIBERO-finetuned policies in the image, pass a space-separated list:
`--build-arg POLICIES="lerobot/xvla-libero your-org/your-policy"`.

## Run or submit

Submit from `containers/libero`. The defaults in `job_bundle/parameter_values.yaml` evaluate
`lerobot/xvla-libero` with the settings from LeRobot's X-VLA documentation.

```console
deadline bundle submit job_bundle --farm-id <farm-id> --queue-id <queue-id> \
  -p Image="${REGISTRY}/${REPOSITORY}:${IMAGE_TAG}"
```

Evaluate SmolVLA with the paper's setting, which re-plans after every action:

```console
deadline bundle submit job_bundle --farm-id <farm-id> --queue-id <queue-id> \
  -p Image="${REGISTRY}/${REPOSITORY}:${IMAGE_TAG}" \
  -p PolicyPath=lerobot/smolvla_libero -p ControlMode=relative -p EpisodeLength=0 \
  -p CameraFlags=camera_mapping -p NActionSteps=1
```

Run a quick check on 2 tasks per suite, and fail the job if overall success drops below 80%:

```console
deadline bundle submit job_bundle ... -p TaskIds=0,1 -p MinSuccessRate=80
```

When the job finishes, download the results:

```console
deadline job download-output --farm-id <farm-id> --queue-id <queue-id> --job-id <job-id>
```

## Parameters and outputs

| Parameter | Default | Meaning |
|---|---|---|
| `Image` | none | The image you pushed, by tag or digest |
| `PolicyPath` | `lerobot/xvla-libero` | Hugging Face repository of the policy. It must be included in the image |
| `TaskIds` | `0-9` | Task indices to run in every suite |
| `Episodes` | `10` | Episodes per task. LIBERO has 50 fixed starting layouts per task |
| `BatchSize` | `10` | Episodes simulated in parallel within one task |
| `NActionSteps` | `0` | Actions per policy call. `0` keeps the checkpoint's setting; `1` re-plans after every action |
| `ControlMode` | `absolute` | `absolute` for X-VLA, `relative` for SmolVLA |
| `EpisodeLength` | `800` | Maximum steps per episode. `0` uses each suite's default |
| `CameraFlags` | `none` | `camera_mapping` renames the cameras for `lerobot/smolvla_libero` |
| `MinSuccessRate` | `0` | Fail `Aggregate` below this overall success, in percent |
| `OutputDir` | `./output` | Where results are written. Job attachments upload it |

```text
output/
├── tasks/<suite>_task<n>/
│   ├── eval/eval_info.json        per-episode success, from lerobot-eval
│   ├── eval/videos/...            rollout videos
│   └── worker.json                GPU model, render backend and image
├── scorecard.json                 per-suite and overall success
├── scorecard.csv                  one row per suite and task
└── tensorboard/                   tensorboard --logdir output/tensorboard
```

## Comparing scores

- **Compare within one worker type.** CPU rendering (OSMesa) and GPU rendering (EGL) give the policy
  slightly different camera images, and success can differ on the same episodes. In our tests, the
  default SmolVLA setting scored 80% on CPU and 100% on GPU on the same 10 episodes. `worker.json`
  records the GPU and the render backend.
- **Published scores may not reproduce.** With the paper's setting, `lerobot/smolvla_libero` scored
  72.8% on this setup (Spatial 89%, Object 68%, Goal 74%, Long 60%), against 87.3% in the SmolVLA
  paper. `lerobot/xvla-libero` scored 98.5% on the same setup, so the gap is specific to that
  checkpoint. Other users report the same gap in
  [lerobot #2354](https://github.com/huggingface/lerobot/issues/2354).
- **MuJoCo stays on 3.3.x.** From MuJoCo 3.4, some LIBERO starting layouts no longer settle
  correctly ([lerobot #4390](https://github.com/huggingface/lerobot/issues/4390)).

## Security, cost, and cleanup

- **Image licensing.** The image contains the LIBERO asset collection, which states no license, so
  keep the image in a private repository and don't publish it. It also contains `lerobot/xvla-libero`,
  `lerobot/smolvla_libero`, the `HuggingFaceTB/SmolVLM2-500M-Video-Instruct` backbone and the
  `facebook/bart-large` tokenizer, all listed as Apache-2.0 on their Hugging Face model cards. Check
  the license of any policy you add with `POLICIES`.
- **Docker access.** The host script adds `job-user` to the `docker` group, which is equivalent to
  root on the worker. Any job on the fleet can then read the worker agent's and fleet role's
  credentials, and other jobs' session data on the same host. Use a dedicated fleet, and limit who can
  submit to its queue.
- **Network.** Evaluation containers run with `--network none`. Only the image pull uses the network.
- **Cost.** You pay for GPU worker time while tasks run, plus image storage in Amazon ECR. The image is
  large, and each new worker pulls it once. Set the fleet's minimum worker count to 0 so it scales
  down when idle. Delete the ECR repository when you're done.

## Troubleshooting

| Symptom | Cause and fix |
|---|---|
| Workers start and are replaced every 10 to 15 minutes, with no logs | The fleet role is missing CloudWatch Logs permissions |
| The worker agent restarts at "Running host configuration script" | The host script contains `{{`, which is parsed as template syntax. Remove it |
| `MemoryError` in an `Eval` task while memory is free | `vm.overcommit_memory` is still 2. Check the host script ran, or raise the fleet's minimum memory |
| `unresolvable CDI devices nvidia.com/gpu=all` or a cgroup "device filter" error | Use `--runtime=nvidia`, as this template does. On these workers, `--gpus all` and Docker's CDI devices fail |
| A policy fails to load or scores near 0% | Check `ControlMode`, `CameraFlags` and `EpisodeLength` against the policy's documentation |

Task logs are in the queue's CloudWatch log group, and worker logs are in the fleet's log group.

## Related resources

- [LeRobot LIBERO documentation](https://huggingface.co/docs/lerobot/en/libero)
- [MuJoCo hand sweep](../mujoco/), a CPU MuJoCo sample that uses the Docker queue environment
- [Blender GPU container](../blender/blender-aswf-ci-base/), another GPU container sample
- [Host configuration scripts](../../host_configuration_scripts/)
