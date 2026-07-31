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

  Deadline Cloud monitor's `.deb` depends on `libwebkit2gtk-4.0-37`, which Ubuntu 24.04 and Debian 13 no longer publish; they carry `libwebkit2gtk-4.1-0` instead. No official repository offers the 4.0 build for those releases, so use Ubuntu 22.04 or Debian 12 for the monitor. The Linux script checks for the package up front and stops with an explanation rather than failing partway through.

  On a newer release, install the submitter without the monitor and authenticate a different way. `deadline auth login` is not an alternative, because it drives the monitor and only accepts profiles the monitor created. Use an ordinary AWS credential source instead, such as an IAM Identity Center profile created with `aws configure sso` or an instance profile, and delete the monitor and profile steps from the script. The artist then signs in through that mechanism rather than the monitor, so what this sample pre-configures no longer applies.
* Administrator access: `root` on Linux, an elevated PowerShell session on Windows.
* Outbound HTTPS to `downloads.deadlinecloud.amazonaws.com` and to the Blender mirror.
* A working default web browser. Deadline Cloud monitor hands off to it to complete sign-in, so without one the artist sees "Failed to execute default Web Browser". Windows Server images normally include Microsoft Edge, so nothing extra is needed there. On Ubuntu 22.04 and later, `apt install firefox` gets a transitional package that installs the Firefox snap, and snaps do not work in every remote-desktop session. Install Firefox from the [Mozilla apt repository](https://support.mozilla.org/kb/install-firefox-linux) instead, and add an apt pin so the `.deb` wins over Ubuntu's snap transitional package. Verified on Ubuntu 22.04: the Mozilla `.deb` completes sign-in in a VNC session.
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

On Windows, running the script through a mechanism that executes as `SYSTEM` rather than as a user, such as Systems Manager Run Command or an EC2 user data script, writes the profile and Blender preferences into a service profile the artist never logs in to. The artist then sees no pre-configured monitor. Run it as the artist's own account: interactively, or as a scheduled task created with `/RU <artist> /RL HIGHEST`.

After either script finishes, the artist signs in through a desktop session on the machine. The scripts install no desktop or remote-access server, so provide one separately.

## How it works

Both scripts run the same five steps, in the same order, under section headers that name each one. The Linux script has one extra section, `Prerequisites`, covering the packages and OpenSSL 1.1 described below.

1. **Validate the monitor URL** and derive the Region, the subdomain, and the profile name (`<subdomain>-<region>`).
2. **Install Blender** from the official archive, verified against its published checksum, into a fixed prefix (`/opt/blender` or `C:\Program Files\Blender`).
3. **Install the submitter.** Read [`manifest.json`](https://downloads.deadlinecloud.amazonaws.com/submitters/manifest.json) to turn "latest" into a concrete version, download that pinned installer, verify its checksum, and run it with `--mode unattended`.
4. **Enable the Blender add-on.** The silent install stages the add-on but cannot enable it, because add-ons live in Blender's per-user preferences while the install runs at system scope. The scripts run the installer's own `add_submitter_to_pref.py` through Blender in background mode, then read the preferences back to confirm.
5. **Install the monitor and create the profile** with `create-profile`, a non-GUI subcommand that writes the profile and exits without needing a display.

Every download is verified against a published SHA-256 checksum, and the scripts fail if a checksum cannot be fetched. An internal Blender mirror must also serve Blender's `blender-<version>.sha256` manifest.

The Linux script also installs `libssl1.1`, because Deadline Cloud monitor links against OpenSSL 1.1 while no current Debian or Ubuntu release provides it. Ubuntu 20.04 is the last release to carry the package, so the script takes it from the Ubuntu archive. That one artifact is published without a `.sha256` beside it, so its expected hash is a constant at the top of the script alongside the version, with a comment naming the index to read a newer hash from.

On Debian this installs an Ubuntu-built `.deb`. Its dependencies are satisfiable on Debian 12, but the combination was verified on Ubuntu 22.04 only. On Debian, prefer whatever OpenSSL 1.1 package your own repositories provide and delete that step.

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

The scripts pass two further flags, both optional:

* `--set-as-deadline-default` points the Deadline Cloud CLI at this profile, by writing `aws_profile_name` under `[defaults]` in `~/.deadline/config`. Without it, `deadline` commands need `--profile` or `AWS_PROFILE`. Drop it on a workstation that submits to more than one monitor.
* `--enable-auto-login` starts sign-in as soon as the monitor opens, rather than making the artist pick the profile first. Keep it unless you want the picker, since skipping the picker is most of what pre-configuring the profile buys.

On Windows the same profile instead delegates to the monitor executable:

```ini
credential_process="C:\Users\artist\AppData\Local\DeadlineCloudMonitor\DeadlineCloudMonitor.exe" get-credentials --profile mystudio-us-west-2
```

The placeholder and empty fields are expected. `create-profile` requires a `--monitor-id`, but the real ID cannot be discovered without AWS credentials, so the scripts pass `pending-first-login`. The monitor replaces it, along with `user_id` and `identity_store_id`, with authoritative values from the portal at the artist's first sign-in. Either form of `credential_process` yields no credentials until that sign-in happens, so it is the intended remaining step.

The placeholder must be non-empty. An empty `--monitor-id` makes the monitor drop the profile from its picker and fall back to asking for the monitor URL, which defeats the point of pre-configuring it. The value is shown verbatim in the monitor's profile list until first sign-in, so it reads as a status rather than looking like a real ID.

Because the cache path is written into the profile at creation time and lives under the invoking user's home directory, the profile only works for the account it was created for.

### Adapting to another DCC

Everything Deadline Cloud does is identical for every DCC, so switching to Maya, Nuke, Houdini, 3ds Max, Cinema 4D, After Effects, or VRED means changing three things, called out in comments in both scripts:

1. **The component names** (`SUBMITTER_COMPONENT` and `BLENDER_COMPONENT`, or `$SubmitterComponent` and `$BlenderComponent`), such as `deadline_cloud_for_houdini` plus `houdini_20_5`. Run `<installer> --help` for the current `--enable-components` values. The `--<dcc>-path` flag is derived from the version component, so it follows automatically.
2. **The Blender install step.** Commercial DCCs need a vendor installer and, in most cases, a license server, so replace that block entirely. Also update the install prefix constant.
3. **The add-on enable step.** It is Blender-specific, including the `Submitters/Blender/` paths and the `deadline_cloud_blender_submitter` name it verifies. Other DCCs are wired up by the installer itself or by an environment variable such as `MAYA_MODULE_PATH` or `NUKE_PATH`, so you can often delete it.

Note that the submitter installer's `--<dcc>-path` flag takes the DCC executable on Windows but the install directory on Linux.

To install more than one DCC, pass a comma-separated `--enable-components` list with every DCC and version component you need, one `--<dcc>-path` flag each, and repeat step 2 per DCC.

## What ends up on the machine

| Item | Linux | Windows |
|---|---|---|
| Blender | `/opt/blender`, symlinked to `/usr/local/bin/blender` | `C:\Program Files\Blender` |
| Submitter and Deadline Cloud CLI | `/opt/DeadlineCloudSubmitter` | `C:\Program Files\DeadlineCloudSubmitter` |
| Monitor | `/usr/bin/deadline-cloud-monitor` (system-wide) | `%LOCALAPPDATA%\DeadlineCloudMonitor` (per user) |
| AWS profile | `~/.aws/config` | `%USERPROFILE%\.aws\config` |
| Deadline Cloud CLI config | `~/.deadline/config` | `%USERPROFILE%\.deadline\config` |

The submitter installer puts the `deadline` CLI on `PATH` itself. On Linux it writes `/etc/profile.d/deadline.sh`, which appends `/opt/DeadlineCloudSubmitter/DeadlineClient`, so the CLI appears in new login shells rather than the one that ran the script.

## Security, cost, and cleanup

* **No credentials are stored, and none are needed.** The scripts write no secrets and call no AWS APIs. The profile delegates to the monitor, which acquires credentials only when the artist signs in interactively.
* **Every installer is checksum-verified**, and verification cannot be skipped. If you mirror Blender internally, serve its checksum manifest too and point the mirror constant at it.
* **Licensing.** Blender is distributed under the GNU GPL. Review its terms for your use.
* **Cost.** The scripts create no AWS resources. Running the workstation is billable, and jobs submitted from it are billed normally.
* **Cleanup.** Uninstall the submitter, then the monitor, then delete the Blender prefix:

  ```console
  # Linux
  sudo /opt/DeadlineCloudSubmitter/uninstall --mode unattended
  sudo rm -rf /opt/DeadlineCloudSubmitter   # the uninstaller leaves THIRD_PARTY_LICENSES behind
  sudo apt-get remove -y deadline-cloud-monitor
  sudo rm -rf /opt/blender /usr/local/bin/blender

  # Windows
  & "C:\Program Files\DeadlineCloudSubmitter\uninstall.exe" --mode unattended
  Remove-Item -Recurse -Force "C:\Program Files\Blender"
  ```

  The Linux uninstaller removes `/etc/profile.d/deadline.sh`, so the `deadline` CLI leaves new login shells. Remove the monitor on Windows through **Settings > Apps > Installed apps**. Then remove the profile stanza from `~/.aws/config` and the `[defaults]` entry from `~/.deadline/config`, and delete the monitor's credential cache (`~/.cache/com.amazonaws.deadline.monitor` on Linux).

## Troubleshooting

**Blender downloads fail with HTTP 403.** `download.blender.org` rejects some automated clients, so the scripts default to a mirror. Pick another from [mirror.blender.org](https://mirror.blender.org/), or host the archive and its checksum manifest internally.

**The Deadline Cloud menu is missing in Blender.** Add-ons register per user, so confirm the script ran for the account that is signing in. On Linux that is the second argument. On Windows it is the account that ran the script. To check, as that same user:

```console
blender --background --python-expr 'import bpy; print("deadline_cloud_blender_submitter" in bpy.context.preferences.addons.keys())'
```

On Windows, write the same two lines to a file and pass `--python <file>` instead. Windows PowerShell does not preserve the inner quotes of an expression passed on the command line, so `--python-expr` raises `NameError` there. The script itself uses a file for this reason. Blender is not on `PATH`, so call it by path:

```console
& 'C:\Program Files\Blender\blender.exe' --background --python C:\Temp\check_addon.py
```

**Deadline Cloud monitor does not appear in the applications menu.** Its desktop entry declares no menu category, so some desktop environments file it nowhere. Launch it by path instead, or add a launcher of your own:

```console
# Linux
deadline-cloud-monitor

# Windows
& "$env:LOCALAPPDATA\DeadlineCloudMonitor\DeadlineCloudMonitor.exe"
```

**The monitor asks for a monitor URL instead of using the profile.** The monitor found no usable profile, most often for one of these reasons:

* The profile went to a different account than the one signing in. On Windows, running the script as `SYSTEM` produces exactly that. Check that the stanza is in the signing-in user's own `~/.aws/config` or `%USERPROFILE%\.aws\config`.
* The profile's `monitor_id` is empty, which makes the monitor drop it from the picker. The scripts always write a non-empty placeholder, so this points to a profile created by hand. Recreate it with a non-empty `--monitor-id` as described under [The profile](#the-profile).

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
