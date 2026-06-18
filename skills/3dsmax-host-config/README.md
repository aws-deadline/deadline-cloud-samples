# 3ds Max Host Config

This skill helps you generate a PowerShell host configuration script for any version of 3ds Max
and supported plugin combinations (V-Ray, Corona, tyFlow, Forest Pack, RailClone, and more) for
AWS Deadline Cloud Service Managed Fleet workers.

## How to use this skill with Kiro

### Prerequisites

- [Kiro](https://kiro.dev) installed
- This repository cloned and opened as a workspace in Kiro
- The 3ds Max installer (and any plugin installers) downloaded from the vendor and available locally
- An S3 bucket in the same region as your Deadline Cloud farm to host the installers

### Steps

1. Open Kiro chat
2. Tell Kiro what you need, for example:
   - `"Create a host configuration script for 3ds Max 2026"`
   - `"Create a host configuration script for 3ds Max 2026 and V-Ray 8"`
   - `"Add a host config script for 3ds Max 2027 with Forest Pack 10 and RailClone 7"`
3. Kiro will generate the `.ps1` script and a `README.md` for your version combination
4. Fill in the `TODO` variables at the top of the script — each installer has its own full S3 URI variable (e.g. `$3DS_MAX_INSTALLER_ZIP_S3_URI="s3://your-bucket/path/to/installer.zip"`)
5. Upload your installers to your S3 bucket
6. Configure your Service Managed Fleet to use the generated script
