# Host Configuration for Cinema 4D and Red Giant

This guide covers setting up the required software installers for Red Giant host config script package build. You'll be fetching the necessary standalone installers from Maxon, storing them in S3, and then putting the provided ps1 script to the host configuration script so that it pulls the installer and runs it in silent mode on each Deadline worker launch. This solution has been tested and verified to work on Windows GPU SMF fleets only, but can also be applied to a CMF as well assuming your instance is a GPU Windows instance with the necessary driver installed to support GPU usage (not fully tested but theoretically should work).

> **⚠️ Performance Impact**: This script can add about **5-10 minutes** to worker launch time due to software installation. This number goes down as you vertically scale your instance size up. For example, a g6.xlarge with 4 vCPUs + 16 GiB of memory adds 10 minutes while a g6.4xlarge with 16 vCPUs and 64 GiB memory adds 6 minutes. Plan accordingly for your fleet scaling and job scheduling. One strategy is to keep a warm worker alive during peak usage hours. Additionally, if you have Cinema 4D jobs that doesn't require Red Giant, you can have one fleet for just Cinema 4D renders via Conda and another fleet for Cinema 4D + Red Giant using this host configuration.

## Prerequisites

- AWS CLI configured with appropriate permissions
- S3 bucket for storing installers (can use your job-attachments bucket)
- Red Giant licenses which are available on SMF and CMF via a [license endpoint](https://docs.aws.amazon.com/deadline-cloud/latest/developerguide/cmf-ubl.html)
- AWS Deadline Cloud farm, Windows GPU SMF (service-managed fleet) with latest driver, queue, and queue-fleet association set up. No need to add conda queue environment to your queue.

## Required Installers

*🔔 Note: the installer names can differ depending on the software versions, please keep note of differences so that the following script setup goes smoothly*

### 1. Red Giant

Download from Red Giant:
1. Log into your Maxon account
2. Navigate to the [Maxon Downloads](https://www.maxon.net/en/downloads) section
3. Download `RedGiant-2025.6.0-Win.exe` (or latest version) for Windows from the section Red Giant

### 2. Maxon App

This is needed to support Red Giant + Universe licensing since it serves as a proxy between your licensing server and the plugins being run.
Download from Maxon:
1. Log into your Maxon account
2. Navigate to the [Maxon App](https://www.maxon.net/en/downloads) section after you scroll down a bit
2. Download `Maxon_App_2025.4.2_Win.exe` (or latest version) for Windows under the section Maxon App

### 3. Microsoft Edge WebView2 Runtime

This is needed for the Maxon App installation to go smoothly. Download from Microsoft:
1. Visit the [Microsoft Edge WebView2 download page](https://developer.microsoft.com/en-us/microsoft-edge/webview2?form=MA13LH#download)
2. Download `MicrosoftEdgeWebView2RuntimeInstallerX64.exe` (x64 version) under the "Evergreen Standalone Installer" section

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

aws s3 cp "RedGiant-2025.6.0-Win.exe" s3://$INSTALLER_S3_BUCKET/Installers/
aws s3 cp "Maxon_App_2025.4.2_Win.exe" s3://$INSTALLER_S3_BUCKET/Installers/
aws s3 cp "MicrosoftEdgeWebView2RuntimeInstallerX64.exe" s3://$INSTALLER_S3_BUCKET/Installers/
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
Update with your chosen bucket's name.
```powershell
$INSTALLER_S3_BUCKET = "your-installer-bucket"
```

**Installer File Names (Update if using different versions):**
Take a look at the names of all of your zip files and executables that you uploaded to S3. Cross-reference them with the variable definitions in the script and update them to match what you have in S3. For example:
```powershell
$REDGIANT_INSTALLER = "RedGiant-2025.6.0-Win.exe"
$MAXON_APP_INSTALLER = "Maxon_App_2025.4.2_Win.exe"
$WEBVIEW2_INSTALLER = "MicrosoftEdgeWebView2RuntimeInstallerX64.exe"
```

### 2. Add Host Config Script to Windows GPU Fleet

The contents of the script `.\install-software.ps1` should go in your Configuration Scripts for your fleet, which you can add to your fleet when you go to Fleets, select your fleet, go under Configurations, and add your script under Worker configuration script. Once pasted, scroll down and set the script timeout to **900 seconds**. For more information, see the [AWS Deadline Cloud SMF administration guide](https://docs.aws.amazon.com/deadline-cloud/latest/developerguide/smf-admin.html).

## Local Installation

1. Install the Red Giant plugin by [following instructions here](https://support.maxon.net/hc/en-us/articles/212354258-How-do-I-install-my-products)
2. [Optional] Learn how to use Red Giant inside Cinema 4D with [this demonstration video](https://www.youtube.com/watch?v=L6B1REPQoPU)
3. Submit to Deadline Cloud from Cinema 4D by using menu command **Extensions > AWS Deadline Cloud Submitter**


## Local Dev Testing
To test the script locally, run Powershell with Admin privileges on a Windows machine, add the credentials to your AWS account in the Powershell windows, and then run the following:

```powershell
# Run the automated installer
.\install-software.ps1
```

You might see failures on the WebView installation though since your machine probably already has it, but you can splice that out and test the rest.

The script will:
1. Download all installers from S3
2. Install Microsoft Edge WebView2 Runtime
3. Install Maxon App
4. Install Red Giant Suite

## Troubleshooting

- Ensure all installer files are present in S3 before running
