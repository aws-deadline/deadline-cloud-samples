# Host Configuration for After Effects, Red Giant, and Universe

This guide covers setting up the required software installers for the After Effects (AE) 2025, Red Giant and Universe (RGU) host config script package build. You'll be fetching the necessary standalone installers from After Effects and Maxon, storing them in S3, and then putting the provided ps1 script to the host configuration script so that it pulls the installer and runs it in silent mode on each Deadline worker launch. This solution has been tested and verified to work on Windows GPU SMF fleets only, but can also be applied to a CMF as well assuming your instance is a GPU Windows instance with the necessary driver installed to support GPU usage (not fully tested but theoretically should work).

> **⚠️ Performance Impact**: This script can add about **15-20 minutes** to worker launch time due to software installation. This number goes down as you vertically scale your instance size up. For example, a g6.xlarge with 4 vCPUs + 16 GiB of memory adds 20 minutes while a g6.4xlarge with 16 vCPUs and 64 GiB memory adds 15 minutes. Plan accordingly for your fleet scaling and job scheduling. One strategy is to keep a warm worker alive during peak usage hours. Additionally, if you have AE jobs that doesn't require Red Giant, you can have one fleet for just AE renders via Conda and another fleet for AE + RGU using this host configuration.

## Prerequisites

- AWS CLI configured with appropriate permissions
- S3 bucket for storing installers (can use your job-attachments bucket)
- Enterprise Adobe account with Admin access to Admin Console and Adobe After Effects license
- Red Giant and Universe licenses
- AWS Deadline Cloud farm, Windows GPU SMF (service-managed fleet) with latest driver, queue, and queue-fleet association set up. No need to add conda queue environment to your queue.

## Required Installers

*🔔 Note: the installer names can differ depending on the software versions, please keep note of differences so that the following script setup goes smoothly*

### 1. Adobe After Effects

Download from Adobe Admin Console (make sure you're using an enterprise account and you have Administrator permissions):
1. Log into [Adobe Admin Console](https://adminconsole.adobe.com/)
2. Navigate to **Packages** > **Create a Package**
3. Choose **Create Managed Package**
4. For OS, select Windows 64-bt.
5. Under available applications, select **After Effects 2025** (or latest version). Continue with remaining default settings and don't include any add-ons since that is out-of-scope of this script.
6. Name the package `After Effects`
7. Download the resulting package zip file, which should be named something like `After Effects_en_US_WIN_64.zip`.

See the [Adobe pre-generated packages documentation](https://helpx.adobe.com/enterprise/using/pre-generated-packages.html) for more information.

### 2. Red Giant

Download from Red Giant:
1. Log into your Maxon account
2. Navigate to the [Maxon Downloads](https://www.maxon.net/en/downloads) section
3. Download `RedGiant-2025.6.0-Win.exe` (or latest version) for Windows from the section Red Giant

### 3. Universe (Optional)

Note that Universe is [now included in Red Giant 2026.2.0 and above by default](https://support.maxon.net/hc/en-us/articles/24114684657692-Red-Giant-2026-2-0-December-3-2025). For older versions of Red Giant, you can download Universe separately following the instructions below.

Download from Red Giant:
1. Log into your Maxon account
2. Navigate to the [Maxon Downloads](https://www.maxon.net/en/downloads) section
3. Download `Universe-2025.3.3_Win.exe` (or latest version) for Windows under the section Red Giant

### 4. Maxon App

This is needed to support Red Giant + Universe licensing since it serves as a proxy between your licensing server and the plugins being run.
Download from Maxon:
1. Log into your Maxon account
2. Navigate to the [Maxon App](https://www.maxon.net/en/downloads) section after you scroll down a bit
2. Download `Maxon_App_2025.4.2_Win.exe` (or latest version) for Windows under the section Maxon App

### 5. Microsoft Edge WebView2 Runtime

This is needed for the Maxon App installation to go smoothly. Download from Microsoft:
1. Visit the [Microsoft Edge WebView2 download page](https://developer.microsoft.com/en-us/microsoft-edge/webview2?form=MA13LH#download)
2. Download `MicrosoftEdgeWebView2RuntimeInstallerX64.exe` (x64 version) under the "Evergreen Standalone Installer" section

### 6. Boris FX Sapphire (optional)

Download from Boris FX:
1. Log into your Boris FX account
2. Navigate to the [Boris FX Downloads](https://borisfx.com/downloads/?product=sapphire&os=windows) section
3. Download Sapphire 2026 (or latest version) for Adobe (Windows 64-Bit)

For Boris FX Sapphire, you will need to bring your own licenses. We recommend setting the `genarts_LICENSE` environment variable to license the software. This can be set either inside the host config script by configuring the `$BORIS_LICENSE_SERVER` variable (e.g., `$BORIS_LICENSE_SERVER = "5053@<license-server-hostname>"`), or in a queue environment. See the "Install Floating Client License Using An Environment Variable" section of [this Boris FX article](https://support.borisfx.com/hc/en-us/articles/11198263161997-License-Instructions-Floating-Licenses) for more details on the format of the environment variable.

To enable Boris FX Sapphire installation, set `$INSTALL_BORIS_SAPPHIRE = $true` in the script configuration section.

### 7. Frischluft Lenscare (optional)

Download from Frischluft:
1. Go to https://www.frischluft.com/lenscare/
2. Select download for After Effects on windows
3. Upload your `Lenscare_ae.key` license file to the S3 bucket at `s3://<your-installer-bucket>/Installers/Lenscare_ae.key`

For Frischluft Lenscare, you will need to bring your own licenses. Lenscare is licensed by copying the `Lenscare_ae.key` license file to the same folder as the plugin. In this sample host config script, you will upload your license file to S3 and the host config script will download the license file from S3 to `C:\Program Files\Adobe\Common\Plug-ins\7.0\MediaCore\Lenscare_ae.key` on the worker. For more information about licensing Lenscare, review the "Install Key File" section of the `readme.txt` inside the downloaded Lenscare zip file.

To enable Lenscare installation, set `$INSTALL_LENSCARE = $true` in the script configuration section.

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
aws s3 cp "RedGiant-2026.3.0-Win.exe" s3://$INSTALLER_S3_BUCKET/Installers/
aws s3 cp "Maxon_App_2026.0.1_Win.exe" s3://$INSTALLER_S3_BUCKET/Installers/
aws s3 cp "MicrosoftEdgeWebView2RuntimeInstallerX64.exe" s3://$INSTALLER_S3_BUCKET/Installers/

# Optional, Maxon Universe is now included in Red Giant 2026.2.0 and above
aws s3 cp "Universe-2026.0.1_Win.exe" s3://$INSTALLER_S3_BUCKET/Installers/

# Optional, use if installing Boris FX Sapphire
aws s3 cp "sapphire-ae-install-2026.exe" s3://$INSTALLER_S3_BUCKET/Installers/

# Optional, use if installing Frischluft Lenscare
aws s3 cp "lenscare_ae_v1.5.5(win).zip" s3://$INSTALLER_S3_BUCKET/Installers/
aws s3 cp "Lenscare_ae.key" s3://$INSTALLER_S3_BUCKET/Installers/
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

### 1. Configure Host Config Installation Script

Before running the installation script, you need to update the configuration variables at the top of the script. All configurable settings are located in the "Script Configuration Variables" section:

**Basic Configuration (Required for all deployments):**
Update with your chosen bucket's name and also change the After Effects version variable if you're not using 2025. For example:
```powershell
$INSTALLER_S3_BUCKET = "your-installer-bucket"
$AE_VERSION = "2025"
```

**Installer File Names (Update if using different versions):**
Take a look at the names of all of your zip files and executables that you uploaded to S3. Cross-reference them with the variable definitions in the script and update them to match what you have in S3. For example:
```powershell
$AE_INSTALLER = "After Effects_en_US_WIN_64.zip"
$REDGIANT_INSTALLER = "RedGiant-2025.6.0-Win.exe"
$UNIVERSE_INSTALLER = "Universe-2025.3.3_Win.exe"
$MAXON_APP_INSTALLER = "Maxon_App_2025.4.2_Win.exe"
$WEBVIEW2_INSTALLER = "MicrosoftEdgeWebView2RuntimeInstallerX64.exe"
```

**Customer Managed Fleet (CMF) Configuration (Optional - SMF users can skip this):**

For SMF deployments, the script works out-of-the-box with the default settings. For CMF, you can create a license endpoint and use it with CMF, see here for information on that: https://docs.aws.amazon.com/deadline-cloud/latest/developerguide/cmf-ubl.html.

Once you have that setup, get the VPC endpoint ID provided on the license endpoints console page and set the following variables as shown:

```powershell
$is_cmf = $true  # Set to $true for Customer Managed Fleets
$vpc_endpoint = "vpce-000000000000000-abcdefg.vpce-svc-000000000000000.us-west-2.vpce.amazonaws.com"  # Your VPC endpoint provided by license endpoints console page
```

This will set the `redshift_LICENSE` environment variable to `7055@$vpc_endpoint` for Red Giant licensing. If you're not using UBL, you'll need to override the `redshift_LICENSE` environment variable with whatever port number or value you need to connect your CMF instance to your license server.

You will also need to install your own Nvidia GPU driver to your CMF instance to support GPU rendering with Red Giant. Otherwise, you will most likely experience hanging or failing jobs.


### 2. Add Host Config Script to Windows GPU Fleet

The contents of the script `.\install-software.ps1` should go in your Configuration Scripts for your fleet, which you can add to your fleet when you go to Fleets, select your fleet, go under Configurations, and add your script under Worker configuration script. Once pasted, scroll down and set the script timeout to **3600 seconds**. For more information, see the [AWS Deadline Cloud SMF administration guide](https://docs.aws.amazon.com/deadline-cloud/latest/developerguide/smf-admin.html).


## Local Dev Testing
To test the script locally, run Powershell with Admin privileges on a Windows machine, add the credentials to your AWS account in the Powershell windows, and then run the following:

```powershell
# Run the automated installer
.\install-software.ps1
```

You might see failures on the WebView installation though since your machine probably already has it, but you can splice that out and test the rest.

The script will:
1. Download all installers from S3
2. Set environment variables for rendering (including Red Giant license server for CMF)
3. Install Microsoft Edge WebView2 Runtime
4. Install After Effects
5. Install Maxon App
6. Install Red Giant Suite
7. Install Universe

## Troubleshooting

- Ensure all installer files are present in S3 before running
- Verify enterprise Adobe account has package creation rights if you can't make the standalone After Effects installer package.
- If your resulting renders are coming out corrupted on CMF, it's possible that you need to do Nvidia driver installation on your CMF to ensure that Red Giant is utilizing your GPU correctly.
