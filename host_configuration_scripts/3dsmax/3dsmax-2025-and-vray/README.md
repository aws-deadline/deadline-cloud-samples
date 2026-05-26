# Sample Host Configuration scripts to install 3ds Max 2025 and V-Ray to Service Managed Fleets for AWS Deadline Cloud

This sample host configuration scripts configures your Service Managed Fleet with 3ds Max 2025 and V-Ray to render your 3ds Max 2025 jobs with V-Ray.

## V-Ray
V-Ray is a professional rendering engine developed by Chaos Group for 3D computer graphics applications. V-Ray integrates as a plugin with 3ds Max, providing photorealistic ray-traced rendering capabilities.

## Installation guide
1. Create an S3 bucket in your AWS account.
2. Download the 3ds Max installer from Autodesk, zip up the installer according to [these steps](/host_configuration_scripts/3dsmax/README.md#creating-a-3ds-max-installer-archive-in-zip-format), and upload it to your S3 bucket.
3. Download the V-Ray for 3ds Max 2025 installer from Chaos and upload it to your S3 bucket
4. Configure the Windows Service Managed fleet's host configuration using [3dsmax-2025-and-vray.ps1](./3dsmax-2025-and-vray.ps1).
    - Note that there are placeholder variables at the start of the script marked with `TODO`. Please replace the values with ones matching your configuration.
5. Save the fleet configuration.
6. Configure your Fleet's IAM role to have read access to your S3 bucket.
7. Recommendation: Set the fleet's min worker count to 1. Review a worker's CloudWatch log to ensure the script is executed successfully prior to production use. 

## Test Job Bundle Submission

You can submit a test job bundle included in this example script (`sunflower_sphere`) to make sure your workers have 3ds Max and V-Ray configured correctly before setting up your workstation.

### Prerequisites

- You either have the [AWS Deadline Cloud Client](https://pypi.org/project/deadline/) Python package installed, or the [Deadline Cloud Submitter](https://docs.aws.amazon.com/deadline-cloud/latest/userguide/submitter.html) installed
- You either have [Deadline Cloud Monitor](https://docs.aws.amazon.com/deadline-cloud/latest/userguide/monitor-onboarding.html) installed and are logged into it or have AWS credentials available with sufficient permissions to submit the job (e.g. `deadline:CreateJob` and `s3:PutObject` to your Job Attachments bucket)

### Job Bundle Submission Steps

1. Open up a terminal
2. Navigate to the `sunflower_sphere` folder in this directory (e.g. `cd sunflower_sphere`)
3. Submit the bundle using the `deadline` CLI
    - With a GUI: `deadline bundle gui-submit .`
    - No GUI: `deadline bundle submit .`
4. Once the job submission completes, you can monitor job progress using the Deadline Cloud Monitor, web monitor, or AWS Deadline Cloud APIs.
5. After the job completes, download the output. It should be a sphere with a sunflower texture pattern on it.
