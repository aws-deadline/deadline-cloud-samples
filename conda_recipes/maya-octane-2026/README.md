# OctaneRender for Maya 2026 conda build recipe

This recipe packages the OctaneRender Studio+ 2026.4 plugin (v25.20) for Maya 2026 on Linux as the `maya-octane` conda package.

## Render Prerequisites

- Autodesk Maya 2026 which can be provided by the `maya` conda package, available from the default conda environment on SMF.
- Linux workers with an NVIDIA GPU. OctaneRender renders only on the GPU.
- OctaneRender licenses and the cuDNN runtime. These dependencies can both be configured on SMF using the [OctaneRender licensing and cuDNN host configuration script](../../host_configuration_scripts/octane_setup/).

## Build Prerequisites

Download the `OctaneRender_Studio+_2026.4_for_Maya_v25.20.run` installer from the [OTOY Downloads Page](https://render.otoy.com/account/downloads.php)(login required) and place it in the `conda_recipes/archive_files` directory.

> [!WARNING]
> You should always use the correct version of the OctaneRender Studio+ plugin for your host application.
> If you are using a different installer version than what is shown in these docs, update the following pieces of the conda recipe before building the package:
> - The filename and version in `deadline-cloud.yaml` and `recipe/recipe.yaml`.
> - The checksum in `recipe/recipe.yaml`.
> - `INSTALLER_NAME` in `recipe/build.sh`.

The installer includes plugins for several Maya versions. The recipe extracts it without modifying the original file and installs only the Maya 2026 plugin and the shared OctaneRender files under `$PREFIX/usr/otoy/ofm_vr`. It also:

- Adds the `octane.mod` module file to the Maya 2026 module path so Maya finds the plugin.
- Copies `octaneRenderer.xml` into Maya's renderer description directory so Maya's command-line renderer accepts `-r octane`.
- Links the shared libraries next to the plugin and into Maya's `lib` directory, as the OTOY installer does.
