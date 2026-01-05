# Unreal Engine Conda Package Recipe

## Overview

This recipe packages Unreal Engine for use in the AWS Deadline Cloud ecosystem. It uses UE 5.6 as an example, but you can adapt it for any UE version, including custom source builds.

Unlike other recipes in this repository, this one is designed to be built **locally** on a machine where Unreal Engine is already installed.

For example, UE 5.6 requires packaging ~80,000 files totaling 20+ GiB. If you submit a conda build job to AWS Deadline Cloud:
- **Without compression**: You'd upload a 20GB zip file as a job attachment, and workers would need to download all 20GB before building.
- **With compression**: Compressing takes time and can reduce the file size to ~10GB, but workers must then decompress it before building, which also takes time.

Either way, the upload/download/decompression overhead makes submitting UE as a job attachment impractical. Building locally on a machine with UE already installed avoids this entirely.

This approach is especially useful for studios using custom UE source builds that aren't available for download.

## Prerequisites

1. **Unreal Engine** installed on your Windows machine
   - Unreal Engine installed via Epic Games Launcher (e.g., `C:\Program Files\Epic Games\UE_5.6`)
   - Or your custom source build location

2. **[rattler-build](https://rattler-build.prefix.dev/)** installed locally
   ```
   # Using conda
   conda install -c conda-forge rattler-build

   # Or using pixi
   pixi global install rattler-build
   ```
3. **Enable Windows long path support**

   Follow the [Microsoft documentation](https://learn.microsoft.com/en-us/windows/win32/fileio/maximum-file-path-limitation?tabs=registry) to enable long path support.

4. **AWS CLI** configured with credentials that have write access to your S3 conda channel

## Adapting the Recipe for Your UE Version

Before building, update `recipe/recipe.yaml` to match your Unreal Engine installation:

1. **Update the version**:
   ```yaml
   context:
     name: "unrealengine"
     version: "5.6"  # Your UE version
   ```

2. **Update the source path**:
   ```yaml
   source:
     - path: 'C:\Program Files\Epic Games\UE_5.6\Engine'  # Your UE Engine path
   ```

   For custom source builds:
   ```yaml
   source:
     - path: 'D:\UnrealEngine\Engine'  # Your custom build path
   ```

## Publishing the Package

1. Publish a conda package by running rattler-build:
   ```
   rattler-build publish <path-to-recipe-file> --to <publish-conda-channel>
   ```

   The build process will:
   - Copy the Engine directory from your UE installation
   - Exclude non-essential files (documentation, source code, build artifacts, etc.)
   - Create a conda package in the channel and re-index the channel
   - For building a test package, use the `package-format` option to reduce compression level and speed up the build process. 
   ```
   --package-format conda:0
   ```

   The channel can be on prefix.dev, anaconda.org, an S3 bucket, a local filesystem folder (or network mount), or a Quetz or Artifactory instance. See the [rattler-build publish documentation](https://rattler-build.prefix.dev/v0.55.0/publish/) for details.

   > **Note:** The build may take up to 90 minutes depending on your disk speed.

### Uploading a locally built conda package to S3

The `rattler-build publish` command can upload directly to S3 and handle indexing automatically. If you need to upload a pre-built package manually:
   ```
   rattler-build publish <path-to-conda-package>.conda --to s3://...
   ```

## Recipe Details

### Excluded Files

The recipe excludes the following to reduce package size:

| Category | Patterns |
|----------|----------|
| Directories | Documentation, Extras, Samples, Templates, FeaturePacks, Intermediate, DerivedDataCache, Saved, Build, Source, Restricted |
| Build artifacts | `*.ipdb`, `*.iobj`, `*.exp`, `*.ilk`, `*.obj`, `*.log` |
| Source files | `*.cpp`, `*.c`, `*.inl`, `*.hpp`, `*.cs` |
| Dev files | `*.vcxproj`, `*.sln`, `*.filters`, `*.user`, `*.rc`, `*.manifest`, `*.pdb`, `*.lib` |

For custom source builds, you may need to adjust these exclusions based on your build configuration.

## Troubleshooting

**Build fails with "path not found"**
- Verify UE is installed and the path in `recipe.yaml` is correct
