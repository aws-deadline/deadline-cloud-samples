# Cinema 4D 2026 Conda Recipe

This recipe packages Cinema 4D 2026.3.3 for Windows Deadline Cloud workers. Unlike an installer-based
recipe, it consumes a ZIP archive created from an existing Cinema 4D installation because the public
package build environment does not provide the Administrator permissions required by the installer.

## Prerequisites

You need:

* Access to the Cinema 4D 2026.3.3 Windows installer and a valid Maxon license.
* A temporary Windows Server 2022 host where you have Administrator permissions.
* At least 64 GiB of storage for the installation and archive.
* The Deadline Cloud CLI and access to the package build queue described in the
  [Conda recipe overview](../README.md#infrastructure-setup-prerequisites).

The temporary host and package build job can incur AWS charges. Terminate the host after uploading
or downloading the archive. Do not place license credentials in the archive.

## Create the Windows archive

1. Launch a temporary Windows Server 2022 EC2 instance with no inbound access. Use AWS Systems
   Manager Session Manager and port forwarding if you need an RDP session.
2. Install Cinema 4D 2026.3.3 using the default installation directory:
   `C:\Program Files\Maxon Cinema 4D 2026`.
3. Optionally install and configure Redshift before creating the archive. The resulting package will
   contain exactly the components installed on this host.
4. Restart the instance so installation changes are complete.
5. In an Administrator PowerShell session, create the archive and calculate its SHA256 for transfer
   verification:

   ```powershell
   Set-Location 'C:\Program Files'
   Compress-Archive `
       -Path '.\Maxon Cinema 4D 2026\' `
       -DestinationPath '.\Cinema4D_2026_2026.3.3_Win.zip'
   (Get-FileHash `
       -Path '.\Cinema4D_2026_2026.3.3_Win.zip' `
       -Algorithm SHA256).Hash.ToLower()
   ```

6. Record the SHA256 and copy `Cinema4D_2026_2026.3.3_Win.zip` to
   `conda_recipes/archive_files/` in this repository. If the archive is in S3, download it from your
   private bucket rather than committing it to the repository. Calculate the downloaded file's
   SHA256 and compare it with the recorded value.
7. Terminate the temporary instance.

## Build the package

From the `conda_recipes` directory, submit the Windows build:

```console
submit-package-job cinema4d-2026
```

The package installs Cinema 4D under `%CONDA_PREFIX%\cinema4d` and configures
`C4D_LOCATION`, `C4D_COMMANDLINE_EXECUTABLE`, and `C4D_VERSION` during Conda activation.

## Plugin Sync

This package includes Plugin Sync activation hooks. During a Deadline Cloud session, the hooks
download the contents of the following S3 prefix and add the session directory to Cinema 4D's
`g_additionalModulePath`:

```text
s3://<job-attachments-bucket>/<root-prefix>/plugins/windows/cinema4d/2026.3/
```

Upload extracted plugin directories and files under that prefix. Plugin Sync also downloads shared
files from `plugins/generic/`. Both non-empty directories are added to
`g_additionalModulePath`. The worker role must be able to read the objects. See the
[Plugin Sync documentation](https://docs.aws.amazon.com/deadline-cloud/latest/developerguide/plugin-sync.html)
for the job attachment bucket variables and upload workflow.

For plugins that change less frequently or need their own dependency metadata, compare the
[Cinema 4D plugin recipes](../cinema4d-2025/#instructions-for-cinema-4d-plugin-packages).

### Test Plugin Sync

The [`plugin_sync_test`](plugin_sync_test/) directory contains a minimal `.pyp` file that does not
register any Cinema 4D commands or require a plugin ID. From this sample directory, upload it to the
version-specific Plugin Sync prefix:

```console
aws s3 cp plugin_sync_test \
    s3://<job-attachments-bucket>/<root-prefix>/plugins/windows/cinema4d/2026.3/plugin_sync_test/ \
    --recursive
```

Submit a small Cinema 4D job that starts Cinema 4D 2026.3.3, then look for these messages in its
session log:

```text
Plugin Sync: Added <session-directory>/deadline-plugins/cinema4d to g_additionalModulePath
CINEMA4D_PLUGIN_SYNC_TEST_LOADED
```

The plugin also writes `cinema4d-plugin-sync-test.loaded` to `OPENJD_SESSION_WORKING_DIR`. Seeing
the log marker confirms that Cinema 4D discovered and executed the synchronized `.pyp` file. Remove
the test directory from S3 after verification.

## Troubleshooting

* If the build cannot find the source, verify the ZIP filename and its location under
  `conda_recipes/archive_files/`.
* If archive transfer verification fails, download it again and compare its SHA256 with the value
  calculated on the temporary host.
* If Cinema 4D cannot find a synchronized plugin, verify the `2026.3` S3 prefix and inspect
  the Conda activation output for `Plugin Sync` messages.
* Cinema 4D and bundled renderers require their own licenses at runtime.
