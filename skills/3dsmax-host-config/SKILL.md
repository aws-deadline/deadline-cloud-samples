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

**Important:** The add-ons in this skill (V-Ray, Corona, tyFlow, AEC plugins) are only supported
as part of a 3ds Max installation. If the customer asks to install a plugin standalone without
3ds Max, let them know this skill only covers 3ds Max + plugin combinations and direct them to
use the `host-config-from-installer` skill instead.

## Core Concepts

- Scripts are PowerShell (`.ps1`) targeting Windows Service Managed Fleets
- Each script downloads installers from a customer-owned S3 bucket using the AWS CLI (`aws s3 cp`)
- All version-specific values are exposed as `$VARIABLES` at the top of the script, marked with `# TODO`
- After installing 3ds Max, every script MUST set these environment variables at Machine scope:
  - `Path` — add `C:\Program Files\Autodesk\3ds Max <VERSION>`
  - `3DSMAX_EXECUTABLE` — path to `3dsmaxbatch.exe`
  - `PYTHONPATH` — 3ds Max Python and Scripts dirs
  - `Path` — also add the Python and Scripts dirs
- Every script MUST install `deadline-cloud-for-3ds-max` via the bundled Python pip
- Scripts MUST end with `Exit 0`
- Each script lives in its own subfolder alongside a `README.md`

## Workflow

You MUST follow these steps in order.

### Step 1: Clarify the request

Ask the user (if not already specified):
- Which 3ds Max version? (e.g. 2026, 2027)
- Any renderer or plugin? (V-Ray, Corona, tyFlow, Forest Pack, RailClone, none)
- If a renderer: which version?

### Step 2: Find the closest existing script as a template

Look in `host_configuration_scripts/3dsmax/` for the most similar existing script and read it in full.

**If updating an existing script** (e.g. bumping 3ds Max 2025 → 2026, or V-Ray 7 → 8):
- Create a new folder and script — do not edit the existing one
- Update every version occurrence: `$VARIABLES`, `Write-Host` messages, install paths, env var names
  (e.g. `VRAY_FOR_3DSMAX2025_MAIN` → `VRAY_FOR_3DSMAX2026_MAIN`)

### Step 3: Determine folder and file names

Follow the existing naming convention:
- Base only: `3dsmax-<YEAR>/3dsmax-<YEAR>.ps1`
- One plugin: `3dsmax-<YEAR>-and-<plugin>/3dsmax-<YEAR>-and-<plugin>.ps1`
- Multiple plugins: `3dsmax-<YEAR>-<plugin1>-and-<plugin2>/...`

When in doubt, look at existing folder names in `host_configuration_scripts/3dsmax/`.

### Step 4: Write the script

Structure:
1. Header comment block — what it installs, tested with, S3 requirements
2. TODO variables — bucket name, folder names, zip names, installer file names, install roots
3. Install 3ds Max — `mkdir C:\3dsmax_setup -Force`, `aws s3 cp`, `Expand-Archive`, `Start-Process Setup.exe -q -Wait`
4. For each plugin — find its add-on in `skills/3dsmax-host-config/add-ons/`, download from S3 into `C:\3dsmax_setup\`, then run its silent installer
5. Configure environment for 3ds Max
6. Configure environment for each plugin (from add-on)
7. Install Deadline Cloud — `python.exe -m ensurepip` then `pip install deadline-cloud-for-3ds-max`
8. `Exit 0`

Key patterns:
```powershell
# Download from S3
aws s3 cp --no-progress "s3://$BUCKET_NAME/$ZIP_FILE" C:\3dsmax_setup\3dsmax.zip

# Install 3ds Max silently
Start-Process "C:\3dsmax_setup\$FOLDER_NAME\Setup.exe" -ArgumentList '-q' -Wait

# Set env vars
[Environment]::SetEnvironmentVariable('3DSMAX_EXECUTABLE', "C:\Program Files\Autodesk\3ds Max $VERSION\3dsmaxbatch.exe", 'Machine')

# Install deadline-cloud-for-3ds-max
& "C:\Program Files\Autodesk\3ds Max $VERSION\Python\python.exe" -m ensurepip
& "C:\Program Files\Autodesk\3ds Max $VERSION\Python\python.exe" -m pip install deadline-cloud-for-3ds-max
```

### Step 5: Write the README.md

Follow the style of `3dsmax-2025-and-vray/README.md`. Include:
- Title and one-line description
- Brief description of any plugins
- Installation guide (S3 bucket, upload installers, configure fleet, save, IAM role, test)
- Note about TODO variables
- Note that config changes only affect Workers launched after the update
- CloudWatch log group: `/aws/deadline/farm-<farm-id>/fleet-<fleet-id>`

### Step 6: Test the script locally

Before considering the script done:
1. Run the generated `.ps1` locally on a Windows machine to verify the install succeeds
2. Verify 3ds Max installed correctly:
   ```powershell
   & "C:\Program Files\Autodesk\3ds Max <YEAR>\3dsmaxbatch.exe" -help
   ```
3. If the script includes V-Ray, use the `sunflower_sphere` test bundle in
   `host_configuration_scripts/3dsmax/3dsmax-2025-and-vray/sunflower_sphere/` to verify rendering works:
   ```
   deadline bundle submit host_configuration_scripts/3dsmax/3dsmax-2025-and-vray/sunflower_sphere
   ```
   The job should complete and produce a rendered sphere with a sunflower texture.
4. For other plugin combinations, verify the plugin loads by opening 3ds Max and checking
   the plugin is available, or run a minimal batch render with a scene that uses the plugin.

### Step 7: Update the top-level README

Check `host_configuration_scripts/3dsmax/README.md` and update if the new script introduces a
version or plugin not already listed.

## Common Mistakes

- Forgetting `mkdir C:\3dsmax_setup -Force` before the first `aws s3 cp`
- Missing `Exit 0` at the end
- Setting env vars before installing — always install first, then configure
- Using `&&` as a command separator — PowerShell uses `;` or separate lines
- Forgetting `-m ensurepip` before `-m pip install`
- When bumping versions: forgetting to update year suffixes in env var names
  (e.g. `VRAY_FOR_3DSMAX2025_MAIN` → `VRAY_FOR_3DSMAX2026_MAIN`)
