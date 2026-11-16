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

Measured on a service-managed fleet of up to 8 spot GPU workers (NVIDIA A10G, L4 and T4), full
protocol (400 episodes):

| Policy | Success | Task time, one GPU back to back | First task to finish on 8 workers | Worker time |
|---|---|---|---|---|
| `lerobot/xvla-libero` (defaults) | **98.5%** (Spatial 97, Object 100, Goal 100, Long 97) | 32 min | **19 min** | about 1.2 GPU worker-hours |
| `lerobot/smolvla_libero` (re-plan every action) | 74.0% (Spatial 90, Object 70, Goal 75, Long 61) | 94 min | 19 min | about 1.8 GPU worker-hours |

Times on 8 workers run from the first task starting to the job finishing, and include each new
worker pulling the image once (about 9 GB compressed). Worker time is the total of the job's worker
sessions and excludes worker start-up. Times vary with spot capacity: a later identical X-VLA job took
12.5 minutes from first task to finish.

Other things the sample shows:

- **Portable results.** Each task writes LeRobot's `eval_info.json` and rollout videos. The `Aggregate`
  step writes `scorecard.json`, `scorecard.csv`, and TensorBoard scalars, and it can fail the job when
  success drops below a threshold. Use the threshold as a regression gate.
- **Repeatable environments.** The image pins LeRobot, MuJoCo, and PyTorch, and it includes the
  benchmark assets and policy weights. Tasks don't use the network.
- **Fast experiments.** To test a different checkpoint or setting, submit the same bundle again with
  different parameters. Each job is independent, so you can test hypotheses in parallel.

## Prerequisites

Set up your farm for containers as described in
[Container support for fleets](https://docs.aws.amazon.com/deadline-cloud/latest/userguide/fleet-container-support.html).
You need these resources:

- A Deadline Cloud farm.
- A queue with job attachments and the **Docker** default queue environment, set to the image you
  push in [Setup](#setup). The console attaches `AmazonEC2ContainerRegistryReadOnly` to the queue
  role so workers can pull the image.
- A Linux service-managed fleet associated with the queue, with:
  - NVIDIA GPU instances such as A10G, L4 or T4, at least 48 GiB of memory, and a 150 GiB root
    volume. One task with 10 episodes in parallel peaks at about 27 GiB.
  - **Enable Docker** selected under container support. The Docker software add-on installs
    rootless Docker and GPU support on each worker.
  - The host configuration script in [`host_config/linux.sh`](host_config/linux.sh).
- A fleet role with CloudWatch Logs permissions for the farm's log groups, as the console creates.
  Without it, workers start and are replaced repeatedly with no logs.
- Spot G-instance GPU quota for Deadline Cloud in your Region, at least as many GPUs as the fleet's
  maximum worker count.
- Docker and the AWS CLI on a `linux/amd64` host to build and push the image, and the
  [Deadline Cloud CLI](https://docs.aws.amazon.com/deadline-cloud/latest/developerguide/submit-jobs-how.html)
  to submit.

## How it works

1. The host configuration script sets `vm.overcommit_memory=1`, because the default strict
   accounting makes PyTorch with many simulator processes fail with `MemoryError` while memory is
   still free.
2. The queue's Docker environment pulls the image and starts one container for each worker session,
   with the GPU available inside it. It mounts the session directory at the same path, so the
   container can write `OutputDir` and read the job's scripts.
3. Each `Eval` task runs `lerobot-eval` for one LIBERO task. The environment's wrap actions run the
   command inside the container, and the results go under `OutputDir/tasks/`.
4. The `Aggregate` step runs after every `Eval` task finishes. It reads all the results and writes
   the scorecard to `OutputDir`.

Like the [MuJoCo hand sweep](../mujoco/), the job template has no Docker commands and doesn't
reference an image. Its commands are the same ones you'd run in the image yourself, and the queue's
environment sets the image they run in. For details, see
[Run portable jobs in containers](https://docs.aws.amazon.com/deadline-cloud/latest/developerguide/containers.html).

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

Then create the queue and fleet from [Prerequisites](#prerequisites), choosing this repository and
tag for the queue's Docker environment.

Push a new tag, or submit by digest, for every rebuild, so results stay traceable to one build.

To include other LIBERO-finetuned policies in the image, pass a space-separated list:
`--build-arg POLICIES="lerobot/xvla-libero your-org/your-policy"`.

## Run or submit

Submit from `containers/libero`. The defaults in `job_bundle/parameter_values.yaml` evaluate
`lerobot/xvla-libero` with the settings from LeRobot's X-VLA documentation.

```console
deadline bundle submit job_bundle --farm-id <farm-id> --queue-id <queue-id> \
  -p DockerImage="${REGISTRY}/${REPOSITORY}:${IMAGE_TAG}"
```

Always pass `DockerImage`. The tasks need your libero-eval-gpu image, not the queue's default.

Evaluate SmolVLA with the paper's setting, which re-plans after every action:

```console
deadline bundle submit job_bundle --farm-id <farm-id> --queue-id <queue-id> \
  -p DockerImage="${REGISTRY}/${REPOSITORY}:${IMAGE_TAG}" \
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
| `DockerImage` | none | The image you pushed, by tag or digest. The queue's Docker environment runs it |
| `PolicyPath` | `lerobot/xvla-libero` | Hugging Face repository of the policy. It must be included in the image |
| `TaskIds` | `0-9` | Task indices to run in every suite |
| `Episodes` | `10` | Episodes per task. LIBERO has 50 fixed starting layouts per task |
| `BatchSize` | `10` | Episodes simulated in parallel within one task |
| `NActionSteps` | `0` | Actions per policy call. `0` keeps the checkpoint's setting; `1` re-plans after every action |
| `ControlMode` | `absolute` | `absolute` for X-VLA, `relative` for SmolVLA |
| `EpisodeLength` | `800` | Maximum steps per episode. `0` uses each suite's default |
| `CameraFlags` | `none` | `camera_mapping` renames the cameras for `lerobot/smolvla_libero` |
| `MinSuccessRate` | `0` | Fail `Aggregate` below this overall success, in percent |
| `RunName` | blank | TensorBoard run name for this job. Blank uses the policy name |
| `OutputDir` | `./output` | Where results are written. Job attachments upload it |

Each `Eval` task stops after 30 minutes, and `Aggregate` after 10. A hung task then fails instead of
keeping a GPU worker busy. A task with the default 10 episodes takes a few minutes. If you raise
`Episodes` a lot, raise `timeout` in `template.yaml` too.

```text
output/
├── tasks/<suite>_task<n>/
│   ├── eval/eval_info.json        per-episode success, from lerobot-eval
│   ├── eval/videos/...            rollout videos
│   └── worker.json                GPU model, render backend and image
├── scorecard.json                 per-suite and overall success
├── scorecard.csv                  one row per suite and task
└── tensorboard/<run>/             TensorBoard scalars and HParams
```

## Comparing jobs in TensorBoard

Each job writes TensorBoard logs under `tensorboard/<RunName>/`:

- `task_success/<suite>` in the **Scalars** tab: success for each task, plotted by task index. Failing tasks stand out.
- The **HParams** tab: the job's policy and settings next to its overall and per-suite success rates.

To compare jobs, give each one its own `RunName`, download their outputs, and copy the run
directories into one folder:

```console
mkdir -p compare
cp -r output-job-a/tensorboard/* output-job-b/tensorboard/* compare/
tensorboard --logdir compare --host 127.0.0.1
```

Open the **HParams** tab for a table of jobs, settings, and scores. The Scalars tab also lists
`hparam/*` charts with one point each. The HParams table reads its values from them, so type
`task_success` in the Scalars filter box to show only the per-task charts.

## Comparing scores

- **Compare within one worker type.** CPU rendering (OSMesa) and GPU rendering (EGL) give the policy
  slightly different camera images, and success can differ on the same episodes. In our tests, the
  default SmolVLA setting scored 80% on CPU and 100% on GPU on the same 10 episodes. `worker.json`
  records the GPU and the render backend.
- **Published scores may not reproduce.** With the paper's setting, `lerobot/smolvla_libero` scored
  74.0% on this setup (Spatial 90%, Object 70%, Goal 75%, Long 61%), against 87.3% in the SmolVLA
  paper. `lerobot/xvla-libero` scored 98.5% on the same setup, so the gap is specific to that
  checkpoint. Other users report the same gap in
  [lerobot #2354](https://github.com/huggingface/lerobot/issues/2354).
- **MuJoCo stays on 3.3.x.** From MuJoCo 3.4, some LIBERO starting layouts no longer settle
  correctly ([lerobot #4390](https://github.com/huggingface/lerobot/issues/4390)).

## Security, cost, and cleanup

- **Image licensing.** The image contains the LIBERO benchmark assets, downloaded from the
  [`lerobot/libero-assets`](https://huggingface.co/datasets/lerobot/libero-assets) mirror of the
  [LIBERO](https://github.com/Lifelong-Robot-Learning/LIBERO) project, whose code is MIT-licensed.
  The assets have no stated license and include 3D models from third parties with their own
  terms: models from TurboSquid, and the grocery models from the
  [HOPE dataset](https://github.com/swtyree/hope-dataset), which is licensed CC BY-NC-SA 4.0
  (non-commercial). Check those terms before using the benchmark, or images and videos rendered
  from it, commercially. Keep the image in a private repository and don't publish it. The image
  also contains `lerobot/xvla-libero`, `lerobot/smolvla_libero`, the
  `HuggingFaceTB/SmolVLM2-500M-Video-Instruct` backbone and the `facebook/bart-large` tokenizer,
  all listed as Apache-2.0 on their Hugging Face model cards. Check the license of any policy you
  add with `POLICIES`.
- **Containers.** Docker runs rootless as the job user, so jobs don't get root access to the worker
  through Docker, and files the job writes belong to the job user. See
  [Security and best practices for containers](https://docs.aws.amazon.com/deadline-cloud/latest/developerguide/containers-security.html).
- **Network.** Tasks don't need the network: the image sets `HF_HUB_OFFLINE=1` and includes
  everything they read. Containers keep Docker's default network access.
- **Cost.** You pay for GPU worker time while tasks run, plus image storage in Amazon ECR. The image is
  large, and each new worker pulls it once. Set the fleet's minimum worker count to 0 so it scales
  down when idle. Delete the ECR repository when you're done.

## Troubleshooting

| Symptom | Cause and fix |
|---|---|
| Workers start and are replaced every 10 to 15 minutes, with no logs | The fleet role is missing CloudWatch Logs permissions |
| The worker agent restarts at "Running host configuration script" | The host script contains `{{`, which is parsed as template syntax. Remove it |
| `MemoryError` in an `Eval` task while memory is free | `vm.overcommit_memory` is still 2. Check the host script ran, or raise the fleet's minimum memory |
| The environment fails with `could not pull` | Check the tag, and that the queue role can pull from Amazon ECR |
| Tasks stay `READY` | Associate the queue with a fleet that has **Enable Docker** selected and GPU instances |
| `exec: "lerobot-eval": executable file not found` | The task ran in the wrong image. Pass `-p DockerImage=...` with your libero-eval-gpu image |
| A policy fails to load or scores near 0% | Check `ControlMode`, `CameraFlags` and `EpisodeLength` against the policy's documentation |

Task logs are in the queue's CloudWatch log group, and worker logs are in the fleet's log group.

## Related resources

- [LeRobot LIBERO documentation](https://huggingface.co/docs/lerobot/en/libero)
- [MuJoCo hand sweep](../mujoco/), a CPU MuJoCo sample that uses the Docker queue environment
- [Blender GPU container](../blender/blender-aswf-ci-base/), another GPU container sample
- [Host configuration scripts](../../host_configuration_scripts/)
