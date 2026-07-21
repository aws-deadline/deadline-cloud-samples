# 3ds Max host configuration scripts for AWS Deadline Cloud

These Windows host configuration scripts install 3ds Max and selected renderers or plugins on AWS Deadline Cloud service-managed fleet workers. 3ds Max requires administrative installation, so host configuration is the recommended delivery boundary.

## Sample index

This table covers every immediate sample directory in `host_configuration_scripts/3dsmax/`.

| Sample | What it demonstrates | Start here when |
|---|---|---|
| [3ds Max 2024](3dsmax-2024/) | Installing the base 2024 application | You need 3ds Max 2024 without bundled render plugins |
| [3ds Max 2025 and Corona 13](3dsmax-2025-and-corona-13/) | Installing 3ds Max with Corona Renderer | Your 2025 scenes render with Corona 13 |
| [3ds Max 2025 and V-Ray](3dsmax-2025-and-vray/) | Installing 3ds Max and V-Ray together | Your 2025 scenes use V-Ray |
| [3ds Max 2025, V-Ray, and AEC plugins](3dsmax-2025-vray-and-aec-plugins/) | Adding Forest Pack, RailClone, and architectural visualization plugins | A 2025 V-Ray workload uses common AEC plugins |
| [3ds Max 2025, V-Ray, and tyFlow](3dsmax-2025-vray-and-tyflow/) | Installing V-Ray and tyFlow with 3ds Max | A 2025 workload combines rendering and particle simulation |
| [3ds Max 2027](3dsmax-2027/) | Installing the base 2027 application | You need 3ds Max 2027 without bundled render plugins |
| [3ds Max 2027 and Corona 14](3dsmax-2027-and-corona-14/) | Installing the first Corona version supporting 3ds Max 2027 | Your 2027 scenes render with Corona 14 |
| [3ds Max 2027 and V-Ray](3dsmax-2027-and-vray/) | Installing 3ds Max 2027 and V-Ray | Your 2027 scenes use V-Ray |
| [3ds Max 2027, V-Ray, and tyFlow](3dsmax-2027-and-vray-and-tyflow/) | Installing V-Ray and tyFlow with 3ds Max 2027 | A 2027 workload combines rendering and particle simulation |
| [3ds Max 2027, V-Ray, and AEC plugins](3dsmax-2027-vray-and-aec-plugins/) | Adding Forest Pack, RailClone, FloorGenerator, and MultiTexture | A 2027 V-Ray workload uses architectural visualization plugins |

The samples currently cover 3ds Max 2024, 2025, and 2027. The Deadline Cloud submitter also supports 3ds Max 2026; adapt the nearest script for that installer and verify all product-specific silent-install options.

## Generate a script for another version with Kiro

The samples cover specific combinations. To create a script for another 3ds Max version, renderer, or plugin combination, you can use [Kiro](https://kiro.dev) with this repository.

### Prerequisites

* Install [Kiro](https://kiro.dev).
* Clone this repository and open it as the Kiro workspace.

### Steps

1. Ask for the combination you need, for example:
   * `Create a host configuration script for 3ds Max 2026`
   * `Create a host configuration script for 3ds Max 2026 and V-Ray 8`
   * `Create a host configuration script for 3ds Max 2027 and Corona 14`
   * `Add a host configuration script for 3ds Max 2026 with Forest Pack 10`
2. Kiro reads [`skills/3dsmax-host-config/SKILL.md`](../../skills/3dsmax-host-config/SKILL.md) and generates a script and README for the requested combination.
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
