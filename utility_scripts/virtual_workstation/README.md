# Virtual workstation setup

Example scripts that turn a fresh Linux or Windows workstation into an AWS Deadline Cloud submission machine. An artist who logs in finds Blender and the Deadline Cloud submitter installed, alongside Deadline Cloud monitor with a profile already configured. The only remaining step is signing in.

Treat each script as a worked example to copy and adapt. Each takes one argument and keeps its settings as constants at the top, so the whole flow reads top to bottom.

## What this sample demonstrates

How to complete the workstation setup that normally requires a person clicking through installers and a monitor sign-in dialog:

* Installing Blender from an official release archive.
* Installing the Deadline Cloud submitter with its silent installer, resolved from the published submitter manifest.
* Enabling the submitter's Blender add-on, which the silent installer alone does not do.
* Installing Deadline Cloud monitor.
* Creating a monitor profile non-interactively with `deadline-cloud-monitor create-profile`, so the profile exists before anyone signs in.

Run either script during provisioning, from EC2 user data, during an AMI or image bake, or by hand on a workstation VM.

Blender stands in for whichever DCC you run. It is used here because it installs unattended from a public archive with no license server, which keeps the example runnable as-is. See [Adapting to another DCC](#adapting-to-another-dcc).

## Prerequisites

* Ubuntu 22.04, Debian 12, or a Windows image, with a desktop environment already present because the scripts do not install one. Blender, the submitter GUI, and the monitor are all desktop applications. An AWS Deadline Cloud base image, a NICE DCV workstation, or a Windows Server image with the Desktop Experience all work.

  Deadline Cloud monitor's `.deb` depends on `libwebkit2gtk-4.0-37`, which Ubuntu 24.04 and Debian 13 no longer publish. The Linux script checks for it up front and stops with an explanation rather than failing partway through. On a later release, add a repository that provides the 4.0 build.
* Administrator access: `root` on Linux, an elevated PowerShell session on Windows.
* Outbound HTTPS to `downloads.deadlinecloud.amazonaws.com` and to the Blender mirror.
* A working default web browser. Deadline Cloud monitor hands off to it to complete sign-in, so without one the artist sees "Failed to execute default Web Browser". Windows Server images include Microsoft Edge. On Ubuntu 22.04 and later, Firefox and Chromium are published only as snaps, which do not work in every remote-desktop session. Installing Firefox from the [Mozilla apt repository](https://support.mozilla.org/kb/install-firefox-linux) gives a working browser.
* Your monitor URL, from the **Monitors** page of the Deadline Cloud console. It must include the Region segment, as in `https://mystudio.us-west-2.deadlinecloud.amazonaws.com/`.
* No AWS credentials. The scripts call no AWS APIs.

The Linux script targets Debian-family images. To use another distribution, replace the `apt-get` calls, install the monitor from its `.rpm` rather than the `.deb`, and satisfy OpenSSL 1.1 the way that distribution expects.

## Run

Linux, as root:

```console
sudo ./setup_workstation_linux.sh https://mystudio.us-west-2.deadlinecloud.amazonaws.com/
```

When provisioning runs as `root` but a different account signs in, name that account:

```console
sudo ./setup_workstation_linux.sh https://mystudio.us-west-2.deadlinecloud.amazonaws.com/ artist
```

Windows, in an elevated PowerShell session **as the artist's own account**. Start PowerShell with **Run as administrator** first: the script declares `#Requires -RunAsAdministrator`, so launching it from an unelevated shell fails with `ScriptRequiresElevation` rather than prompting.

```console
.\setup_workstation_windows.ps1 https://mystudio.us-west-2.deadlinecloud.amazonaws.com/
```

The monitor, its profile, and Blender's add-on preferences are all per user. Linux writes them for another account with `runuser`, but Windows cannot do so without that account's password, so the Windows script has no equivalent of the second argument.

## How it works

Both scripts run the same five steps, in the same order, under matching section headers.

1. **Validate the monitor URL** and derive the Region, the subdomain, and the profile name (`<subdomain>-<region>`).
2. **Install Blender** from the official archive, verified against its published checksum, into a fixed prefix (`/opt/blender` or `C:\Program Files\Blender`).
3. **Install the submitter.** Read [`manifest.json`](https://downloads.deadlinecloud.amazonaws.com/submitters/manifest.json) to turn "latest" into a concrete version, download that pinned installer, verify its checksum, and run it with `--mode unattended`.
4. **Enable the Blender add-on.** The silent install stages the add-on but cannot enable it, because add-ons live in Blender's per-user preferences while the install runs at system scope. The scripts run the installer's own `add_submitter_to_pref.py` through Blender in background mode, then read the preferences back to confirm.
5. **Install the monitor and create the profile** with `create-profile`, a non-GUI subcommand that writes the profile and exits without needing a display.

Every download is verified against a published SHA-256 checksum, and the scripts fail if a checksum cannot be fetched. An internal Blender mirror must also serve Blender's `blender-<version>.sha256` manifest.

The Linux script also installs `libssl1.1`, because Deadline Cloud monitor links against OpenSSL 1.1 while no current Debian or Ubuntu release provides it. Ubuntu 20.04 is the last release to carry the package, so the script takes it from the Ubuntu archive. That one artifact is published without a `.sha256` beside it, so its expected hash is a constant at the top of the script alongside the version, with a comment naming the index to read a newer hash from.

### The profile

`create-profile` writes an AWS profile that resolves credentials through the monitor rather than through IAM Identity Center stanzas:

```ini
[profile mystudio-us-west-2]
region=us-west-2
credential_process=cat "/home/artist/.cache/com.amazonaws.deadline.monitor/credentials_mystudio-us-west-2.json"
user_id=
identity_store_id=
monitor_id=pending-first-login
```

It also points the Deadline Cloud CLI at that profile in `~/.deadline/config`.

The placeholder and empty fields are expected. `create-profile` requires a `--monitor-id`, but the real ID cannot be discovered without AWS credentials, so the scripts pass `pending-first-login`. The monitor replaces it, along with `user_id` and `identity_store_id`, with authoritative values from the portal at the artist's first sign-in. `credential_process` reads a cache file that the same sign-in creates, so the profile yields no credentials until then. That sign-in is the intended remaining step.

The placeholder must be non-empty. An empty `--monitor-id` makes the monitor drop the profile from its picker and fall back to asking for the monitor URL, which defeats the point of pre-configuring it. The value is shown verbatim in the monitor's profile list until first sign-in, so it reads as a status rather than looking like a real ID.

Because the cache path is written into the profile at creation time and lives under the invoking user's home directory, the profile only works for the account it was created for.

### Adapting to another DCC

Everything Deadline Cloud does is identical for every DCC, so switching to Maya, Nuke, Houdini, 3ds Max, Cinema 4D, After Effects, or VRED means changing three things, called out in comments in both scripts:

1. **The component name** (`BLENDER_COMPONENT` / `$BlenderComponent`). Run `<installer> --help` for the current `--enable-components` values, such as `deadline_cloud_for_maya` or `deadline_cloud_for_houdini` plus a version component like `houdini_20_5`.
2. **The Blender install step.** Commercial DCCs need a vendor installer and, in most cases, a license server, so replace that block entirely.
3. **The add-on enable step.** It is Blender-specific. Other DCCs are wired up by the installer itself or by an environment variable such as `MAYA_MODULE_PATH` or `NUKE_PATH`, so you can often delete it.

Note that the submitter installer's `--<dcc>-path` flag takes the DCC executable on Windows but the install directory on Linux.

To install more than one DCC, pass a comma-separated `--enable-components` list with every DCC and version component you need, one `--<dcc>-path` flag each, and repeat step 2 per DCC.

## What ends up on the machine

| Item | Linux | Windows |
|---|---|---|
| Blender | `/opt/blender`, symlinked to `/usr/local/bin/blender` | `C:\Program Files\Blender` |
| Submitter and Deadline Cloud CLI | `/opt/DeadlineCloudSubmitter` | `C:\Program Files\DeadlineCloudSubmitter` |
| Monitor | `/usr/bin/deadline-cloud-monitor` | `%LOCALAPPDATA%\DeadlineCloudMonitor` |
| AWS profile | `~/.aws/config` | `%USERPROFILE%\.aws\config` |
| Deadline Cloud CLI config | `~/.deadline/config` | `%USERPROFILE%\.deadline\config` |

The submitter installer puts the `deadline` CLI on `PATH` itself, through `/etc/profile.d/deadline.sh` on Linux, so it is available in new login shells rather than the one that ran the script.

## Security, cost, and cleanup

* **No credentials are stored, and none are needed.** The scripts write no secrets and call no AWS APIs. The profile delegates to the monitor, which acquires credentials only when the artist signs in interactively.
* **Every installer is checksum-verified**, and verification cannot be skipped. If you mirror Blender internally, serve its checksum manifest too and point the mirror constant at it.
* **Licensing.** Blender is distributed under the GNU GPL. Review its terms for your use.
* **Cost.** The scripts create no AWS resources. Running the workstation is billable, and jobs submitted from it are billed normally.
* **Cleanup.** Run `/opt/DeadlineCloudSubmitter/uninstall` or its Windows equivalent, remove the monitor with your package manager or through Windows "Apps & features", and delete the Blender prefix. Then remove the profile stanza from `~/.aws/config` and the `[defaults]` entry from `~/.deadline/config`.

## Troubleshooting

**Blender downloads fail with HTTP 403.** `download.blender.org` rejects some automated clients, so the scripts default to a mirror. Pick another from [mirror.blender.org](https://mirror.blender.org/), or host the archive and its checksum manifest internally.

**The Deadline Cloud menu is missing in Blender.** Add-ons register per user, so confirm the script ran for the right account: the second argument on Linux, or the signed-in account on Windows. To check directly:

```console
blender --background --python-expr 'import bpy; print("deadline_cloud_blender_submitter" in bpy.context.preferences.addons.keys())'
```

On Windows, call `& 'C:\Program Files\Blender\blender.exe'` instead, since the script does not add Blender to `PATH`.

**Deadline Cloud monitor does not appear in the applications menu.** Its desktop entry declares no menu category, so some desktop environments file it nowhere. Launch it by path instead, or add a launcher of your own:

```console
# Linux
deadline-cloud-monitor

# Windows
& "$env:LOCALAPPDATA\DeadlineCloudMonitor\DeadlineCloudMonitor.exe"
```

**The monitor asks for a monitor URL instead of using the profile.** The profile's `monitor_id` is empty, so the monitor dropped the profile from its picker. Check the stanza in `~/.aws/config`, then re-run the script or recreate the profile with a non-empty placeholder as described under [The profile](#the-profile).

**Submission fails with a credentials error.** Expected until the artist signs in to the monitor once. Check with `deadline auth status`, which reports `NEEDS_LOGIN` before sign-in and `AUTHENTICATED` after.

**On Windows, the script cannot find the monitor after installing it.** The installer honors WOW64 redirection, so under a 32-bit host process it installs into `C:\Windows\SysWOW64\config\systemprofile\AppData\Local\DeadlineCloudMonitor\` even though `%LOCALAPPDATA%` points elsewhere, and the `InstallLocation` it records still names `System32`. The script tries the recorded path, its `SysWOW64` equivalent, and `%LOCALAPPDATA%`, and reports every candidate when none exists. To find it by hand:

```console
Get-ItemProperty "HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\*" |
    Where-Object { $_.DisplayName -eq "DeadlineCloudMonitor" } |
    Select-Object InstallLocation
```

## Related resources

* [Set up your workstation](https://docs.aws.amazon.com/deadline-cloud/latest/userguide/submitter.html)
* [Deadline Cloud CLI](https://github.com/aws-deadline/deadline-cloud)
* [Blender download mirror](https://mirror.blender.org/)
