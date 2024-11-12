# V-Ray conda build recipe

## Decide what version of the archive file to download
- Download `vraystd_adv_62022_rhel8_clang-gcc-11.2` for **x86**

- Download `vraystd_adv_62022_rhel8_arm64_clang-gcc-11.2` for **ARM**

## Download the archive file
- Download the `vraystd_adv_62022_rhel8_clang-gcc-11.2` or `vraystd_adv_62022_rhel8_arm64_clang-gcc-11.2` full download file from [Chaos](https://download.chaos.com/?platform=47&product=47)\
**_NOTE:_** Need to have a Chaos account to access the link

## Build Conda Package
- place it in the `conda_recipes/archive_files` directory in your git clone of the
[deadline-cloud-samples](https://github.com/aws-deadline/deadline-cloud-samples) repository for
submitting package build jobs.

- Follow this [README](https://github.com/aws-deadline/deadline-cloud-samples/blob/mainline/conda_recipes/README.md) to submit a job building the V-Ray conda package