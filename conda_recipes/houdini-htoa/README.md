# Houdini Arnold (HtoA) Conda Recipe for AWS Deadline Cloud

## Overview

This directory contains the conda/rattler build recipe for Autodesk Arnold for Houdini (HtoA) 6.4.4.1 repackaged for Deadline Cloud managed fleets. The package installs the Houdini plugin, command‑line Arnold tools, and the Houdini package metadata required for Houdini 20.0 environments.

## Package Information

- **Application**: HtoA 6.4.4.1 (build rd99f711) for Houdini 20.0.896
- **Supported Platforms**: linux-64
- **Source**: Autodesk Arnold download portal (self-extracting `.run` installer)
- **License**: LicenseRef-AutodeskEULA
- **Build Tool**: rattler-build (invoked by `submit-package-job`)

## Prerequisites

Before building this package ensure:

1. **Deadline Cloud Infrastructure**
   - A farm with a queue dedicated to package building (e.g. `replai-studio-package-building-queue`).
   - Linux workers with connectivity to the target S3 Conda channel.
2. **Deadline Cloud CLI** installed on the workstation submitting the job.
3. **Autodesk Account** with access to download the Houdini Arnold installer.
4. **Source archive** downloaded (see below).

## Archive File Instructions

1. Download `htoa-6.4.4.1_rd99f711_houdini-20.0.896_gcc11.2_linux.run` from the Autodesk Arnold website.
2. Place the installer in `conda_recipes/archive_files/` (relative to the repository root).
3. Optionally verify the SHA256 hash: `ea9e5fcc41fb79b30731efd1e26b77040778a8b57c6e2d13c22598187173e33f`.

The build script automatically makes the installer executable, extracts it with Qt Installer Framework flags, and copies the payload into `$PREFIX/opt/htoa`.

## Building the Package

From the `conda_recipes` directory:

```bash
# Submit using the default queue and channel
./submit-package-job houdini-htoa

# Submit to a specific queue
./submit-package-job houdini-htoa -q "replai-studio-package-building-queue"

# Use an alternate S3 channel prefix (bucket derived from the queue defaults)
./submit-package-job houdini-htoa --s3-channel MyCustomChannel
```

By default the job uses the S3 channel `s3://<queue-attachments-bucket>/Conda/Default`. Ensure the queue role has `s3:PutObject`, `s3:GetObject`, and `s3:ListBucket` permissions for the chosen bucket/prefix so the `rattler-index` step can upload the package metadata.

### Manual Local Builds (Optional)

If you want to test locally, you can run `rattler-build` (requires the installer to be present):

```bash
rattler-build build \
  --recipe-dir recipe/ \
  --target-platform linux-64
```

## What the Recipe Installs

- `opt/htoa/` – Arnold plugin files and binaries extracted from the installer.
- Symlinks in `$PREFIX/bin` for Arnold utilities (`kick`, `maketx`, `noice`, `oslc`, `oslinfo`).
- `opt/houdini/packages/htoa.json` – Houdini package definition pointing to the plugin location.
- Conda activation scripts that export `HTOA`, `ARNOLD_LOCATION`, `HOUDINI_DSO_ERROR`, attempt to detect the Houdini version, and prepend Arnold’s Python modules.

## Using the Package in Deadline Cloud

After the package is uploaded to the S3 Conda channel and the channel is reindexed:

1. Add `htoa=0.1.*` to the Houdini job’s conda environment specification.
2. Ensure the Deadline Cloud queue used for Houdini jobs has read access to the channel.
3. When the job spins up, Houdini’s package loading system will read `opt/houdini/packages/htoa.json` and load the Arnold plugin automatically.

## Troubleshooting

- **Package build fails due to missing installer**: confirm the `.run` file exists under `conda_recipes/archive_files/` and matches the expected filename.
- **S3 upload AccessDenied**: update the queue role IAM policy to allow write and list access to the channel bucket/prefix.
- **Houdini cannot find HtoA at runtime**: verify the package version constraint (`houdini >=20.0,<21`) matches your Houdini package and that the conda environment sets `HOUDINI_PATH`/`PYTHONPATH` as expected.

## Recipe Structure

```
houdini-htoa/
├── README.md                  # This file
├── deadline-cloud.yaml        # Deadline Cloud submission metadata
└── recipe/
    ├── recipe.yaml            # rattler-build recipe definition
    └── build.sh               # Linux build script
```

## Updating the Recipe

1. Replace version identifiers in `recipe/recipe.yaml` and `deadline-cloud.yaml` for new HtoA/Houdini releases.
2. Update SHA256 hashes and expected installer filename.
3. Adjust build logic in `build.sh` if the installer layout changes.
4. Rebuild via `submit-package-job` and verify that the new package uploads and indexes successfully.

## Resources

- Autodesk Arnold: https://www.arnoldrenderer.com/
- Houdini Packages Documentation: https://www.sidefx.com/docs/houdini/ref/plugins.html
- AWS Deadline Cloud Developer Guide: https://docs.aws.amazon.com/deadline-cloud/latest/developerguide/
- Rattler Build Documentation: https://prefix-dev.github.io/rattler-build/
