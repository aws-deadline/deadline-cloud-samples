# Sample Host Configuration script to install 3ds Max 2027 and V-Ray to Service Managed Fleets for AWS Deadline Cloud

This sample host configuration script configures your Service Managed Fleet with 3ds Max 2027 and V-Ray.

## Installation guide
1. Create an S3 bucket in your AWS account.
2. Download the 3ds Max installer from Autodesk, zip up the installer, and upload it to your S3 bucket.
3. Download the V-Ray for 3ds Max 2027 installer from Chaos and upload it to your S3 bucket.
4. Configure the Windows Service Managed fleet's host configuration using [3dsmax-2027-and-vray.ps1](./3dsmax-2027-and-vray.ps1).
    - Replace the `TODO` variables at the top with your S3 URIs.
5. Save the fleet configuration.
6. Configure your Fleet's IAM role to have `s3:GetObject` access to your S3 bucket.
7. Recommendation: Set the fleet's min Worker count to 1. Review the Worker's CloudWatch logs (`/aws/deadline/farm-<farm-id>/fleet-<fleet-id>`) to verify the script runs successfully before production use.
    - **Note**: Configuration changes only affect Workers launched after the update is applied.
