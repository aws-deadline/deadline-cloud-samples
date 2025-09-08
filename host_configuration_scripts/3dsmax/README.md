# Sample Host Configuration scripts to install 3ds Max to Service Managed Fleets for AWS Deadline Cloud

This folder contains sample host configuration scripts you can use to configure your AWS Deadline Cloud Windows Service Managed Fleets to install and run 3ds Max jobs on your workers.
Please see the README.md in each sample script for more steps on how to set it up.

## 3ds Max
3ds Max is a popular Digital Content Creation tool provided by Autodesk. 3ds Max runs on Windows, and requires administrative access to install onto a host. Because of the administrative requirement, Deadline Cloud recommends installing 3ds Max on to the worker host using Host Configuration Scripts.

- Note: While the example installs 3ds Max 2024, Deadline Cloud's submitter supports 3ds Max 2025, 2026 as well. The installation script should work equivalently for 3ds Max 2025, 2026.

## Common Prerequisites
- Each sample requires you to have the 3ds Max installer in an S3 bucket in your AWS account. You can download the 3ds Max installer directly from Autodesk.
- The host configuration scripts will download the installers from your S3 bucket, so your Fleet roles will need to be granted s3:GetObject permissions for the installers in S3.
