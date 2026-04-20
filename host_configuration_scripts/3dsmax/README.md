# Sample Host Configuration scripts to install 3ds Max to Service Managed Fleets for AWS Deadline Cloud

This folder contains sample host configuration scripts you can use to configure your AWS Deadline Cloud Windows Service Managed Fleets to install and run 3ds Max jobs on your workers.
Please see the README.md in each sample script for more steps on how to set it up.

## 3ds Max
3ds Max is a popular Digital Content Creation tool provided by Autodesk. 3ds Max runs on Windows, and requires administrative access to install onto a host. Because of the administrative requirement, Deadline Cloud recommends installing 3ds Max on to the worker host using Host Configuration Scripts.

- Note: While the example installs 3ds Max 2024, Deadline Cloud's submitter supports 3ds Max 2025, 2026 as well. The installation script should work equivalently for 3ds Max 2025, 2026.

## Generating a script for your version using Kiro

The sample scripts in this folder cover specific version combinations. If you need a script for a different version of 3ds Max, a different renderer, or a different plugin combination, you can use [Kiro](https://kiro.dev) to generate one for you.

### Prerequisites

- [Kiro](https://kiro.dev) installed
- This repository cloned and opened as a workspace in Kiro

### Steps

1. In the Kiro chat, type a request like:
   - `"Create a host configuration script for 3ds Max 2026"`
   - `"Create a host configuration script for 3ds Max 2026 and V-Ray 8"`
   - `"Create a host configuration script for 3ds Max 2027 and Corona 14"`
   - `"Add a host configuration script for 3ds Max 2026 with Forest Pack 10"`
2. Kiro will read the skill in `skills/3dsmax-host-config/SKILL.md` and generate the correct script and README for your version combination.
3. Review the generated script, fill in the `TODO` variables at the top (your S3 bucket name, installer file names), and configure your fleet.

## Common Prerequisites
- Each sample requires you to have the 3ds Max installer in an S3 bucket in your AWS account. You can download the 3ds Max installer directly from Autodesk.
- The host configuration scripts will download the installers from your S3 bucket, so your Fleet roles will need to be granted s3:GetObject permissions for the installers in S3.
