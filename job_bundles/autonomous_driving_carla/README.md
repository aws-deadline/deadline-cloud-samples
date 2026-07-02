# Autonomous Driving Simulation Using CARLA

## Introduction

This job bundle runs a [CARLA](https://carla.org/) autonomous driving simulation parameter sweep
on AWS Deadline Cloud with configurable multi-sensor capture. It demonstrates how to use
Deadline Cloud to orchestrate GPU-accelerated simulation workloads with Docker containers.

The job runs a lane-change cut-in scenario where an NPC vehicle starts behind the ego vehicle,
accelerates to position itself 20 meters ahead of the ego during a 105-second get-ahead phase,
then cuts into the ego's lane. It sweeps across configurable ego speeds, NPC speeds, and NPC
starting distances, creating a task for each parameter combination (default 2×2×2 = 8 tasks).
Each task captures multi-sensor data from user-selected camera viewpoints and produces per-camera
videos plus a stitched grid video.

**Output per task:**
- RGB frames from each selected camera viewpoint
- Semantic segmentation frames
- LiDAR point clouds (.ply)
- 2D and 3D bounding boxes (KITTI format)
- Per-camera scenario videos (H.264 MP4)
- Stitched grid video (if multiple cameras selected)

## Prerequisites

1. An [AWS account](https://aws.amazon.com/resources/create-account/) with access to GPU instances (g6.4xlarge recommended).
2. A Deadline Cloud farm with:
   - A queue with a Conda queue environment (channels: `conda-forge`, packages: `ffmpeg`)
   - A GPU fleet (minimum: 1 NVIDIA GPU, 16 vCPU, 64 GiB memory)
3. [Docker](https://docs.docker.com/get-docker/) installed locally for building the CARLA image.
4. An [Amazon ECR](https://aws.amazon.com/ecr/) repository in your account to host the built image.
5. The [Deadline Cloud CLI](https://github.com/aws-deadline/deadline-cloud) installed locally.

### IAM Permissions

Your queue role needs ECR pull permissions (the task script runs `docker pull` under queue role credentials). Attach a policy like:

    {
      "Effect": "Allow",
      "Action": [
        "ecr:GetDownloadUrlForLayer",
        "ecr:BatchGetImage",
        "ecr:BatchCheckLayerAvailability"
      ],
      "Resource": "arn:aws:ecr:<REGION>:<ACCOUNT_ID>:repository/*"
    },
    {
      "Effect": "Allow",
      "Action": "ecr:GetAuthorizationToken",
      "Resource": "*"
    }

### Fleet Host Configuration

Your fleet workers need Docker and the NVIDIA Container Toolkit. Attach the
[docker_nvidia_container_toolkit](../../host_configuration_scripts/docker_nvidia_container_toolkit)
host configuration script to your fleet. See its
[README](../../host_configuration_scripts/docker_nvidia_container_toolkit/README.md) for details.

## Building the Docker Image

The job runs inside a Docker container based on [`carlasim/carla:0.9.16`](https://hub.docker.com/r/carlasim/carla).
The base CARLA image ships the simulator but lacks the Python environment, scenario runner,
and sensor capture scripts needed for this job. The custom image layers on Python 3.10,
`scenario_runner`, and the entrypoint/capture scripts so each Deadline Cloud task can
boot CARLA, execute the driving scenario, and record sensor data in a single container.

1. **Create an ECR repository** (if you don't have one):

       aws ecr create-repository --repository-name carla-deadline --region <REGION>

2. **Build the image:**

       cd docker/
       docker build -t carla-deadline:0.9.16 .

   > **Note:** The Dockerfile pulls `carlasim/carla:0.9.16` from Docker Hub as the base image.
   > The first build will download ~8 GB.

3. **Push to ECR:**

       aws ecr get-login-password --region <REGION> | \
         docker login --username AWS --password-stdin <ACCOUNT_ID>.dkr.ecr.<REGION>.amazonaws.com

       docker tag carla-deadline:0.9.16 \
         <ACCOUNT_ID>.dkr.ecr.<REGION>.amazonaws.com/carla-deadline:0.9.16

       docker push <ACCOUNT_ID>.dkr.ecr.<REGION>.amazonaws.com/carla-deadline:0.9.16

## Submit the Job

From the bundle directory:

    cd autonomous_driving_carla
    deadline bundle gui-submit .

In the **Job-specific settings** tab:

1. **Scenario Settings** — Configure ego speeds, NPC speeds, and NPC distances (comma-separated integers). The cross-product creates your task grid.
2. **Camera Viewpoints** — Select which cameras to capture (Front is enabled by default). Available positions: Front, Front Left, Front Right, Rear, Rear Left, Rear Right.
3. **Advanced** — Set your Container Image URI to `<ACCOUNT_ID>.dkr.ecr.<REGION>.amazonaws.com/carla-deadline:0.9.16` and the AWS Region where your ECR lives.

Alternatively, submit via CLI:

    deadline bundle submit . \
      --farm-id <FARM_ID> \
      --queue-id <QUEUE_ID> \
      --name "CARLA Lane Change Demo" \
      -p ImageURI=<ACCOUNT_ID>.dkr.ecr.<REGION>.amazonaws.com/carla-deadline:0.9.16 \
      -p AwsRegion=<REGION>

## Monitor the Job

Monitor progress in the Deadline Cloud console. Each task shows its parameter values
(EgoSpeed, NpcSpeed, NpcDistance) in the task table. Tasks typically complete in ~13 minutes each.

The log output shows:
- Scenario generation and parameter values
- CARLA server boot and readiness
- Sensor capture progress (frame count per camera)
- Video encoding for each camera
- Grid video stitching (if multiple cameras)

## Output Structure

Each task produces output in a subdirectory named for its parameters:

    outputs/
    └── ego20_npc30_dist10/
        ├── rgb/
        │   ├── front/frame_000001.png ... frame_000062.png
        │   └── rear/frame_000001.png ... frame_000062.png
        ├── semantic/
        │   ├── front/...
        │   └── rear/...
        ├── lidar/frame_000001.ply ...
        ├── bbox_2d/{front,rear}/frame_*.txt
        ├── bbox_3d/frame_*.txt
        └── video/
            ├── front_scenario.mp4
            ├── rear_scenario.mp4
            └── grid_scenario.mp4

## Docker Image Contents

The `docker/` directory contains the files needed to build the image:

| File | Purpose |
|------|---------|
| `Dockerfile` | Builds the CARLA + scenario_runner + multi-sensor capture image |
| `entrypoint.sh` | Container entrypoint: boots CARLA, runs scenario, captures sensors |
| `capture_sensors.py` | Multi-sensor capture with configurable camera selection via `CAMERAS` env var |

## Known Limitations

- **Linux only**: The CARLA Docker image requires a Linux host with NVIDIA GPU drivers. Workers must run on Linux fleets.
- **x86_64 only**: The CARLA Docker image does not support ARM architectures.
- **Mosaic images**: RGB/semantic mosaic images are generated when 2 or more cameras are selected. The layout is 2×3 when all 6 are active, or a smaller grid otherwise.
- **Capture rate scales with camera count**: The capture script writes PNGs synchronously per flush. Each flush writes one RGB and one semantic-segmentation frame per selected camera, plus an RGB mosaic and a semantic mosaic whenever 2+ cameras are enabled. With all 6 cameras that's 14 PNG writes per frame set vs 2 with a single camera, and the increased I/O slows flushes well below the 7 FPS target. The video encoder is fixed at 7 FPS, so the same 7-minute scenario produces a longer per-camera video with few cameras enabled and a shorter, denser multi-view video with many cameras enabled. This synchronous design is a deliberate tradeoff to keep this proof-of-concept sample's architecture small and easy to adapt — a production pipeline would parallelize sensor I/O.
