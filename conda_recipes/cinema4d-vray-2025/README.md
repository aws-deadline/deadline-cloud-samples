# Conda build recipe for Cinema 4D V-Ray

## About

This package build recipe creates a conda package for the vray plugin you
provide in an input folder.


## Building the package for Windows

1. Install the V-Ray for Cinema 4D plugin by [following instructions here](https://docs.chaos.com/display/VC4D/Installation).
  i. Choose "Workstation" install
2. [Optional] Verify that "V-Ray" works with Cinema 4D locally. You can test this using any of the sample scenes available [here](https://www.chaos.com/cloud/scenes?srsltid=AfmBOorJmV6Bugw1DTiIyfiA1gxANUxdp1tUaHOTdyZLJnBGJxLON8Xi#cinema-4d).
3. Copy the "V-Ray" folder from your installation directory to conda_recipes/archive_files/cinema4d-vray-2025/win-64.
(The default installation location on Windows is C:\Program Files\Maxon Cinema 4D 2025\plugins\V-Ray)


### Build the package on Deadline Cloud

If you create a package build queue as described in the Deadline Cloud developer guide page
[Create a conda channel using S3](https://docs.aws.amazon.com/deadline-cloud/latest/developerguide/configure-jobs-s3-channel.html),
you can submit the package to build on your farm.

Note that this approach automatically determines a new build number each time you run
the package build job, you do not have to handle that yourself like when building locally.

```
C:\Dev\deadline-cloud-samples\conda_recipes>submit-package-job cinema4d-vray-2025
No channel URL was provided, using a default prefix on the queue's job attachments bucket
Building packages into channel s3://<MY_S3_CHANNEL_BUCKET>/Conda/Default
...
```

On Service Mangaged Fleets V-Ray licensing should work with no setup required.
On Customer Managed Fleets follow this [licensing guide](https://docs.aws.amazon.com/deadline-cloud/latest/developerguide/cmf-ubl.html).


### Build the package locally


From the `conda_recipes` directory, run:

```
C:\Dev\deadline-cloud-samples\conda_recipes>conda build cinema4d-vray-2025/recipe --no-test
Adding in variants from internal_defaults
...
####################################################################################
Source and build intermediates have been left in C:\...\conda-bld.
There are currently 1 accumulated.
To remove them, you can run the ```conda build purge``` command

C:\Dev\deadline-cloud-samples\conda_recipes>dir C:\...\conda-bld\win-64
...
04/10/2025  02:21 PM           232,806 cinema4d-vray-2025-0.conda
...
```

Note: The `--no-test` skips a build error locating cinema4d package only
required at runtime and already provided by the SMF default Conda environment.

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
    C:\Dev\deadline-cloud-samples\conda_recipes>copy output\win-64\cinema4d-vray-2025-h9490d1a_0.conda temp-local-channel\win-64
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
