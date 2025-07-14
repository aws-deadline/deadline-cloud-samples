# Houdini 20.5 Conda Recipe

## Download the archive file for Linux

Download the houdini-20.5.654-linux_x86_64_gcc11.2.tar.gz file from SideFX.
Place the file in the `conda_recipes/archive_files` directory in your git clone
of the [https://github.com/aws-deadline/deadline-cloud-samples](deadline-cloud-samples)
repository for submitting package build jobs.

## Building the package

Follow this [README](https://github.com/aws-deadline/deadline-cloud-samples/blob/mainline/conda_recipes/README.md) to get everything set
up to submit pacakge build jobs.

To submit a package build job for Houdini 20.5, enter the `conda_recipes` directory and run the following
from your shell:

```
./submit-package-job houdini-20.5
```

## Instructions for Houdini plugin packages

Plugins can be registered with Houdini following the standard process of creating
and loading Houdini [package](https://www.sidefx.com/docs/houdini/ref/plugins.html)
files. 

## Adapting for other Houdini versions
This recipe is written for Houdini 20.5.654, but should be able to be adapted
for any 20.5 patch release or even modified to work with older Houdini versions
such as 19.5 or 20.0. At minimum you would need to grab the specific installers
for a different version and modify the `sourceArchiveFilename` in `deadline-cloud.yaml`
and the version string and archive hash in `recipe.yaml`.