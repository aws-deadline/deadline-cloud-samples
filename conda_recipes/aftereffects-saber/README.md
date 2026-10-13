# Saber Plugin Conda Recipe for After Effects

## About
This recipe installs the `Saber.aex` plugin file into the `Plug-ins` directory of the After Effects (AE)
Conda package. Use it as a template for recipes that add other plugins to your After Effects setup on
Deadline Cloud.

For plugins that change often, you can deliver them without building a package. See
[Plugin Sync](../aftereffects-25.1/README.md#plugin-sync) in the After Effects recipe.

## Plugin solution for After Effects
The After Effects package sets the `AE_LOCATION` environment variable to its installation directory.
After Effects loads plugins from `$AE_LOCATION/Plug-ins`, so plugin recipes install their files there.
Plugins for Windows workers must have the `.aex` extension.

## Create a Windows archive of Saber
Follow these instructions to install After Effects 25 on a new EC2 instance as Administrator, install
the Saber plugin, and create an archive of the plugin for the recipe. If you have a Windows workstation
with After Effects installed, you can do steps 3, 4, 6, and 7 without starting an EC2 instance.

1. Launch a fresh Windows Server 2022 instance.
   1. From the AWS EC2 management console, select the option to Launch instance.
   2. Enter instance name "Create Windows AE archive".
   3. Select "Microsoft Windows Server 2022 Base" for the AMI.
   4. Select an instance type with enough vCPUs and RAM. A c5.4xlarge has 16 vCPUs and 32 GiB RAM.
   5. Select "Proceed without a key pair" for the "Key pair (login)" option.
   6. Make sure that "Allow RDP traffic" is unchecked. We will use SSM port forwarding to avoid sending RDP
      protocol traffic directly over the internet.
   7. Set the storage to at least 64 GiB. Adjust other settings as you like, e.g. if you want an encrypted volume of type gp3.
   8. Select "Launch instance."
   9. If it asks, select "Proceed without key pair" and proceed with the launch.
   10. Once it launched, navigate to the instance detail page. Select "Connect," and with "Session manager" selected, again select "Connect."
       If it says "SSM Agent is not online," you may have to wait a few minutes for it to initialize.
   11. Create a secure password for the Administrator account. From the Administrator powershell window that session manager,
       enter the following command with your secure password substituted to change the password.
       1. `net user Administrator MY_SECURE_PASSWORD`
2. Connect to the instance with SSM port forwarding and RDP.
   1. Install or update the AWS CLI v2 from https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html.
   2. Install or update the Session Manager plugin from https://docs.aws.amazon.com/systems-manager/latest/userguide/session-manager-working-with-install-plugin.html.
   3. Run the following command, using AWS credentials that have suitable permissions, to start the SSM port forwarding. Replace INSTANCE_ID with the one you launched.
      1. `aws ssm start-session --document-name AWS-StartPortForwardingSession --parameters "localPortNumber=33389,portNumber=3389" --target INSTANCE_ID`
   4. Open RDP, and enter the following connection details:
      1. Computer: `localhost:33389`
      2. User name: `Administrator`
   5. Enter the password you set for Administrator after you created the instance. You should now have a remote desktop session to your instance.
3. Install Adobe AE 25 on the instance.
   1. Download Adobe Creative Cloud after logging into your Adobe account.
   2. Download Adobe AE 25 from Creative Cloud App.
   3. The AE installer will launch. Proceed to install as normal with the components you want included.
4. Install the Saber plugin.
   1. Download the [Saber plugin](https://www.videocopilot.net/blog/2016/03/new-plug-in-saber-now-available-100-free) and install it.
   2. Log in with a powershell window again, either from the EC2 management console session manager or reconnecting to RDP.
   3. Run the following commands to create the archive.
      1. `Compress-Archive -Path 'C:\Program Files\Adobe\Adobe After Effects 2025\Support Files\Plug-ins\VideoCopilot\Saber.aex' -DestinationPath Saber_1_0_40_Windows_installation.zip`
      2. `(Get-FileHash -Path "Saber_1_0_40_Windows_installation.zip" -Algorithm SHA256).Hash.ToLower()`
   4. Record the file sha256 hash, and upload the archive to your private S3 bucket. You can use a PowerShell command like
      `Write-S3Object -BucketName MY_BUCKET_NAME -Key Saber_1_0_40_Windows_installation.zip -File Saber_1_0_40_Windows_installation.zip`.
5. From the AWS EC2 management console, select the instance you used and terminate it.
6. Download the zip file to the `conda_recipes/archive_files` directory of your clone of this repository. Replace the Windows `sha256` value in
   [`recipe/meta.yaml`](recipe/meta.yaml) with the SHA256 you recorded.
7. Follow the [Conda recipe overview](../README.md) to build the recipe into your Conda channel.
