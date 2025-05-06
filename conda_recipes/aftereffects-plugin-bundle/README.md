# Conda build recipe for a bundle of After Effects plugins

## About

This package build recipe creates a conda package that bundles together all the After Effects plugins
you provide in an input folder. Note that if your plugins require network licenses, you will have to
handle that separately.

To understand how After Effects plugins work in a conda package, see the instructions for plugin
packages in the [After Effects recipe README](../aftereffects-25.1/README.md).

## Building the package for Windows

First copy all the Windows `.aex` plugin files that you want to include into
the [`conda_recipes/archive_files/aftereffects-plugin-bundle/win-64`](../archive_files/aftereffects-plugin-bundle/win-64/)
directory. You can find the plugins you're using locally in the After Effects installation
directory like `C:\Program Files\Adobe\Adobe After Effects <version>\Support Files\Plug-ins`.

### Build the package locally

To build locally on Windows, you can follow the linked installation instructions for either
[rattler-build](https://rattler.build/) or [conda-build](https://docs.conda.io/projects/conda-build).

IMPORTANT: Conda packages have a build number that you need to update to a new number each time you
build and publish the package for the same version number. Edit the meta.yaml and recipe.yaml files
in the `build` section from `number: 0` to a bigger number each time you follow these instructions.

From the `conda_recipes` directory, run one of the following build commands:

```
C:\Dev\deadline-cloud-samples\conda_recipes>rattler-build build -r aftereffects-plugin-bundle/recipe

 ╭─ Finding outputs from recipe
 │ Found 1 variants
 ...
 ╭─ Build summary
 │
 │ ╭─ Build summary for recipe: aftereffects-plugin-bundle-1.0-h9490d1a_1
 │ │ Artifact: C:\Dev\deadline-cloud-samples\conda_recipes\output\win-64\aftereffects-plugin-bundle-1.0-h9490d1a_1.conda (253.17 KiB)
 │ │ Variant configuration (hash: h9490d1a_1):
 │ │ ╭─────────────────┬──────────╮
 │ │ │ target_platform ┆ "win-64" │
 │ │ ╰─────────────────┴──────────╯
 │ │
 │ │ Run dependencies:
 │ │ ╭──────────────────┬──────────╮
 │ │ │ Name             ┆ Spec     │
 │ │ ╞══════════════════╪══════════╡
 │ │ │ Run dependencies ┆          │
 │ │ │ aftereffects     ┆ >=25,<26 │
 │ │ ╰──────────────────┴──────────╯
 │ │
 │ │
 │ ╰─────────────────── (took 0 seconds)
 │
 ╰─────────────────── (took 0 seconds)
```

or

```
C:\Dev\deadline-cloud-samples\conda_recipes>conda build aftereffects-plugin-bundle/recipe --no-test
Adding in variants from internal_defaults
...
####################################################################################
Source and build intermediates have been left in C:\...\conda-bld.
There are currently 1 accumulated.
To remove them, you can run the ```conda build purge``` command

C:\Dev\deadline-cloud-samples\conda_recipes>dir C:\...\conda-bld\win-64
...
04/10/2025  02:21 PM           232,806 aftereffects-plugin-bundle-1.0-0.conda
...
```

### Publish the locally built package to an S3 conda channel

To publish your package to an S3 conda channel, two things need to happen:

1. Copy the Windows package into the `win-64` subdirectory of the channel.
2. Update the channel index (`repodata.json` and some other files) so that they
   include metadata about the new package.

You can accomplish this with the AWS CLI to synchronize S3 data and the `conda index`
command that is available when you install [conda-build](https://docs.conda.io/projects/conda-build).

Here's an example of doing this for the package that was built by rattler-build:

1. Synchronize the `win-64` subdirectory of the channel locally.
    ```
    C:\Dev\deadline-cloud-samples\conda_recipes>set CHANNEL_BUCKET=<MY_S3_CHANNEL_BUCKET>

    C:\Dev\deadline-cloud-samples\conda_recipes>aws s3 sync s3://%CHANNEL_BUCKET%/Conda/Default/win-64 ./temp-local-channel/win-64
    ...
    ```
2. Copy the package you built into the `win-64` subdirectory.
    ```
    C:\Dev\deadline-cloud-samples\conda_recipes>copy output\win-64\aftereffects-plugin-bundle-1.0-h9490d1a_0.conda temp-local-channel\win-64
            1 file(s) copied.
    ...
    ```
3. Update the channel index with the new package.
    ```
    C:\Dev\deadline-cloud-samples\conda_recipes>conda index --subdir win-64 --zst ./temp-local-channel
    Indexing ['win-64'] does not include 'noarch'
    ...
    ```
4. Synchronize the local copy of the `win-64` subdirectory back to S3.
    ```
    C:\Dev\deadline-cloud-samples\conda_recipes>aws s3 sync ./temp-local-channel/win-64 s3://%CHANNEL_BUCKET%/Conda/Default/win-64
    upload: temp-local-channel\win-64\repodata.json to s3://<MY_S3_CHANNEL_BUCKET>/Conda/Default/win-64/repodata.json
    ...
    ```

### Build the package on Deadline Cloud

If you create a package build queue as described in the Deadline Cloud developer guide page
[Create a conda channel using S3](https://docs.aws.amazon.com/deadline-cloud/latest/developerguide/configure-jobs-s3-channel.html),
you can submit the package to build on your farm.

Note that this approach automatically determines a new build number each time you run
the package build job, you do not have to handle that yourself like when building locally.

```
C:\Dev\deadline-cloud-samples\conda_recipes>submit-package-job aftereffects-plugin-bundle
No channel URL was provided, using a default prefix on the queue's job attachments bucket
Building packages into channel s3://<MY_S3_CHANNEL_BUCKET>/Conda/Default
...
```