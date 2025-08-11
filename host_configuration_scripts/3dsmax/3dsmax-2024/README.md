# Sample Host Configuration scripts to install 3ds Max to Service Managed Fleets for AWS Deadline Cloud

## 3ds Max
3ds Max is a popular Digital Content Creation tool provided by Autodesk. 3ds Max runs on Windows, and requires administrative access to install onto a host. Because of the administrative requirement, Deadline Cloud recommends installing 3ds Max on to the worker host using Host Configuration Scripts.

- Note: While the example installs 3ds Max 2024, Deadline Cloud's submitter supports 3ds Max 2025, 2026 as well. The installation script should work equivalently for 3ds Max 2025, 2026.

## Installation guide
1. Create a S3 bucket in the same region as your farm.
2. Download the 3ds Max installer from Autodesk, and zip up the installer as `3ds Max.zip`.
3. Configure the Windows Service Managed fleet's host configuration using [3ds Max-2024.ps1](./3ds Max-2024.ps1).
4. Save the fleet configuration.
5. Configure the Fleet IAM role to have S3 bucket access.
6. Recommendation: Set the fleet's min worker count to 1. Review a worker's CloudWatch log to ensure the script is executed successfully prior to production use. 

## Detailed Step by Step installation guide
Blog - [Coming soon]