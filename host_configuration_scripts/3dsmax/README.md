# Sample Host Configuration scripts to install 3ds Max to Service Managed Fleets for AWS Deadline Cloud

This folder contains sample host configuration scripts you can use to configure your AWS Deadline Cloud Windows Service Managed Fleets to install and run 3ds Max jobs on your workers.
Please see the README.md in each sample script for more steps on how to set it up.

## 3ds Max
3ds Max is a popular Digital Content Creation tool provided by Autodesk. 3ds Max runs on Windows, and requires administrative access to install onto a host. Because of the administrative requirement, Deadline Cloud recommends installing 3ds Max on to the worker host using Host Configuration Scripts.

- Note: While the example installs 3ds Max 2024 and 2025, Deadline Cloud's submitter supports 3ds Max 2026 and 2027 as well. The installation script should work equivalently for 3ds Max 2026 and 2027.

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
- Each sample requires you to have the 3ds Max installer in an S3 bucket in your AWS account. You can download the 3ds Max installer directly from Autodesk. See the next section for instructions on how to properly package the installer files.
- The host configuration scripts will download the installers from your S3 bucket, so your Fleet roles will need to be granted s3:GetObject permissions for the installers in S3.

## Creating a 3ds Max installer archive in .zip format
Autodesk provides 3ds Max as a .7z archive which cannot be easily extracted from the command line without 3rd party software like [7-zip](https://www.7-zip.org/). To get around this problem, the examples in this folder expect a .zip archive instead. You can create a .zip archive with the following steps:

1. Navigate to the [Products and Services page on the Autodesk Website](https://manage.autodesk.com/products), sign into your Autodesk account, and click View details under 3ds Max.
<img width="1431" height="703" alt="image" src="https://github.com/user-attachments/assets/b0df83ac-0eaa-431f-8216-763db29c5705" />

2. Select your version and then click the dropdown icon next to the **Download** button and choose **Direct Download**. Note that this dropdown has different options than the one on the previous page. This will download a .7z and a .exe file.
<img width="587" height="645" alt="image" src="https://github.com/user-attachments/assets/32faf766-e26c-4dea-94ac-c8fde7dc8ccd" />

3. With both the .7z and .exe file in the same folder, double-click the .exe file and wait for it to extract the .7z for you. When the extraction is done, choose **Open in folder**.
<img width="514" height="154" alt="image" src="https://github.com/user-attachments/assets/42450f53-800f-4703-8b63-353bca2bed83" />

4. Finally, select all files in the resulting folder and right-click them to bring up the context menu. Choose **Send to > Compressed (zipped) folder**.
<img width="925" height="547" alt="image" src="https://github.com/user-attachments/assets/48ba83fe-f1e8-4396-ac3b-ded1f10bf55f" />
