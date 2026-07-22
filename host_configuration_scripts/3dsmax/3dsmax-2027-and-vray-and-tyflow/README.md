# Sample Host Configuration script to install 3ds Max 2027, V-Ray, and tyFlow to Service Managed Fleets for AWS Deadline Cloud

This sample host configuration script configures your Service Managed Fleet with 3ds Max 2027, V-Ray, and tyFlow.

## Installation guide
1. Create an S3 bucket in your AWS account.
2. Download the 3ds Max installer from Autodesk, zip up the installer, and upload it to your S3 bucket.
3. Download the V-Ray for 3ds Max 2027 installer from Chaos and upload it to your S3 bucket.
    - WARNING: Do not rename the V-Ray installer executable. The installer may silently fail if you give it a new name after downloading it from the Chaos Group website
4. Download the tyFlow plugin file for 3ds Max 2027 and upload it to your S3 bucket.
5. Configure the Windows Service Managed fleet's host configuration using [3dsmax-2027-and-vray-and-tyflow.ps1](./3dsmax-2027-and-vray-and-tyflow.ps1).
    - Replace the `TODO` variables at the top with your S3 URIs.
6. Save the fleet configuration.
7. Configure your Fleet's IAM role to have `s3:GetObject` access to your S3 bucket.
8. Recommendation: Set the fleet's min Worker count to 1. Review the Worker's CloudWatch logs (`/aws/deadline/farm-<farm-id>/fleet-<fleet-id>`) to verify the script runs successfully before production use.
    - Configuration changes only affect Workers launched after the update is applied.
