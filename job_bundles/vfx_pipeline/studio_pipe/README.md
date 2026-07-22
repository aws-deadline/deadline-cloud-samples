# `studio_pipe`: the pipeline launcher

`studio_pipe` is the single "context" layer of the sample pipeline. It is a
small, pip-installable Python package with one job:

> resolve a shot's context from the config hierarchy, then tell the right
> software, plugins, and assets to be present and set the environment, wherever
> it is running (artist workstation or farm worker).

It is the stand-in for the desktop launcher / "set project" tooling a studio
normally builds (ShotGrid Desktop, ftrack-connect, in-house apps).

## Install

```bash
pip install ./studio_pipe          # from job_bundles/vfx_pipeline
export STUDIO_ROOT=$(pwd)/studio   # point at the shared-drive mock
```

## Commands

| Command | Where | What it does |
|---------|-------|--------------|
| `studio-pipe resolve <shot>` | workstation | Print the merged context for `project/sequence/shot`. |
| `studio-pipe launch <shot>` | workstation | Export `SHOT_*`/`FLOW_*` and exec the DCC on the shot asset (the artist supplies their own Conda env with `blender` on `PATH`). |
| `studio-pipe submit <shot>` | workstation | Fill the static job bundle's parameters from context (incl. `CondaPackages`/`CondaChannels`/`PluginModules`) and submit. |
| `studio-pipe autodownload` | workstation | Download finished outputs to `studio/renders` via `deadline queue sync-output` (with `--job-id`, waits on that job first). |

A shot is addressed as `project/sequence/shot`, e.g. `moonrise/seq010/sh010`.

Software delivery is not a `studio-pipe` subcommand: Blender and the in-house
`moonrise_scatter` add-on are packaged as Conda packages built with `rattler-build`
and published to an S3-hosted Conda channel with `aws s3 sync` (from the recipes
under [`../conda_recipes/`](../conda_recipes/)). A Conda queue environment
attached to the queue reads the job's
`CondaPackages`/`CondaChannels` parameters, solves the env, caches it per worker
host, and puts `blender` on `PATH` before any render step runs.

## The module map

```
studio_pipe/
├── context.py      resolve(): deep-merge studio<project<sequence<shot -> ShotContext
├── software.py     context software.* -> CondaPackages / CondaChannels / PluginModules
├── launch.py       workstation: build env (SHOT_*/FLOW_*) + exec the DCC
├── submit.py       context -> static-bundle parameters -> `deadline bundle submit`
├── autodownload.py finished outputs -> `deadline queue sync-output` (+ optional `job wait`)
└── cli.py          argparse front end wiring the above into `studio-pipe`
```

The launcher resolves one config hierarchy into the context that drives both the
workstation DCC launch and the farm submission. Software itself is delivered out
of band by Conda: `software.py` turns the shot's `software.dcc` /
`software.plugins` / `software.conda_channels` into the `CondaPackages`,
`CondaChannels`, and `PluginModules` parameters, and the Conda queue environment
attached to the queue installs them on the worker before the render runs. See
the top-level pipeline README for the full architecture.

When `studio-pipe submit` runs, any `FLOW_*` variable already set in your shell
takes precedence over the value derived from the shot config. That is what makes
`export FLOW_PROJECT_ID=...` / `export FLOW_SECRET_ARN=...` (the walkthrough's
"set project" step) and the `FLOW_PUBLISH=FALSE studio-pipe submit ...` escape
hatch work.
