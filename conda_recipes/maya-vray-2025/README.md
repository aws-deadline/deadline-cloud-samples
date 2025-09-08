# V-Ray conda build recipe
Use this recipe to create a V-Ray for Maya conda package to use with AWS Deadline Cloud. Conda packages let you customize the software you can use with your Deadline Cloud deployment. Read more about how to host a conda channel for these custom conda packages [here](https://github.com/aws-deadline/deadline-cloud-samples/tree/mainline/conda_recipes#infrastructure-setup-prerequisites).

## Requirement
### Download the archive file
- Download the `vray_adv_62002_maya2025_rhel8` full download file from [Chaos](https://download.chaos.com/downloads/23688/vray-maya-2025-62002-adv)\
**_NOTE:_** Need to have a Chaos account to access the link
- place the downloaded file in the `conda_recipes/archive_files` directory in your git clone of the
[deadline-cloud-samples](https://github.com/aws-deadline/deadline-cloud-samples) repository.

### Build required conda package(s)
To use V-Ray for Maya, we need to build:
1. Maya 2025 conda package by:
    - Follow Maya 2025 [README](../maya-2025/README.md) for getting archive file
    - running `./submit-package-job maya-2025` to build the package
2. (_Optional - build this for Maya adaptor_) Maya adaptor conda package by running:
    - [_Prerequisite_] Deadline Cloud package: `./submit-package-job deadline`
    - [_Prerequisite_] OpenJD runtime adaptor package:`./submit-package-job openjd-adaptor-runtime`
    - Maya adaptor package:`./submit-package-job maya-openjd`
    
    **_NOTE:_** Need to also add `conda-forge` to list of conda channel since Maya adaptor and prerequisite packages depend on it to run successful.

## Build Conda Package
- Follow this [README](https://github.com/aws-deadline/deadline-cloud-samples/blob/mainline/conda_recipes/README.md) to submit a job building V-Ray for Maya conda package.