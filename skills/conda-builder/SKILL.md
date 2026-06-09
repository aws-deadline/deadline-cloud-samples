---
name: conda-builder
description: >
  Create or update DCC conda recipes for AWS Deadline Cloud by mimicking existing
  deadline-cloud-samples recipes. Currently supports Blender. To be expanded to other
  DCCs. Handles recipe creation, Docker-based building on AL2023, local channel
  indexing, and testing with rattler-build.
tags: [skill, conda, rattler-build, deadline-cloud, recipe, dcc]
---

# Conda Recipe Builder for Deadline Cloud DCCs

## Overview

This skill creates and tests `rattler-build` conda recipes for DCCs used with AWS
Deadline Cloud, by mimicking the structure and conventions of existing recipes in
`deadline-cloud-samples/conda_recipes/`. Recipes are built in an AL2023 Docker
container (matching the service-managed fleet OS) and indexed into a local conda
channel for testing.

### Supported DCCs

Per-DCC guides live in the `dcc/` subdirectory. Each guide covers the DCC-specific
download URL patterns, SHA256 hash sources, required system libraries, and smoke
test commands.

| DCC | Guide |
|-----|-------|
| Blender | [`dcc/blender.md`](dcc/blender.md) |

**If the user asks for a DCC that isn't listed above, respond with:**

> "That DCC isn't supported yet in this skill. Please ask for an update to the
> [deadline-cloud-samples](https://github.com/aws-deadline/deadline-cloud-samples)
> repository to add it."

Do not attempt to build a recipe for an unsupported DCC.

## Usage

Use this skill when:
- A new DCC version needs a conda recipe for Deadline Cloud
- An existing recipe needs updating to a newer patch release
- You need to build and test a DCC conda package locally
- Someone asks "create a <DCC> X.Y recipe" or "update <DCC> to X.Y.Z"

## Core Concepts (shared across DCCs)

- Recipes use the `rattler-build` format (`recipe.yaml`)
- Build inside an AL2023 Docker container to match the GLIBC version on Deadline
  Cloud's service-managed fleet (SMF) workers
- The `build.sh` script typically copies the DCC archive into `$PREFIX/opt/<dcc>`,
  creates symlinks, and sets environment variables via `env_vars.d` JSON files
- DCC-specific runtime library requirements (X11, EGL, etc.) are listed in each
  per-DCC guide
- SHA256 hashes should always come from the DCC vendor's official hash file —
  never guess or compute them from downloads

## Workflow

You **MUST** follow these steps in order.

### Step 1: Identify the DCC and version

Ask the user which DCC and which version. Then **read the matching guide in
`dcc/<dcc>.md`** — it contains the vendor-specific download URLs, hash sources,
and required system libraries. Do not proceed without reading it.

If the DCC is not listed in the "Supported DCCs" table above, stop and direct the
user to request an update to `deadline-cloud-samples`.

### Step 2: Get the archive SHA256 hashes

Follow the per-DCC guide to fetch the official SHA256 hashes for both Linux and
Windows archives.

### Step 3: Find the previous recipe

Look in `deadline-cloud-samples/conda_recipes/` for the most recent `<dcc>-*`
directory. Read all files from it to use as the template:
- `recipe/recipe.yaml`
- `recipe/build.sh`
- `recipe/build_win.sh` (if present)
- `deadline-cloud.yaml`
- `README.md`

### Step 4: Create the new recipe

Create `deadline-cloud-samples/conda_recipes/<dcc>-X.Y/` mirroring the previous
recipe. Update:

- `recipe/recipe.yaml` — `context.version`, `context.major_minor_version`, and both
  `sha256` values (linux + windows). URLs are usually templated from context
  variables and update automatically.
- `recipe/build.sh` and `recipe/build_win.sh` — copy unchanged unless the DCC guide
  says otherwise. These scripts should be version-agnostic (use `$PKG_VERSION`).
- `deadline-cloud.yaml` — `sourceArchiveFilename` and `sourceDownloadInstructions`
  for both platforms.
- `README.md` — version numbers throughout.

### Step 5: Set up the AL2023 Docker build container

Build (or reuse) an AL2023 image from the
[`containers/al2023-deadline/Dockerfile.worker-equivalent`](../../containers/al2023-deadline/Dockerfile.worker-equivalent)
Dockerfile in `deadline-cloud-samples`. This image replicates an April 2026
snapshot of the SMF worker AMI, so GLIBC and runtime libraries match what the
DCC will see on a real worker — no need to install system packages ad-hoc.

Check for an existing container:

```bash
docker ps -a --filter name=al2023-conda-build
```

If the image isn't built yet, build it from the Dockerfile (takes ~5 minutes the
first time, cached after that):

```bash
docker build \
    -f deadline-cloud-samples/containers/al2023-deadline/Dockerfile.worker-equivalent \
    -t al2023-deadline-worker:latest \
    deadline-cloud-samples/containers/al2023-deadline/
```

Start the container with the workspace and conda channel mounted:

```bash
docker run -d --name al2023-conda-build \
    -v $(pwd):/workspace \
    -v $HOME/my-conda-channel:/my-conda-channel \
    -w /workspace \
    al2023-deadline-worker:latest sleep infinity
```

The image already includes `gcc`, Python 3.11, X11/Mesa/EGL libraries, AWS CLI,
Docker tooling, and all the other runtime libraries the SMF worker has. You only
need to add `rattler-build` and Miniconda on top:

```bash
# Install rattler-build
docker exec al2023-conda-build bash -c '
    curl -fsSL https://github.com/prefix-dev/rattler-build/releases/latest/download/rattler-build-x86_64-unknown-linux-musl \
        -o /usr/local/bin/rattler-build && chmod +x /usr/local/bin/rattler-build
'

# Install Miniconda + conda-build (for conda index)
docker exec al2023-conda-build bash -c '
    curl -fsSL https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh \
        -o /tmp/miniconda.sh && bash /tmp/miniconda.sh -b -p /opt/conda
    export PATH=/opt/conda/bin:$PATH
    conda tos accept --override-channels --channel https://repo.anaconda.com/pkgs/main
    conda tos accept --override-channels --channel https://repo.anaconda.com/pkgs/r
    conda install -y -c conda-forge conda-build
'
```

If the per-DCC guide calls for additional system libraries beyond what the
worker-equivalent image provides, install them with `yum install -y` as a
fallback — but first confirm they're actually missing by checking the image.

### Step 6: Build the package

```bash
docker exec al2023-conda-build bash -c '
    export PATH=/opt/conda/bin:$PATH
    rattler-build build \
        --recipe /workspace/deadline-cloud-samples/conda_recipes/<dcc>-X.Y/recipe/recipe.yaml \
        --target-platform linux-64 \
        --output-dir /my-conda-channel
'
```

The recipe's built-in test may require DCC-specific runtime libraries — see the
per-DCC guide. To skip the test: `--no-test`.

### Step 7: Index the channel

```bash
docker exec al2023-conda-build bash -c '
    export PATH=/opt/conda/bin:$PATH
    conda index /my-conda-channel
'
```

### Step 8: Test the package

```bash
docker exec al2023-conda-build bash -c '
    export PATH=/opt/conda/bin:$PATH
    conda create -y -n <dcc>-test \
        -c file:///my-conda-channel --override-channels <dcc>=X.Y
    eval "$(/opt/conda/bin/conda shell.bash hook)"
    conda activate <dcc>-test
    # Run DCC-specific smoke test from the per-DCC guide
'
```

### Step 9: Optional — test with openjd-cli

For a full end-to-end test using the Deadline Cloud job bundle, install
`openjd-cli` and run the matching job template. See the per-DCC guide for the
exact commands.

## Common Mistakes

- Building outside AL2023 — GLIBC mismatch causes runtime failures on SMF workers
- Missing DCC-specific runtime libraries in the container — the DCC won't launch
  and the recipe test will fail
- Forgetting `conda index` after building — the package won't be discoverable
- Guessing SHA256 hashes — always fetch from the vendor's official hash file
- Running a full-resolution render for a smoke test — use low resolution + low
  samples for a fast check (~5-10 seconds)

## Quick Reference

| Item | Value |
|------|-------|
| Recipe location | `deadline-cloud-samples/conda_recipes/<dcc>-X.Y/` |
| Build tool | `rattler-build build --recipe ...` |
| Index tool | `conda index /my-conda-channel` |
| Docker image | `al2023-deadline-worker:latest` (built from `containers/al2023-deadline/Dockerfile.worker-equivalent`) |
| Container name | `al2023-conda-build` |
| Per-DCC guides | `dcc/<dcc>.md` |
