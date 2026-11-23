# Autodesk 3ds Max 2025 conda build recipe

> **Autodesk Cloud Rights:** Autodesk 3ds Max has its own licensing requirements separate from AWS.
> Confirm you have the appropriate licenses before proceeding. See additional details on
> [Autodesk Cloud Rights for 3ds Max](https://www.autodesk.com/support/technical/article/caas/sfdcarticles/sfdcarticles/Subscription-Benefits-FAQ-Cloud-Rights.html).

## Creating an archive file for Windows

The Windows installer requires Administrator permissions that are not available in most conda package
build environments, such as on Deadline Cloud service-managed fleets. Follow these instructions to
install 3ds Max 2025 on a freshly created EC2 instance as Administrator, and create an archive file
for use by the conda build recipe.

1. Launch a fresh Windows Server 2022 instance (any current Windows Server AMI with enough vCPUs and RAM works).
   1. From the AWS EC2 management console, select the option to Launch instance.
   2. Enter instance name "Create Windows 3ds Max archive".
   3. Select "Microsoft Windows Server 2022 Base" for the AMI.
   4. Select an instance type with enough vCPUs and RAM, for example c5.4xlarge has 8 vCPUs and 16 GiB RAM.
   5. Select "Proceed without a key pair" for the "Key pair (login)" option.
   6. We will use SSM port forwarding to avoid sending RDP protocol traffic directly over the internet.
      1. Make sure that "Allow RDP traffic" is unchecked.
      2. Make sure the security group does not allow any inbound traffic.
      3. Make sure to remove any public IP addresses from the instance.
   7. Set the storage to at least 64 GiB. Adjust other settings as you like, e.g. if you want an encrypted volume of type gp3.
   8. Select "Launch instance."
   9. If it asks, select "Proceed without key pair" and proceed with the launch.
   10. Once it launched, navigate to the instance detail page. Select "Connect," and with "Session manager" selected, again select "Connect."
       If it says "SSM Agent is not online," you may have to wait a few minutes for it to initialize.
   11. Create a secure password for the Administrator account. From the Administrator PowerShell window that session manager,
       enter the following command with your secure password substituted to change the password.
       1. `net user Administrator MY_SECURE_PASSWORD`
2. Connect to the instance with SSM port forwarding and RDP.
   1. Install or update the AWS CLI v2 from https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html.
   2. Install or update the Session Manager plugin from https://docs.aws.amazon.com/systems-manager/latest/userguide/session-manager-working-with-install-plugin.html.
   3. Run the following command, using AWS credentials that have suitable permissions, to start the SSM port forwarding. Replace INSTANCE_ID with the one you launched.
      1. `aws ssm start-session --document-name AWS-StartPortForwardingSession --parameters "localPortNumber=3389,portNumber=3389" --target INSTANCE_ID`
   4. Open RDP, and enter the following connection details:
      1. Computer: `localhost:3389`
      2. User name: `Administrator`
   5. Enter the password you set for Administrator after you created the instance. You should now have a remote desktop session to your instance.
3. Install 3ds Max 2025 on the instance.
   1. Download the 3ds Max 2025 installer for Windows from Autodesk (for example via Autodesk Access).
   2. Run the installer on the EC2 instance and complete installation using the default settings.
   3. *(Optional)* Install the `deadline-cloud-for-3ds-max` Python package inside 3ds Max if you want the Deadline Cloud
      integration baked into the package. Note that doing so pins the adaptor at archive-creation time and skips runtime
      upgrades that the Deadline Cloud conda channel would otherwise provide; for production fleets, prefer letting the
      channel deliver the adaptor at job-init time.
4. From an Administrator PowerShell window, create the archive from the installed files and capture its hash.
   1. `Compress-Archive -Path 'C:\Program Files\Autodesk\3ds Max 2025' -DestinationPath Autodesk_3dsMax_2025_Windows_installation.zip`
   2. `(Get-FileHash -Path "Autodesk_3dsMax_2025_Windows_installation.zip" -Algorithm SHA256).Hash.ToLower()`
5. Upload the zip to your private S3 bucket. You can use a PowerShell command like
   `Write-S3Object -BucketName MY_BUCKET_NAME -Key Autodesk_3dsMax_2025_Windows_installation.zip -File Autodesk_3dsMax_2025_Windows_installation.zip`.
6. Terminate the EC2 instance.
7. Download the zip file to the `conda_recipes/archive_files` directory in your git clone of the
   [deadline-cloud-samples](https://github.com/aws-deadline/deadline-cloud-samples) repository for
   submitting package build jobs, and update the Windows source artifact hash in `meta.yaml`.

The build script installs `pywin32` into 3ds Max's embedded Python to enable automation and exports
environment variables (`ADSK_3DSMAX_*`) so jobs can find both the GUI (`3dsmax.exe`) and batch
(`3dsmaxbatch.exe`) executables. See the *Notes on environment variables* section below for details.

## Build tool

This recipe uses `conda-build` to stay consistent with the existing 3ds Max test pipeline. Migration to
[`rattler-build`](https://github.com/prefix-dev/rattler-build) (already adopted by `blender-5.1`,
`maya-2026`, and others in this repository) is tracked as a follow-up — feel free to open an issue or PR.

## Notes on environment variables

The activation script exports the following variables so jobs and the
[`deadline-cloud-for-3ds-max`](https://github.com/aws-deadline/deadline-cloud-for-3ds-max) adaptor can
locate the right executable:

| Variable | Path | When to use |
| --- | --- | --- |
| `ADSK_3DSMAX_BATCH_EXE` | `…/3ds Max 2025/3dsmaxbatch.exe` | **Default.** Non-GUI batch render. Compliant with Autodesk Cloud Rights, which allow up to 10 batch render licenses per GUI subscription seat. |
| `ADSK_3DSMAX_EXECUTABLE` | `…/3ds Max 2025/3dsmax.exe` | GUI executable. Use only if your Autodesk subscription's GUI seats cover the rendering workload. |
| `3DSMAX_EXECUTABLE` (`.bat` only) | `…/3ds Max 2025/3dsmaxbatch.exe` | Legacy variable consumed by the current adaptor; kept pointing at the batch exe so existing jobs render with the safer default. |

Limitations:

- POSIX shells cannot export variable names that begin with a digit, so `3DSMAX_EXECUTABLE` is set
  only by the `.bat` activation script. Bash activation relies on the `ADSK_*` variables.
- The current adaptor reads `3DSMAX_EXECUTABLE` only. Until
  [deadline-cloud-for-3ds-max#190](https://github.com/aws-deadline/deadline-cloud-for-3ds-max/issues/190)
  ships, jobs that need to switch between batch and GUI explicitly will require either a small adaptor
  hot-patch or a fleet-level override of `3DSMAX_EXECUTABLE`. Once that adaptor change lands, the
  adaptor will read both `ADSK_3DSMAX_BATCH_EXE` and `ADSK_3DSMAX_EXECUTABLE` and pick the right one
  for the job.

## Renderer plug-ins (e.g., Corona)

If you intend to render with Corona or other third-party renderers, ensure their DLLs are present in the
3ds Max plug-in search path (e.g., `Autodesk/3ds Max 2025/Plugins`). The main `3dsmax` package does not
carry Corona binaries; use the `3dsmax-corona` package to place the real Corona DLLs into the
environment. Without that package (or manually copied DLLs), Max will warn about missing plug-ins and
the adaptor will fail.
