# V-Ray conda build recipe
Use this recipe to create a V-Ray for Maya conda package to use with AWS Deadline Cloud. Conda packages let you customize the software you can use with your Deadline Cloud deployment. Read more about how to host a conda channel for these custom conda packages [here](https://github.com/aws-deadline/deadline-cloud-samples/tree/mainline/conda_recipes#infrastructure-setup-prerequisites).

## Requirement
### Download the archive file
- Download the `vray_adv_71002_maya2026_rhel8` full download file from [Chaos](https://download.chaos.com/downloads/23688/vray-maya-2026-71002-adv)\
**_NOTE:_** Need to have a Chaos account to access the link
- place the downloaded file in the `conda_recipes/archive_files` directory in your git clone of the
[deadline-cloud-samples](https://github.com/aws-deadline/deadline-cloud-samples) repository.

### Build required conda package(s)
To use V-Ray for Maya, we need to build:
1. Maya 2026 conda package by:
    - Follow Maya 2026 [README](../maya-2026/README.md) for getting archive file
    - running `./submit-package-job maya-2026` to build the package
2. (_Optional - build this for Maya adaptor_) Maya adaptor conda package by running:
    - [_Prerequisite_] Deadline Cloud package: `./submit-package-job deadline`
    - [_Prerequisite_] OpenJD runtime adaptor package:`./submit-package-job openjd-adaptor-runtime`
    - Maya adaptor package:`./submit-package-job maya-openjd`
    
    **_NOTE:_** Need to also add `conda-forge` to list of conda channel since Maya adaptor and prerequisite packages depend on it to run successful.

## Build Conda Package
- Follow this [README](https://github.com/aws-deadline/deadline-cloud-samples/blob/mainline/conda_recipes/README.md) to submit a job building V-Ray for Maya conda package.

## Customization for Different Versions
To adapt this recipe for different Maya or V-Ray versions:

### Update Version Numbers
1. **Edit `recipe/recipe.yaml`**:
   - Change `version_maya: "2026"` to your Maya version (e.g., "2025", "2024")
   - Change `version_vray: "7.10.02"` to your V-Ray version (e.g., "6.20.01")
   - Update the `sha256` hash to match your V-Ray installer file

2. **Edit `recipe/build.sh`**:
   - Update `MAYA_VERSION=2026` to match your Maya version
   - Update the installer filename in `VRAY_INSTALLER` variable
   - Update the sed command pattern to match your V-Ray module name (e.g., `VRayForMaya2025rhel8`)

3. **Edit `deadline-cloud.yaml`**:
   - Update `sourceArchiveFilename` to match your V-Ray installer filename
   - Update download instructions with correct Chaos Group download link

### Test End-to-End
1. **Build the package**: `./submit-package-job maya-vray-[your-version]`
2. **Test Maya integration**:
   ```bash
   mayapy -c "import maya.standalone; maya.standalone.initialize(); import vray; print('V-Ray loaded'); maya.standalone.uninitialize()"
   ```
3. **Test rendering**: Submit a V-Ray render job using your custom package
4. **Verify output**: Check that rendered images are produced correctly
