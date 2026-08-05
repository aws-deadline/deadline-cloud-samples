---
name: 3dsmax-host-config
description: >
  Create or update 3ds Max host configuration scripts for AWS Deadline Cloud Service Managed Fleets.
  Use when asked to "add a 3ds Max host config script", "create a host configuration for 3ds Max",
  "add support for 3ds Max YEAR", "update V-Ray to version X", "add Forest Pack", "update Forest Pack",
  "add RailClone", "add tyFlow", "add Corona", or when any new 3ds Max version or plugin combination
  needs a host configuration script.
tags: [skill, 3dsmax, host-configuration, deadline-cloud, powershell, service-managed-fleet]
---

# 3ds Max Host Configuration Script Builder

## Overview

This skill creates host configuration PowerShell scripts for AWS Deadline Cloud Windows Service Managed
Fleets. These scripts install 3ds Max (and optionally renderer plugins) onto worker hosts at fleet
startup, since 3ds Max requires administrative access to install.

All scripts live under `host_configuration_scripts/3dsmax/` and follow a consistent structure.

Plugin-specific instructions are in `skills/3dsmax-host-config/add-ons/`. Each `.md` file there is
a self-contained building block. When a customer needs a plugin, find the relevant add-on and
incorporate it into the ps1.

## Usage

Use this skill when:
- A new 3ds Max version needs a host configuration script
- A new plugin combination needs a script for an existing or new version
- An existing script needs its 3ds Max version, renderer version, or plugin version bumped
- Someone asks "add host config for 3ds Max X", "update to V-Ray 8", or "bump 3ds Max to 2026"

The add-ons in this skill (V-Ray, Corona, tyFlow, AEC plugins) are only supported
as part of a 3ds Max installation. If the customer asks to install a plugin standalone without
3ds Max, let them know this skill only covers 3ds Max + plugin combinations and direct them to
use the `host-config-from-installer` skill instead.

## Core Concepts

- Scripts are PowerShell (`.ps1`) targeting Windows Service Managed Fleets
- Each script downloads installers from a customer-owned S3 bucket using the AWS CLI (`aws s3 cp`)
- All version-specific values are exposed as `$VARIABLES` at the top of the script, marked with `# TODO`
- Each installer/plugin gets its own full S3 URI variable (e.g. `$3DS_MAX_INSTALLER_ZIP_S3_URI`). Do NOT use a shared `$BUCKET_NAME` + filename pattern
- The 3ds Max installer variable MUST include a comment linking to the zip creation guide:
  `# Guide on how to create the 3ds Max installer zip file: https://github.com/aws-deadline/deadline-cloud-samples/blob/mainline/host_configuration_scripts/3dsmax/README.md`
- After installing 3ds Max, every script MUST set these environment variables at Machine scope:
  - `Path`: add `C:\Program Files\Autodesk\3ds Max <VERSION>`
  - `3DSMAX_EXECUTABLE`: path to `3dsmaxbatch.exe`
  - `PYTHONPATH`: 3ds Max Python and Scripts dirs
  - `Path`: also add the Python and Scripts dirs
- Every script MUST install `deadline-cloud-for-3ds-max` via the bundled Python pip
- Scripts MUST end with `Exit 0`
- Each script lives directly under `host_configuration_scripts/3dsmax/`; a single shared `README.md` there documents every script with one sample-index row

## Workflow

You MUST follow these steps in order.

### Step 1: Clarify the request

Ask the user (if not already specified):
- Which 3ds Max version? (e.g. 2026, 2027)
- Any renderer or plugin? (V-Ray, Corona, tyFlow, Forest Pack, RailClone, none)
- If a renderer: which version?

### Step 2: Find the closest existing script as a template

Look in `host_configuration_scripts/3dsmax/` for the most similar existing script and read it in full.

**If updating an existing script** (e.g. bumping 3ds Max 2025 to 2026, or V-Ray 7 to 8):
- Create a new script at the directory root. Do not edit the existing one
- Update every version occurrence: `$VARIABLES`, `Write-Host` messages, install paths, env var names
  (e.g. `VRAY_FOR_3DSMAX2025_MAIN` to `VRAY_FOR_3DSMAX2026_MAIN`)

### Step 3: Determine the script file name

Scripts live directly under `host_configuration_scripts/3dsmax/` (no per-script subfolder). Follow the existing naming convention:

- Base only: `3dsmax-<YEAR>.ps1`
- One plugin: `3dsmax-<YEAR>-and-<plugin>.ps1`
- Multiple plugins: `3dsmax-<YEAR>-<plugin1>-and-<plugin2>.ps1`

When in doubt, look at the existing script names in `host_configuration_scripts/3dsmax/`.
### Step 4: Write the script

Structure:
1. Header comment block: what it installs and tests with, plus S3 requirements
2. TODO variables: one full S3 URI variable per installer/plugin file, each marked with `# TODO` and the zip guide comment for the 3ds Max installer
3. Install 3ds Max: `mkdir C:\3dsmax_setup -Force`, `aws s3 cp`, `Expand-Archive`, `Start-Process Setup.exe -q -Wait`
4. For each plugin, find its add-on in `skills/3dsmax-host-config/add-ons/`, download from S3 into `C:\3dsmax_setup\`, then run its silent installer
5. Configure environment for 3ds Max
6. Configure environment for each plugin (from add-on)
7. Install Deadline Cloud: `python.exe -m ensurepip` then `pip install deadline-cloud-for-3ds-max`
8. `Exit 0`

Key patterns:
```powershell
# TODO variables: one full S3 URI per installer/plugin
# Guide on how to create the 3ds Max installer zip file: https://github.com/aws-deadline/deadline-cloud-samples/blob/mainline/host_configuration_scripts/3dsmax/README.md
$3DS_MAX_INSTALLER_ZIP_S3_URI="s3://your-bucket-name/path/to/3ds-max-<YEAR>.zip"

# Download from S3 using the URI variable directly
aws s3 cp --no-progress "$3DS_MAX_INSTALLER_ZIP_S3_URI" C:\3dsmax_setup\3dsmax.zip

# Install 3ds Max silently. Setup.exe is at the root after extracting
Start-Process "C:\3dsmax_setup\Setup.exe" -ArgumentList '-q' -Wait

# Set env vars
[Environment]::SetEnvironmentVariable('3DSMAX_EXECUTABLE', "C:\Program Files\Autodesk\3ds Max $VERSION\3dsmaxbatch.exe", 'Machine')

# Install deadline-cloud-for-3ds-max
& "C:\Program Files\Autodesk\3ds Max $VERSION\Python\python.exe" -m ensurepip
& "C:\Program Files\Autodesk\3ds Max $VERSION\Python\python.exe" -m pip install deadline-cloud-for-3ds-max
```

### Step 5: Document the script in the shared README

All scripts share a single `host_configuration_scripts/3dsmax/README.md`. Do NOT create a per-script README. Add a row for the new script to the sample-index table under its 3ds Max version section (`### 3ds Max <YEAR>`) with:
- A link to the `.ps1`
- What it installs
- Extra vendor installers to stage in S3 (V-Ray, Corona, tyFlow, Forest Pack, RailClone, etc.), or a dash if none

If a `### 3ds Max <YEAR>` section does not exist yet, add one in version order.
### Step 6: Test the script locally and on a fleet worker

Before considering the script done:
1. Run the generated `.ps1` locally on a fresh Windows machine to verify the install succeeds end-to-end
2. Verify 3ds Max installed correctly:
   ```powershell
   & "C:\Program Files\Autodesk\3ds Max <YEAR>\3dsmaxbatch.exe" -help
   ```
3. Configure a Service Managed Fleet with the script, set min worker count to 1, and wait for a worker to start
4. If the script includes V-Ray, submit the `sunflower_sphere` test bundle against the fleet to verify rendering works end-to-end:
   ```
   deadline bundle submit host_configuration_scripts/3dsmax/examples/sunflower_sphere
   ```
   The job should complete and produce a rendered sphere with a sunflower texture.
5. For other plugin combinations, create a minimal job bundle that exercises the plugin and submit it to the fleet to confirm the setup is good before production use.

## Common Mistakes

- Using a shared `$BUCKET_NAME` variable. Each installer must have its own full S3 URI variable instead
- Using `$FOLDER_NAME\Setup.exe`. After `Expand-Archive`, `Setup.exe` is at the root of `C:\3dsmax_setup\`
- Missing `Exit 0` at the end
- Setting env vars before installing. Always install first, then configure
- Using `&&` as a command separator. PowerShell uses `;` or separate lines
- Forgetting `-m ensurepip` before `-m pip install`
- When bumping versions: forgetting to update year suffixes in env var names
  (e.g. `VRAY_FOR_3DSMAX2025_MAIN` to `VRAY_FOR_3DSMAX2026_MAIN`)
