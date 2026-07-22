# VRED 2026 Conda Recipe

## Download the Installation File For Linux

Download the VRED Core 2026 installation file for Linux (VREDCOre-2026.sh) from Autodesk Account page.
Place the file in the `conda_recipes/archive_files` directory within your local clone of the [deadline-cloud-samples](https://github.com/aws-deadline/deadline-cloud-samples) repository for submitting package build jobs.

## Building the Package

To set up your environment for submitting package build jobs, please refer to this [README](https://github.com/aws-deadline/deadline-cloud-samples/blob/mainline/conda_recipes/README.md).

Once your environment is prepared, go to the `conda_recipes` directory and execute the following command from your shell to submit a package build job for VRED 2026:

```
./submit-package-job vredcore-2026
```

## Prerequisites for Package Usage

For VRED's GPU rendering capabilities, an X Server must be running in the background. This Conda package automatically starts X Server, but the Linux user running this package must have the following permissions:

1. Membership in the 'tty' group
2. Read/write permissions for virtual terminals (/dev/tty1)

These requirements can be set up using:
```bash
# Adds the user to the group 'tty'
sudo usermod -a -G tty job-user

# Sets permissions of /dev/tty1 device file to 660 (to give read + write permissions to group)
sudo chmod 660 /dev/tty1
```

Note: If you're using this package within Deadline Cloud Service-Managed Fleet (SMF), these prerequisites are already configured for the job-user and no additional setup is required.
