# A starter AWS Deadline Cloud farm (Terraform)

## Overview

This Terraform configuration deploys an [AWS Deadline Cloud](https://aws.amazon.com/deadline-cloud/) farm you can use to run jobs that render images, reconstruct 3D scenes, or transform your data in custom ways. This is the Terraform equivalent of the [CloudFormation starter_farm template](../../../cloudformation/farm_templates/starter_farm/).

Sample jobs to submit are available in the [deadline-cloud-samples on GitHub](https://github.com/aws-deadline/deadline-cloud-samples/tree/mainline/job_bundles#readme), Deadline Cloud provides many [integrated submitter plugins for applications](https://github.com/aws-deadline/#integrations), and you can [build your own jobs](https://docs.aws.amazon.com/deadline-cloud/latest/developerguide/building-jobs.html).

The deployed farm includes one or more [service-managed fleets](https://docs.aws.amazon.com/deadline-cloud/latest/userguide/smf-manage.html) that you select during deployment. The production queue supports Conda virtual environments for the applications that jobs need, and the package build queue can be used to build more packages if needed.

It configures two Conda channels by default: a private channel on an S3 bucket you provide and the [deadline-cloud channel](https://docs.aws.amazon.com/deadline-cloud/latest/userguide/create-queue-environment.html#conda-queue-environment). The `deadline-cloud` channel provides applications like Blender, Houdini, Maya, and Nuke. You can add the [conda-forge channel](https://conda-forge.org/) to this list by setting the `prod_conda_channels` variable to `"deadline-cloud conda-forge"` to access packages created and maintained by the [conda-forge community](https://conda-forge.org/community/).

When supported applications need licenses to run, they will use Deadline Cloud's usage-based licensing. See [Deadline Cloud pricing](https://aws.amazon.com/deadline-cloud/pricing/) to learn which applications are supported and the associated costs.

## Prerequisites

Before deploying this Terraform configuration, check that you have the following resources created in your AWS Account. The AWS region should be the same as the one you use to deploy the Terraform configuration.

1. [Terraform](https://www.terraform.io/downloads) >= 1.0 installed
2. AWS credentials configured (via `aws configure`, environment variables, or IAM role)
3. An Amazon S3 bucket to hold job attachments and your Conda channel. From the [Amazon S3 management console](https://s3.console.aws.amazon.com/s3/home), create an S3 bucket. You will need the bucket name to deploy the Terraform configuration.
4. A Deadline Cloud monitor to view and manage the jobs you will submit to your queues. From the [AWS Deadline Cloud management console](https://console.aws.amazon.com/deadlinecloud/home), select the "Go to Monitor setup" option and follow the steps to enter a name for your monitor URL, enable IAM Identity Center, and then create a user login account to access the monitor. Your monitor URL will look similar to `https://..deadlinecloud.amazonaws.com/`. You will need this URL to log in with the Deadline Cloud monitor desktop application.

## Resources Created

This configuration creates the following resources:

| Resource | Description |
|----------|-------------|
| `awscc_deadline_farm` | The Deadline Cloud farm |
| `awscc_deadline_queue` (x2) | Production queue and Package Build queue |
| `awscc_deadline_queue_environment` | Conda queue environment for the production queue |
| `awscc_deadline_fleet` (up to 3) | CPU Linux, CPU Windows, and/or CUDA Linux fleets |
| `awscc_deadline_queue_fleet_association` (up to 6) | Associations between queues and fleets |
| `aws_iam_role` (x3) | IAM roles for queues and fleet |
| `aws_iam_role_policy` (x3) | IAM policies for S3 access and CloudWatch Logs |

## Deployment

### 1. Initialize Terraform

```bash
cd terraform/farm_templates/starter_farm
terraform init
```

### 2. Configure Variables

Create a `terraform.tfvars` file or pass variables via command line:

```hcl
# Required
job_attachments_bucket_name = "your-s3-bucket-name"

# Optional - customize as needed
aws_region    = "us-west-2"
farm_name     = "My Deadline Cloud Farm"

# Fleet configuration (set to empty string to skip)
cpu_linux_fleet_name   = "CPU Linux Fleet"
cpu_windows_fleet_name = ""  # Skip Windows fleet
cuda_linux_fleet_name  = ""  # Skip CUDA fleet
```

### 3. Review the Plan

```bash
terraform plan
```

### 4. Apply the Configuration

```bash
terraform apply
```

### 5. Add User Access

From the [AWS Deadline Cloud management console](https://console.aws.amazon.com/deadlinecloud/home), navigate to the farm that you created, and select the "Access management" tab. Select "Users", then "Add user", and then add the user you created for yourself from the prerequisites. Use the "Owner" access level to give yourself full access.

## Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `aws_region` | AWS region | `us-west-2` |
| `job_attachments_bucket_name` | S3 bucket for job attachments | (required) |
| `farm_name` | Farm display name | `Starter Deadline Cloud Farm` |
| `prod_queue_name` | Production queue name | `Production Job Queue` |
| `package_build_queue_name` | Package build queue name | `Package Build Queue` |
| `prod_conda_channels` | Default Conda channels | `deadline-cloud` |
| `cpu_linux_fleet_name` | CPU Linux fleet name (empty to skip) | `CPU Linux Fleet` |
| `cpu_windows_fleet_name` | CPU Windows fleet name (empty to skip) | `""` |
| `cuda_linux_fleet_name` | CUDA Linux fleet name (empty to skip) | `""` |
| `max_cpu_linux_worker_count` | Max workers for CPU Linux fleet | `10` |
| `cpu_linux_instance_market_type` | `spot` or `on-demand` | `spot` |

See `main.tf` for the complete list of configurable variables.

## Outputs

| Output | Description |
|--------|-------------|
| `farm_id` | The Deadline Cloud farm ID |
| `farm_arn` | The Deadline Cloud farm ARN |
| `prod_queue_id` | The production queue ID |
| `package_build_queue_id` | The package build queue ID |
| `cpu_linux_fleet_id` | The CPU Linux fleet ID (if created) |
| `cpu_windows_fleet_id` | The CPU Windows fleet ID (if created) |
| `cuda_linux_fleet_id` | The CUDA Linux fleet ID (if created) |

## Install the Deadline client tools on your workstation

1. From the [AWS Deadline Cloud management console](https://console.aws.amazon.com/deadlinecloud/home),
   select the "Downloads" page on the left navigation area.
2. Download and install the Deadline Cloud monitor desktop application. Use your monitor URL and
   the user account from the prerequisites to log in from the Deadline Cloud monitor desktop. This also
   provides AWS credentials to the Deadline Cloud CLI.
3. Download and install the Deadline Cloud submitter installer for your platform, or install the
   Deadline Cloud CLI into your existing Python installation [from PyPI](https://pypi.org/project/deadline/)
   using a command like `pip install "deadline[gui]"`. You can then use the command
   `deadline handle-web-url --install` to install the job attachments download handler on supported operating systems.
4. From the terminal, run the command `deadline config gui`, and select the farm and production queue you deployed.
   Select OK to apply the settings.

## Initialize the S3 Conda channel

Before submitting jobs, initialize the S3 Conda channel by publishing a package to it. See [Publish packages to an Amazon S3 conda channel](https://docs.aws.amazon.com/deadline-cloud/latest/developerguide/publish-packages-s3-channel.html) in the AWS Deadline Cloud Developer Guide for instructions.

## Submit a test job

This test job runs the `imagemagick identify` command on a directory of images to extract properties of the images and write them to a text file. Before proceeding with this test job, make sure the S3 Conda channel is initialized according to the instructions above. An uninitialized Conda channel will fail during the "Launch Conda" action.

1. If you don't have a local copy of [deadline-cloud-samples](https://github.com/aws-deadline/deadline-cloud-samples) GitHub repository, you can make a git clone or [download it as a ZIP](https://github.com/aws-deadline/deadline-cloud-samples/archive/refs/heads/mainline.zip).
2. From the `job_bundles` directory of `deadline-cloud-samples`, run the following command:
   ```
   $ deadline bundle gui-submit cli_job
   ```
3. From the "Shared job settings" tab, give the job a name like "Starter farm test job", then enter "imagemagick" into the "Conda Packages" parameter and if it's not already included, add "conda-forge" to the "Conda Channels" parameter. These parameters are for the Conda queue environment that provides applications to the job.
4. From the "Job-specific settings" tab, select the directory `turntable_with_maya_arnold` within the samples as the "Input/Output Data Directory". This directory has some .png files to process.
5. Replace the "Bash Script" text box contents with the following script:
   ```
   find . -type f -iname "*.png" -exec magick identify {} \; | tee identified_images.txt
   ```
6. Select "Submit" and accept any prompts to submit the job to your queue.
7. From Deadline Cloud monitor, navigate to the production queue to watch the job you submitted. When it is running, right click on the task and select "View logs". It may take several minutes as Deadline Cloud starts an instance in your fleet to run the job. Within the log, you can find output that is similar to:
   ```
   + find . -type f -iname '*.png' -exec magick identify '{}' ';'
   + tee identified_images.txt
   ./screenshots/turntable_job_bundle_submitter_gui.png PNG 657x844 657x844+0+0 8-bit sRGB 59671B 0.000u 0:00.000
   ./screenshots/windows_desktop_submitter_bat_file.png PNG 237x231 237x231+0+0 8-bit sRGB 29790B 0.000u 0:00.000
   ./screenshots/turntable_job_output_video_screenshot.png PNG 962x693 962x693+0+0 8-bit sRGB 674715B 0.000u 0:00.000
   ```
8. When it is complete, download the output of the job. The custom script you entered populates a text file with image metadata. The output is written to the provided input/output directory, so look in the `turntable_with_maya_arnold` directory to find a file `identified_images.txt` with contents matching the logged output from the job:
   ```
   ./screenshots/turntable_job_bundle_submitter_gui.png PNG 657x844 657x844+0+0 8-bit sRGB 59671B 0.000u 0:00.000
   ./screenshots/windows_desktop_submitter_bat_file.png PNG 237x231 237x231+0+0 8-bit sRGB 29790B 0.000u 0:00.000
   ./screenshots/turntable_job_output_video_screenshot.png PNG 962x693 962x693+0+0 8-bit sRGB 674715B 0.000u 0:00.000
   ```

You can also submit the sample job with a single command from your terminal as follows:

```
$ deadline bundle submit cli_job \
    --name "Starter farm test job" \
    -p CondaPackages=imagemagick \
    -p "CondaChannels=s3://your-s3-bucket-name/Conda/Default deadline-cloud conda-forge" \
    -p DataDir=./turntable_with_maya_arnold \
    -p 'BashScript=find . -type f -iname "*.png" -exec magick identify {} \; | tee identified_images.txt'
```

## Use the farm for production

### Set up more users and groups with farm access

Use the [AWS IAM Identity Center management console](https://aws.amazon.com/iam/identity-center/) to create more users and groups, then give them permission to access the farm from the [AWS Deadline Cloud management console](https://console.aws.amazon.com/deadlinecloud/home).

### Build more Conda packages

See the [Conda recipe samples](../../../conda_recipes/README.md) to learn about the package building queue deployed by the template. If you write custom tools and plugins, you can write your own Conda package recipes to provide them to the farm.

### Run jobs from job bundles

Run jobs from the [job bundle samples](../../../job_bundles/README.md). Make copies of the code and build your own.

### Run jobs from DCC integrated submitters

Run the submitter installer in the downloads section of the [AWS Deadline Cloud management console](https://console.aws.amazon.com/deadlinecloud/home), or start from the [submitter source code on GitHub](https://github.com/aws-deadline/).

## Customize the farm

### Select fleets to deploy

By deploying fleets with multiple different hardware configurations, you can create a farm that supports a wide variety of jobs. The starter farm Terraform configuration comes with three different fleet configurations: a CPU Linux fleet, a CPU Windows fleet, and a CUDA Linux fleet. Each fleet that you name will be deployed, and if you set its name to be empty, it will be skipped.

When different steps of your jobs have different requirements, you can edit your job template to have [`hostRequirements`](https://github.com/OpenJobDescription/openjd-specifications/wiki/2023-09-Template-Schemas#33-hostrequirements) that control the operating system, memory requirements, or whether a GPU is available for each step.

### Customize the Terraform variables

Each fleet has variables to control the maximum number of workers, whether to use spot or on-demand instances, and control the vCPUs and RAM of worker hosts. If you use spot instances, you generally want to include wider ranges of these properties when possible to increase the available instance types you can get.

The default Conda channels that come after the S3 Conda channel are controlled by the `prod_conda_channels` variable that defaults to `"deadline-cloud"`. You can modify this to include [conda-forge](https://conda-forge.org/) or channels such as [bioconda](https://bioconda.github.io/).

### Modify the Conda queue environment for the production queue

The Terraform configuration includes a queue environment that creates Conda virtual environments for jobs to use. By default, this is the template file [conda_queue_env.yaml.tftpl](conda_queue_env.yaml.tftpl). You can edit this file to customize the Conda environment behavior, such as changing the default channels, adjusting caching behavior, or modifying the environment creation logic.

See the [queue environment samples](https://github.com/aws-deadline/deadline-cloud-samples/tree/mainline/queue_environments) for more ideas on how to configure queue environments.

### Create a Terraform configuration for your own farm

If you want to organize the queues in your farm differently from this starter sample, or you need a different set of fleet configurations, you can copy this Terraform configuration and start editing it. See the [CUDA farm CloudFormation template](../../../cloudformation/farm_templates/cuda_farm/README.md) for an example where the starter farm has been simplified and specialized for jobs that use CUDA.

We recommend you follow Infrastructure as Code best practices, such as keeping your configurations in version control and strictly making changes by editing the configuration and deploying it instead of mixing Terraform together with manual infrastructure updates from the AWS console. See the [AWS Well-Architected guidance on Infrastructure as Code](https://docs.aws.amazon.com/wellarchitected/latest/devops-guidance/dl.eac.1-organize-infrastructure-as-code-for-scale.html) to dive deeper into this topic.

## Security scanning

All Terraform configurations have been validated with security scanning tools:

- **[Checkov](https://github.com/bridgecrewio/checkov)** - Static analysis for infrastructure as code
- **[tflint](https://github.com/terraform-linters/tflint)** - Terraform linter

Run security scans on your modifications:

```bash
# Install tools
pip install checkov
brew install tflint  # or see https://github.com/terraform-linters/tflint

# Run scans
checkov -d . --framework terraform
tflint
```

This template has been validated with:
- **Checkov**: 37 passed, 0 failed
- **tflint**: No issues
- **terraform validate**: Success

## Cleanup

To destroy all resources:

```bash
terraform destroy
```

## Comparison with CloudFormation

This Terraform configuration creates identical resources to the [CloudFormation starter_farm template](../../../cloudformation/farm_templates/starter_farm/). See the [parent README](../../README.md) for a comparison table.
