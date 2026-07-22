---
name: host-config-from-installer
description: >
  Interactively install any Windows .exe software with the customer, test it, upload the installer
  to S3, and convert the working steps into a PowerShell host configuration script for AWS Deadline
  Cloud Service Managed Fleets. Use when a customer says "I have an installer", "I want to install X
  on my fleet", "convert my install steps to a host config", or "help me set up X on Deadline Cloud
  workers". Works for any software that ships as a Windows .exe installer.
tags: [skill, host-configuration, deadline-cloud, powershell, installer, service-managed-fleet, windows]
---

# Host Config from Installer

## Overview

This skill walks a customer through installing any Windows `.exe` software on their local machine
and verifying it works. It then uploads the installer to S3 and converts the verified steps into a
PowerShell host configuration script for AWS Deadline Cloud Windows Service Managed Fleets.

The generated `.ps1` is based on commands that were tested and confirmed working, not
guesswork or templates.

## Usage

Use this skill when:
- A customer has a `.exe` installer and wants it running on their Deadline Cloud fleet workers
- A customer wants to convert a manual install process into a host config script
- The software isn't covered by an existing specific skill (e.g. `3dsmax-host-config`)

## Prerequisites

Before starting, confirm the customer has:
- The `.exe` installer file available locally on a Windows machine
- AWS CLI installed and configured with credentials that have `s3:PutObject` access
- An S3 bucket in the same region as their Deadline Cloud farm (or willingness to create one)
- PowerShell available on their local machine

## Workflow

You MUST follow these steps in order. At each step, execute the command and check the output.
Do not proceed until the step succeeds.

### Step 1: Gather information

Ask the customer:
- What software are they installing? (name and version)
- Where is the installer file located locally? (full path)
- Do they have an S3 bucket already, or do they need one created?
- What is their AWS region?

### Step 2: Try the silent install

Run the installer with common silent flags. Try them in this order until one works:

```powershell
# Attempt 1 - NSIS style
Start-Process "<installer-path>" -ArgumentList '/S' -Wait -PassThru

# Attempt 2 - Inno Setup style
Start-Process "<installer-path>" -ArgumentList '/VERYSILENT', '/SUPPRESSMSGBOXES', '/NORESTART' -Wait -PassThru

# Attempt 3 - MSI wrapped in exe
Start-Process "<installer-path>" -ArgumentList '/quiet', '/norestart' -Wait -PassThru

# Attempt 4 - InstallShield style
Start-Process "<installer-path>" -ArgumentList '-s' -Wait -PassThru
```

After each attempt, check whether the software was installed by looking for it in
`C:\Program Files\` or `C:\Program Files (x86)\`. Ask the customer to confirm.

If none of the above work, ask the customer to check the installer's documentation or
run `<installer-path> /?` or `<installer-path> /help` to discover the correct flags.

### Step 3: Verify the install

Once installed, verify the software runs correctly. Ask the customer to run the most basic
verification command for the software:

```powershell
# Check the install directory exists
Get-ChildItem "C:\Program Files\<SoftwareName>"

# Try running the executable
& "C:\Program Files\<SoftwareName>\<executable>.exe" --version
```

Confirm with the customer that the output looks correct before proceeding.

### Step 4: Capture environment changes

Ask the customer to check what environment variables or PATH entries the installer added:

```powershell
# Check machine-level env vars
[System.Environment]::GetEnvironmentVariables('Machine') | Format-List
```

Note down any new variables or PATH entries. The host config script must set them explicitly,
since the installer won't run interactively on fleet workers.

### Step 5: Ensure the S3 bucket exists

If the customer doesn't have a bucket yet, create one:

```powershell
aws s3 mb s3://<bucket-name> --region <region>
```

> Make sure the fleet's IAM role has `s3:GetObject` permission on this bucket.
> Without it, workers won't be able to download the installer at runtime.

If they already have one, verify access:

```powershell
aws s3 ls s3://<bucket-name>
```

### Step 6: Upload the installer to S3

```powershell
aws s3 cp "<local-installer-path>" s3://<bucket-name>/<installer-filename>
```

Confirm the upload succeeded:

```powershell
aws s3 ls s3://<bucket-name>/<installer-filename>
```

### Step 7: Generate the host config script

Using the working install command from Step 2 and the env vars from Step 4, generate a `.ps1`
host configuration script. Place it in a new folder under `host_configuration_scripts/`:

```
host_configuration_scripts/<software-name>/<software-name>.ps1
host_configuration_scripts/<software-name>/README.md
```

The script MUST follow this structure:

```powershell
<#
Description of what this script installs.
Tested with: <software name and version>.
Requirements:
- S3 bucket containing the installer
- Fleet role with s3:GetObject permission
#>

# TODO: Replace with your bucket name
$BUCKET_NAME="your-bucket-name"

# TODO: Replace with your installer file name
$INSTALLER_FILE="<installer-filename>"

Write-Host ' --- Downloading installer --- '

mkdir C:\software_setup -Force
aws s3 cp --no-progress "s3://$BUCKET_NAME/$INSTALLER_FILE" C:\software_setup\

Write-Host ' --- Installing <software> --- '

Start-Process "C:\software_setup\$INSTALLER_FILE" -ArgumentList '<verified-silent-flags>' -Wait

Write-Host ' --- Configuring environment --- '

# Set any env vars captured in Step 4
[Environment]::SetEnvironmentVariable('<VAR_NAME>', '<value>', 'Machine')

Exit 0
```

### Step 8: Write the README.md

Include:
- What the script installs
- Installation guide (S3 bucket, upload installer, configure fleet, IAM role, test)
- Note about TODO variables to replace
- Note that config changes only affect Workers launched after the update is applied
- Recommendation to set min Worker count to 1 and check CloudWatch logs
  (log group: `/aws/deadline/<farm-id>/<fleet-id>`)

## Common Mistakes

- Not using `-Wait` in `Start-Process`, which lets the script proceed before the install finishes
- Forgetting `mkdir C:\software_setup -Force` before the first download
- Missing `Exit 0` at the end
- Env vars set during interactive install won't apply on fleet workers. They MUST be set
  explicitly with `[Environment]::SetEnvironmentVariable(..., 'Machine')`
- Fleet IAM role must have `s3:GetObject` on the bucket, which is easy to forget
