# V-Ray 7.20.02 conda build recipe for Maya 2025
Use this recipe to create a V-Ray 7.20.02 (Update 2 DR2) for Maya 2025 conda package to use with AWS Deadline Cloud. Conda packages let you customize the software you can use with your Deadline Cloud deployment. Read more about how to host a conda channel for these custom conda packages [here](https://github.com/aws-deadline/deadline-cloud-samples/tree/mainline/conda_recipes#infrastructure-setup-prerequisites).

## Requirement
### Download the archive file
- Download the `vray_adv_72002_maya2025_dr2_rhel8` full download file from [Chaos](https://www.chaos.com/vray/maya)\
**_NOTE:_** Need to have a Chaos account to access the link. Ensure the download completes fully (~1.1 GB). Truncated downloads will fail with installer checksum errors.
- Place the downloaded file in the `conda_recipes/archive_files` directory in your git clone of the
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
- Build command: `./submit-package-job maya-vray-7.2-2025`
