# Isaac Lab Newton RL sweep

Train a reinforcement learning policy with [Isaac Lab](https://isaac-sim.github.io/IsaacLab/) 3.0 on
the [Newton](https://github.com/newton-physics/newton) physics backend, sweeping PPO hyperparameters
in parallel across GPU workers, then rank every run and publish the best policy. One submitted job.

The whole pipeline runs **directly on an Amazon Linux 2023 service-managed fleet worker**: no
container image to build or host, and no conda package. Isaac Lab 3.0 made Isaac Sim optional, and
the Newton-only install fits inside the worker's glibc.

```
Step 1  TrainSweep                        Step 2  Aggregate
  parameterSpace: lr x entropy x seed       dependsOn: TrainSweep
  ┌──────────────────────────────┐
  │ lr=0.001  ent=0.001  seed=1  │ ─┐
  │ lr=0.001  ent=0.005  seed=1  │  │
  │ lr=0.0005 ent=0.001  seed=1  │  │  parallel        results.csv
  │ lr=0.0005 ent=0.005  seed=1  │  ├──  across  ──▶   report.html
  │ lr=0.0001 ent=0.001  seed=1  │  │  workers         best_policy/
  │ lr=0.0001 ent=0.005  seed=1  │ ─┘
  └──────────────────────────────┘
  └──────────── shared OutputDir (job attachment, INOUT) ────────────┘
```

## What this sample demonstrates

**A declared parameter space instead of a hand-rolled grid.** Six lines of `parameterSpace` produce
the task list, and the service schedules it:

```yaml
taskParameterDefinitions:
- name: LearningRate
  type: FLOAT
  range: [0.001, 0.0005, 0.0001]
- name: EntropyCoef
  type: FLOAT
  range: [0.001, 0.005]
- name: Seed
  type: INT
  range: "1-{{Param.SeedsPerConfig}}"
combination: "LearningRate * EntropyCoef * Seed"
```

The usual batch-array equivalent needs a grid-expansion script, a manifest uploaded to object storage,
index arithmetic inside the job to map an array index back to a combination, and a separate command
to collect results once everything finishes. Here the combinations are visible in the template, each
one is an independently retryable task, and `dependsOn` replaces the manual reduce.

How much of the sweep actually runs at once is a property of the fleet, not the job. On a fleet that
scales to one worker these six tasks run back to back; the scheduler spreads them as workers become
available, and nothing in the bundle changes either way.

**Per-step environments.** The training step builds the full Isaac Lab environment (~7.6 GB with CUDA
PyTorch). The aggregate step only reads TensorBoard event files, so it gets its own small environment
instead. Scoping with `stepEnvironments` rather than one job-wide environment keeps the reduce step
from installing a CUDA toolchain it never uses.

For a different shape of robotics workload, see
[MuJoCo sim-to-policy](../mujoco_sim_to_policy/), which generates data, finetunes an imitation-learning
policy, and renders the result as a linear three-step pipeline. This sample is the fan-out and reduce
counterpart, and it trains with reinforcement learning rather than imitation.

## Prerequisites

* A Deadline Cloud farm and queue with **job attachments configured**. The sample passes its scripts
  and requirements file in, and its results back out, through job attachments.
* A **Linux service-managed fleet with GPU workers**. The training step requires
  `amount.worker.gpu >= 1` and at least 16 GiB of memory. Verified on an NVIDIA A10G (driver
  580.178.04) and an L40S.
* Workers need **outbound internet access** to PyPI, GitHub (for the `uv` installer), and NVIDIA's
  public asset bucket.
* The [Deadline Cloud CLI](https://pypi.org/project/deadline/) to submit, and optionally
  [`openjd-cli`](https://pypi.org/project/openjd-cli/) to validate locally.

No GPU is needed on the machine you submit from.

## How it works

### The container-free install

Isaac Sim's own Python wheels are tagged `manylinux_2_35`, and Amazon Linux 2023 ships glibc 2.34.
glibc is the loader, so no amount of packaging works around that mismatch, and until Isaac Lab 3.0 a
container was the only option. Isaac Lab 3.0 moves Isaac Sim to an optional extra and defaults to
Newton, a Warp-native backend. Every package on that path resolves to a wheel needing glibc 2.34 or
older, so it installs directly on the worker.

Two details carry that:

* **`antlr4-python3-runtime` installs first, on its own.** It is the only package in the tree
  published as a source distribution, and the only one exempt from the wheels-only rule. It is pure
  Python, so it needs no toolchain, but it must precede the wheels-only pass: `hydra-core` requires
  `antlr4 ==4.9.*`, and without it that pass cannot satisfy `hydra-core`. Omitting it from
  `requirements-isaaclab3.txt` does not remove it from the dependency graph.
* **`--no-build` makes an incompatible pin fail at install time.** Without it the resolver walks
  backwards for anything installable: unpinned `hydra-core` resolves to 0.11.3, a 2019 release with
  no `hydra.core` module, and the job then fails at import time away from the cause.

`isaaclab` itself is installed with `--no-deps`, because its published metadata hard-depends on
`omniverseclient`, which is NVIDIA-proprietary and `manylinux_2_35` only. Everything else it declares
is already pinned in the requirements file.

### Assets, and why there is a shim

Excluding `omniverseclient` removes the only component that fetches remote assets, and Isaac Lab's
stock tasks do need assets: even cartpole loads a ground plane. Two pieces handle that.

`scripts/prefetch_assets.py` downloads them up front over plain HTTPS. Isaac Lab publishes its asset
root as an S3 URL in its own `apps/isaaclab.python.kit`, so an ordinary HTTP client gets the same
bytes. The script computes the **dependency closure** with `pxr.Sdf` rather than taking a fixed list,
which matters: `cartpole.usd` is a USD *crate* file that references `./Props/instanceable_meshes.usd`,
and neither `grep` nor `strings` reads a crate reliably. For the default task the closure is 5 files
and about 23 KB.

`scripts/omni_client_shim.py` stands in for `omni.client`. A lazily imported dependency looks like it
should only matter on the remote-asset path, but `retrieve_file_path` runs
`UsdUtils.ModifyAssetPaths` across every layer and calls an existence check on each reference to
decide whether to rewrite it, and that check imports `omni.client` for anything not present locally.
The default ground plane references `OmniPBR.mdl`, which ships inside Omniverse Kit, so a fully
prefetched scene still reaches it. The shim reports that nothing exists remotely, which leaves the
reference unrewritten: correct for a material binding in a headless run with no camera sensors,
because nothing evaluates it.

One consequence is load-bearing: **a missing asset fails** rather than being downloaded
mid-simulation, which keeps asset fetching an explicit and logged step.

### What this configuration cannot do

**Rendering.** The Newton renderer does not evaluate MDL materials, and RTX rendering needs Isaac
Lab's `ov` extra, which reinstates both the proprietary dependency and the glibc 2.35 floor, and with
it the container. This sample is for physics-driven RL: locomotion, manipulation from state
observations, control. A camera-conditioned policy that needs photorealistic renders is out of scope
here.

## Run or submit

```console
deadline bundle submit .
```

Useful variants:

```console
# A larger, statistically meaningful sweep: 6 combinations x 3 seeds = 18 tasks.
deadline bundle submit . -p SeedsPerConfig=3

# A fast smoke test. Finishes in a couple of minutes per task.
deadline bundle submit . -p MaxIterations=5 -p NumEnvs=16

# Rank on episode length instead of reward.
deadline bundle submit . -p RankMetric=Train/mean_episode_length
```

Validate the template and see the task list it expands to, without a farm:

```console
openjd check template.yaml
openjd summary template.yaml
openjd summary template.yaml -p SeedsPerConfig=3
```

At defaults `openjd summary` reports 7 tasks: 6 training tasks plus the aggregate.

## Parameters and outputs

| Parameter | Default | Purpose |
|---|---|---|
| `RequirementsFile` | `requirements-isaaclab3.txt` | Pinned environment. Edit to change Isaac Lab versions. |
| `ScriptsDir` | `scripts` | Prefetcher, shim, environment report, and aggregator. |
| `OutputDir` | `output` | All results. Flows back as a job attachment. |
| `Task` | `Isaac-Cartpole-Direct` | Gym id to train. See the note below before changing. |
| `NumEnvs` | `1024` | Parallel environments per run. The main throughput lever. |
| `MaxIterations` | `150` | PPO iterations per run. |
| `SeedsPerConfig` | `1` | Seeds per combination. Total tasks are 6 times this. |
| `AssetRoot` | NVIDIA's public asset URL | Where prefetched assets come from. |
| `RankMetric` | `Train/mean_reward` | TensorBoard tag used to rank runs. |

Outputs under `OutputDir`:

```
runs/lr0.0005_ent0.001_seed1/
    config.json                                  hyperparameters, written before training starts
    logs/rsl_rl/cartpole_direct/<ts>_run/
        events.out.tfevents.*                    TensorBoard scalars
        model_0.pt  model_50.pt  model_59.pt     checkpoints at save_interval
        params/agent.yaml  params/env.yaml       the fully resolved configuration
results.csv                                      one ranked row per run
report.html                                      the same table with a bar chart, self-contained
best_policy/
    model_*.pt                                   the winning run's checkpoints
    metadata.json                                the hyperparameters and metrics that won
```

`<ts>` is a timestamp: `--run_name` is a *suffix* that rsl_rl appends to the run's start time, so the
directory is named like `2026-10-22_16-20-20_run`. The aggregator walks the tree rather than assuming
the name.

A run that produces no metrics is reported as `no-metrics` and ranked last rather than failing the
aggregate step, so one diverged task does not cost you the other results.

A real run at `MaxIterations=60`, ranked by `Train/mean_reward`:

| rank | run | mean_reward | mean_episode_length | total_fps |
|---|---|---|---|---|
| 1 | `lr0.0005_ent0.001_seed1` | 4.9185 | 300.00 | 109,201 |
| 2 | `lr0.0001_ent0.001_seed1` | 4.8831 | 297.88 | 111,160 |
| 3 | `lr0.001_ent0.001_seed1` | 4.8766 | 297.59 | 112,809 |
| 4 | `lr0.0005_ent0.005_seed1` | 4.8664 | 297.41 | 110,762 |
| 5 | `lr0.0001_ent0.005_seed1` | 4.7902 | 292.49 | 110,124 |
| 6 | `lr0.001_ent0.005_seed1` | 4.6227 | 282.32 | 113,220 |

That spread is not a finding. Cartpole is solved well before 60 iterations, so episode length sits
at or near its 300-step cap and every configuration scores about the same; the gaps are within
single-seed noise. Raise `SeedsPerConfig` to separate a real difference from variance, or point
`Task` at a task that is not already solved.

### Changing the task

`Task` accepts any Isaac Lab gym id, but assets are prefetched explicitly rather than downloaded on
demand, so a different task usually needs different asset seeds. Submit once, read the path out of the
`FileNotFoundError`, and add it to `DEFAULT_SEEDS` in `scripts/prefetch_assets.py`. The script follows
dependencies from there on its own. Tasks whose scenes are built entirely from Isaac Lab's primitive
spawners need no assets at all.

Hyperparameter names are specific to the `rsl_rl` PPO configuration
(`agent.algorithm.learning_rate`, `agent.algorithm.entropy_coef`). Another RL library, selected with
`--rl_library`, exposes a different configuration tree.

## Security, cost, and cleanup

**Cost.** Six GPU tasks at defaults, roughly 5 to 10 minutes each depending on instance type, plus one
short aggregate task. Each task independently builds the environment and pays about 55 seconds of
Warp CUDA kernel compilation; see the note below on avoiding that. Raising `SeedsPerConfig` multiplies
GPU time linearly.

**A persistent volume removes most of the repeated setup.** Warp JIT-compiles its CUDA kernels on
first use, and the cache lives in the session directory here, so every task recompiles. On a fleet
with `persistentVolumeConfiguration`, point `WARP_CACHE_PATH` and the virtual environment at the
mount instead and both costs are paid once.

**Licensing.** Isaac Lab is BSD-3-Clause; Newton, Warp, and MuJoCo Warp are Apache-2.0. This sample
redistributes no NVIDIA software or assets: the requirements file names public packages that the
worker installs itself, and `prefetch_assets.py` downloads scene assets from NVIDIA's own public
bucket at runtime, which places you in the same position as using Isaac Lab anywhere else. Review
NVIDIA's terms for the assets and packages your task uses. If you switch to a configuration that
installs the `ov` extra or Isaac Sim, you are then installing NVIDIA-proprietary components and
their licenses apply.

**Cleanup.** Everything the job writes lands under `OutputDir` in job attachments. Delete the job and
its attachments when you are done. Nothing is created outside the farm.
