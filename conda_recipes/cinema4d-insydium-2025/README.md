# Conda build recipe for INSYDIUM X-Particles

## About

This package build recipe creates a conda package for the INSYDIUM plugin you
provide in an input folder.

Note: INSYDIUM requires a [GPU](https://insydium.ltd/help/?q=My+render+node+system+does+not+have+a+GPU%2C+will+INSYDIUM+Fused+work%3F).


## Building the package for Windows

To build the INSYDIUM package, follow these instructions:

1. Install by following [instructions here](https://insydium.ltd/help/?q=1608)
2. [Optional] Verify that "INSYDIUM" works with Cinema 4D locally. You can test this using any of the sample scenes available [here](https://insydium.ltd/support-home/content-repository/).
3. Copy the "INSYDIUM" folder from your installation directory to `conda_recipes/archive_files/cinema4d-insydium-2025/win-64`. (The default installation location on Windows is `C:\Program Files\Maxon Cinema 4D 2025\plugins\INSYDIUM`)

### Build the package on Deadline Cloud

If you create a package build queue as described in the Deadline Cloud developer guide page
[Create a conda channel using S3](https://docs.aws.amazon.com/deadline-cloud/latest/developerguide/configure-jobs-s3-channel.html),
you can submit the package to build on your farm.

Note that this approach automatically determines a new build number each time you run
the package build job, you do not have to handle that yourself like when building locally.

```
C:\Dev\deadline-cloud-samples\conda_recipes>submit-package-job cinema4d-insydium-2025
No channel URL was provided, using a default prefix on the queue's job attachments bucket
Building packages into channel s3://<MY_S3_CHANNEL_BUCKET>/Conda/Default
...
```

### Build the package locally


From the `conda_recipes` directory, run:

```
C:\Dev\deadline-cloud-samples\conda_recipes>conda build cinema4d-insydium-2025/recipe --no-test
Adding in variants from internal_defaults
...
####################################################################################
Source and build intermediates have been left in C:\...\conda-bld.
There are currently 1 accumulated.
To remove them, you can run the ```conda build purge``` command

C:\Dev\deadline-cloud-samples\conda_recipes>dir C:\...\conda-bld\win-64
...
04/10/2025  02:21 PM           232,806 cinema4d-insydium-2025-0.conda
...
```

The --no-test flag avoids a conda error if cinema4d-2025 package hasn't already
been built locally.

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
    C:\Dev\deadline-cloud-samples\conda_recipes>copy output\win-64\cinema4d-insydium-2025-h9490d1a_0.conda temp-local-channel\win-64
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
