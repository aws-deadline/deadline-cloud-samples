# AYON Launcher Conda Package

This recipe packages the [AYON Launcher](https://github.com/ynput/ayon-launcher) as a conda package for AWS Deadline Cloud workers. It provides the pipeline runtime needed for headless publishing on Service-Managed Fleet (SMF) and Customer-Managed Fleet (CMF) workers.

## What's included

The package repackages the pre-built AYON Launcher release (cx_Freeze'd binary) containing:
- Python 3.11 runtime
- `ayon-python-api` (AYON server REST client)
- Core launcher logic (bundle resolution, addon discovery)
- All bundled dependencies

## How it works

The AYON Launcher conda package provides the **runtime environment**. The studio-specific **bundle** (addons + dependency package) is delivered separately via Deadline Cloud job attachments. This separation means:
- The conda package rarely changes (only on launcher releases)
- Studios control addon versions via their AYON server bundle configuration
- No conda package rebuild needed when addons are updated

## Building

### Prerequisites

```bash
# Install rattler-build
pixi global install rattler-build
```

> **Build each platform on a matching-OS host.** The build scripts are bash
> (`build.sh` / `build_win.sh`), and rattler-build runs the build script through the
> **build host's native shell** — bash on Linux, `cmd.exe` on Windows — while the
> `if: unix` / `if: win` selectors choose the branch by the **target** platform. As a
> result:
> - Build **linux-64 on a Linux host** (bash runs `build.sh` directly).
> - Build **win-64 on a Windows host** (`cmd.exe` expands `%RECIPE_DIR%` and launches
>   bash to run `build_win.sh`; bash ships with the Deadline Cloud sample Windows
>   workers and Git for Windows).
>
> Cross-OS builds are **not supported** — e.g. building linux-64 from Windows fails
> because `cmd.exe` does not expand `$RECIPE_DIR`, and building win-64 from Linux fails
> because bash does not expand `%RECIPE_DIR%`. When submitting with
> `submit-package-job`, the job runs rattler-build on a fleet worker, so ensure the
> queue has a fleet whose OS matches each requested conda platform (see the repo's
> top-level `conda_recipes/README.md`).

### Linux (linux-64)

The Linux source is downloaded directly from GitHub releases:

```bash
rattler-build build --recipe recipe/recipe.yaml --target-platform linux-64
```

### Windows (win-64)

The Windows source requires a pre-extracted zip in `archive_files/`. Since AYON only publishes an `.exe` installer for Windows, you must extract it first:

1. On a Windows machine, run the installer with `/VERYSILENT /DIR=C:\ayon-launcher`
2. Zip the contents: `Compress-Archive -Path C:\ayon-launcher\* -DestinationPath AYON-1.6.1-win.zip`
3. Place the zip at `../../archive_files/AYON-1.6.1-win.zip` (relative to the recipe directory)

Then build:

```bash
rattler-build build --recipe recipe/recipe.yaml --target-platform win-64
```

## Publishing to a conda channel

```bash
# Upload packages
aws s3 cp output/linux-64/ayon-launcher-*.conda s3://<your-bucket>/Conda/Default/linux-64/
aws s3 cp output/win-64/ayon-launcher-*.conda s3://<your-bucket>/Conda/Default/win-64/

# Index the channel
rattler-index s3 s3://<your-bucket>/Conda/Default
```

## Queue configuration

Add your conda channel to the queue's `CondaChannels` parameter:

```
conda-forge s3://<your-bucket>/Conda/Default deadline-cloud
```

The queue role needs `s3:GetObject` and `s3:ListBucket` permissions on the channel bucket.

## Version updates

To package a new AYON Launcher version:

1. Update `context.version` in `recipe.yaml`
2. Update the `sha256` for the Linux source (from the `.json` metadata file in the GitHub release)
3. For Windows: extract the new installer and upload the zip to `archive_files/`
4. Build both platforms and upload to the channel

## Environment variables set by the package

| Variable | Value | Description |
|----------|-------|-------------|
| `AYON_LAUNCHER_DIR` | `$CONDA_PREFIX/opt/ayon-launcher` | Path to the launcher installation |
| `AYON_HEADLESS_MODE` | `1` | Runs the launcher without GUI |

## Additional environment variables needed at runtime

These must be provided by the job (via step environment or job parameters):

| Variable | Description |
|----------|-------------|
| `AYON_SERVER_URL` | URL of the AYON server |
| `AYON_API_KEY` | API key for server authentication |
| `AYON_BUNDLE_NAME` | Bundle name to resolve addons from |
