# Isaac Sim Replicator Synthetic Data Generation

Domain-randomized synthetic perception data from
[NVIDIA Isaac Sim](https://developer.nvidia.com/isaac/sim)'s
[Replicator](https://docs.isaacsim.omniverse.nvidia.com/latest/replicator_tutorials/index.html),
generated in parallel across AWS Deadline Cloud workers:

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
`sdg/dataset/` with one global frame index, verifies that the frame count on disk
matches what was asked for, and **fails the job if the dataset came up short**.

It shares its container image with
[`containers/isaacsim-so101-workshop`](../../containers/isaacsim-so101-workshop).

## What makes it portable

The template contains **no Docker commands and does not reference a container
image**. It is written for a queue with a
[Docker queue environment](https://docs.aws.amazon.com/deadline-cloud/latest/developerguide/containers-queue-environment.html)
on a service-managed fleet with the `docker` software add-on, which wraps each
task's `onRun` into the container for you.

The same template also runs under `openjd run` on any host with Isaac
Sim installed, with no edits:

```bash
openjd run template.yaml --step "1 - Generate" \
    --tasks ShardIndex=1 \
    -p SdgFrames=4 -p SdgShards=1 -p OutputDir=/tmp/sdg
```

## Prerequisites

**The fast path: deploy the farm, build the image, submit.**

```bash
# 1. A farm, queue, GPU fleet with the Docker add-on, and the Docker queue
#    environment, in one stack.
cd ../../cloudformation/farm_templates/isaacsim_farm
aws cloudformation deploy \
    --template-file deadline-cloud-isaacsim-farm-template.yaml \
    --stack-name deadline-cloud-isaacsim-farm \
    --capabilities CAPABILITY_NAMED_IAM \
    --parameter-overrides JobAttachmentsBucketName=YOUR_BUCKET

# 2. The container image, into your own Amazon ECR.
cd ../../../containers/isaacsim-replicator   # see its README for the NGC login
```

Read [the farm template's README](../../cloudformation/farm_templates/isaacsim_farm/README.md)
first for one thing that will otherwise stop you: **the default service quota
for GPUs on service-managed fleets is zero**, for both Spot and On-Demand. A new
account cannot start a GPU worker until an increase is approved, and approval is
not immediate.

If you would rather assemble it yourself, the requirements are:

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
   that "GPUs without RT Cores (A100, H100) are not supported", including in
   headless mode. Use g5, g6 or g6e class instances.

   Raise the root volume: the container image unpacks to roughly 29 GB, and
   Docker keeps images on the root volume regardless of any persistent storage.

   `aws deadline get-fleet` may report `softwareAddOns` as `null` even when it is
   set, because the AWS CLI's bundled botocore drops fields its model does not
   know. Confirm with a current boto3 rather than the CLI.

   > **Do not attach the
   > [`docker_nvidia_container_toolkit`](../../host_configuration_scripts/docker_nvidia_container_toolkit/)
   > host configuration script to a fleet with the add-on.** That script is the
   > pre-feature manual path: it installs *rootful* Docker and adds `job-user` to
   > the `docker` group. The add-on installs *rootless* Docker and deliberately
   > does neither, and it configures the NVIDIA Container Toolkit itself. The two
   > conflict.

2. **A [Docker queue environment](../../queue_environments/docker_queue_env.yaml)
   on the queue**, with its `DockerImage` parameter pointing at your ECR image.
   The image pull runs under the **queue role**, so that role needs ECR read
   permission (`AmazonEC2ContainerRegistryReadOnly` covers it; the farm template
   scopes it to one repository instead).

   The copy in this repository parses the ECR region from the registry host. The
   environment the console creates derives it from the worker's availability zone
   instead, so with that one the repository must live in the same Region as the
   fleet.

3. **A container image in a registry you control.** Build
   [`containers/isaacsim-replicator`](../../containers/isaacsim-replicator/) for
   the `primitives` and `usd` scene sources, which is a short Dockerfile over
   NVIDIA's NGC base image. `SceneSource=workshop` instead needs
   [`containers/isaacsim-so101-workshop`](../../containers/isaacsim-so101-workshop/),
   because it loads USD files that ship inside that image.

   > **This bundle does not, and cannot, provide a working default image.** The
   > built image contains Omniverse Kit, which may not be redistributed, so there
   > is no public URI to point at. The base image is pullable from NVIDIA with a
   > free NGC account, so building it yourself is a short prerequisite rather
   > than a licensing negotiation. Keep the built image private.

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
| `SdgFrames` | `256` | Total frames across all shards. Split exactly. The first `SdgFrames % SdgShards` shards take one extra. |
| `SdgShards` | `4` | Parallel Generate tasks. Each one repeats the Kit boot. A 4-frame shard spends most of its wall clock booting. |
| `SdgBaseSeed` | `30001` | Shard N uses `SdgBaseSeed + (N-1)*1000`. |
| `SceneSource` | `primitives` | `primitives`, `workshop`, or `usd`. See [Scenes](#scenes). |
| `SceneUsd` | _(empty)_ | Required when `SceneSource=usd`. Your stage, delivered by job attachments. See [Supplying your own stage](#supplying-your-own-stage). |
| `SceneUsdClass` | `asset` | Semantic class applied to `SceneUsd` when the stage declares none. Ignored when it does. |
| `SceneUsdSha256` | _(empty)_ | Optional. SHA-256 of the stage the submitter exported; Generate refuses to render anything else. Empty skips the check. |
| `SdgObjects` | `6` | Randomized foreground objects (primitives scene). |
| `Width` / `Height` | `640` / `480` | Render resolution. |
| `Renderer` | `RaytracedLighting` | `PathTracing` is available but much slower and unproven headless in NVIDIA's own docs. Treat as experimental. |
| `RtSubframes` | `8` | Render subframes per capture. NVIDIA documents a floor of 2 when randomized materials load late. Higher values remove ghosting at linear cost. |
| `AntiAliasing` | `3` | 0 off, 1 TAA, 2 FXAA, 3 DLSS, 4 RTXAA. |
| `Annotators` | `rgb,bounding_box_2d_tight,semantic_segmentation` | Comma-separated. See [Output](#output). |
| `StepTimeoutSeconds` | `1800` | Per-task wall clock. A cold worker spends two minutes or more on Kit boot before the first frame. |

## Scenes

**`primitives` (default)** builds the scene entirely from `rep.create.*`
primitives and lights: cubes, spheres, cylinders, cones and tori on a plane,
with randomized pose, scale, color, lighting and camera orbit. It references no
NVIDIA-authored asset of any kind, which is what makes it publishable. It is also
the clearer example: every randomizer is visible in
[`scripts/sdg_scene.py`](scripts/sdg_scene.py) in about thirty lines.

**`workshop`** is opt-in and loads the Apache-2.0 USD files included in the
`isaacsim-so101-workshop` image: the SO-101 arm and the vial rack. It
deliberately skips `lightbox-simple.usd`, which declares a `payload` arc
pointing at NVIDIA's `rsd455.usd` RealSense camera geometry on S3, and it rebinds
materials to randomized OmniPBR rather than inheriting the NVIDIA `vMaterials`
MDLs that the vial and robot normally use.

**`usd`** renders a stage you supply through `SceneUsd`, delivered by job
attachments. The stage is *referenced into* the Replicator scene rather than
opened as the stage, so this sample's camera orbit and lighting randomization
still apply and your stage keeps its own materials. Pose is randomized; nothing
is recolored, because it is your asset.

> **SDG annotations come from semantic labels, not geometry.** If you build your
> own scene, a visually perfect stage that never calls
> `isaacsim.core.utils.semantics.add_labels()` does not produce bounding boxes,
> leaves an empty segmentation mask, and still reports success.
>
> For `SceneSource=usd` the sample checks for you: a stage that already declares
> semantics keeps them, and one that does not is labelled with `SceneUsdClass`
> so the annotators emit something rather than nothing.

### Supplying your own stage

Every layer and texture the stage depends on has to arrive with it. Job
attachments uploads only what the submitter declared, so build
`asset_references.yaml` from the dependency closure rather than by hand:

```python
from pxr import UsdUtils
layers, assets, unresolved = UsdUtils.ComputeAllDependencies("scene.usda")
assert not unresolved, unresolved
```

#### Submit what is on screen, not what is on disk

They are not the same file. Unsaved edits sit in a dirty root layer, and Kit
routes much of its interaction into the **session layer**, which is never saved
with the stage at all — so even a saved stage can differ from the viewport.
Export a flattened snapshot of the composed stage instead of sending the path
the user opened:

```python
import omni.usd, hashlib, tempfile, pathlib

stage = omni.usd.get_context().get_stage()
snapshot = pathlib.Path(tempfile.mkdtemp()) / "scene.usda"
stage.Flatten().Export(str(snapshot))        # folds in unsaved + session edits

digest = hashlib.sha256(snapshot.read_bytes()).hexdigest()
# submit with SceneUsd=<snapshot>  SceneUsdSha256=<digest>
```

`Flatten()` captures both an unsaved attribute edit and a session-layer-only
transform, verified. Pass the digest as `SceneUsdSha256` and Generate recomputes
it on the worker, refusing to render anything else — so the job proves it
rendered your scene rather than assuming it.

> Do not try to detect staleness by reopening the file path. USD's layer cache
> returns the live, dirty layer for a path already open in the process, so the
> comparison silently succeeds. Check `layer.dirty`, or export to a fresh path.

The hash covers the stage description only. Textures, MDL and referenced layers
legitimately resolve to different paths on a worker, and anything under
`ISAACSIM_ASSET_ROOT` is meant to resolve locally rather than travel with the
job; missing dependencies are caught by the reference check below instead.

#### Two failure modes

Both are refused rather than rendered through:

* **A stage with dangling references opens, renders, and reports success.** The
  referencing prims exist locally whether or not their targets resolve, so a
  prim count passes and the dataset comes out empty. Job attachments makes this
  easy to hit because it relocates every file it uploads, so a reference
  authored relative to the wrong directory resolves on your workstation and
  dangles on the worker. The Generate step runs `ComputeAllDependencies` and
  exits with the missing paths named before the first frame.
* **`omniverse://` paths never resolve on a worker.** There is no Nucleus.
  Either localize those layers at submit time (`UsdUtils.LocalizeAsset` or
  `UsdUtils.CreateNewUsdzPackage`) or keep the assets under the image's
  configured `ISAACSIM_ASSET_ROOT` and reference them from there. That variable
  takes the highest precedence of Isaac Sim's five asset-root layers and accepts
  an HTTPS root or a local directory, so an asset pack unpacked onto a fleet
  persistent volume works without redistributing anything.

## Output

`BasicWriter` writes **flat** into each shard's directory, with no per-annotator
subdirectories:

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
640x480**. `distance_to_camera` adds about 1.2 MiB/frame and `normals` about
4.7 MiB/frame, so both are off by default.

### Reproducibility

The same seed reproduces the same **scene configuration**. It does not reproduce
bit-identical pixels: DLSS is temporal and accumulates history across subframes.
Set `AntiAliasing=0` if you need a tighter frame-to-frame comparison.

## Measured

8 frames across 2 shards, `g6.2xlarge` (L4), driver 580.178.04, **cold** (no
shader cache and no cached image):

| | |
|---|---|
| Container image pull (9 GB compressed) | ~150 s |
| Omniverse Kit boot, cold shader cache | 120-190 s |
| Capture, 640x480, `RtSubframes=8` | ~0.67 frames/s |
| Whole job, 2 shards + merge | ~500 s |

Kit boot dominates a small job. Narrow shards are poor value. A warm Omniverse
shader cache cuts that boot time by roughly an order of magnitude (separately
measured at **35 s warm** against **347 s cold** for the same image). Expect the
boot line to fall sharply once a persistent volume is available. See
[Known limitations](#known-limitations).

Scaling: frames scale linearly and shards divide wall clock down to the fleet's
`maxWorkerCount`, though a service-managed fleet scales out from zero at
`scaleOutWorkersPerMinute` (default 10/min), so an 8-shard job realistically
reaches about 5x rather than 8x: the last shard starts minutes after the first. For 10k frames:
`SdgFrames=10000 SdgShards=20`, roughly 500 frames per shard and 2-5 GB of output.

## Known limitations

- **No COCO output yet.** The bounding boxes are written as `.npy` plus a labels
  JSON per frame. Converting those to one `instances.json` needs a numpy pass in
  the Merge step and is not implemented.
- **Measured numbers above are cold.** At the time of writing, combining the
  Docker add-on with `persistentVolumeConfiguration` on a fleet breaks container
  startup, so the shader cache cannot be used. The boot line should fall toward
  the warm figure above once it can.
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
  that captures frames, does not report an error, and leaves an empty output
  directory.
- **Each shard asserts its own artifacts.** Isaac Sim's `python.sh` does not
  always propagate the Python exit code. The Generate step counts `rgb_*.png`
  files on disk rather than trusting a return value or a self-reported frame
  count.
- **Dome light intensity is fixed, not randomized.** That attribute is typed
  `int` and Replicator hands the writer node a `TfPyObjWrapper` regardless of how
  the distribution is built, throwing on every frame while capture continues.
  Brightness variation comes from the Distant light instead.
