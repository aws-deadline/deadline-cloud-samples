# Blender Plugin Build

This conda recipe packages multiple Blender addons from a zip archive containing individual addon zip files.

## Usage

1. Create a zip archive containing multiple Blender addon zip files
2. Place the archive at `archive_files/blender-plugins.zip`
3. Update the SHA256 hash in `recipe/recipe.yaml`
4. Build the conda package

The recipe will install all zip files as Blender addons when the conda environment is activated and remove them when deactivated.

## Addon Solution for Blender
When adding addons to Blender on SMF, we use the activate and deactivate scripts to install/uninstall the addon with Blenders API. If your addon needs additional dependencies, we don't recommend installing them there.
Install your Python dependencies in the build script, then move them into Blender's Python in the activate script. 

