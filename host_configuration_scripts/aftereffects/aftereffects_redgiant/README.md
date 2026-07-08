# Host Configuration for After Effects and Plugins

This guide covers setting up host configuration scripts for installing Adobe After Effects and optional plugins on AWS Deadline Cloud workers. You'll be fetching standalone installers, storing them in S3, and using the provided PowerShell script as a host configuration script that pulls and installs the software in silent mode on each worker launch.

This solution has been tested and verified to work on Windows GPU SMF fleets, but can also be applied to a CMF assuming your instance is a GPU Windows instance with the necessary driver installed to support GPU usage (not fully tested but theoretically should work).

> **Performance Note**: Software installation adds time to worker launch (varies with instance size — larger instances with more vCPUs and memory tend to complete faster). Plan accordingly for your fleet scaling and job scheduling. One strategy is to keep a warm worker alive during peak usage hours. Additionally, if you have AE jobs that don't require Red Giant, you can have one fleet for just AE renders via Conda and another fleet for AE + plugins using this host configuration.

> **Looking for faster subsequent boot times?** See the [`aftereffects_redgiant_persistent`](../aftereffects_redgiant_persistent/) variant which uses persistent volumes to install software once and restore on subsequent boots without reinstalling.

## Prerequisites

- AWS CLI configured with appropriate permissions
- S3 bucket for storing installers (can use your job-attachments bucket)
- Enterprise Adobe account with Admin access to Admin Console and Adobe After Effects license
- AWS Deadline Cloud farm, Windows GPU SMF (service-managed fleet) with latest driver, queue, and queue-fleet association set up. No need to add conda queue environment to your queue.
- Licenses for any plugins being used

## Required Installers

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

Make sure to update the `$AE_INSTALLER` variable with the name of the package zip file in the script configuration section.

### 2. Red Giant (Optional)

Red Giant now [includes Universe by default as of version 2026.2.0](https://support.maxon.net/hc/en-us/articles/24114684657692-Red-Giant-2026-2-0-December-3-2025), so a separate Universe installer is no longer needed.

Download from Red Giant:
1. Log into your Maxon account
2. Navigate to the [Maxon Downloads](https://www.maxon.net/en/downloads) section
3. Download `RedGiant-2025.6.0-Win.exe` (or latest version) for Windows from the section Red Giant

To enable Red Giant installation, set `$INSTALL_RED_GIANT = $true` in the script configuration section.

Make sure to update the `$RED_GIANT_INSTALLER` variable with the name of the Red Giant installer.

### 3. Maxon App (required for Red Giant)

This is needed to support Red Giant + Universe licensing since it serves as a proxy between your licensing server and the plugins being run.
Download from Maxon:
2. Navigate to the [Maxon App](https://www.maxon.net/en/downloads) section after you scroll down a bit
2. Download `Maxon_App_2025.4.2_Win.exe` (or latest version) for Windows under the section Maxon App

Make sure to update the `$MAXON_APP_INSTALLER` variable with the name of the Maxon App installer.

### 4. Microsoft Edge WebView2 Runtime (required for Red Giant)

This is needed for the Maxon App installation to go smoothly. Download from Microsoft:
1. Visit the [Microsoft Edge WebView2 download page](https://developer.microsoft.com/en-us/microsoft-edge/webview2?form=MA13LH#download)
2. Download `MicrosoftEdgeWebView2RuntimeInstallerX64.exe` (x64 version) under the "Evergreen Standalone Installer" section

Make sure to update the `$WEBVIEW2_INSTALLER` variable with the name of the WebView2 installer.

### 5. Boris FX Sapphire (Optional)

Download from Boris FX:
1. Log into your Boris FX account
2. Navigate to the [Boris FX Downloads](https://borisfx.com/downloads/?product=sapphire&os=windows) section
3. Download Sapphire 2026 (or latest version) for Adobe (Windows 64-Bit)

For Boris FX Sapphire, you will need to bring your own licenses. We recommend setting the `genarts_LICENSE` environment variable to license the software. This can be set either inside the host config script by configuring the `$BORIS_LICENSE_SERVER` variable (e.g., `$BORIS_LICENSE_SERVER = "5053@<license-server-hostname>"`), or in a queue environment. See the "Install Floating Client License Using An Environment Variable" section of [this Boris FX article](https://support.borisfx.com/hc/en-us/articles/11198263161997-License-Instructions-Floating-Licenses) for more details on the format of the environment variable.

To enable Boris FX Sapphire installation, set `$INSTALL_BORIS_SAPPHIRE = $true` in the script configuration section.

Make sure to update the `$BORIS_SAPPHIRE_INSTALLER` variable with the name of the Boris FX Sapphire installer.

### 6. Frischluft Lenscare (Optional)

Download from Frischluft:
1. Go to https://www.frischluft.com/lenscare/
2. Select download for After Effects on windows
3. Upload your `Lenscare_ae.key` license file to the S3 bucket at `s3://<your-installer-bucket>/Installers/Lenscare_ae.key`

For Frischluft Lenscare, you will need to bring your own licenses. Lenscare is licensed by copying the `Lenscare_ae.key` license file to the same folder as the plugin. In this sample host config script, you will upload your license file to S3 and the host config script will download the license file from S3 to `C:\Program Files\Adobe\Common\Plug-ins\7.0\MediaCore\Lenscare_ae.key` on the worker. For more information about licensing Lenscare, review the "Install Key File" section of the `readme.txt` inside the downloaded Lenscare zip file.

To enable Lenscare installation, set `$INSTALL_LENSCARE = $true` in the script configuration section.

Make sure to update the `$LENSCARE_INSTALLER` variable with the name of the Lenscare installer.

### 7. RE:Vision Effects ReelSmart Motion Blur (Optional)

Download from RE:Vision Effects:
1. Go to https://revisionfx.com/products/rsmb/after-effects/
2. Scroll down to the Download section on the page and download the Windows installer (`RSMB6AEInstaller.zip`)
3. Go to https://revisionfx.com/faq/setting-up-your-site-for-floating-licenses/
4. Download the floating license software for Windows (`FloatingLicensing.zip`)

For ReelSmart Motion Blur, you will need to bring your own licenses. We recommend setting the `RVL_SERVER` environment variable to license the software. This can be set either inside the host config script by configuring the `$RVL_SERVER` variable (e.g., `$RVL_SERVER = "<license-server-hostname>"`), or in a queue environment. See the ["Setting up floating license clients" page from RE:Vision](https://revisionfx.com/faq/setting-floating-license-clients/#Windows) for more details on the format of the environment variable.

To enable ReelSmart Motion Blur installation, set `$INSTALL_RSMB = $true` in the script configuration section.

Make sure to update the `$RSMB_INSTALLER` variable with the name of the ReelSmart Motion Blur installer.

## S3 Bucket Setup

### 1. Create S3 Bucket Structure

If you have a job attachments bucket, you can just go ahead and use that. If you want a separate bucket, go ahead and create one. Then, add a folder called Installers to the S3 bucket. These steps can be done on the AWS console or completed by doing the following:
```bash
export INSTALLER_S3_BUCKET=your-installer-bucket
aws s3api put-object --bucket $INSTALLER_S3_BUCKET --key Installers/
```

### 2. Upload Installers

To upload the installers to S3, you can upload the `.zip` and `.exe` files to your bucket under the Installers folder via the AWS S3 console. For a programmatic approach, navigate to your local folder where you downloaded your installers (for ex. Downloads) and run the following:

```bash
export INSTALLER_S3_BUCKET=your-installer-bucket

aws s3 cp "After Effects_en_US_WIN_64.zip" s3://$INSTALLER_S3_BUCKET/Installers/

# Optional, use if installing Red Giant
aws s3 cp "RedGiant-2026.3.0-Win.exe" s3://$INSTALLER_S3_BUCKET/Installers/
aws s3 cp "Maxon_App_2026.0.1_Win.exe" s3://$INSTALLER_S3_BUCKET/Installers/
aws s3 cp "MicrosoftEdgeWebView2RuntimeInstallerX64.exe" s3://$INSTALLER_S3_BUCKET/Installers/

# Optional, use if installing Boris FX Sapphire
aws s3 cp "sapphire-ae-install-2026.exe" s3://$INSTALLER_S3_BUCKET/Installers/

# Optional, use if installing Frischluft Lenscare
aws s3 cp "lenscare_ae_v1.5.5(win).zip" s3://$INSTALLER_S3_BUCKET/Installers/
aws s3 cp "Lenscare_ae.key" s3://$INSTALLER_S3_BUCKET/Installers/

# Optional, use if installing ReelSmart Motion Blur
aws s3 cp "RSMB6AEInstaller.zip" s3://$INSTALLER_S3_BUCKET/Installers/
aws s3 cp "FloatingLicensing.zip" s3://$INSTALLER_S3_BUCKET/Installers/
```

### 3. Update IAM Role Permissions

Then, go to your Fleet role and add the following inline policy to that role:
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
                "arn:aws:s3:::<your bucket>/Installers*"
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

Before deploying, update the configuration variables at the top of the script. All configurable settings are in the "Script Configuration Variables" section:

**Basic Configuration (Required for all deployments):**
```powershell
$INSTALLER_S3_BUCKET = "your-installer-bucket"
$AE_VERSION = "2025"
```

**Installer File Names (Update if using different versions):**

Cross-reference the variable definitions in the script with the filenames you uploaded to S3 and update them to match:
```powershell
$AE_INSTALLER = "After Effects_en_US_WIN_64.zip"
$RED_GIANT_INSTALLER = "RedGiant-2026.3.0-Win.exe"
$MAXON_APP_INSTALLER = "Maxon_App_2026.1.0_Win.exe"
$WEBVIEW2_INSTALLER = "MicrosoftEdgeWebView2RuntimeInstallerX64.exe"
```

**Plugin Toggles:**

Enable or disable plugins by setting the corresponding flags:
```powershell
$INSTALL_RED_GIANT = $true       # Red Giant + Maxon App + WebView2
$INSTALL_BORIS_SAPPHIRE = $false # Boris FX Sapphire
$INSTALL_LENSCARE = $false       # Frischluft Lenscare
$INSTALL_RSMB = $false           # RE:Vision Effects RSMB
```

**Dev testing without licenses:**

Both Lenscare and RSMB support installation without license files for dev testing. The plugins will produce watermarked output but are otherwise fully functional:
```powershell
$LENSCARE_HAS_LICENSE = $false  # Installs Lenscare without license — renders will be watermarked
$RSMB_HAS_LICENSE = $false      # Installs RSMB without license — renders will be watermarked
```

> Boris FX Sapphire and Red Giant always require licensing (via license server environment variables).

**Customer Managed Fleet (CMF) Configuration (Optional — SMF users can skip this):**

For CMF, set up a license endpoint and configure the VPC endpoint. See the [CMF UBL guide](https://docs.aws.amazon.com/deadline-cloud/latest/developerguide/cmf-ubl.html) for details.

```powershell
$is_cmf = $true
$vpc_endpoint = "vpce-000000000000000-abcdefg.vpce-svc-000000000000000.us-west-2.vpce.amazonaws.com"
```

You will also need to install your own Nvidia GPU driver on your CMF instance to support GPU rendering with Red Giant.

### 2. Add Host Config Script to Windows GPU Fleet

Copy the script contents into your fleet's **Worker configuration script** and set timeout to **3600 seconds**. See the [SMF administration guide](https://docs.aws.amazon.com/deadline-cloud/latest/developerguide/smf-admin.html) for details on configuring host configuration scripts.

## Local Dev Testing

To test the script locally, run PowerShell with Admin privileges on a Windows machine, add the credentials to your AWS account in the PowerShell window, and then run:

```powershell
.\install-software.ps1
```

You might see failures on the WebView2 installation since your machine probably already has it, but you can splice that out and test the rest.

## Troubleshooting

- Ensure all installer files are present in S3 before running
- Verify enterprise Adobe account has package creation rights if you can't make the standalone After Effects installer package
- If your resulting renders are coming out corrupted on CMF, it's possible that you need to do Nvidia driver installation on your CMF to ensure that Red Giant is utilizing your GPU correctly
