# Maya 2026 conda build recipe

## Requirements

This recipe requires rattler-build version > 0.32.0 due to a bug fix for cleaning up .pyc files during the build process. Earlier versions may fail to build properly. See [rattler-build issue #1191](https://github.com/prefix-dev/rattler-build/issues/1191) for more details.

## Instructions for Maya plugin packages

This Maya conda build recipe configures the `MAYA_MODULE_PATH` environment variable
to include several paths to search for plugin `.mod` files. When creating a plugin
package, place its `.mod` file in one of these so that Maya loads the plugin at startup.

* `$PREFIX/usr/autodesk/maya$MAYA_VERSION/modules`
* `$PREFIX/usr/autodesk/modules/maya/$MAYA_VERSION`
* `$PREFIX/usr/autodesk/modules/maya`

## Download the archive file for Linux

Download the Autodesk_Maya_2026_Linux_64bit.tgz full download file from Autodesk, and
place it in the `conda_recipes/archive_files` directory in your git clone of the
[https://github.com/aws-deadline/deadline-cloud-samples](deadline-cloud-samples) repository for
submitting package build jobs.

