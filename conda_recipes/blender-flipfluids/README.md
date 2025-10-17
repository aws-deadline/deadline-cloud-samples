# FLIP Fluids addon conda build recipe for Blender

## About
This recipe installs the demo version of the FLIP Fluids addon to Blender. To write conda recipes to add more addons to your Blender Deadline Cloud setup, use this recipe as a template to guide your development.

## Addon Solution for Blender
When adding addons to Blender on SMF, we use the activate and deactivate scripts to install/uninstall the addon with Blenders API. If your addon needs additional dependencies, we don't recommend installing them there.
Install your Python dependencies in the build script, then move them into Blender's Python in the activate script. 

## Creating an archive file for Blender Addons
Blender addons are typically contained in a zip archive. One would think that it'd be simple enough to use that archive as the source file for our rattler build, however, rattler will automatically extract the contents
of source files during build. In this case we want to use the zip archive directly instead of having all the files extracted. To solve for this, we've added the addon to a zip archive. It's a zip of a zip. During the build, rattler will
extract the FLIP Fluid addon into the `$SRC_DIR/flipfluids/` directory. From there we can include it in the installation directory and have Blender install it. 