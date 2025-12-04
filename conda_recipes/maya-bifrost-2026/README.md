# Bifrost for Maya conda build recipe

This package provides Autodesk Bifrost 2.14.1.0 support for Maya 2026.

## Supported Maya Versions

- Maya 2026

## Download the installer file for Linux

Download the `Bifrost_2.14.1.0_Maya2026_Linux.run` installer from Autodesk, and
place it in the `conda_recipes/archive_files` directory in your git clone of the
[deadline-cloud-samples](https://github.com/aws-deadline/deadline-cloud-samples) repository for
submitting package build jobs.

**Note:** You will need an Autodesk account and appropriate licensing to access the Bifrost installer.

## Build required conda package(s)

To use Bifrost for Maya, you need to build:

1. **Maya 2026 conda package** by:
   - Following Maya 2026 [README](../maya-2026/README.md) for getting the archive file
   - Running `./submit-package-job maya-2026` to build the package

2. **(_Optional - for Maya adaptor_) Maya adaptor conda package** by running:
   - [_Prerequisite_] Deadline Cloud package: `./submit-package-job deadline`
   - [_Prerequisite_] OpenJD runtime adaptor package: `./submit-package-job openjd-adaptor-runtime`
   - Maya adaptor package: `./submit-package-job maya-openjd`

## Build Conda Package

Follow this [README](https://github.com/aws-deadline/deadline-cloud-samples/blob/mainline/conda_recipes/README.md) to submit a job building Bifrost for Maya conda package.

Run: `./submit-package-job maya-bifrost-2026`

## Customization for Different Versions

To adapt this recipe for different Maya or Bifrost versions:

### Update Version Numbers

1. **Edit `recipe/recipe.yaml`**:
   - Change `major_version: "2026"` to your Maya version (e.g., "2025", "2024")
   - Change `minor_version: "2.14.1.0"` to your Bifrost version
   - Update the `version` context variable accordingly
   - Update the `sha256` hash to match your Bifrost installer file

2. **Edit `recipe/build.sh`**:
   - Update the installer filename and extraction logic if needed
   - Verify the installation paths match your Bifrost version

3. **Edit `deadline-cloud.yaml`**:
   - Update `sourceArchiveFilename` to match your Bifrost installer filename
   - Update download instructions with correct Autodesk download information

### Test End-to-End

1. **Build the package**: `./submit-package-job maya-bifrost-[your-version]`
2. **Test Maya integration**:
   ```bash
   mayapy -c "import maya.standalone; maya.standalone.initialize(); import maya.cmds as cmds; cmds.loadPlugin('bifrostGraph'); print('Bifrost loaded'); maya.standalone.uninitialize()"
   ```
3. **Test Bifrost functionality**: Create and submit a Bifrost simulation job
4. **Verify output**: Check that Bifrost simulations run correctly and produce expected results

## About Bifrost

Autodesk Bifrost is a procedural platform that enables artists to create complex simulations and effects for Maya. It provides tools for:

- Fluid simulations (liquids, smoke, fire)
- Particle systems and dynamics
- Procedural modeling and geometry processing
- Visual programming through a node-based interface
- Integration with Maya's rendering pipeline