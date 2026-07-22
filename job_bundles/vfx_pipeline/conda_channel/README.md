# conda_channel: example Conda channel

This directory is a small, committed Conda channel, checked into the repo
so you can browse on GitHub what a conda channel actually is: a directory of
package files plus an index. Nothing here needs to be built to be inspected.

It belongs to the `vfx_pipeline` sample, which delivers DCC software (and the
in-house Blender add-on below) to render workers as conda packages pulled by a
Conda queue environment. In production a studio publishes a channel like this
one to S3 and points the render job's `CondaChannels` parameter at it; this
committed copy is a local stand-in for that S3-hosted channel.

## What's in a channel

A channel is organized into per-platform subdirs. `noarch/` holds
platform-independent packages (pure-Python add-ons like this one); native
software (e.g. a compiled Blender build) lives in `linux-64/`, `win-64/`,
`osx-64/`, or `osx-arm64/`. Each subdir has its own `repodata.json`, the
index a conda client reads to solve an environment. It lists every package
in the subdir with its name, version, build string, dependencies (`depends`),
sha256, and size.

This channel currently holds one package, `moonrise_scatter`, the sample's
in-house Blender add-on (a `noarch: generic` package that declares
`requirements.run: blender`). The `linux-64/` and `win-64/` subdirs are here to
show the layout; they hold only an (empty) `repodata.json` until a native
package is built for that platform:

```
conda_channel/
├── noarch/                                       # platform-independent packages
│   ├── moonrise_scatter-1.0.0-h4616a5c_0.conda   # the package
│   └── repodata.json                             # the subdir's index
├── linux-64/
│   └── repodata.json                             # empty index (no packages yet)
└── win-64/
    └── repodata.json                             # empty index (no packages yet)
```

(A `.gitignore` here re-allows `noarch/*.conda` so this one package is committed
on purpose, even though the repo root normally ignores built `.conda` files.)

## Commands

```bash
# Build a recipe into this channel (writes the .conda AND updates repodata.json)
rattler-build build --recipe ../conda_recipes/moonrise_scatter-1.0.0/recipe/recipe.yaml --output-dir .

# Install from this local channel to test (a local channel is referenced by path)
conda create -n test -c ./ -c conda-forge moonrise_scatter    # or  -c file://$(pwd)

# Publish the channel to S3
aws s3 sync . s3://<bucket>/Conda
```

## Add a new package

1. Write or copy a recipe under `../conda_recipes/<name>/recipe/recipe.yaml`.
2. `rattler-build build --recipe ../conda_recipes/<name>/recipe/recipe.yaml --output-dir .`
   drops the package in the right subdir and rebuilds `repodata.json`
   automatically.
3. Commit it (or `aws s3 sync . s3://<bucket>/Conda`) to publish.
4. Reference it from a job via `CondaPackages`/`CondaChannels`. See the
   [pipeline README](../README.md) for how the channel is wired in at run time.

Built with [`rattler-build`](https://rattler.build/) 0.68.0, the conda package
builder from prefix.dev, which writes the package and the `repodata.json` index
in one `build` step.

## Learn more

- rattler-build docs: https://rattler.build/ (mirror: https://prefix-dev.github.io/rattler-build/)
- Conda channels concept: https://docs.conda.io/projects/conda/en/latest/user-guide/concepts/channels.html
- AWS Deadline Cloud developer guide (queue environments install from a conda channel): https://docs.aws.amazon.com/deadline-cloud/latest/developerguide/
- The sample's build recipes: [`../conda_recipes/`](../conda_recipes/)
- The sample's pipeline README (how this channel is used at run time): [`../README.md`](../README.md)
