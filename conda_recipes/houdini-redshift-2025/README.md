# Redshift for Houdini Conda Recipe

## Download the installer for Linux

Download the Redshift installer `redshift_2025.6.0_1924545106_linux_x64.run` from Maxon.
Place the file in the `conda_recipes/archive_files` directory in your git clone
of the [https://github.com/aws-deadline/deadline-cloud-samples](deadline-cloud-samples)
repository for submitting package build jobs.

## Building the package

Follow this [README](https://github.com/aws-deadline/deadline-cloud-samples/blob/mainline/conda_recipes/README.md) to get everything set
up to submit package build jobs.

To submit a package build job for Redshift for Houdini, enter the `conda_recipes` directory and run the following
from your shell:

```
./submit-package-job houdini-redshift-2025
```

## Integration with Houdini

This package is designed to work with the [Houdini conda package](../houdini-20.5/README.md). It automatically detects the
installed Houdini version by calling `houdini --version` and configures the appropriate Redshift plugin version. 

Redshift plugins for Houdini are versioned to the exact patch release of Houdini. Using a Redshift plugin version that
isn't for the exact same Houdini version can result in instability. This package will attempt to use the best Redshift
plugin version to match the version of Houdini provided by:
1. Looking for an exact match between the Houdini version and available Redshift plugin versions
2. If no exact match is found, it will use a plugin version that matches the major.minor version of Houdini
3. If no matching major.minor version is found, the package will exit and not configure Redshift
4. If the `houdini --version` call doesn't print a valid version string, the package will exit and not configure Redshift

## Adapting for other Redshift versions

This recipe can be adapted for other Redshift versions by modifying the `sourceArchiveFilename` in `deadline-cloud.yaml`
and the version string in `recipe.yaml`. You may also need to update the build script if the Redshift installer structure
changes between versions.

> **Warning**: When changing the Redshift version, be sure to check what versions of Houdini it supports due to how the
plugin [integrates with Houdini](#integration-with-houdini). Details on Redshift version support for Houdini can be
found [here](https://help.maxon.net/r3d/houdini/en-us/Content/html/Houdini+Plugin+Configuration.html).
