# SimFoundry pick-and-place sweep

Sweep a Franka pick-and-place over method, scene and fruit in
[SimFoundry](https://github.com/NVlabs/SimFoundry)'s OmniGibson scenes. Each task tries to pick one
fruit and put it on a plate, records an MP4, and scores the attempt from object poses in
simulation. The two methods are a scripted planner and a pre-trained robot policy.

| Method | What drives the arm |
|---|---|
| `scripted` | OmniGibson's `StarterSemanticActionPrimitives`: `GRASP` on the fruit, then `PLACE_ON_TOP` on the plate. NVIDIA cuRobo plans each motion |
| `policy` | Physical Intelligence's π0.5 DROID joint-position checkpoint, served by [OpenPI](https://github.com/Physical-Intelligence/openpi) next to the simulator and given a language instruction such as `put the banana on the green plate`. Observations and actions follow SimFoundry's policy-eval stage |

The default sweep is 8 tasks: `Method` × `Scene` (`droid_desk_serve_fruits`, one of SimFoundry's
published DROID desks, and a scene you reconstructed) × `Target` (`banana`, `apple`).

## Results

One run of the 8 tasks, on NVIDIA L4 and A10G workers. A task succeeds when the fruit rose at least
5 cm and ends released, with its centre over the plate's footprint.

| Scene | Fruit | `scripted` | `policy` |
|---|---|---|---|
| `droid_desk_serve_fruits` | banana | success | success |
| `droid_desk_serve_fruits` | apple | fail: grasped, then no plan to the plate | success |
| reconstructed `Fruits.mp4` | banana | success | fail: never grasped |
| reconstructed `Fruits.mp4` | apple | success | fail: never grasped |

The policy is zero-shot. It works on the published desk, which SimFoundry built to look like the
DROID setup it was trained on, and not in the reconstructed scene, which has no desk or background.
In two more runs on the published desk, it placed the banana both times and the apple once. Both
methods use assisted grasping, which attaches the fruit once the fingers close on it, so these rates
are higher than with physical grasping.

## Files

| Path | Contents |
|---|---|
| [`Dockerfile`](Dockerfile) | Builds on the [`full_pipeline`](../full_pipeline/) image. Adds cuRobo and `openpi-client` to the `simfoundry` env, and OpenPI in its own uv environment |
| [`job_bundle/template.yaml`](job_bundle/template.yaml) | The job: one step, one task per method, scene and fruit |
| [`job_bundle/scripts/pick_place.py`](job_bundle/scripts/pick_place.py) | Runs one attempt and writes `rollout.mp4` and `result.json` |
| [`job_bundle/scripts/policy_server.sh`](job_bundle/scripts/policy_server.sh) | Starts the OpenPI server once per session and compiles its first inference |
| [`job_bundle/scripts/warmup_policy.py`](job_bundle/scripts/warmup_policy.py) | The warm-up inference |

## Prerequisites

Everything in the [sample's prerequisites](../README.md#prerequisites), including a GPU fleet with
the `grid:r580` runtime and the Docker queue environment, and also:

- **Fleet workers with at least 120,000 MiB of memory and a 24 GB GPU.** The policy server takes
  45% of the GPU's memory, and Isaac Sim and cuRobo share the rest.
- **A reconstructed scene**, such as the `output/fruits` directory the
  [`full_pipeline`](../full_pipeline/) job writes. The job reads its
  `s14_og/reconstructed_og_scene.json` and the object assets in `s13_usd/objects`.
- **Internet access from the workers.** The job downloads the published scenes from Hugging Face and
  the 12 GB policy checkpoint from OpenPI's public Google Cloud Storage bucket.

## Build and submit

Build the [`full_pipeline`](../full_pipeline/) image first, then this one from
`containers/simfoundry/pick_place_sweep`, and push it as the
[sample README](../README.md#build-and-push-the-image) describes. The build compiles cuRobo's CUDA
kernels for `8.6;8.9`, which takes about 8 minutes, and needs no GPU.

```console
docker build --tag simfoundry:9e34ebe-rocky10-pick .
```

```console
deadline bundle submit job_bundle --farm-id <farm-id> --queue-id <queue-id> \
  -p DockerImage=<account-id>.dkr.ecr.<region>.amazonaws.com/simfoundry:9e34ebe-rocky10-pick \
  -p ReconstructedScene=<path-to-full-pipeline-output>/fruits
```

| Parameter | Default | Meaning |
|---|---|---|
| `ReconstructedScene` | none | The reconstructed scene's directory. Job attachments upload it, about 50 MB for `Fruits.mp4` |
| `ReconstructedRobotPosition` | `-0.6,-0.05,0` | Where the robot stands in the reconstructed scene. Stage 14 puts it 1 m behind the scene origin, out of reach of most objects |
| `PlateName` | `teal` | Part of the plate's category name |
| `PlateWord` | `green plate` | What the instruction calls the plate |
| `PolicyConfig` | `pi05_droid_jointpos_polaris` | The OpenPI config to serve |
| `PolicyCheckpoint` | `gs://openpi-assets/checkpoints/pi05_droid_jointpos` | The checkpoint, trained on DROID with joint-position actions |
| `EpisodeSeconds` | `60` | Simulated time the policy gets, at 15 actions a second |

To change the sweep, edit the `Method`, `Scene` and `Target` ranges in the template. A `Scene` is
`reconstructed` or the name of a scene under `assets/scenes/DROID/` in the
[`simfoundry-assets`](https://huggingface.co/datasets/nadunRanawaka1/simfoundry-assets) dataset.

## What you get

`output/<method>_<scene>_<fruit>/` per task:

- `rollout.mp4`: a camera beside the robot, DROID's first exterior camera and the wrist camera.
- `result.json`: `success`, `lifted` and `max_lift_m`, and under `placement` the fruit's final
  position against the plate's bounding box. For `scripted`, each primitive's outcome and error.
  For `policy`, the steps, the inference count and time, and the gripper commands.
- `scene.json`: the scene file the attempt loaded.

`placement.og_ontop_predicate` is OmniGibson's own `OnTop` check. It is often false for a fruit
resting inside the teal tray's rim, so `success` doesn't use it.

## How it works

`StarterSemanticActionPrimitives` supports robots with a mobile base and a trunk. `pick_place.py`
subclasses it for a desk-mounted arm: planning uses the arm joints only, and a target out of reach
fails rather than navigating. Three more changes:

- The grasp puts the fingertips at a quarter of the fruit's height and closes them across its short
  side. Upstream aims the hand at the top of the fruit's box, which the Panda's short fingers miss,
  and gets a NaN pose for the Franka-Robotiq, whose finger lengths it leaves empty.
- cuRobo ignores the desk's background mesh, which the robot is mounted in. The floor plane at desk
  height stands in for the desk top.
- The final approach ignores the fruit in the planner, because the open fingers straddle it inside
  cuRobo's collision margin.

For `policy`, the first task in a session starts the OpenPI server in the session container and
sends it one inference, so its model compiles before the rollout. The rollout follows SimFoundry's
`1_eval_policy_og_scene.py`: the same three cameras, absolute joint-position control, and the
gripper action inverted and binarised. It reports the gripper's position as DROID does, 0 open and
1 closed, for either gripper.

## Troubleshooting

| Symptom | Fix |
|---|---|
| `Policy server exited before it was ready` | The lines after it are the server's log. A download error means the worker can't reach `storage.googleapis.com` |
| `Target out of reach of the fixed-base arm` | The fruit is too far from the robot. For the reconstructed scene, change `ReconstructedRobotPosition` |
| `There is no accessible path` | cuRobo found no collision-free motion in its attempts. The task still records the attempt |
| `'<name>' matches [] in the scene` | No object's category contains `Target` or `PlateName` |
| `CUDA out of memory` in the policy server | Use a GPU with at least 24 GB, or lower `XLA_PYTHON_CLIENT_MEM_FRACTION` in `policy_server.sh` |

## Cost and cleanup

The 8 tasks took 17 minutes on four workers that already held the image. From cold, a worker takes
about 20 minutes to start and pull the image before its first task.
A `scripted` task takes 7 to 9 minutes, most of it starting Isaac Sim and planning. The first
`policy` task in a session spends about 2.5 minutes downloading and compiling the policy. Each
later one takes 1.5 to 3 minutes. The output is about 25 MB.

The image is about 9 GB larger than the `full_pipeline` image. Delete tags you no longer need.

## Licences

The cuRobo commit OmniGibson pins, from StanfordVL's fork, is under the NVIDIA License, which allows
non-commercial use only: research or evaluation. OpenPI's code is Apache 2.0, and its π0.5 weights
are under the Gemma Terms of Use. See the [image README](../simfoundry-rocky10/README.md#licences)
for the rest of the image.
