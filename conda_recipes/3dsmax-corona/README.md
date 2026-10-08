# 3dsmax-corona conda package

This package repackages the Corona Renderer plug-in for Autodesk 3ds Max into a conda-installable bundle. It should be installed alongside the matching `3dsmax` conda package.

> **Licensing:** Corona Renderer is distributed under the Chaos EULA. You must hold a valid Corona
> license that covers your rendering workload before deploying this package on a fleet. See the
> [Chaos website](https://www.chaos.com/corona) for licensing details.

## Contents
- Corona Renderer payload for 3ds Max (version 13.2) sourced from `archive_files/3dsmax-corona-2025-13-2/win-64`.
- Windows-only build that copies the plug-in files into the 3ds Max installation inside the conda prefix.

## Usage
1. Ensure the `3dsmax` conda package for the matching major version is installed.
2. Install this package via your conda channel (e.g., `conda install 3dsmax-corona-2025`).
3. Activate the environment; the plug-in will live under the 3ds Max plug-ins directory.

## Building the archive payload
If you need to refresh the archive payload:
1. Run the Corona installer `.exe` for 3ds Max on a Windows OS.
2. After install, copy the Corona files from `C:\Program Files\Chaos\Corona\Corona Renderer for 3ds Max\2025` (or matching year) into `archive_files/3dsmax-corona-2025-13-2/win-64/` in this repo.
3. Build the conda package (`conda build conda_recipes/3dsmax-corona/recipe`).

## Notes
- Platform: `win-64` only.
- License: Chaos EULA (see vendor site).
- Documentation: https://docs.chaos.com/display/CRMAX
