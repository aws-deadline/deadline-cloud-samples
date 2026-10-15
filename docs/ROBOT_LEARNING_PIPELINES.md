# Robot learning pipelines

How this repository's robotics samples compose into a path from an untrained arm
to a policy that acts on its own, and which tool to reach for at each stage.

Each sample here runs on its own. This document covers what they add up to, and
the decisions that dominate the result: where your
action labels come from, and which appearance gap you are trying to close.

## The one decision that shapes everything

A policy learns from pairs of *observation* and *action*. Getting observations
is easy. Getting trustworthy actions is the whole problem, and there are only
three sources:

| Source of actions | What it costs | What you get |
|---|---|---|
| **Teleoperation** on the real robot | Human time, one episode at a time | Ground truth, correct embodiment, real appearance |
| **Simulation** | Authoring a scene and a scripted or learned controller | Ground truth for free, exactly correct physics, simulated appearance |
| **Inverse dynamics** on video | A model that covers your embodiment | Approximate actions from footage you did not act in |

Simulation is the cheapest source of *correct* actions, and it is the one most
teams skip because the appearance looks wrong. That is the right trade to make,
because appearance is the easier half to fix.

[MuJoCo sim-to-policy](../job_bundles/mujoco_sim_to_policy/) is this path end to
end. A scripted pick in simulation produces a LeRobot dataset, then an ACT policy
trains on it, and a rollout video shows the learned policy driving the sim. No
teleoperation, neither an inverse-dynamics model nor world-model post-training. If you
want one sample that takes an untrained arm to an autonomous one, that is it.

## Appearance gaps, which pull in opposite directions

Pipelines are easy to assemble in the wrong order here.

**The real-to-sim gap.** A policy trained on real camera images cannot drive a
simulator, because sim renders do not look real. `mujoco_sim_to_policy` closes
this by training on images from the same renderer the policy will run in. Train
and deploy share a renderer, so what the policy learns transfers.

**The sim-to-real gap.** The reverse, and the one standing between a sim-trained
policy and real hardware. A policy trained only on one renderer's output has
learned that renderer, not the task.

Generative video attacks the second gap, which is where
[Cosmos 3 dream trajectories](../job_bundles/cosmos3_dream_trajectories/) fits:
feed it a simulator frame and it produces photorealistic, varied video of the
same scene. Train on that variety and the policy stops depending on one
renderer.

The samples are not alternatives. Simulation supplies correct actions, and
generative video supplies the appearance variety that lets those actions
transfer.

## Which tool for which job

| Tool | It is | Use it for | Do not use it for |
|---|---|---|---|
| **MuJoCo** | A fast physics simulator | Scripted demonstrations, policy training, evaluation rollouts | Photorealism |
| **Isaac Sim** | A physics simulator with an RTX renderer | Labelled perception data (segmentation, bounding boxes, depth), domain randomization, contact-rich manipulation | Anything where authoring 3D assets costs more than the labels are value |
| **Cosmos 3** | A world foundation model rather than a simulator | Appearance and scene diversity; recovering actions from video for the embodiments it covers | Physics you intend to trust. Its model card states outputs "should not be treated as physically accurate simulation" |
| **GR00T** | A robot foundation policy (vision-language-action) | The thing all of the above trains | Data generation. GR00T-*Dreams* is the data pipeline and a different thing despite the name |

Isaac Sim samples for synthetic perception data and SO-101 sim-to-policy are in
flight at the time of writing and are not linked here yet.

## Where Cosmos 3 stops being able to help

Cosmos 3 generates video for any scene you condition it on. Its **inverse
dynamics**, which recovers actions from video and accepts only a fixed set of
embodiments, among them general camera motion, autonomous vehicle, egocentric motion,
single and dual Franka Panda, Agibot, UR, Google robot, WidowX 250, and UMI.

**SO-101 and SO-100 are not in that set**, and no parameter changes it. Running
inverse dynamics on SO-101 footage returns a trajectory in some other
embodiment's action space: plausible numbers that no SO-101 can execute, in a
file that looks like a dataset.

Taking your actions from simulation avoids that problem entirely. A
simulator already knows the joint commands it issued, so there is no
embodiment-coverage question, no approximation, and no second model to run.

If you do need actions from video for an SO-100 or SO-101 class arm, NVIDIA's
GR00T-Dreams publishes `seonghyeonye/IDM_so100` under Apache-2.0, ungated. It is
SO-100-trained, so treat it as a starting point for SO-101 rather than a
drop-in: the topology matches, the calibration does not.

## What belongs on Deadline Cloud, and what does not

Deadline Cloud has neither EFA nor cross-node NCCL, and neither placement groups nor gang
scheduling. That draws a sharp line:

| Stage | Fits? | Why |
|---|---|---|
| Generate demonstrations in simulation | **Yes** | Episodes are independent; one task per episode |
| Generate synthetic video | **Yes** | Clips are independent; one task per clip |
| Recover actions from video | **Yes** | Per-clip, embarrassingly parallel |
| Train a policy, single node | **Yes**, but without benefit | It runs; the fan-out buys nothing |
| Post-train a world model, multi node | **No** | Needs EFA and collectives. Use SageMaker training jobs, HyperPod, or Batch multi-node parallel |
| Evaluate a policy over many rollouts | **Yes** | The best fit of all: one rollout per task |

The pattern useful to remember: Deadline Cloud is for the stages where work
divides into independent tasks, and the number of those tasks is what you
actually want to scale. Training is the exception, and it is one step out of
five.

## A path for an SO-101

Ordered so that each stage is useful before the next exists.

1. **Get a policy working in simulation.**
   [MuJoCo sim-to-policy](../job_bundles/mujoco_sim_to_policy/) end to end. That path
   is the baseline, it runs without hardware, and it gives you a number to beat.
2. **Add appearance variety.** Render frames from the simulator, feed them to
   [Cosmos 3 dream trajectories](../job_bundles/cosmos3_dream_trajectories/) as
   conditioning images, and you get photorealistic video of the same scene. Use
   `ActionMode=none`: you already have correct actions from step 1, so there is
   nothing for inverse dynamics to recover.
3. **Retrain on the mixture** and compare evaluation rollouts against step 1. A
   policy that holds up across renderers is one with a chance on hardware.
4. **Add labelled perception data** from Isaac Sim if the task needs detection
   or segmentation rather than end-to-end control.
5. **Collect real teleoperation last**, and only as much as step 3 shows you
   need. Real demonstrations are the scarcest input, so spend them where
   synthetic data provably stops short rather than at the start.

Step 2 is the one that needs justifying with measurements rather than assumed,
and so step 3 compares against step 1 rather than replacing it.

## Costs useful to know before you plan

Verified SageMaker and EC2 on-demand rates, us-west-2, at the time of writing:

| Thing | Cost |
|---|---|
| Simulation data generation and policy training on a G-family GPU worker | Single-digit dollars for a sample-sized run |
| Cosmos 3 video generation | One GPU per clip for the length of the clip, plus a one-off ~35 GB weight download per worker |
| A persistent SageMaker endpoint hosting Cosmos 3 | A flat 1.25x the matching EC2 rate, with no idle discount |
| Post-training a 14B world model on NVIDIA's recipe, 4x ml.p5.48xlarge | **$253/hour**, so about $6,000 per day |

The last line is why this document recommends taking actions from simulation
rather than post-training a world model to produce them. Post-training buys
better *dynamics*, not better looks: image-to-video already preserves the
conditioning frame, so your scene appears correct without it. Simulation gives
you correct dynamics for free.

If you do want a post-trained world model, NVIDIA publishes checkpoints that are
already post-trained, `Cosmos-Predict2-14B-Sample-GR00T-Dreams-GR1` and
`-DROID`, so stage one is free. They are conditional on Hugging Face with
auto-approval, and they cover GR1 humanoid and Franka rather than SO-101.

## Licensing, briefly

Model licences differ by generation, and the differences are not cosmetic:

* **Cosmos 3** is [OpenMDW 1.1](https://openmdw.ai/license/1-1/): no
  field-of-use restriction, no commercial restriction, and it explicitly
  imposes nothing on outputs. Ungated.
* **Cosmos-Predict2 and 2.5** are under the
  [NVIDIA Open Model License](https://www.nvidia.com/en-us/agreements/enterprise-software/nvidia-open-model-license/):
  commercially usable, but with a "Built on NVIDIA Cosmos" attribution
  requirement in stated circumstances, and a grant that is revoked for
  circumventing the model's safety guardrails. Gated.
* **NVIDIA's published GR00T N1 and N1.5 checkpoints** are under a
  **non-commercial** licence. They are ungated and download without
  complaint, which makes this an easy mistake.
* **MuJoCo, LeRobot, and `seonghyeonye/IDM_so100`** are open and ungated.

Prefer the leftmost column of that list. A pipeline built on Cosmos 3 and
simulation has no attribution obligation and no gate.

## Related reading

* [Job bundles index](../job_bundles/) for every sample, robotics or otherwise.
* [Docker container queue environment](../queue_environments/docker_queue_env.yaml)
  for running containerised models with GPU access and a persistent weight
  cache.
* [AWS Deadline Cloud developer guide](https://docs.aws.amazon.com/deadline-cloud/latest/developerguide/index.html)
