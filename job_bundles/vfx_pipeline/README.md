# A sample VFX pipeline on AWS Deadline Cloud

A working shot-render-and-publish pipeline for a studio moving renders to a
cloud farm. Every section starts from a piece of pipeline you already run and
shows the Deadline Cloud mechanism it becomes.

This sample targets a studio that:
- manages its own software and plugins
- defines its own workflows and render scripts
- keeps existing assets and software on a shared network drive
- has a pipeline/environment tool that sets up both workstation and render-farm
  environments
- wants service-managed fleets for simple management and autoscaling

Almost everything here is a placeholder you would swap for your own tooling:

- Blender as the render DCC, swappable for Maya, Nuke, Houdini, or anything
  else.
- `moonrise_scatter`, a Blender plugin (here a trivial Python add-on),
  standing in for your third-party or in-house plugins.
- `studio_pipe`, an environment manager that resolves a shot's context and
  sets up paths and environment variables (here a small Python script), standing
  in for ftrack, Kitsu, or your custom tools.
- `studio/`, a directory of config, assets, and renders, standing in for
  your shared network drive.
- The "shots" themselves are model-review turntables (the render script spins
  the subject a full rotation across the frame range), standing in for your
  shot animation. A turntable keeps the sample assets small.

Unlike the other samples in this repository, there is no first-party submitter.
The sample is for studios that already have render jobs defined and drive
submission to Deadline Cloud from their own launcher.

The DCC and plugins reach the farm as Conda packages, built from the recipes in
[`conda_recipes/`](conda_recipes/) and installed at run time by a Conda queue
environment. Conda is one implementation of a general pattern;
[Getting software onto the worker](#getting-software-onto-the-worker) describes
the pattern and where a different tool would slot in.

![Architecture diagram. On-prem, a studio holds an artist workstation running studio-pipe, shared storage, and an auto-downloader. In AWS, an S3 bucket holds job attachments and the studio's Conda channel, and a Deadline Cloud farm holds a queue and a fleet. The numbered flow in the diagram is listed below.](../../.images/vfx_pipeline_architecture.png)

The numbered flow in the diagram:

1. The workstation uploads the shot's `.blend` to S3 as a job attachment.
2. `studio-pipe submit` submits the job to the queue.
3. The queue schedules the job onto a worker in the fleet.
4. The worker pulls the shot and its Conda packages from S3. The Conda queue
   environment installs Blender and the add-on from the channel, then the step
   graph runs: render frames (one task per frame), then
   thumbnail and preview movie in parallel, then publish for review. The
   publish step pushes a Version to Autodesk Flow / ShotGrid.
5. The worker uploads finished outputs back to S3.
6. The on-prem auto-downloader pulls those outputs from S3 into shared storage.

The studio publishes its software to the Conda channel in S3 as a separate
build step, outside this flow.

## Key concepts

The Deadline Cloud and AWS terms this sample uses, one line each. Links go to the
docs.

- [Amazon S3](https://docs.aws.amazon.com/AmazonS3/latest/userguide/Welcome.html):
  AWS's cloud file storage. Files live in a named container called a bucket.
- [AWS Secrets Manager](https://docs.aws.amazon.com/secretsmanager/latest/userguide/intro.html):
  a managed store for secrets like API keys, used here to hold the Flow credential.
- [Farm](https://docs.aws.amazon.com/deadline-cloud/latest/userguide/manage-farms.html):
  a render environment holding your queues and fleets.
- [Queue](https://docs.aws.amazon.com/deadline-cloud/latest/userguide/manage-queues.html):
  accepts submitted jobs and hands them to a fleet to run.
- [Fleet](https://docs.aws.amazon.com/deadline-cloud/latest/userguide/manage-fleets.html):
  the pool of workers. A service-managed fleet is machines AWS starts and
  stops for you as work arrives and drains.
- [Job bundle](https://docs.aws.amazon.com/deadline-cloud/latest/userguide/create-job-bundle.html):
  a folder describing a job's parameters, steps, and the files it needs.
  Written in [Open Job Description](https://github.com/OpenJobDescription/openjd-specifications/wiki) (OpenJD).
- Step, task, and step graph: a step is one stage of a job (render, encode,
  publish). A step can fan out into many tasks (one render task per frame) run
  across the fleet. Steps chained by dependencies form the job's step graph.
- [preSubmission hook](https://docs.aws.amazon.com/deadline-cloud/latest/developerguide/provide-user-defined-parameters.html):
  a script in the bundle that the Deadline Cloud CLI runs on the artist's
  workstation at submit time (before the job reaches the farm), used here to fill
  the job's parameters from environment variables.
- [Queue environment](https://docs.aws.amazon.com/deadline-cloud/latest/userguide/create-queue-environment.html):
  setup that runs on the worker before a job's steps, used here to install the
  DCC and plugins.
- [Job attachments](https://docs.aws.amazon.com/deadline-cloud/latest/userguide/job-attachments.html):
  the mechanism that moves a job's input and output files between the studio and
  the worker through S3.
- [Conda channel and recipe](#getting-software-onto-the-worker):
  a channel is a location holding software packages and an index. A recipe is the
  build definition that turns your software into one of those packages.

## How your pipeline maps to Deadline Cloud

If you run a pipeline today, you already have most of these pieces under
different names. Here is the translation; the rest of this README is the long
form of each row.

| What you have today | What it becomes on Deadline Cloud | Where in this sample |
|---|---|---|
| A render manager/scheduler (Deadline 10, Tractor, Qube) | A farm: a queue that accepts jobs and a fleet of workers that run them | the architecture above |
| Always-on render nodes with software pre-installed | Service-managed fleet workers that boot from a base image with no studio software on it; the fleet scales workers out as tasks queue and back in when they drain | [The cloud-worker constraint](#the-cloud-worker-constraint) |
| A NAS every render node mounts | Software published to an S3 Conda channel and cached per worker host; shot assets uploaded as job attachments | [`studio/`](studio/), [Getting software onto the worker](#getting-software-onto-the-worker) |
| Your job/task graph (frames, then comp, then publish) | An Open Job Description step graph with per-step status, logs, and retries | [`job_bundle/`](job_bundle/blender_shot_render/) |
| Per-frame task distribution | A step that fans out into one task per frame, scheduled across the fleet | [Post-render work as separate steps](#post-render-work-as-separate-retryable-steps) |
| Your "set project" / context tool | The `studio_pipe` launcher, which resolves the config hierarchy and exports context as environment variables | [`studio_pipe`](studio_pipe/) |
| Your "submit to farm" button | `studio-pipe submit` plus a preSubmission hook that fills the job's parameters from context | [A static, parameterized bundle](#a-static-parameterized-bundle) |
| A plugin deploy/install step | Package the plugin as a Conda package alongside the DCC; the queue environment installs both and the render step enables it | [Delivering plugins](#delivering-plugins) |
| Publish to a tracker (ShotGrid/ftrack) | The `PublishToFlow` step, an isolated retryable step that reads credentials from Secrets Manager | [Credentials via Secrets Manager](#credentials-via-secrets-manager-and-the-queue-role) |
| A license server your farm reaches | Usage-based licensing, or bring-your-own license endpoints (fleet/queue setup) | [Bring your own licensed software](#bring-your-own-licensed-software) |
| Render nodes writing frames straight to the mounted show drive | A cloud worker can't see that drive, so outputs come back through `deadline queue sync-output`, the official auto-downloader | [Syncing renders back](#syncing-renders-back) |

## What happens on submit

An artist has a shot open, runs `studio-pipe submit`, and:

1. The launcher resolves the shot's context and exports it, including the Flow
   settings.
2. Still on the workstation, the bundle's preSubmission hook reads the `FLOW_*`
   environment variables to fill the job's parameters. The shot's `.blend` is
   declared as an input path
   parameter, so it uploads as a job attachment (see
   [A static, parameterized bundle](#a-static-parameterized-bundle)). The job
   carries only the Conda specs (`blender=4.2 moonrise_scatter=1.0.0`) and
   channels for the queue environment to install (see
   [Getting software onto the worker](#getting-software-onto-the-worker)).
3. On the farm, the Conda queue environment attached to the queue installs the
   software (Blender + the add-on) and puts `blender` on `PATH`. Then the job
   runs this step graph:

```
RenderShot          one task per frame
  ├─ GenerateMovie       encode the frames to H.264
  ├─ GenerateThumbnail   pull a poster frame
  └─ PublishToFlow       register the Version, upload media, advance the task
```

4. `studio-pipe autodownload --job-id ...` waits for the job, then runs Deadline
   Cloud's `deadline queue sync-output` to download the frames, movie, and
   thumbnail into `studio/renders/`.
5. The review Version appears in Flow, media attached, its Task advanced.

The farm distributes the per-frame `RenderShot` tasks across the fleet.
`GenerateMovie` and `GenerateThumbnail` depend only on `RenderShot`, so they run
in parallel; `PublishToFlow` waits for both because it uploads both.

## Components

```
studio/          the shared "drive": config, assets, renders
studio_pipe/     the launcher (resolve / launch / submit / autodownload)
job_bundle/      the static, parameterized Open Job Description render job
conda_recipes/   recipes for the studio's software (Blender + the add-on)
tools/           make_sample_assets.py (generates the sample .blend shots)
```

[`studio/`](studio/) stands in for shared storage, addressed through
`STUDIO_ROOT`. Shot settings live in a config hierarchy (studio → project →
sequence → shot) that the launcher merges into one resolved context per shot. It
is ordinary layered production config, here so the launcher has something
realistic to read.

[`studio_pipe`](studio_pipe/) is the launcher, the stand-in for a studio's "set
project" tooling. It resolves a shot's context and exports the resolved settings
as environment variables, whether it runs on an artist workstation or is filling
a farm job's parameters. The same codebase runs in both places: when submit-time
and render-time environments are built by two different scripts, they drift, and
eventually a shot renders differently on the farm than at the desk. Sharing one
resolver and one config keeps both places in agreement.

[`conda_recipes/`](conda_recipes/) holds the recipes that turn the studio's
software into Conda packages: the DCC ([`blender-4.2`](conda_recipes/blender-4.2/))
and the in-house add-on
([`moonrise_scatter-1.0.0`](conda_recipes/moonrise_scatter-1.0.0/)). You build them
with `rattler-build` and publish the channel to S3 with `aws s3 sync` (see the
[Walkthrough](#walkthrough)).

## How it works

Each section takes one row of the mapping table above and explains the mechanism
and the reasoning behind it.

### The cloud-worker constraint

A service-managed fleet worker boots from a base image, runs your job, and goes
away. It is not on your network, so it cannot see the NAS your artists mount, and
it starts bare, without Blender, its plugins, or any studio tools. A studio
running its own render nodes solves this by mounting the same filesystem
everywhere. On a cloud farm, everything a job needs (software,
plugins, scene files) has to be moved to the worker, and each section below is
about moving one of those things.

### Getting software onto the worker

The pattern is independent of the tool: copy your software artifacts to S3 as a
build step, then pull them onto the worker at run time from a queue environment.
A queue environment runs before a job's own actions, so whatever it installs is
present on `PATH` before the first render task. A studio's existing software
system plugs in here. Only the queue environment's setup script changes.

This sample uses Conda, a package manager Deadline Cloud has built-in support
for. Conda installs software from a channel: a location holding package files
and an index of what's in them. First you build a channel, then the worker
installs from it.

Build the studio's software into packages and upload them to a channel on S3.
[`rattler-build`](https://rattler.build/latest/) builds a package
from a recipe, then `aws s3 sync` copies it up:

```bash
rattler-build build --recipe conda_recipes/moonrise_scatter-1.0.0/recipe/recipe.yaml \
  --output-dir ./channel
aws s3 sync ./channel s3://<your-bucket>/Conda
```

Blender itself does not have to be built: it is already in the public
`deadline-cloud` channel, so in practice you build only your in-house packages
(here, `moonrise_scatter`). [`conda_channel/`](conda_channel/) is a committed
example channel so you can see what `aws s3 sync` uploads.

Then, at render time, the queue environment installs those packages onto the
worker before the job runs. Each job tells it what to install through two
parameters the launcher fills: `CondaPackages` (`blender=4.2
moonrise_scatter=1.0.0`) and `CondaChannels` (`deadline-cloud` plus your S3
channel).

The install is cached on each worker. The first job on a worker downloads and
installs the software; later jobs requesting the same software reuse that install
and start rendering in seconds. A large DCC is downloaded once per worker rather
than once per job, and each submission only has to carry the shot's `.blend` and
scripts.

### Delivering plugins

`moonrise_scatter` is a Conda package built from
[`conda_recipes/moonrise_scatter-1.0.0/`](conda_recipes/moonrise_scatter-1.0.0/).
Its recipe declares Blender as a runtime dependency, so installing the add-on
pulls in Blender too, and the package sets `BLENDER_USER_SCRIPTS` so Blender
discovers the add-on on startup. The render script then enables the add-on by
name and drives it headlessly, the way a studio tool runs on a farm. Delivering a
plugin is a recipe plus a channel publish, the same path as the DCC.

The add-on is purpose-built because this repository is MIT-0 licensed (MIT with
no attribution requirement) and nearly every real Blender add-on is GPL
(importing `bpy` makes a work a derivative of Blender), so vendoring one would be
a license conflict. To package a real third-party add-on, see
[Add real plugins](#add-real-plugins-including-third-party-ones).

### Passing shot context as environment variables

The launcher hands a shot's context to the processes it starts as environment
variables (`SHOT_FRAME_RANGE`, `SHOT_RESOLUTION_X`, `FLOW_PROJECT_ID`, and so
on), the interface a DCC launcher already speaks.

Environment variables carry shot context to a process, but the config owns it.
Take resolution. It looks like an environment setting, but it is a property
of the shot: it lives in the shot config, the launcher exports it as
`SHOT_RESOLUTION_X`, and the render script applies it to the scene. Reserve
environment variables that aren't backed by config for facts about the machine,
such as a scratch path or a mount point.

The submission path reuses the same variables. The "set project" step exports the
Flow context into the shell, and the bundle's preSubmission hook reads those same
`FLOW_*` variables to fill the job's parameters, so an artist with a shot open
submits without re-typing the project id or asset name.

### A static, parameterized bundle

The render job is an Open Job Description bundle in
[`job_bundle/blender_shot_render/`](job_bundle/blender_shot_render/). At submit
time the launcher fills the bundle's parameters from the resolved context and
submits the bundle as it sits on disk. It never generates or edits the template.
Because the bundle is static, you can read, diff, and
code-review it, and a reviewer sees exactly what a submission will run. Only the
parameter values vary between submissions.

The bundle declares the shot asset as an input file parameter. When you pass a
path to such a parameter, the Deadline Cloud client uploads that file as a job
attachment and rewrites the path so the job reads the copy on the worker. Because
the job refers to the file by parameter rather than by an absolute studio path,
it runs on a worker that cannot see the studio filesystem. Software reaches the
worker through
the `CondaPackages`/`CondaChannels` parameters instead (see
[Getting software onto the worker](#getting-software-onto-the-worker)); the
bundle has no software-staging step of its own, so it stays scoped to the render
work.

### Job attachments

Job attachments are how per-job files travel between the studio and the worker.
On submit, the client uploads the job's input files (here, the shot's `.blend`)
to S3. The worker downloads them before the job runs, and uploads the job's
outputs back to S3 when it finishes. This mechanism replaces the shared
filesystem an on-prem farm would use for the same files.

You configure the S3 bucket once on the queue. After that the client and worker
move files in and out for you. Because there is no shared filesystem to maintain,
job attachments scale to many concurrent jobs, and you pay only for the S3
storage and requests you use. Uploads are content-addressed: a file is stored
under a hash of its contents. Re-submitting an unchanged asset uploads nothing,
and two shots that reference the same texture or cache keep a single copy on S3.

Getting outputs back onto the studio drive is the [Syncing renders
back](#syncing-renders-back) step below.

### Post-render work as separate, retryable steps

`RenderShot` fans out into one task per frame. Each frame is a pure function of
its frame number (the subject's rotation is derived from it), so the tasks are
independent and reproducible. Modeling the encode, thumbnail, and publish as
separate steps gives each its own status and logs, its own retry (a Flow publish
that fails on a brief network blip is retried without re-rendering a frame), and
its own scheduling. The movie and thumbnail use Blender's bundled FFmpeg and image
writers, so the only software the job needs is Blender and its add-on.

### Credentials via Secrets Manager and the queue role

`PublishToFlow` needs an API credential, which it reads at run time from AWS
Secrets Manager using the worker's queue role (the AWS identity a queue's jobs
run as, carrying a set of permissions), granted permission to read that one
secret. The credential never appears in the repository, the submission output, or
the job's details in the Deadline Cloud console. Rotating it touches no job.

### Syncing renders back

On-prem, a render node writes frames straight to the mounted show drive, with no
"copy back" step. A service-managed fleet worker does not share a
filesystem with the studio, so in the default configuration finished frames come
back instead through Deadline Cloud's official auto-downloader,
`deadline queue sync-output`. It walks the queue for outputs finished since its
last run and restores them to the paths they were submitted from. Because
this sample submits each shot with its `OutputDir` set to
`studio/renders/<shot_id>`, those outputs land straight on the shared drive.

`studio-pipe autodownload` wraps that command. Given `--job-id` it first runs
`deadline job wait` so submitting and then fetching a shot is a single command,
then syncs. Without `--job-id` it syncs every newly finished output in the queue,
resuming where its last run left off; a studio runs this mode continuously, on a
schedule.

This sample submits and downloads on one machine, so outputs come back to the
same paths they were submitted from. If your artists download on a different
machine or operating system than they submit from, the paths won't line up and
`sync-output` needs to be told how to translate them; the
[automatic downloads](https://docs.aws.amazon.com/deadline-cloud/latest/userguide/auto-downloads.html)
guide covers that case.

## Walkthrough

### Prerequisites

- A Deadline Cloud farm and queue backed by a Linux service-managed fleet. New
  to Deadline Cloud entirely? Start with the
  [getting started guide](https://docs.aws.amazon.com/deadline-cloud/latest/userguide/getting-started.html),
  or stand up a farm from this repository's
  [CloudFormation](../../cloudformation/) or [Terraform](../../terraform/)
  templates.
- The Conda queue environment
  ([`conda_queue_env_improved_caching.yaml`](../../queue_environments/conda_queue_env_improved_caching.yaml))
  attached to the queue. The
  [queue environments README](../../queue_environments/README.md#create-a-queue-environment-for-your-queue)
  shows how to attach one, via the console or
  `aws deadline create-queue-environment`. If you created your queue in the
  console with the default Conda queue environment, that also works: it reads
  the same `CondaPackages`/`CondaChannels` parameters. The improved-caching
  variant makes repeat jobs on a warm worker start faster.
- The [Deadline Cloud CLI](https://github.com/aws-deadline/deadline-cloud) configured
  with a default farm and queue.
- [`rattler-build`](https://rattler.build/latest/) and the `aws`
  CLI for the build step.
- Python 3.9+ and Blender locally.
- For the publish step: a Flow site and a script credential in Secrets Manager
  (next section). No Flow site? Skip that section and submit with
  `FLOW_PUBLISH=FALSE`.

### Studio setup (once)

An administrator does this once, when standing the pipeline up: publish the
studio's software and store the Flow credential. Artists never repeat it.

Publish the studio's in-house software to a Conda channel on S3 the queue can
read. Blender comes from the public `deadline-cloud` channel, so you build only
`moonrise_scatter`. You can reuse the S3 bucket the queue already uses for job
attachments: the queue's permissions already cover paths under `Conda/` in that
bucket, so there is nothing to change in AWS access control. Find the bucket name
with `deadline queue get`.

```bash
cd job_bundles/vfx_pipeline
CHANNEL=s3://<queue-bucket>/Conda
rattler-build build --recipe conda_recipes/moonrise_scatter-1.0.0/recipe/recipe.yaml \
  --output-dir ./channel
aws s3 sync ./channel "$CHANNEL"
# Point software.conda_channels in studio/config/studio.yaml at $CHANNEL.
```

Rebuild only when the studio's software changes.

For the publish step, store the Flow script credentials in Secrets Manager and
grant the queue role read access, as in the upstream
[`blender_turntable_to_flow`](../blender_turntable_to_flow/README.md#flow-credentials-aws-secrets-manager-do-this-once)
sample. (Skip this if you are not publishing to Flow.)

### Artist workflow

An artist installs the launcher once:

```bash
cd job_bundles/vfx_pipeline
pip install ./studio_pipe
export STUDIO_ROOT=$(pwd)/studio
deadline config set settings.allow_bundle_hooks true   # let the CLI run the bundle's preSubmission hook
blender --background --python tools/make_sample_assets.py   # sample only: generate the demo shots
```

A "set project" step then puts the Flow context in the environment. The secret's
ARN (its full AWS resource identifier, shown when you create the secret) is a
stable studio-wide value, so a studio's tooling exports it for every artist; the
project id varies per show and can instead live in `project.yaml`. Variables
exported here win over the shot config's values.

```bash
export FLOW_SECRET_ARN=arn:aws:secretsmanager:us-west-2:<account>:secret:...  # studio-wide, set once
export FLOW_PROJECT_ID=1234          # per show; or set flow.project_id in project.yaml

studio-pipe resolve moonrise/seq010/sh010    # inspect the resolved shot context
studio-pipe launch  moonrise/seq010/sh010    # open the shot in Blender at the desk
studio-pipe submit  moonrise/seq010/sh010    # submit to the farm

# Render without publishing to Flow (no Flow setup needed):
FLOW_PUBLISH=FALSE studio-pipe submit moonrise/seq010/sh010

# Wait for the job, then download its outputs to studio/renders:
studio-pipe autodownload --job-id job-XXXX
```

`studio-pipe submit --dry-run <shot>` prints the resolved parameter values and
the `deadline bundle submit` command without submitting. Anything after `--` on
`submit` passes through to `deadline bundle submit`, such as
`-- --farm-id ... --queue-id ...`.

### Running the render stages without a farm

The render, encode, and thumbnail scripts run under Blender directly, which is how
to iterate before submitting. Point Blender at the add-on with
`BLENDER_USER_SCRIPTS` (the same variable its Conda package sets on the farm), so
`--addon-module` can enable it:

```bash
ASSET=studio/assets/moonrise/seq010/sh010/hero_vehicle.blend
OUT=/tmp/vfx_out; mkdir -p "$OUT/frames"
# Make the add-on discoverable from its source in the recipe.
SCRIPTS=/tmp/vfx_scripts; mkdir -p "$SCRIPTS/addons"
cp -r conda_recipes/moonrise_scatter-1.0.0/recipe/moonrise_scatter "$SCRIPTS/addons/"
export BLENDER_USER_SCRIPTS="$SCRIPTS"
B=blender   # or /Applications/Blender.app/Contents/MacOS/blender on macOS

"$B" --background "$ASSET" --python job_bundle/blender_shot_render/scripts/render_shot.py -- \
  --frame 1 --frame-range 1-4 --resolution-x 320 --resolution-y 180 --samples 8 \
  --output-prefix "$OUT/frames/sh010_" \
  --addon-module moonrise_scatter
```

## Next steps

Concrete extensions to take this from sample to production. Each points at the
file to change here or the Deadline Cloud docs to read.

### Bring your own licensed software

Blender needs no license server, so this sample has none. Real DCCs and
renderers (Maya, Nuke, Houdini, V-Ray, Arnold) check out floating licenses,
and a cloud worker has to reach a license server to get one. Deadline Cloud can
serve usage-based licensing for supported products, or route to your own license
endpoint. Start with the usage-based licensing overview
([manage-license-usage.html](https://docs.aws.amazon.com/deadline-cloud/latest/userguide/manage-license-usage.html)),
then bring your own licenses / license endpoints
([byol.html](https://docs.aws.amazon.com/deadline-cloud/latest/userguide/byol.html)).
The license configuration is fleet/queue setup and is independent of everything
in this bundle.

### Swap or add a DCC

The DCC is named in the config (`software.dcc`) as a Conda spec (`name`,
`version`). Point it at a new name/version whose package exists in a channel the
queue can reach. Many DCCs are already in the `deadline-cloud` channel; for
others, add a recipe under [`conda_recipes/`](conda_recipes/) and publish it with
`rattler-build` + `aws s3 sync` (see the [Walkthrough](#walkthrough)). Then rewrite
the render and encode invocations in
[`job_bundle/blender_shot_render/scripts/`](job_bundle/blender_shot_render/scripts/)
to drive the new application. For how other DCCs are packaged and invoked, read
the upstream conda recipes in [`../../conda_recipes`](../../conda_recipes) and the
sibling job bundles ([`../maya_cli_render`](../maya_cli_render),
[`../nuke_render`](../nuke_render),
[`../houdini_husk_usd_render`](../houdini_husk_usd_render)).

### Add real plugins, including third-party ones

Plugins are `plugins` entries under `software` in the config, each a Conda spec
with the add-on `module` to enable. The in-house add-on here is built from source
committed in its recipe
([`conda_recipes/moonrise_scatter-1.0.0/`](conda_recipes/moonrise_scatter-1.0.0/)).
A real third-party add-on gets its own recipe that installs the add-on into
`share/blender/scripts/addons/`. Either way you publish it to the channel with
`rattler-build` + `aws s3 sync` and the queue environment installs it. Adding a
plugin is a recipe plus a config entry, with no bundle change.

### Scale the fleet

This sample runs on a small service-managed fleet. Raise the fleet's maximum
worker count so more frames render in parallel, and pick worker instance types
that match the work, such as GPU instances for GPU rendering. See the fleet and
auto scaling topics in the
[Deadline Cloud User Guide](https://docs.aws.amazon.com/deadline-cloud/latest/userguide/)
(search for "service-managed fleets", "auto scaling", and "worker instance
types"). Fleet sizing is queue configuration and needs no change to the bundle.

### Integrate a different production tracker

Flow publishing is one isolated step, `PublishToFlow`, with its own status,
logs, and retry. To target ftrack, Kitsu, or an in-house tracker, replace
[`scripts/publish_to_flow.py`](job_bundle/blender_shot_render/scripts/publish_to_flow.py)
(and the step's `pip install` line) with a client for the new system. Keep the
Secrets-Manager-plus-queue-role pattern for credentials so nothing sensitive
lands in the bundle, its parameters, or the monitor.

### Harden for production

- Pin exact software and plugin versions in the config (`software.dcc.version`,
  `software.plugins[].version`) and build them as immutable channel packages so a
  render is reproducible and the queue environment's cache stays warm.
- Put the studio config and `studio_pipe` under version control so a submission's
  resolved context is auditable and reviewable.
- Split the fleets by cost profile: because the steps are independently
  schedulable, run the CPU-only encode and thumbnail steps on a cheaper CPU fleet
  and keep GPU renders on a GPU fleet.
