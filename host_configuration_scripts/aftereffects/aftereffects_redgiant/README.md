# Host Configuration for After Effects and Plugins

This guide covers setting up host configuration scripts for installing Adobe After Effects and optional plugins on AWS Deadline Cloud workers. You'll be fetching standalone installers, storing them in S3, and using the provided PowerShell script as a host configuration script that pulls and installs the software in silent mode on each worker launch.

This solution has been tested and verified to work on Windows GPU SMF fleets, but can also be applied to a CMF assuming your instance is a GPU Windows instance with the necessary driver installed to support GPU usage (not fully tested but theoretically should work).

> **Performance Note**: Software installation adds time to worker launch (varies with instance size — larger instances with more vCPUs and memory tend to complete faster). Plan accordingly for your fleet scaling and job scheduling. One strategy is to keep a warm worker alive during peak usage hours. Additionally, if you have AE jobs that don't require Red Giant, you can have one fleet for just AE renders via Conda and another fleet for AE + plugins using this host configuration.

> **Faster subsequent boots are built in.** If a persistent volume is attached to the fleet, the script installs once to it and restores on later boots instead of reinstalling — see [Persistent Volumes (Automatic)](#persistent-volumes-automatic). No separate script or flag is needed.

## Prerequisites

- AWS CLI configured with appropriate permissions
- S3 bucket for storing installers (can use your job-attachments bucket)
- Enterprise Adobe account with Admin access to Admin Console and Adobe After Effects license
- AWS Deadline Cloud farm, Windows GPU SMF (service-managed fleet) with latest driver, queue, and queue-fleet association set up. No need to add conda queue environment to your queue.
- Licenses for any plugins being used

> **Note:** For detailed instructions for each installer, see [Installer download and setup](#installer-download-and-setup).

## S3 Bucket Setup

### 1. Choose or Create an S3 Bucket

If you have a job attachments bucket, you can just go ahead and use that. If you want a separate bucket, go ahead and create one.

The script downloads each installer from the full S3 URI you set in its `CONFIG` block, so you're free to organize the objects however you like — at the bucket root, under a shared prefix (e.g. `Installers/`), or in per-software folders. There is no required folder structure. Whatever locations you choose, note down each object's full S3 URI (format `s3://bucket/key`), since you'll paste those URIs into the script config in the [Usage](#usage) step.

### 2. Upload Installers

Upload the `.zip` and `.exe` files to your bucket via the AWS S3 console, or programmatically. The examples below upload to the bucket root; if you prefer a prefix, append it to the destination (e.g. `s3://$INSTALLER_S3_BUCKET/Installers/`) and adjust your config URIs to match.

```bash
export INSTALLER_S3_BUCKET=your-installer-bucket

aws s3 cp "After Effects_en_US_WIN_64.zip" s3://$INSTALLER_S3_BUCKET/

# Optional, use if installing Red Giant
aws s3 cp "RedGiant-2026.3.0-Win.exe" s3://$INSTALLER_S3_BUCKET/
aws s3 cp "Maxon_App_2026.0.1_Win.exe" s3://$INSTALLER_S3_BUCKET/
aws s3 cp "MicrosoftEdgeWebView2RuntimeInstallerX64.exe" s3://$INSTALLER_S3_BUCKET/

# Optional, use if installing Boris FX Sapphire
aws s3 cp "sapphire-ae-install-2026.exe" s3://$INSTALLER_S3_BUCKET/

# Optional, use if installing Frischluft Lenscare
aws s3 cp "lenscare_ae_v1.5.5(win).zip" s3://$INSTALLER_S3_BUCKET/
aws s3 cp "Lenscare_ae.key" s3://$INSTALLER_S3_BUCKET/

# Optional, use if installing ReelSmart Motion Blur
aws s3 cp "RSMB6AEInstaller.zip" s3://$INSTALLER_S3_BUCKET/
aws s3 cp "FloatingLicensing.zip" s3://$INSTALLER_S3_BUCKET/
```

### 3. Update IAM Role Permissions

Then, go to your Fleet role and add the following inline policy to that role. Scope the `Resource` to wherever you uploaded your installers — the whole bucket as shown below, or narrow it to a prefix (e.g. `arn:aws:s3:::<your bucket>/Installers/*`) if you grouped the objects under one:
```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Sid": "ReadBucket",
            "Action": [
                "s3:GetObject"
            ],
            "Resource": [
                "arn:aws:s3:::<your bucket>/*"
            ],
            "Condition": {
                "StringEquals": {
                    "aws:ResourceAccount": "<your aws account id>"
                }
            }
        }
    ]
}
```
This allows the host config script to pull down the installers from your S3 bucket in order to install those softwares to your worker.

## Usage

### 1. Configure the Script

Before deploying, edit the `CONFIG` block at the top of the script.

> Supply the license server or key values documented for each plugin in the [Installer download and setup](#installer-download-and-setup) section.

**Dev testing without licenses:** Boris FX Sapphire, Lenscare, and RSMB can be installed without a license by leaving their license variable blank (`$BORIS_LICENSE_SERVER`, `$LENSCARE_LICENSE_S3_URI`, `$RSMB_LICENSE_SERVER` respectively). The script skips license setup and prints a warning instead of failing. The plugins are fully functional but produce watermarked output — intended for dev testing only. Red Giant licensing is handled separately (blank `$RED_GIANT_LICENSE_SERVER` means UBL, not "no license").

### 2. Add Host Config Script to Windows GPU Fleet

Copy the script contents into your fleet's **Worker configuration script** and set timeout to **3600 seconds**. See the [SMF administration guide](https://docs.aws.amazon.com/deadline-cloud/latest/developerguide/smf-admin.html) for details on configuring host configuration scripts.

## Persistent Volumes (Automatic)

If your fleet has a persistent volume configured, this script uses it automatically — software installs once to the volume and subsequent boots restore in seconds instead of reinstalling. With no volume attached, it performs a normal install; no configuration is required.

To configure a persistent volume on your fleet, see the [Deadline Cloud persistent storage developer guide](https://docs.aws.amazon.com/deadline-cloud/latest/developerguide/smf-persistent-storage-dev.html) and [user guide](https://docs.aws.amazon.com/deadline-cloud/latest/userguide/volumes.html).

> **Sizing Tip**: After Effects + Red Giant + Maxon App total ~10-15 GiB. 100 GiB is more than sufficient. The console default is 200 GiB.

## Local Dev Testing

To test the script locally, run PowerShell with Admin privileges on a Windows machine, add the credentials to your AWS account in the PowerShell window, and then run:

```powershell
.\install-software.ps1
```

You might see failures on the WebView2 installation since your machine probably already has it, but you can splice that out and test the rest.

## Debugging

The script runs in strict mode (`$ErrorActionPreference = "Stop"`), so any unhandled error aborts it immediately rather than continuing in a bad state. Errors are never suppressed: a single trap near the top of the script writes the error message to the output stream, which is captured in the worker's CloudWatch Logs alongside the script's normal `Write-Host` progress output. To diagnose a failure, open the worker's host-configuration log in CloudWatch and look for the `ERROR:` line and the last operation that printed before it.

## Troubleshooting

- Ensure all installer objects are present in S3 at the exact URIs you configured before running
- Verify enterprise Adobe account has package creation rights if you can't make the standalone After Effects installer package
- If your resulting renders are coming out corrupted on CMF, it's possible that you need to do Nvidia driver installation on your CMF to ensure that Red Giant is utilizing your GPU correctly

## Installer download and setup

*Note: Installer names can differ depending on software versions. Keep note of differences so that the script configuration goes smoothly.*

### 1. Adobe After Effects

1. Log into [Adobe Admin Console](https://adminconsole.adobe.com/)
2. Navigate to **Packages** > **Create a Package**
3. Choose **Create Managed Package**
4. For OS, select Windows 64-bit
5. Under available applications, select **After Effects 2025** (or latest version). Continue with remaining default settings and don't include any add-ons since that is out-of-scope of this script.
6. Name the package `After Effects`
7. Download the resulting package zip file, which should be named something like `After Effects_en_US_WIN_64.zip`.

See the [Adobe pre-generated packages documentation](https://helpx.adobe.com/enterprise/using/pre-generated-packages.html) for more information.

Set `$AE_INSTALLER_S3_URI` in the script's CONFIG block to the full S3 URI of the package zip (format `s3://bucket/key.zip`, e.g., `s3://<your-installer-bucket>/After Effects_en_US_WIN_64.zip`).

### 2. Red Giant (Optional)

Red Giant now [includes Universe by default as of version 2026.2.0](https://support.maxon.net/hc/en-us/articles/24114684657692-Red-Giant-2026-2-0-December-3-2025), so a separate Universe installer is no longer needed.

Download from Red Giant:
1. Log into your Maxon account
2. Navigate to the [Maxon Downloads](https://www.maxon.net/en/downloads) section
3. Download `RedGiant-2025.6.0-Win.exe` (or latest version) for Windows from the section Red Giant

To install Red Giant, set `$RED_GIANT_S3_URI` to the full S3 URI of the Red Giant installer (format `s3://bucket/key.exe`). Red Giant also requires Maxon App and WebView2, so set `$MAXON_APP_S3_URI` and `$WEBVIEW2_S3_URI` as well.

**Red Giant licensing (`$RED_GIANT_LICENSE_SERVER`):**

Red Giant/Redshift licensing is controlled by `$RED_GIANT_LICENSE_SERVER` (format `port@host`). Leave it blank to use Usage-Based Licensing (UBL) — the default, which works on SMF with no extra setup. Set it to point at a custom license server (supported on both SMF and CMF) or at a UBL license endpoint (typically on CMF). See the [CMF UBL guide](https://docs.aws.amazon.com/deadline-cloud/latest/developerguide/cmf-ubl.html) for setting up a license endpoint on CMF.

```powershell
$RED_GIANT_LICENSE_SERVER = "7055@my-license-server"  # blank = UBL
```

### 3. Maxon App (required for Red Giant)

This is needed to support Red Giant + Universe licensing since it serves as a proxy between your licensing server and the plugins being run.
Download from Maxon:
1. Navigate to the [Maxon App](https://www.maxon.net/en/downloads) section after you scroll down a bit
2. Download `Maxon_App_2025.4.2_Win.exe` (or latest version) for Windows under the section Maxon App

Set `$MAXON_APP_S3_URI` to the full S3 URI of the Maxon App installer (format `s3://bucket/key.exe`).

### 4. Microsoft Edge WebView2 Runtime (required for Red Giant)

This is needed for the Maxon App installation to go smoothly. Download from Microsoft:
1. Visit the [Microsoft Edge WebView2 download page](https://developer.microsoft.com/en-us/microsoft-edge/webview2?form=MA13LH#download)
2. Download `MicrosoftEdgeWebView2RuntimeInstallerX64.exe` (x64 version) under the "Evergreen Standalone Installer" section

Set `$WEBVIEW2_S3_URI` to the full S3 URI of the WebView2 Runtime installer (format `s3://bucket/key.exe`).

### 5. Boris FX Sapphire (Optional)

Download from Boris FX:
1. Log into your Boris FX account
2. Navigate to the [Boris FX Downloads](https://borisfx.com/downloads/?product=sapphire&os=windows) section
3. Download Sapphire 2026 (or latest version) for Adobe (Windows 64-Bit)

For Boris FX Sapphire, you will need to bring your own licenses. We recommend setting the `genarts_LICENSE` environment variable to license the software. This can be set either inside the host config script by configuring the `$BORIS_LICENSE_SERVER` variable (e.g., `$BORIS_LICENSE_SERVER = "5053@<license-server-hostname>"`), or in a queue environment. See the "Install Floating Client License Using An Environment Variable" section of [this Boris FX article](https://support.borisfx.com/hc/en-us/articles/11198263161997-License-Instructions-Floating-Licenses) for more details on the format of the environment variable.

To install Boris FX Sapphire, set `$BORIS_SAPPHIRE_S3_URI` to the full S3 URI of the Boris FX Sapphire installer (format `s3://bucket/key.exe`), along with `$BORIS_LICENSE_SERVER`. Leave `$BORIS_LICENSE_SERVER` blank to install without a license for dev testing (watermarked output).

### 6. Frischluft Lenscare (Optional)

Download from Frischluft:
1. Go to https://www.frischluft.com/lenscare/
2. Select download for After Effects on windows
3. Upload your `Lenscare_ae.key` license file to your S3 bucket (e.g. `s3://<your-installer-bucket>/Lenscare_ae.key`)

For Frischluft Lenscare, you will need to bring your own licenses. Lenscare is licensed by copying the `Lenscare_ae.key` license file to the same folder as the plugin. In this sample host config script, you will upload your license file to S3 and the host config script will download the license file from S3 to `C:\Program Files\Adobe\Common\Plug-ins\7.0\MediaCore\Lenscare_ae.key` on the worker. For more information about licensing Lenscare, review the "Install Key File" section of the `readme.txt` inside the downloaded Lenscare zip file.

To install Lenscare, set `$LENSCARE_S3_URI` to the full S3 URI of the Lenscare installer zip, and `$LENSCARE_LICENSE_S3_URI` to the full S3 URI of your key file. Leave `$LENSCARE_LICENSE_S3_URI` blank to install without a license for dev testing (watermarked output).

### 7. RE:Vision Effects ReelSmart Motion Blur (Optional)

Download from RE:Vision Effects:
1. Go to https://revisionfx.com/products/rsmb/after-effects/
2. Scroll down to the Download section on the page and download the Windows installer (`RSMB6AEInstaller.zip`)
3. Go to https://revisionfx.com/faq/setting-up-your-site-for-floating-licenses/
4. Download the floating license software for Windows (`FloatingLicensing.zip`)

For ReelSmart Motion Blur, you will need to bring your own licenses. We recommend setting the `RVL_SERVER` environment variable to license the software. The script sets this from the `$RSMB_LICENSE_SERVER` config value (format `port@host`), or you can set it in a queue environment instead. See the ["Setting up floating license clients" page from RE:Vision](https://revisionfx.com/faq/setting-floating-license-clients/#Windows) for more details on the format of the environment variable.

To install ReelSmart Motion Blur, set `$RSMB_S3_URI` to the full S3 URI of the ReelSmart Motion Blur installer zip, along with `$RSMB_LICENSING_S3_URI` (full S3 URI of the floating licensing zip) and `$RSMB_LICENSE_SERVER` (format `port@host`). Leave `$RSMB_LICENSE_SERVER` blank to install without a license for dev testing (watermarked output); the floating licensing zip is only needed when a license server is set.
