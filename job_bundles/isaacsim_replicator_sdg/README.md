# Isaac Sim Replicator Synthetic Data Generation

Domain-randomized synthetic perception data from
[NVIDIA Isaac Sim](https://developer.nvidia.com/isaac/sim)'s
[Replicator](https://docs.isaacsim.omniverse.nvidia.com/latest/replicator_tutorials/index.html),
fanned out across AWS Deadline Cloud workers:

```
 ┌──────────────────────────┐
 │      1. Generate         │        ┌──────────────┐
 │  ╭────────────────────╮  │        │  2. Merge    │
 │  │ shard 1  (seed S)  │  │        │  renumber    │
 │  │ shard 2  (seed S+1k)│ │ ─────▶ │  into one    │
 │  │   ...              │  │        │  dataset/    │
 │  │ shard N            │  │        │  + verify    │
 │  ╰────────────────────╯  │        └──────────────┘
 │     N PARALLEL TASKS     │
 └──────────────────────────┘
 └──────── shared OutputDir (job attachment) ────────┘
```

Each Generate task renders its own deterministically-seeded slice of the dataset
into its own directory. Merge renumbers every shard's frames into one flat
`sdg/dataset/` with a single global index, verifies that the frame count on disk
matches what was asked for, and **fails the job if the dataset came up short**.

It shares its container image with
[`containers/isaacsim-so101-workshop`](../../containers/isaacsim-so101-workshop).

## What makes it portable

The template contains **no Docker commands and names no container image**. It is
written for a queue with a
[Docker queue environment](https://docs.aws.amazon.com/deadline-cloud/latest/developerguide/containers-queue-environment.html)
on a service-managed fleet carrying the `docker` software add-on, which wraps each
task's `onRun` into the container for you.

The same template therefore also runs under `openjd run` on any host with Isaac
Sim installed, with no edits:

```bash
openjd run template.yaml --step "1 - Generate" \
    --tasks ShardIndex=1 \
    -p SdgFrames=4 -p SdgShards=1 -p OutputDir=/tmp/sdg
```

## Prerequisites

1. **A Linux x86_64 GPU service-managed fleet with the Docker add-on.**

   ```json
   "instanceCapabilities": {
     "osFamily": "linux",
     "cpuArchitectureType": "x86_64",
     "softwareAddOns": [{ "name": "docker" }],
     "rootEbsVolume": { "sizeGiB": 500 },
     "acceleratorCapabilities": {
       "selections": [{ "name": "a10g" }, { "name": "l4" }, { "name": "l40s" }],
       "count": { "min": 1, "max": 1 }
     }
   }
   ```

   **The accelerator selection is not arbitrary.** Isaac Sim's RTX renderer
   requires RT Cores, and NVIDIA
   [states](https://docs.isaacsim.omniverse.nvidia.com/latest/installation/requirements.html)
   that "GPUs without RT Cores (A100, H100) are not supported" — including in
   headless mode. Use g5, g6 or g6e class instances.

   Raise the root volume: the container image unpacks to roughly 29 GB.

   > **Do not attach the
   > [`docker_nvidia_container_toolkit`](../../host_configuration_scripts/docker_nvidia_container_toolkit/)
   > host configuration script to a fleet with the add-on.** That script is the
   > pre-feature manual path: it installs *rootful* Docker and adds `job-user` to
   > the `docker` group. The add-on installs *rootless* Docker and deliberately
   > does neither, and it configures the NVIDIA Container Toolkit itself. The two
   > conflict.

2. **A Docker queue environment on the queue**, with its `DockerImage` parameter
   pointing at your ECR image. The image pull runs under the **queue role**, so
   that role needs ECR read permission
   (`arn:aws:iam::aws:policy/AmazonEC2ContainerRegistryReadOnly` covers it).

   Keep the ECR repository in the **same account and region as the fleet**: the
   default queue environment derives the ECR region from the worker's own
   availability zone rather than from the image URI.

3. **Build the container image and push it to a registry you control.**

   ```bash
   cd ../../containers/isaacsim-so101-workshop
   docker build -t isaacsim-so101-workshop:2.3.2 .
   ```

   > **This bundle does not, and cannot, ship a working default image.** The built
   > image contains Omniverse Kit, which may not be redistributed, so there is no
   > public URI to point at. The base image `nvcr.io/nvidia/isaac-lab:2.3.2` is
   > anonymously pullable from NVIDIA, so building it yourself is a one-command
   > prerequisite rather than a licensing negotiation. Keep the built image
   > private.

4. **The Deadline Cloud CLI** configured (`deadline config show`).

## Submit

```bash
deadline bundle submit . \
    -p OutputDir=/path/to/output \
    -p SdgFrames=256 \
    -p SdgShards=4
```

## Parameters

| Parameter | Default | Notes |
|---|---|---|
| `SdgFrames` | `256` | Total frames across all shards. Split exactly; the first `SdgFrames % SdgShards` shards take one extra. |
| `SdgShards` | `4` | Parallel Generate tasks. Each pays its own Kit boot, so very narrow shards spend most of their time booting. |
| `SdgBaseSeed` | `30001` | Shard N uses `SdgBaseSeed + (N-1)*1000`. |
| `SceneSource` | `primitives` | `primitives` or `workshop`. See [Scenes](#scenes). |
| `SdgObjects` | `6` | Randomized foreground objects (primitives scene). |
| `Width` / `Height` | `640` / `480` | Render resolution. |
| `Renderer` | `RaytracedLighting` | `PathTracing` is available but much slower and unproven headless in NVIDIA's own docs. Treat as experimental. |
| `RtSubframes` | `8` | Render subframes per capture. NVIDIA documents a floor of 2 when randomized materials load late; higher removes ghosting at linear cost. |
| `AntiAliasing` | `3` | 0 off, 1 TAA, 2 FXAA, 3 DLSS, 4 RTXAA. |
| `Annotators` | `rgb,bounding_box_2d_tight,semantic_segmentation` | Comma-separated. See [Output](#output). |
| `StepTimeoutSeconds` | `1800` | Per-task wall clock. A cold worker spends two minutes or more on Kit boot before the first frame. |

## Scenes

**`primitives` (default)** builds the scene entirely from `rep.create.*`
primitives and lights — cubes, spheres, cylinders, cones and tori on a plane,
with randomized pose, scale, colour, lighting and camera orbit. It references no
NVIDIA-authored asset of any kind, which is what makes it publishable. It is also
the better teaching artifact: every randomizer is visible in
[`scripts/sdg_scene.py`](scripts/sdg_scene.py) in about thirty lines.

**`workshop`** is opt-in and loads the Apache-2.0 USD files that ship inside the
`isaacsim-so101-workshop` image: the SO-101 arm and the vial rack. It
deliberately skips `lightbox-simple.usd`, which carries a `payload` to NVIDIA's
`rsd455.usd` RealSense camera geometry on S3, and it rebinds materials to
randomized OmniPBR rather than inheriting the NVIDIA `vMaterials` MDLs that the
vial and robot normally use.

> If you build your own scene, remember that **SDG annotations come from semantic
> labels, not geometry**. A visually perfect stage with no
> `isaacsim.core.utils.semantics.add_labels()` pass produces zero bounding boxes
> and an empty segmentation mask, and the run still reports success.

## Output

`BasicWriter` writes **flat** into each shard's directory — there are no
per-annotator subdirectories:

```
sdg/
  sdg01/                                     <- one dir per shard, frames from 0
    rgb_0000.png
    semantic_segmentation_0000.png
    semantic_segmentation_labels_0000.json
    bounding_box_2d_tight_0000.npy
    bounding_box_2d_tight_labels_0000.json
    bounding_box_2d_tight_prim_paths_0000.json
  sdg02/
  sdg01.json                                 <- per-shard summary + timings
  sdg02.json
  dataset/                                   <- Merge output, globally renumbered
    rgb_000000.png ... rgb_000007.png
    ...
sdg_summary.json
logs/
  sdg01.log, _inner_exit_sdg01, _marker_sdg01_NNNN
```

Per-frame size with the default annotator set is roughly **0.2-0.45 MB at
640x480**. Adding `distance_to_camera` costs about 1.2 MiB/frame and `normals`
about 4.7 MiB/frame, so both are off by default.

### Reproducibility, stated honestly

The same seed reproduces the same **scene configuration**. It does not reproduce
bit-identical pixels: DLSS is temporal and accumulates history across subframes.
Set `AntiAliasing=0` if you need a tighter frame-to-frame comparison.

## Measured

8 frames across 2 shards, `g6.2xlarge` (L4), driver 580.178.04, **cold** — no
shader cache and no cached image:

| | |
|---|---|
| Container image pull (9 GB compressed) | ~150 s |
| Omniverse Kit boot, cold shader cache | 120-190 s |
| Capture, 640x480, `RtSubframes=8` | ~0.67 frames/s |
| Whole job, 2 shards + merge | ~500 s |

Kit boot dominates a small job, which is why narrow shards are poor value. A
warm Omniverse shader cache cuts that boot cost by roughly an order of magnitude
(separately measured at **35 s warm** against **347 s cold** for the same image),
so expect the boot line to fall sharply once a persistent volume is in play — see [Known limitations](#known-limitations).

Scaling: frames scale linearly and shards divide wall clock down to the fleet's
`maxWorkerCount`, though a service-managed fleet scales out from zero at
`scaleOutWorkersPerMinute` (default 10/min), so an 8-shard job realistically
reaches about 5x rather than 8x: the last shard starts minutes after the first. For 10k frames:
`SdgFrames=10000 SdgShards=20`, roughly 500 frames per shard and 2-5 GB of output.

## Known limitations

- **No COCO output yet.** The bounding boxes land as `.npy` plus a labels JSON
  per frame. Converting those to a single `instances.json` needs a numpy pass in
  the Merge step and is not implemented.
- **Measured numbers above are cold.** At the time of writing, combining the
  Docker add-on with `persistentVolumeConfiguration` on a fleet breaks container
  startup, so the shader cache cannot be used. The numbers will improve
  substantially when it can.
- **`PathTracing` is unverified headless.** NVIDIA's own path-tracing SDG example
  runs with `headless: False`.

## How it works

- **Not `AppLauncher`.** The script launches Isaac Sim through
  `isaacsim.SimulationApp` with an explicit `experience=`. All four Isaac Lab
  experience files set `exts."omni.replicator.core".Orchestrator.enabled = false`,
  which disables exactly the subsystem `rep.orchestrator.step()` drives. Isaac
  Sim's own `isaacsim.exp.base.python.kit` enables the full Replicator stack.
- **The experience path is passed explicitly** because a Docker queue environment
  starts the container with `--entrypoint /bin/sh`, so the image's entrypoint
  never runs and `EXP_PATH` is unset.
- **Isaac Sim is invoked through `python.sh`**, not the bare
  `kit/python/bin/python3`, which lacks the wrapper's `PYTHONPATH`.
- **Drain before detach.** `rep.orchestrator.wait_until_complete()` runs *before*
  `writer.detach()`. Detaching first discards queued writes and produces a run
  that captures frames, reports no error, and leaves an empty output directory.
- **Each shard asserts its own artifacts.** Isaac Sim's `python.sh` does not
  always propagate the Python exit code, so the Generate step counts `rgb_*.png`
  files on disk rather than trusting a return value or a self-reported frame
  count.
- **Dome light intensity is fixed, not randomized.** That attribute is typed
  `int` and Replicator hands the writer node a `TfPyObjWrapper` regardless of how
  the distribution is built, throwing on every frame while capture continues.
  Brightness variation comes from the Distant light instead.
