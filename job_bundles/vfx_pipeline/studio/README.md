# `studio/`: the shared network drive

This directory stands in for the shared storage a traditional VFX pipeline is
built around (a NAS/SAN mounted at, say, `/mnt/studio` or `S:\` on
every artist workstation and render node). In this sample it's just a folder.
Point the `STUDIO_ROOT` environment variable at it and every part of the
pipeline reads and writes here.

```
studio/
├── config/                  the project ▸ sequence ▸ shot config hierarchy (committed)
│   ├── studio.yaml          studio-wide defaults (software versions, render defaults, Flow site)
│   └── projects/
│       └── moonrise/
│           ├── project.yaml
│           └── sequences/
│               └── seq010/
│                   ├── sequence.yaml
│                   └── shots/
│                       ├── sh010/shot.yaml
│                       └── sh020/shot.yaml
├── assets/                  the .blend scene files (NOT committed; generated)
└── renders/                 finished renders, pulled back by the autodownloader (NOT committed)
```

Software does not live under `studio/`. Blender and the in-house
`moonrise_scatter` add-on are packaged as Conda packages: the recipes are in
[`../conda_recipes/`](../conda_recipes/), built with `rattler-build` and published
to an S3-hosted Conda channel with `aws s3 sync`. Workers pull them at run time
through the Conda queue environment.

## The config hierarchy

Configuration is layered, lowest precedence first:

```
studio.yaml  <  project.yaml  <  sequence.yaml  <  shot.yaml
```

The launcher (`studio_pipe`) walks this hierarchy for a shot and deep-merges the
layers into one resolved context. That single dictionary drives everything
downstream: the DCC launch on the workstation, the job parameters at submit time,
and the render on the worker. A value set in `shot.yaml` wins over the sequence,
which wins over the project, which wins over the studio default. Layering this
way lets a shot override "just the frame range" while inheriting the show's
resolution and the studio's Blender version.

Try it once the launcher is installed:

```bash
export STUDIO_ROOT=$(pwd)/studio
studio-pipe resolve moonrise/seq010/sh010
```

## Software delivery via Conda

The config hierarchy names the software the studio standardizes on
(`software.dcc`, `software.plugins`, `software.conda_channels`). The launcher
turns that into the render job's `CondaPackages` / `CondaChannels` parameters.
The actual packages come from Conda channels (Blender from the public
`deadline-cloud` channel and the in-house `moonrise_scatter` add-on from the
studio's S3-hosted channel, built with `rattler-build` and published with
`aws s3 sync`), and are installed on each worker by the Conda queue environment
attached to the queue. See the top-level pipeline README for why software is
delivered with a package manager rather than staged as archives on the shared
drive.

## Assets and renders

`assets/` holds the `.blend` scene files referenced by each shot's `asset:`
key. Generate the sample assets with:

```bash
blender --background --python ../tools/make_sample_assets.py
```

`renders/` is where the autodownloader (`studio-pipe autodownload`) deposits
finished frames, movies, and thumbnails pulled back from the farm, closing the
loop so artists see results on the same drive they submitted from.
