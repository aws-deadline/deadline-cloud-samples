# Maya 2026 conda build recipe

## Instructions for Maya plugin packages

This Maya conda build recipe configures the `MAYA_MODULE_PATH` environment variable
to include the paths to search for plugin `.mod` files. When creating a plugin
package, place its `.mod` file in one of these so that Maya loads the plugin at startup.

* `$PREFIX/usr/autodesk/maya$MAYA_VERSION/modules`
* `$PREFIX/usr/autodesk/modules/maya/$MAYA_VERSION`
* `$PREFIX/usr/autodesk/modules/maya`

## Download the archive file for Linux

Download the Autodesk_Maya_2026_ML_Linux_64bit.tgz full download file from Autodesk, and
place it in the `conda_recipes/archive_files` directory in your git clone of the
[deadline-cloud-samples](https://github.com/aws-deadline/deadline-cloud-samples) repository for
submitting package build jobs.

