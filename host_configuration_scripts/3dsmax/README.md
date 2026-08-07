# 3ds Max host configuration scripts for AWS Deadline Cloud

These Windows host configuration scripts install 3ds Max and selected renderers or plugins on AWS Deadline Cloud service-managed fleet workers. 3ds Max requires administrative installation, so host configuration is the recommended delivery boundary.

Each script is self-contained: it downloads the installers you stage in your own S3 bucket and runs their silent installs. Replace the `TODO` variables at the top of the script with your S3 URIs before using it.

## Sample index

Scripts are grouped by 3ds Max version. Each installs the listed software. Some need extra vendor installers that you stage in S3 (see the notes column).

### 3ds Max 2024

| Script | Installs | Extra installers to stage |
|---|---|---|
| [3dsmax-2024.ps1](3dsmax-2024.ps1) | Base 3ds Max 2024 | None |

### 3ds Max 2025

| Script | Installs | Extra installers to stage |
|---|---|---|
| [3dsmax-2025-and-corona-13.ps1](3dsmax-2025-and-corona-13.ps1) | 3ds Max 2025 + Corona 13 | Corona 13 (Chaos) |
| [3dsmax-2025-and-vray.ps1](3dsmax-2025-and-vray.ps1) | 3ds Max 2025 + V-Ray | V-Ray (Chaos) |
| [3dsmax-2025-vray-and-aec-plugins.ps1](3dsmax-2025-vray-and-aec-plugins.ps1) | 3ds Max 2025 + V-Ray + Forest Pack + RailClone + FloorGenerator + MultiTexture | V-Ray (Chaos); Forest Pack & RailClone (iToo); FloorGenerator; MultiTexture |
| [3dsmax-2025-vray-and-tyflow.ps1](3dsmax-2025-vray-and-tyflow.ps1) | 3ds Max 2025 + V-Ray + tyFlow | V-Ray (Chaos); tyFlow |
| [3dsmax-2025-and-pencilplus-4.ps1](3dsmax-2025-and-pencilplus-4.ps1) | 3ds Max 2025 + Pencil+ 4 (NTR, renders watermark-free under 3dsmaxcmd) | Pencil+ 4 (PSOFT) |

### 3ds Max 2027

| Script | Installs | Extra installers to stage |
|---|---|---|
| [3dsmax-2027.ps1](3dsmax-2027.ps1) | Base 3ds Max 2027 | None |
| [3dsmax-2027-and-corona-14.ps1](3dsmax-2027-and-corona-14.ps1) | 3ds Max 2027 + Corona 14 (first Corona to support 2027) | Corona 14 (Chaos) |
| [3dsmax-2027-and-vray.ps1](3dsmax-2027-and-vray.ps1) | 3ds Max 2027 + V-Ray | V-Ray (Chaos) |
| [3dsmax-2027-and-vray-and-tyflow.ps1](3dsmax-2027-and-vray-and-tyflow.ps1) | 3ds Max 2027 + V-Ray + tyFlow | V-Ray (Chaos); tyFlow |
| [3dsmax-2027-vray-and-aec-plugins.ps1](3dsmax-2027-vray-and-aec-plugins.ps1) | 3ds Max 2027 + V-Ray + Forest Pack + RailClone + FloorGenerator + MultiTexture | V-Ray (Chaos); Forest Pack & RailClone (iToo); FloorGenerator; MultiTexture |
| [3dsmax-2027-and-pencilplus-4.ps1](3dsmax-2027-and-pencilplus-4.ps1) | 3ds Max 2027 + Pencil+ 4 (NTR, renders watermark-free under 3dsmaxcmd) | Pencil+ 4 (PSOFT) |

The samples cover 3ds Max 2024, 2025, and 2027. The Deadline Cloud submitter also supports 3ds Max 2026. Adapt the nearest script for that installer and verify all product-specific silent-install options.

> **Using 3ds Max 2027?** Read [Known issue: Autodesk ADP "Failed to start"](#known-issue-autodesk-adp-failed-to-start-3ds-max-2027) before provisioning a fleet.

## Installation guide

The steps are the same for every script. Only the installers you stage in S3 differ (see the "Extra installers" column above).

1. Create an S3 bucket in your AWS account (same region as your farm recommended).
2. Download the 3ds Max installer from Autodesk and zip it following [Creating a 3ds Max installer archive in .zip format](#creating-a-3ds-max-installer-archive-in-zip-format), then upload it to your S3 bucket.
3. Download any extra installers listed for your chosen script (V-Ray, Corona, tyFlow, Forest Pack, RailClone, FloorGenerator, MultiTexture) from their vendors and upload them to your S3 bucket.
   - **V-Ray:** do not rename the V-Ray installer executable. It may silently fail if renamed after download from Chaos.
4. Configure the Windows service-managed fleet's host configuration with your chosen script, and replace the `TODO` variables at the top with your S3 URIs.
5. Save the fleet configuration.
6. Grant the fleet's IAM role `s3:GetObject` access to your S3 bucket.
7. Recommendation: set the fleet's min worker count to 1 and review the worker's CloudWatch logs (`/aws/deadline/farm-<farm-id>/fleet-<fleet-id>`) to confirm the script runs successfully before production use.

> Host configuration changes only affect workers launched after the update is applied. Existing workers are not updated.

## Test job bundle (V-Ray)

[`examples/sunflower_sphere/`](examples/sunflower_sphere/) is a ready-to-submit job bundle for verifying that a worker has 3ds Max and V-Ray configured correctly.

### Prerequisites

- The [AWS Deadline Cloud client](https://pypi.org/project/deadline/) or the [Deadline Cloud submitter](https://docs.aws.amazon.com/deadline-cloud/latest/userguide/submitter.html) installed.
- [Deadline Cloud monitor](https://docs.aws.amazon.com/deadline-cloud/latest/userguide/monitor-onboarding.html) logged in, or AWS credentials with permission to submit the job (e.g. `deadline:CreateJob` and `s3:PutObject` to your job attachments bucket).

### Steps

1. From `examples/sunflower_sphere/`, submit with the `deadline` CLI:
   - GUI: `deadline bundle gui-submit .`
   - No GUI: `deadline bundle submit .`
2. Monitor progress in the Deadline Cloud monitor or through the APIs.
3. After the job completes, download the output, a sphere with a sunflower texture pattern.

## Known issue: Autodesk ADP "Failed to start" (3ds Max 2027)

3ds Max 2027 launched in server mode (`3dsmaxbatch.exe` / `3dsmaxcmd.exe`, as render nodes do) can abort during startup with `ADP Failed to start` (exit code `-12`) when the launching user is opted out of the Autodesk Analytics Program (ADP). This blocks all rendering on affected workers. It applies to every 3ds Max 2027 script above (`3dsmax-2027`, `3dsmax-2027-and-vray`, `3dsmax-2027-and-corona-14`, `3dsmax-2027-and-vray-and-tyflow`, `3dsmax-2027-vray-and-aec-plugins`). This mirrors [deadline-cloud-for-3ds-max discussion #271](https://github.com/aws-deadline/deadline-cloud-for-3ds-max/discussions/271).

The 3ds Max log shows:

```
ADP Initialize: OptedOut
Starting network
ADP Failed to start
3ds Max Exit Code = -12
```

### Root cause

The failure occurs when the launching user is opted out of ADP. The opted-out path runs a "Starting network" step that cold-starts the Autodesk SSO server app `AdSSO.exe`. That executable is not installed: the ADP SDK bundled with 3ds Max 2027 still expects the legacy `AdSSO.exe`, but the installed Autodesk Identity Manager provides `AdSSOServices.dll` / `AdskIdentityManager.exe` and no `AdSSO.exe`. The SSO cold-start times out, ADP reports failure, and Max exits `-12`. The opted-in path (`ADP Initialize: Done`) skips the SSO step entirely.

Render nodes hit this because they run in server mode and their service account defaults to opted out. It is not headless-specific (a server-mode launch while opted out fails on an interactive workstation too) and not a Deadline Cloud issue (it reproduces with a plain `3dsmaxbatch.exe` launch).

### Workarounds

1. **Use 3ds Max 2026 render nodes** (not affected).
2. **Record an ADP opt-in consent for the render user before launch**, if you agree to it. Writing `%APPDATA%\Autodesk\ADPSDK\UserConsent\UnNamed.json` with all `optIn: true` and `userActionRequired: false` makes ADP reach `Done` so 3ds Max starts normally. On a service-managed fleet, write the file into the Default user profile from your host configuration script so every new profile (including the render service account) inherits it:

   ```powershell
   $consentDir = "C:\Users\Default\AppData\Roaming\Autodesk\ADPSDK\UserConsent"
   New-Item -ItemType Directory -Path $consentDir -Force | Out-Null
   $consent = @{
       preferences = @(
           @{ consentId = "ADSK_PUD_CONTRACTUAL_NECESSITY_DESKTOP";   optIn = $true },
           @{ consentId = "ADSK_PUD_OPTIMIZATION_IMPROVEMENT_DESKTOP"; optIn = $true },
           @{ consentId = "ADSK_PUD_GO_TO_MARKET_DESKTOP";            optIn = $true }
       )
       userActionRequired = $false
       userId = "UnNamed"
   }
   $consent | ConvertTo-Json -Depth 5 |
       Set-Content -Path (Join-Path $consentDir "UnNamed.json") -Encoding UTF8
   ```

   Writing this file records consent to Autodesk's analytics program. Apply it only if you accept that. Tooling should not opt users in on their behalf. Recording consent is a host-configuration or administrator step, not something the submitter or adaptor does automatically.

Opting out does not work: the same file with `optIn: false` still fails. A proper fix must come from Autodesk (make the opted-out server-mode path non-fatal, or provide a way to fully disable ADP).

## Generate a script for another version with Kiro

The samples cover specific combinations. To create a script for another 3ds Max version, renderer, or plugin combination, you can use [Kiro](https://kiro.dev) with this repository.

### Prerequisites

* Install [Kiro](https://kiro.dev).
* Clone this repository and open it as the Kiro workspace.

### Steps

1. Ask for the combination you need:
   * `Create a host configuration script for 3ds Max 2026`
   * `Create a host configuration script for 3ds Max 2026 and V-Ray 8`
   * `Create a host configuration script for 3ds Max 2027 and Corona 14`
   * `Add a host configuration script for 3ds Max 2026 with Forest Pack 10`
2. Kiro reads [`skills/3dsmax-host-config/SKILL.md`](../../skills/3dsmax-host-config/SKILL.md) and generates a `.ps1` script in this directory, then adds a row to the sample index above.
3. Review and test the generated script, replace its `TODO` values with your S3 bucket and installer names, and then configure the fleet.

## Common prerequisites

* Download each licensed installer from its vendor and place it in an S3 bucket in your account.
* Grant the fleet role `s3:GetObject` for the installer objects.
* Review installer versions, checksums where available, silent flags, licensing, and restart requirements before using a script.

## Creating a 3ds Max installer archive in .zip format

Autodesk distributes 3ds Max as a `.7z` archive plus an extraction executable. The samples expect a ZIP so Windows can extract it without third-party software such as [7-Zip](https://www.7-zip.org/).

1. Open the [Autodesk Products and Services page](https://manage.autodesk.com/products), sign in, and choose **View details** for 3ds Max.
   <img width="1431" height="703" alt="Autodesk product details page" src="https://github.com/user-attachments/assets/b0df83ac-0eaa-431f-8216-763db29c5705" />
2. Select the version, open the menu beside **Download**, and choose **Direct Download**. Keep the downloaded `.7z` and `.exe` in the same folder.
   <img width="587" height="645" alt="Autodesk direct download menu" src="https://github.com/user-attachments/assets/32faf766-e26c-4dea-94ac-c8fde7dc8ccd" />
3. Run the `.exe`, wait for extraction, and choose **Open in folder**.
   <img width="514" height="154" alt="Autodesk extraction completion dialog" src="https://github.com/user-attachments/assets/42450f53-800f-4703-8b63-353bca2bed83" />
4. Select all extracted files and choose **Send to > Compressed (zipped) folder**.
   <img width="925" height="547" alt="Windows compressed folder menu" src="https://github.com/user-attachments/assets/48ba83fe-f1e8-4396-ac3b-ded1f10bf55f" />
