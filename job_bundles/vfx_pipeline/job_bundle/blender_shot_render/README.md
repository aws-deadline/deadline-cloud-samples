# `blender_shot_render`: the static render job bundle

The farm half of the sample VFX pipeline: a static, parameterized OpenJD job
bundle. It renders a shot's Blender asset into frames and encodes those frames
into a review movie with a matching thumbnail. A final step publishes the result
to Autodesk Flow Production Tracking.

It is normally submitted by the launcher (`studio-pipe submit <shot>`), which
fills the parameters from a shot's resolved context. Nothing in the bundle is
generated per submission. The launcher only supplies parameter values.

See the [pipeline README](../../README.md) for the whole architecture; this file
covers the bundle itself.

## The step graph

```
(Conda queue environment; before the job)   solve CondaPackages -> blender on PATH
RenderShot                (one task per frame)   open the .blend, render the frame
  ├─ GenerateMovie       (depends: RenderShot)   PNG sequence -> H.264 mp4
  ├─ GenerateThumbnail   (depends: RenderShot)   mid frame -> jpg
  └─ PublishToFlow       (depends: GenerateMovie, GenerateThumbnail)
```

Software is not a step in this bundle. The Conda queue environment attached to
the queue runs before the job and puts `blender` on `PATH`; `RenderShot` is
the job's first action.

`GenerateMovie` and `GenerateThumbnail` fan out in parallel; `PublishToFlow`
waits for both. Each is a first-class, independently retryable/observable step,
so a failed Flow publish can be retried without re-rendering a frame.

## Software via Conda

The job's software (Blender plus the in-house `moonrise_scatter` Blender add-on)
is delivered as Conda packages. The bundle names what it needs
(`CondaPackages`, `CondaChannels`) and
leaves the how to a Conda queue environment attached to the queue
([`queue_environments/conda_queue_env_improved_caching.yaml`](../../../../queue_environments/conda_queue_env_improved_caching.yaml)).
Before the job runs, that queue environment reads those two parameters, solves
the environment, caches it per worker host (persisted under `~/.conda` /
`~/.persisted_envs`), and puts `blender` on `PATH` for every step.

Blender comes from the public `deadline-cloud` channel; `moonrise_scatter`
comes from the studio's own Conda channel (an S3 prefix, built with
`rattler-build` and published with `aws s3 sync` from the recipes under
[`../../conda_recipes/`](../../conda_recipes/)). `moonrise_scatter`
is a `noarch` package that declares `requirements.run: blender` and sets
`BLENDER_USER_SCRIPTS`, so installing it into the env makes the add-on
discoverable by Blender, with no PATH plumbing in the job. The movie and thumbnail
are produced with Blender's bundled FFmpeg/image writers, so there is no
second tool to install.

The shot's `.blend` asset does travel as a job attachment (the `ShotAsset`
parameter) and is opened by `RenderShot`, the right tool for a small, per-shot
input that changes every submission.

## Parameters

The launcher supplies these from the resolved shot context:

| Parameter | Example | Source |
|-----------|---------|--------|
| `ShotId` | `moonrise_seq010_sh010` | context `shot_id` |
| `FrameRange` | `1-48` | `render.frame_range` |
| `ResolutionX` / `ResolutionY` | `1920` / `1080` | `render.resolution` |
| `Samples` | `96` | `render.samples` |
| `FrameRate` | `24` | `render.frame_rate` |
| `ShotAsset` | path to `hero_vehicle.blend` | context `asset` (job attachment) |
| `CondaPackages` | `blender=4.2 moonrise_scatter=1.0.0` | `software.dcc` + `software.plugins` |
| `CondaChannels` | `deadline-cloud s3://…/Conda` | `software.conda_channels` |
| `PluginModules` | `moonrise_scatter` | `software.plugins[].module` |

`CondaPackages` and `CondaChannels` are read by the Conda queue environment (not
by any step in this bundle); `PluginModules` is passed to `render_shot.py` as
`--addon-module` to enable each add-on inside Blender.

The `Flow*` parameters are `HIDDEN` and filled by the `preSubmission` hook
(`scripts/flow_params_from_env.py`) from the studio's `FLOW_*` environment
variables, the same variables the launcher exports. To submit without
publishing, set `FLOW_PUBLISH=FALSE`.

## Flow credentials

Identical to the upstream `blender_turntable_to_flow` sample: store
`{site_url, script_name, api_key}` in AWS Secrets Manager and grant the queue
role `secretsmanager:GetSecretValue` on that ARN. `PublishToFlow` reads it at
runtime. Full one-time setup is in the [pipeline README](../../README.md).

## Test it locally

Validate and inspect the template without a farm:

```bash
pip install openjd-cli
openjd check template.yaml
openjd summary template.yaml -p ShotId=test -p FrameRange=1-4 \
  -p ResolutionX=320 -p ResolutionY=180 -p Samples=8 -p FrameRate=24 \
  -p EnableFlowPublish=FALSE
```

The individual scripts also run directly under Blender (tested with Blender
4.2+), which is how to iterate on them before submitting. Because
`--addon-module` only enables an add-on that is already importable, the render
script needs `BLENDER_USER_SCRIPTS` pointed at the add-on first (the same
variable its Conda package sets on the farm). The pipeline README's
"[Running the render stages without a farm](../../README.md#running-the-render-stages-without-a-farm)"
section gives a copy-pasteable command that sets this up and renders a frame.

## Submit via the launcher

```bash
export STUDIO_ROOT=/path/to/job_bundles/vfx_pipeline/studio
studio-pipe submit moonrise/seq010/sh010 -- --farm-id farm-XXXX --queue-id queue-XXXX
```

(Everything after `--` is passed straight through to `deadline bundle submit`.)
