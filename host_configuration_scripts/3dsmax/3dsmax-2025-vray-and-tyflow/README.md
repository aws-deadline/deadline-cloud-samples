# Sample Host Configuration scripts to install 3ds Max 2025, V-Ray and tyFlow to Service Managed Fleets for AWS Deadline Cloud

This sample host configuration script configures your Service Managed Fleet with 3ds Max 2025, V-Ray, and tyFlow to render your 3ds Max 2025 jobs with V-Ray and tyFlow plugins.

## V-Ray
V-Ray is a professional rendering engine developed by Chaos Group for 3D computer graphics applications. V-Ray integrates as a plugin with 3ds Max, providing photorealistic ray-traced rendering capabilities.

## tyFlow
tyFlow is a powerful particle system and physics simulation plugin for 3ds Max, enabling complex procedural animations and effects.

## Installation guide
1. Create an S3 bucket in your AWS account.
2. Download the 3ds Max installer from Autodesk, zip up the installer, and upload it to your S3 bucket.
3. Download the V-Ray for 3ds Max 2025 installer from Chaos and upload it to your S3 bucket.
4. Download the tyFlow plugin file and upload it to your S3 bucket.
5. Configure the Windows Service Managed fleet's host configuration using [3dsmax-2025-vray-and-tyflow.ps1](./3dsmax-2025-vray-and-tyflow.ps1).
    - Note that there are placeholder variables at the start of the script marked with `TODO`. Please replace the values with ones matching your configuration.
    - **Note**: The tyFlow installation section (lines 57-62) can be adapted for other 3ds Max versions by updating the plugins directory path to match your target version.
6. Save the fleet configuration.
    - **Important**: Configuration changes only affect Worker instances launched after this update is applied. Existing Workers will continue using the previous configuration.
7. Configure your Fleet's IAM role to have read access to your S3 bucket.
8. For testing: Set the fleet's min Worker count to 1 which will spin up a Worker and run the Host Configuration script on it. Review Worker's CloudWatch logs (found in the `/aws/deadline/farm-<farm-id>/fleet-<fleet-id>` log group) to ensure the script is executed successfully on the Worker prior to production use.