# Sample Host Configuration script to install 3ds Max 2027 to Service Managed Fleets for AWS Deadline Cloud

This sample host configuration script configures your Service Managed Fleet with 3ds Max 2027 to render your 3ds Max 2027 jobs.

## Installation guide
1. Create an S3 bucket in the same region as your Deadline Cloud farm.
2. Download the 3ds Max 2027 installer from Autodesk, zip up the installer folder, and upload it to your S3 bucket.
3. Configure the Windows Service Managed Fleet's host configuration using [3dsmax-2027.ps1](./3dsmax-2027.ps1).
    - Note that there are placeholder variables at the start of the script marked with `TODO`. Replace the values with ones matching your configuration.
4. Save the fleet configuration.
5. Configure your Fleet's IAM role to have `s3:GetObject` access to your S3 bucket.
6. Recommendation: Set the fleet's min worker count to 1. Review a worker's CloudWatch log to ensure the script executes successfully prior to production use.
    - Log group: `/aws/deadline/farm-<farm-id>/fleet-<fleet-id>`

> **Note:** Host configuration changes only affect Workers launched after the update is applied. Existing workers will not be updated.
