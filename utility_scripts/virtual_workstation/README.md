# Virtual workstation setup

Provisioning scripts that turn a fresh Linux or Windows workstation into a ready-to-use AWS Deadline Cloud submission machine. An artist who logs in finds Blender and the Deadline Cloud submitter already installed, alongside Deadline Cloud monitor with a profile configured. The only remaining step is signing in.

## What this sample demonstrates

How to complete every part of workstation setup that normally requires a person clicking through installers and a monitor sign-in dialog:

* Installing Blender from an official release archive.
* Installing the Deadline Cloud submitter with a silent, unattended installer resolved from the published submitter manifest and verified against its SHA-256 checksum.
* Enabling the Blender add-on in the artist's Blender preferences, which the unattended installer alone does not do.
* Installing Deadline Cloud monitor from its Linux package or Windows installer.
* Creating a monitor profile non-interactively with `deadline-cloud-monitor create-profile`, so the profile exists before anyone signs in.

Run these during instance provisioning (EC2 user data, an AMI or image bake, or by hand on a workstation VM).

## Prerequisites

* A Linux or Windows workstation image with a desktop environment already present, because the scripts do not install one. Blender, the submitter GUI, and the monitor are all desktop applications. An AWS Deadline Cloud base image, a NICE DCV workstation, or a Windows Server image with the Desktop Experience all work.
* Administrator access: `root` on Linux, an elevated PowerShell session on Windows. On Windows that session should be the artist's own account, because the monitor and its profile install per user.
* Outbound HTTPS to `downloads.deadlinecloud.amazonaws.com` and to the Blender download mirror.
* Your monitor URL, which looks like `https://<subdomain>.<region>.deadlinecloud.amazonaws.com/`. Find it on the **Monitors** page of the Deadline Cloud console.
* Optional: AWS credentials with `deadline:ListMonitors` permission on the instance. See [Monitor ID discovery](#monitor-id-discovery).

Linux support covers Debian-family (`apt`) and RHEL-family (`dnf`) distributions.

## How it works

Each script runs the same five steps.

1. **Parse the monitor URL** into its subdomain and region. The region is where the monitor lives; the subdomain identifies it. The default profile name is `<subdomain>-<region>`.
2. **Install Blender** by downloading the official archive for the requested version and unpacking it to a fixed prefix (`/opt/blender` or `C:\Program Files\Blender`).
3. **Install the submitter.** The script reads [`manifest.json`](https://downloads.deadlinecloud.amazonaws.com/submitters/manifest.json) to resolve the latest version for the platform. It downloads that pinned installer, verifies its published SHA-256 checksum, and runs it with `--mode unattended`. Only the Blender components are enabled, and the installer is told where Blender lives so it can match add-on files to the Blender version.
4. **Enable the Blender add-on.** The unattended installer stages the add-on under the submitter prefix but cannot enable it, because add-ons live in Blender's *per-user* preferences and the install runs at system scope. The script runs the installer's own `add_submitter_to_pref.py` through Blender in `--background` mode as the workstation user, then reads the preferences back to confirm the add-on registered.
5. **Install the monitor and create a profile.** After installing the monitor, the script calls `deadline-cloud-monitor create-profile`, a non-GUI subcommand that writes the profile and exits without needing a display. The monitor added it in version 1.0.2 for exactly this purpose: letting IT administrators configure Deadline Cloud client tools so artists do not have to set up profiles by hand. It is not covered in the Deadline Cloud user guide, which documents only the interactive profile wizard, so run `deadline-cloud-monitor create-profile --help` on the monitor version you deploy to confirm the arguments.

### What the profile contains

`create-profile` writes an AWS profile that resolves credentials through the monitor rather than through IAM Identity Center SSO stanzas:

```ini
[profile mymonitor-us-west-2]
region=us-west-2
credential_process=cat "/home/artist/.cache/com.amazonaws.deadline.monitor/credentials_mymonitor-us-west-2.json"
user_id=
identity_store_id=
monitor_id=monitor-00000000000000000000000000000000
```

It also points the Deadline Cloud CLI at that profile in `~/.deadline/config`:

```ini
[deadline-cloud-monitor]
path=/usr/bin/deadline-cloud-monitor

[defaults]
aws_profile_name=mymonitor-us-west-2
```

This shape has consequences worth knowing about:

* `user_id` and `identity_store_id` are empty and `credential_process` reads a cache file that does not exist yet. The profile produces no usable credentials until the artist signs in to the monitor once. That sign-in is the intended remaining step, not a defect.
* The profile must be created *as the workstation user*, because the cache path baked into `credential_process` is inside that user's home directory. The same applies to the monitor install on Windows and to Blender's add-on preferences on both platforms.

Each platform handles that differently:

* **Linux** runs the per-user steps through `runuser`, so provisioning as `root` works. Pass `--workstation-user` to name the artist's account.
* **Windows** cannot run a process as another local user without that user's password. Run the script in an elevated session as the artist's own account. To provision from a separate admin account instead, pass `-SkipMonitor` for the machine-wide parts, then run the script again as the artist. The script fails fast rather than writing the profile into the wrong home directory.

### Monitor ID discovery

`create-profile` requires a `--monitor-id` argument. Current monitor IDs are `monitor-` followed by 32 hexadecimal characters, matching the [`GetMonitor` API pattern](https://docs.aws.amazon.com/deadline-cloud/latest/APIReference/API_GetMonitor.html). The monitor stores whatever value it is given without validating the format, and replaces it with the authoritative value on the artist's first sign-in.

The scripts try to get the real ID, but do not require it:

* If you pass `--monitor-id` / `-MonitorId`, that value is used.
* Otherwise, if the AWS CLI is present and credentials are available, the script calls `deadline:ListMonitors` and matches on the subdomain from your monitor URL.
* Otherwise, the script writes a placeholder of 32 zeros and warns. The profile still works, because the first sign-in corrects the ID.

Passing the ID explicitly, or giving the instance a role with `deadline:ListMonitors`, produces a fully correct profile before anyone signs in.

## Run or submit

Linux, as root:

```console
sudo ./setup_workstation_linux.sh \
    --monitor-url https://mymonitor.us-west-2.deadlinecloud.amazonaws.com/
```

Windows, in an elevated PowerShell session:

```console
.\setup_workstation_windows.ps1 `
    -MonitorUrl https://mymonitor.us-west-2.deadlinecloud.amazonaws.com/
```

Useful variants:

```console
# Provisioning runs as root but the artist logs in as a different user
sudo ./setup_workstation_linux.sh \
    --monitor-url https://mymonitor.us-west-2.deadlinecloud.amazonaws.com/ \
    --workstation-user artist

# Pin the monitor ID so the profile is correct before the first sign-in
sudo ./setup_workstation_linux.sh \
    --monitor-url https://mymonitor.us-west-2.deadlinecloud.amazonaws.com/ \
    --monitor-id monitor-1234567890abcdef1234567890abcdef

# A different Blender version, and only the monitor profile on a machine that
# already has Blender and the submitter
sudo ./setup_workstation_linux.sh \
    --monitor-url https://mymonitor.us-west-2.deadlinecloud.amazonaws.com/ \
    --blender-version 4.2.0
sudo ./setup_workstation_linux.sh \
    --monitor-url https://mymonitor.us-west-2.deadlinecloud.amazonaws.com/ \
    --skip-blender --skip-submitter
```

## Parameters and outputs

| Linux | Windows | Default | Purpose |
|---|---|---|---|
| `--monitor-url` | `-MonitorUrl` | required | Monitor URL. Required unless the monitor step is skipped. |
| `--profile-name` | `-ProfileName` | `<subdomain>-<region>` | Name of the AWS profile to create. |
| `--monitor-id` | `-MonitorId` | discovered | Monitor ID. See [Monitor ID discovery](#monitor-id-discovery). |
| `--workstation-user` | `-WorkstationUser` | invoking user | Account that signs in to the monitor and owns the profile. On Windows it must match the account running the script. |
| `--blender-version` | `-BlenderVersion` | `4.5.0` | Blender version to install. |
| `--blender-mirror` | `-BlenderMirror` | `https://download.blender.org/release` | Base URL for Blender downloads. |
| `--skip-blender` | `-SkipBlender` | off | Do not install Blender. |
| `--skip-submitter` | `-SkipSubmitter` | off | Do not install the submitter. |
| `--skip-monitor` | `-SkipMonitor` | off | Do not install the monitor or create a profile. |

Only Blender versions the submitter supports are accepted: 3.6, 4.0 through 4.5, 5.0, and 5.1. The script fails early on any other version rather than installing a Blender the submitter cannot target.

What ends up on the machine:

| Path | Linux | Windows |
|---|---|---|
| Blender | `/opt/blender`, symlinked to `/usr/local/bin/blender` | `C:\Program Files\Blender` |
| Submitter and Deadline Cloud CLI | `/opt/DeadlineCloudSubmitter` | `C:\Program Files\DeadlineCloudSubmitter` |
| Monitor | `/usr/bin/deadline-cloud-monitor` | `%LOCALAPPDATA%\DeadlineCloudMonitor` |
| AWS profile | `~/.aws/config` | `%USERPROFILE%\.aws\config` |
| Deadline Cloud CLI config | `~/.deadline/config` | `%USERPROFILE%\.deadline\config` |

The submitter installer adds the `deadline` CLI to `PATH` itself, through `/etc/profile.d/deadline.sh` on Linux. It is available in new login shells, not in the shell that ran the script.

## Security, cost, and cleanup

* **No credentials are stored.** The scripts never write secrets. The profile delegates to the monitor, which acquires credentials only when the artist signs in interactively.
* **Least privilege for discovery.** The only AWS call is `deadline:ListMonitors`, which is read-only. An instance role scoped to that single action is enough, and nothing here needs write access. You can omit credentials entirely and accept the placeholder monitor ID.
* **Installers are verified.** Submitter installers are checked against their published SHA-256 checksums, and the script fails on a mismatch. Blender archives are downloaded over HTTPS. If you mirror them internally, point `--blender-mirror` at a source you trust.
* **Licensing.** Blender is distributed under the GNU GPL. Review its license terms for your use.
* **Cost.** The scripts create no AWS resources and incur no Deadline Cloud charges. Running the workstation instance itself is billable, and jobs submitted from it are billed normally.
* **Cleanup.** To remove the submitter, run `/opt/DeadlineCloudSubmitter/uninstall` or the Windows equivalent that its installer provides. Remove the monitor with your package manager or through Windows "Apps & features", and delete `/opt/blender`. Finally, remove the profile stanza from `~/.aws/config` and the `[defaults]` entry from `~/.deadline/config`.

## Troubleshooting

**The monitor fails to start with `libssl.so.1.1: cannot open shared object file`.** The monitor links against OpenSSL 1.1, which current distributions no longer include. The Linux script installs the compatibility package first (`libssl1.1` on Debian-family, `compat-openssl11` from EPEL on RHEL 9 derivatives). If it fails, install that package for your distribution and re-run.

**Blender downloads fail with HTTP 403.** `download.blender.org` rejects some automated clients. Use `--blender-mirror` with an [official Blender mirror](https://mirror.blender.org/), or with an archive you host internally.

**The Deadline Cloud menu is missing in Blender.** The add-on registers in per-user Blender preferences, so it applies only to the account it was registered for. On Linux, confirm you passed the right `--workstation-user`. On Windows, confirm the script ran as the artist's account; if it did not, it prints the exact command to run in their session. To check the state directly:

```console
blender --background --python-expr 'import bpy; print("deadline_cloud_blender_submitter" in bpy.context.preferences.addons.keys())'
```

**Submission fails with a credentials error.** Expected until the artist signs in to the monitor once, because `credential_process` reads a cache file the sign-in creates. Verify with `deadline auth status`.

**`create-profile` reports success but no profile appears.** `create-profile` exits 0 even when it fails, so both scripts parse its output and then read back `~/.aws/config` to confirm. If they report a failure, run the `create-profile` command by hand to see the underlying message.

## Related resources

* [Deadline Cloud monitor setup](https://docs.aws.amazon.com/deadline-cloud/latest/userguide/submitter.html)
* [Install Deadline Cloud submitters](https://docs.aws.amazon.com/deadline-cloud/latest/userguide/submitter-installers.html)
* [Deadline Cloud CLI](https://github.com/aws-deadline/deadline-cloud)
* [Blender download mirror](https://mirror.blender.org/)
