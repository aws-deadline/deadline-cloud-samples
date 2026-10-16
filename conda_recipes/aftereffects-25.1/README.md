# Adobe After Effects 25.1 Conda Recipe

This recipe packages Adobe After Effects 25.1 for Windows Deadline Cloud workers. It consumes a ZIP
archive of an existing After Effects installation because the installer requires Administrator
permissions that most package build environments, such as Deadline Cloud service-managed fleets, do
not provide.

The package installs After Effects under `%CONDA_PREFIX%\aftereffects` and sets `AE_LOCATION`,
`AE_VERSION`, and `AE_PLUGIN_SYNC_VERSION` during Conda activation. It also adds the installation to
`PATH` so jobs can run `aerender`.

## Prerequisites

You need:

* An Adobe account with access to After Effects 25.1 and a valid license for rendering.
* A temporary Windows Server 2022 host where you have Administrator permissions, or a Windows
  workstation with After Effects 25.1 installed.
* At least 64 GiB of storage for the installation and archive.
* The Deadline Cloud CLI and access to the package build queue described in the
  [Conda recipe overview](../README.md#infrastructure-setup-prerequisites).

The temporary host and package build job can incur AWS charges. Terminate the host after uploading
or downloading the archive. Do not place license credentials in the archive.

## Create the Windows archive

If you have a Windows workstation with After Effects 25.1 installed, skip to step 3.5.

1. Launch a fresh Windows Server 2022 instance.
   1. From the AWS EC2 management console, select **Launch instance**.
   2. Enter the instance name "Create Windows AE archive".
   3. Select "Microsoft Windows Server 2022 Base" for the AMI.
   4. Select an instance type with enough vCPUs and RAM, such as c5.4xlarge with 16 vCPUs and 32 GiB RAM.
   5. Select **Proceed without a key pair** for the **Key pair (login)** option.
   6. Clear **Allow RDP traffic**. The following steps use SSM port forwarding instead of sending RDP
      traffic directly over the internet.
   7. Set the storage to at least 64 GiB. Adjust other settings as needed, such as using an encrypted
      gp3 volume.
   8. Select **Launch instance**. If prompted, select **Proceed without key pair**.
   9. After the instance launches, open its detail page. Select **Connect**, then, with
      **Session Manager** selected, select **Connect** again. If it says "SSM Agent is not online,"
      wait a few minutes for the agent to start.
   10. In the Administrator PowerShell window that Session Manager opens, set a secure password for
       the Administrator account:

       ```powershell
       net user Administrator MY_SECURE_PASSWORD
       ```
2. Connect to the instance with SSM port forwarding and RDP.
   1. Install or update the [AWS CLI v2](https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html).
   2. Install or update the
      [Session Manager plugin](https://docs.aws.amazon.com/systems-manager/latest/userguide/session-manager-working-with-install-plugin.html).
   3. Start SSM port forwarding with AWS credentials that have suitable permissions. Replace
      `INSTANCE_ID` with the ID of the instance you launched.

      ```console
      aws ssm start-session --document-name AWS-StartPortForwardingSession --parameters "localPortNumber=33389,portNumber=3389" --target INSTANCE_ID
      ```
   4. Open an RDP client and connect to `localhost:33389` as `Administrator` with the password you
      set.
3. Install After Effects 25.1 on the instance.
   1. Sign in to your Adobe account and download Adobe Creative Cloud.
   2. Download After Effects 25.1 from the Creative Cloud app.
   3. Install After Effects with the components that your jobs need.
   4. Open a PowerShell window, either from Session Manager or the RDP session.
   5. Create the archive and calculate its SHA256:

      ```powershell
      Compress-Archive `
          -Path 'C:\Program Files\Adobe\Adobe After Effects 2025\Support Files' `
          -DestinationPath Adobe_AfterEffects_25_1_Windows_installation.zip
      (Get-FileHash `
          -Path Adobe_AfterEffects_25_1_Windows_installation.zip `
          -Algorithm SHA256).Hash.ToLower()
      ```
   6. Record the SHA256 and upload the archive to your private S3 bucket:

      ```powershell
      Write-S3Object -BucketName MY_BUCKET_NAME -Key Adobe_AfterEffects_25_1_Windows_installation.zip -File Adobe_AfterEffects_25_1_Windows_installation.zip
      ```
4. From the AWS EC2 management console, terminate the instance.
5. Download the archive to the `conda_recipes/archive_files` directory of your clone of this
   repository. Replace the Windows `sha256` value in [`recipe/meta.yaml`](recipe/meta.yaml) with the
   SHA256 you recorded.

## Build the package

From the `conda_recipes` directory, submit the Windows build:

```console
submit-package-job aftereffects-25.1
```

## Plugin Sync

This package includes Plugin Sync activation hooks. During a Deadline Cloud session, the hooks
download the contents of the following S3 prefix into the After Effects `Plug-ins` directory:

```text
s3://<job-attachments-bucket>/<root-prefix>/plugins/windows/aftereffects/25.1/
```

Upload `.aex` files, or plugin directories that contain them, under that prefix. The worker role must
be able to read the objects. See the
[Plugin Sync documentation](https://docs.aws.amazon.com/deadline-cloud/latest/developerguide/plugin-sync.html)
for the variables that identify the bucket and for the upload workflow.

After Effects has no environment variable for adding plugin directories, so this recipe works
differently from the Plugin Sync hooks in other recipes:

* The activate hook copies the plugins into `%AE_LOCATION%\Plug-ins\deadline-plugin-sync`, which After
  Effects scans when it starts. The deactivate hook removes that directory so later sessions that
  reuse the environment start without them.
* Plugins are Windows binaries, so the hooks don't use the `plugins/generic/` prefix.
* The hooks skip a `startup/` subfolder because scripts don't belong in the `Plug-ins` directory.

Plugin Sync delivers plugin files only. If a plugin requires license activation, configure licensing
separately.

For plugins that change less often, or for a versioned set of plugins, compare the
[Saber recipe](../aftereffects-saber/) and the [plugin bundle recipe](../aftereffects-plugin-bundle/).

### Test Plugin Sync

This repository doesn't include plugin binaries, so test with any After Effects plugin that you have
the right to install on render workers, such as the free Saber plugin from Video Copilot.

1. Upload the plugin to the version-specific prefix:

   ```console
   aws s3 cp Saber.aex s3://<job-attachments-bucket>/<root-prefix>/plugins/windows/aftereffects/25.1/Saber.aex
   ```
2. Submit a job that renders a project that applies the plugin's effect.
3. Look for these messages in the session log:

   ```text
   Plugin Sync: Downloading After Effects plugins from s3://<job-attachments-bucket>/<root-prefix>/plugins/windows/aftereffects/25.1/
   Plugin Sync: Installed plugins into <conda-prefix>/aftereffects/Plug-ins/deadline-plugin-sync; file count: 1
   ```

   If After Effects can't find the plugin, `aerender` logs "This project contains a reference to a
   missing effect" and renders the layer without the effect. `aerender` can exit with code 0 in this
   case, so also check the rendered output.
4. Remove the test plugin from S3 after verification.

To test the hooks without S3 access or an After Effects installation, run the unit tests from the
`recipe` directory in a bash shell, such as Git Bash on Windows:

```console
bash test_zzz_scripts.sh
```

## Troubleshooting

* If the build can't find the source, verify the ZIP filename and its location under
  `conda_recipes/archive_files/`.
* If After Effects can't find a synchronized plugin, verify the `25.1` S3 prefix and look for
  `Plugin Sync` messages in the Conda activation output.
* "Could not fully remove" in the deactivate output means a process that After Effects started still
  has a plugin file open. Session cleanup removes the environment after the session ends.
* After Effects requires its own license at runtime.
