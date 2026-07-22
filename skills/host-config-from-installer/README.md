# Host Config from Installer

This skill helps you create a PowerShell host configuration script for any Windows `.exe` software
you want to run on AWS Deadline Cloud Service Managed Fleet workers.

Instead of writing the script manually, Kiro will walk you through installing the software on your
local machine and verifying it works. It then uploads the installer to S3 and generates the script from the steps
that were confirmed working.

## How to use this skill with Kiro

### Prerequisites

- [Kiro](https://kiro.dev) installed
- This repository cloned and opened as a workspace in Kiro
- The `.exe` installer file available on your local Windows machine
- AWS CLI installed and configured with credentials that have S3 access

### Steps

1. Open Kiro chat
2. Tell Kiro what you want to install:
   - `"I have a RealFlow 10 installer and I want to run it on my Deadline Cloud fleet"`
   - `"Help me create a host config script for Marvelous Designer 12"`
   - `"I want to install this .exe on my Service Managed Fleet workers"`
3. Kiro will guide you step by step: it runs and tests the installer, uploads it to S3, then
   generates the `.ps1` script
4. At the end, review the generated script, fill in any `TODO` variables, and configure your fleet
