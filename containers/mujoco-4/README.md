# MuJoCo 4.0 feature sweeps in a container

Run two [MuJoCo](https://github.com/google-deepmind/mujoco) 4.0 parameter sweeps on AWS Deadline Cloud
from an image in Amazon ECR. Each sweep exercises a feature that MuJoCo 4.0 introduced:
elasto-plasticity and speculative contacts. The job templates have no Docker commands. The queue's
Docker environment runs every task inside the container.

For the MuJoCo 3.11.0 Shadow Hand sweep, see [`../mujoco/`](../mujoco/).

## The sweeps

| Bundle | MuJoCo 4.0 feature | Scene | Tasks |
|---|---|---|---|
| [`plasticity_sweep/`](plasticity_sweep/) | Continuum elasto-plasticity for 3D flexes (`yield`) | [`model/plastic/torsion.xml`](https://github.com/google-deepmind/mujoco/blob/4.0.0/model/plastic/torsion.xml): two bars twisted past 180 degrees and released | 8 yield strains, then `Summarize` |
| [`speculative_sweep/`](speculative_sweep/) | Speculative contacts (`<flag speculative="enable"/>`) | [`model/speculative/newton.xml`](https://github.com/google-deepmind/mujoco/blob/4.0.0/model/speculative/newton.xml): a Newton's cradle of five 3 mm steel plates | 2 release angles x 5 timesteps x speculative on or off = 20, then `Summarize` |

Each task simulates 2 seconds and writes about 40 PNG frames, an H.264 MP4 and a `metrics.json`.
The `Summarize` step reads the `metrics.json` files in its job's `OutputDir` and writes `summary.csv`.
Each job gets only its own output from job attachments, so give each job its own local download
directory. Downloading both jobs into the same directory overwrites the first job's `summary.csv`.

## Files

| Path | Contents |
|---|---|
| [`mujoco4-rocky9/`](mujoco4-rocky9/) | The image: MuJoCo 4.0.0, the `plastic/` and `speculative/` example models, and the `mj4-sweep` and `mj4-summarize` commands |
| [`plasticity_sweep/template.yaml`](plasticity_sweep/template.yaml) | The yield strain sweep |
| [`speculative_sweep/template.yaml`](speculative_sweep/template.yaml) | The timestep and speculative contacts sweep |

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
REPOSITORY=mujoco4-rocky9
IMAGE_TAG=4.0.0
REGISTRY="${ACCOUNT_ID}.dkr.ecr.${REGION}.amazonaws.com"
IMAGE_URI="${REGISTRY}/${REPOSITORY}:${IMAGE_TAG}"
```

Build the image and check that the sweep command runs.
The build itself runs a short point of each sweep. A broken renderer fails the build.

```console
cd containers/mujoco-4/mujoco4-rocky9
docker build --platform linux/amd64 --tag "${REPOSITORY}:${IMAGE_TAG}" .
docker run --rm "${REPOSITORY}:${IMAGE_TAG}" mj4-sweep --help
```

Create the repository once, then log in, tag and push.

```console
aws ecr create-repository --region "${REGION}" --repository-name "${REPOSITORY}"
aws ecr get-login-password --region "${REGION}" | \
  docker login --username AWS --password-stdin "${REGISTRY}"
docker tag "${REPOSITORY}:${IMAGE_TAG}" "${IMAGE_URI}"
docker push "${IMAGE_URI}"
```

Use a version tag or a digest in jobs, not `latest`.
A mutable tag can resolve to a different image in each session.

## Submit the jobs

Submit each bundle from `containers/mujoco-4`, passing the image you pushed.
Always pass `DockerImage`. The tasks need your MuJoCo image, not the queue's default.

```console
cd containers/mujoco-4
deadline bundle submit plasticity_sweep --farm-id <farm-id> --queue-id <queue-id> \
  -p DockerImage=<account-id>.dkr.ecr.<region>.amazonaws.com/mujoco4-rocky9:4.0.0
deadline bundle submit speculative_sweep --farm-id <farm-id> --queue-id <queue-id> \
  -p DockerImage=<account-id>.dkr.ecr.<region>.amazonaws.com/mujoco4-rocky9:4.0.0
```

When a job finishes, download its output into the bundle's `output/` directory.

```console
deadline job download-output --farm-id <farm-id> --queue-id <queue-id> --job-id <job-id>
```

## What you get

Each task gets its own directory, named for its parameters.

```text
speculative_sweep/output/
├── angle58-dt8ms-specenable/
│   ├── frames/angle58-dt8ms-specenable-0000.png ... -0040.png
│   ├── clip.mp4
│   └── metrics.json
├── ... 19 more combinations
└── summary.csv
```

Both jobs take these parameters.

| Parameter | Default | Meaning |
|---|---|---|
| `DockerImage` | none | The image URI. The queue's Docker environment pulls and runs it |
| `Duration` | `2.0` | Simulated seconds per task, which is also the clip length |
| `Fps` | `20.0` | Rendered frames per simulated second. Rendering sets the cost |
| `VideoBitrate` | `2M` | Target bitrate for each MP4 |
| `OutputDir` | `./output` | Where the results go. Job attachments upload it |

Edit the task parameter ranges in each `template.yaml` to change a sweep.

### Plasticity: permanent twist against yield strain

An escapement wrench twists two bars to about 188 degrees, then slips off and lets go.
The blue bar is elastic and untwists to zero. The orange bar is elasto-plastic.
The `YieldStrain` task parameter sets its stretching yield strain, `mjModel.flex_yield`.
The scene's default is 0.025.

| `YieldStrain` | Peak twist | Final twist | Final plastic strain (L1) |
|---|---|---|---|
| 0.002 | 188.0° | 3.4° | 2.04 |
| 0.005 | 188.0° | 14.5° | 2.47 |
| 0.01 | 188.0° | 31.8° | 3.79 |
| 0.025 | 187.9° | 82.0° | 8.81 |
| 0.05 | 187.6° | 91.5° | 10.01 |
| 0.1 | 187.1° | 55.9° | 6.34 |
| 0.15 | 186.8° | 17.5° | 2.09 |
| 0.2 | 186.6° | 3.2° | 0.40 |

The elastic bar ends at 0.0° in every task.

The permanent twist peaks between 0.025 and 0.1 and falls off on both sides.
At a high yield strain the bar barely yields, so it springs back almost fully.
At a low yield strain it yields early on the way up, then yields again in reverse while it untwists.
That second yield undoes most of the first. The plastic state peaks near 15 at a yield strain of 0.002
and ends near 2.

### Speculative contacts: tunnelling against timestep

Plate 1 is pulled back and released into the other four.
Each plate is 3 mm thick, with a 17 mm gap between neighbouring faces.
A task reports `tunneled` when, at any step, a plate has passed its neighbour.
Travel per step is how far the swinging plate moves in one timestep at its fastest, the `travel_mm`
column of `summary.csv`.

| Release | Timestep | Travel per step | Speculative off | Speculative on |
|---|---|---|---|---|
| 30° | 2 ms | 3.1 mm | held | held |
| 30° | 4 ms | 6.3 mm | held | held |
| 30° | 6 ms | 9.4 mm | **tunnels** | held |
| 30° | 8 ms | 12.5 mm | **tunnels** | held |
| 30° | 12 ms | 18.8 mm | **tunnels** | **tunnels** |
| 58° | 2 ms | 6.0 mm | **tunnels** | held |
| 58° | 4 ms | 11.9 mm | **tunnels** | held |
| 58° | 6 ms | 17.9 mm | **tunnels** | held |
| 58° | 8 ms | 23.8 mm | **tunnels** | **tunnels** |
| 58° | 12 ms | 35.8 mm | **tunnels** | **tunnels** |

Without speculative contacts, 8 of 10 runs tunnel. With them, 3 of 10 tunnel.
The scene's defaults, 58° at 4 ms, tunnel at the first impact without the flag.

Every run that tunnels with the flag on travels more than the 17 mm gap in one step.
Speculative sweeps use the velocity at the start of the step. A stationary plate struck mid-step gets
its velocity only after the solver runs. In one step, the impact can then cross two gaps.
The [model's notes](https://github.com/google-deepmind/mujoco/blob/4.0.0/model/speculative/README.md)
give the remedy: pick a timestep at which one step's travel can't jump across two gaps.
The 58° run at 6 ms travels 17.9 mm, just over one gap, and holds.

Not every tunnel happens at the first impact, about 0.55 seconds in. These runs tunnel near 1.6
seconds, when the momentum returns through the row: 30° at 12 ms with the flag off and on, and 58° at 2 ms and
6 ms with the flag off. The `first_tunnel_s` column records when.

## How it works

The templates don't reference an image or call Docker.
Their commands are plain argv, like `mj4-sweep cradle --timestep-ms 8 --speculative enable`.

The queue's `DockerContainer` environment starts one container for each session.
It mounts the session directory at the same path inside the container.

The environment uses the `WRAP_ACTIONS` extension. Its `onWrapTaskRun` hook replaces each task's
`onRun` with a `docker container exec` of the same command and arguments.
`Summarize` runs `mj4-summarize` from the image. The bundles don't upload any scripts.
Containers run rootless, so files that the job writes belong to the job user on the worker.

The templates use the `EXPR` extension to build each task's label, such as `angle58-dt8ms-specenable`.
They also join paths with `/`, as in `Param.OutputDir / label`.

[`mujoco4-rocky9/README.md`](mujoco4-rocky9/README.md) describes how `mj4-sweep` applies each
parameter to the compiled model.

To learn more, see these pages:

- [Docker queue environment](https://docs.aws.amazon.com/deadline-cloud/latest/developerguide/containers-queue-environment.html)
  and [Share the session working directory](https://docs.aws.amazon.com/deadline-cloud/latest/developerguide/containers-share-session-directory.html)
  in the developer guide.
- [RFC 0008: Environment wrap actions](https://github.com/OpenJobDescription/openjd-specifications/blob/mainline/rfcs/0008-environment-wrap-actions.md)
  for the `WRAP_ACTIONS` syntax.
- [RFC 0005: Expression language](https://github.com/OpenJobDescription/openjd-specifications/blob/mainline/rfcs/0005-expression-language.md)
  for `EXPR`.
- [Speculative contacts](https://mujoco.readthedocs.io/en/latest/computation/speculative.html) in the
  MuJoCo documentation.

## Cost and cleanup

The tasks run in parallel. A spot fleet scales toward its maximum worker count.
On a fleet of up to four 16 vCPU spot workers, the plasticity job ran in about 2 minutes and the
speculative job in about 1.7 minutes from first task start. Each task takes about 5 seconds.
The first session on a worker also pulls the image, about 300 MB compressed in Amazon ECR.
Each run writes about 25 MB (plasticity) or 75 MB (speculative) to your job attachments bucket.

Delete image tags you no longer need from Amazon ECR. Job output stays in your job attachments bucket.

## Troubleshooting

| Symptom | Fix |
|---|---|
| `exec: "mj4-sweep": executable file not found in $PATH` | The task ran in the wrong image. Pass `-p DockerImage=...` with your MuJoCo 4 image |
| The environment fails with `could not pull` | Check the tag, and that the queue role can pull from Amazon ECR |
| Tasks stay `READY` | Associate the queue with a fleet that has the Docker software add-on |
| `plastic_bar has no plastic stretching state` | `--model` points at a scene whose bar has `yield="0"` in its MJCF. Plastic state is only allocated for a yield set above zero at compile time |
| You need logs | Session logs are in CloudWatch under `/aws/deadline/<farm-id>/<queue-id>` |

## Tested with

MuJoCo 4.0.0 on Rocky Linux 9, built for `linux/amd64`.
Both bundles ran end to end on a Linux service-managed spot fleet with 16 vCPUs per worker and the
Docker software add-on, using the console's default Docker queue environment. Every task succeeded on
its first attempt, and the results matched the tables above.
Deadline Cloud CLI 0.60.11 and Open Job Description CLI 0.8.0, in November 2026.

## Related resources

- [Run portable jobs in containers](https://docs.aws.amazon.com/deadline-cloud/latest/developerguide/containers.html)
  in the developer guide.
- [Security and best practices for containers](https://docs.aws.amazon.com/deadline-cloud/latest/developerguide/containers-security.html).
- [`model/plastic/`](https://github.com/google-deepmind/mujoco/tree/4.0.0/model/plastic) and
  [`model/speculative/`](https://github.com/google-deepmind/mujoco/tree/4.0.0/model/speculative)
  in the MuJoCo repository, which describe every 4.0 example scene.
