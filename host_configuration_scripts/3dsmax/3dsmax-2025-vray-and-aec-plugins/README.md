# Sample Host Configuration scripts to install 3ds Max 2025, V-Ray, and AEC plugins to Service Managed Fleets for AWS Deadline Cloud

This sample host configuration script configures your Service Managed Fleet with 3ds Max 2025, V-Ray, Forest Pack, RailClone, and additional AEC plugins to render your 3ds Max 2025 jobs with V-Ray and architectural visualization plugins.

## V-Ray
V-Ray is a professional rendering engine developed by Chaos Group for 3D computer graphics applications. V-Ray integrates as a plugin with 3ds Max, providing photorealistic ray-traced rendering capabilities.

## Forest Pack
Forest Pack is a plugin for 3ds Max that provides scattering and distribution tools for creating realistic forests, vegetation, and other scattered objects in architectural and environmental visualizations.

## RailClone
RailClone is a parametric modeling plugin for 3ds Max that enables the creation of complex linear and area-based structures like fences, roads, buildings, and architectural elements.

## Additional Plugins
This script also installs FloorGenerator and MultiTexture plugins for enhanced architectural visualization capabilities.

## Version Compatibility
This script can be adapted for other compatible versions by updating the variable names and paths accordingly:
- 3ds Max 2026 or other versions
- V-Ray 7 or compatible versions
- Compatible versions of Forest Pack, RailClone, and other AEC plugins

## Installation guide
1. Create an S3 bucket in your AWS account.
2. Download the 3ds Max installer from Autodesk, zip up the installer, and upload it to your S3 bucket.
3. Download the V-Ray for 3ds Max 2025 installer from Chaos and upload it to your S3 bucket.
4. Download the Forest Pack installer from iToo Software and upload it to your S3 bucket.
5. Download the RailClone installer from iToo Software and upload it to your S3 bucket.
6. Download the FloorGenerator and MultiTexture plugin files and upload them to your S3 bucket.
7. Configure the Windows Service Managed fleet's host configuration using [3dsmax-2025-vray-and-aec-plugins.ps1](./3dsmax-2025-vray-and-aec-plugins.ps1).
    - Note that there are placeholder variables at the start of the script marked with `TODO`. Please replace the values with ones matching your configuration.
    - **Note**: The plugin installation sections can be adapted for other 3ds Max versions by updating the plugins directory path to match your target version.
8. Save the fleet configuration.
    - **Important**: Configuration changes only affect Worker instances launched after this update is applied. Existing Workers will continue using the previous configuration.
9. Configure your Fleet's IAM role to have read access to your S3 bucket.
10. For testing: Set the fleet's min Worker count to 1 which will spin up a Worker and run the Host Configuration script on it. Review Worker's CloudWatch logs (found in the `/aws/deadline/farm-<farm-id>/fleet-<fleet-id>` log group) to ensure the script is executed successfully on the Worker prior to production use.