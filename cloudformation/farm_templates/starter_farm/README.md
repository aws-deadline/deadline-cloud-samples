# A starter AWS Deadline Cloud farm

## Overview

This CloudFormation template deploys an [AWS Deadline Cloud](https://aws.amazon.com/deadline-cloud/) farm
you can use to run jobs that render images, reconstruct 3D scenes, or transform your data
in custom ways. Sample jobs to submit are available in the
[deadline-cloud-samples on GitHub](https://github.com/aws-deadline/deadline-cloud-samples/tree/mainline/job_bundles#readme),
Deadline Cloud provides many [integrated submitter plugins for applications](https://github.com/aws-deadline/#integrations),
and you can [build your own jobs](https://docs.aws.amazon.com/en_us/deadline-cloud/latest/developerguide/building-jobs.html).

The deployed farm includes one or more [service-managed fleets](https://docs.aws.amazon.com/deadline-cloud/latest/userguide/smf-manage.html)
that you select during deployment. The production queue supports conda virtual environments for the applications that jobs need,
and the package build queue can be used to build more packages if needed. It configures two conda channels by default:
a private channel on an S3 bucket you provide and the
[deadline-cloud channel](https://docs.aws.amazon.com/deadline-cloud/latest/userguide/create-queue-environment.html#conda-queue-environment).
The `deadline-cloud` channel provides applications like Blender, Houdini, Maya, and Nuke.
You can add the [conda-forge channel](https://conda-forge.org/) to this list when deploying the CloudFormation
template to access packages created and maintained by the [conda-forge community](https://conda-forge.org/community/).
When supported applications need licenses to run, they will use Deadline Cloud's
usage-based licensing. See [Deadline Cloud pricing](https://aws.amazon.com/deadline-cloud/pricing/) to learn which
applications are supported and the associated costs.

See the section [Customizing the farm](#a-customizing) to learn how you can use the CloudFormation template parameters
to adjust which fleets are deployed or fork this sample into your own template.

## Prerequisites

Before deploying this CloudFormation template, check that you have the following resources created in
your AWS Account. The AWS region should be the same as the one you use to deploy the CloudFormation template.

1. An Amazon S3 bucket to hold job attachments and your conda channel. From the
   [Amazon S3 management console](https://s3.console.aws.amazon.com/s3/home), create an S3 bucket.
   You will need the bucket name to deploy the CloudFormation template.
2. A Deadline Cloud monitor to view and manage the jobs you will submit to your queues. From the
   [AWS Deadline Cloud management console](https://console.aws.amazon.com/deadlinecloud/home),
   select the "Go to Monitor setup" option and follow the steps to enter a name for your monitor URL,
   enable IAM Identity Center, and then create a user login account to access the monitor. Your
   monitor URL will look similar to `https://<ENTERED_MONITOR_NAME>.<AWS_REGION>.deadlinecloud.amazonaws.com/`,
   You will need this URL to log in with the Deadline Cloud monitor desktop application.

## Setup Instructions

### Deploy the CloudFormation template to your AWS account

1. Download the [deadline-cloud-starter-farm-template.yaml](deadline-cloud-starter-farm-template.yaml)
   CloudFormation template.
2. From the [CloudFormation management console](https://console.aws.amazon.com/cloudformation/),
   navigate to Create Stack > With new resources (standard).
3. Select the option to Upload a template file, then upload the `deadline-cloud-starter-farm-template.yaml`
   file that you downloaded.
4. Enter a name for the stack, like "StarterFarm", the S3 bucket name you created or selected during
   prerequisites, and any parameter customizations:
   1. If you want to use the [conda-forge channel](https://conda-forge.org/), change the parameter
      value for ProdCondaChannels to "deadline-cloud conda-forge". The sample job bundle
      [Turntable with Maya/Arnold](https://github.com/aws-deadline/deadline-cloud-samples/tree/mainline/job_bundles/turntable_with_maya_arnold)
      shows how you can use the FFmpeg provided by conda-forge to encode a video.
   2. Edit the fleet configuration parameters if you need a higher vCPU count, more RAM, more EBS bandwidth, etc.
5. Follow the CloudFormation console steps to complete stack creation.
6. From the [AWS Deadline Cloud management console](https://us-west-2.console.aws.amazon.com/deadlinecloud/home),
   navigate to the farm that you created, and select the "Access management" tab. Select "Users",
   then "Add user", and then add the user you created for yourself from the prerequisites. Use the "Owner"
   access level to give yourself full access.

### Install the Deadline client tools on your workstation

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

### Initialize the S3 conda channel

#### Option 1: To initialize the channel with an empty `repodata.json`:

1. Create a file `empty_channel_repodata.json` and edit to contain the following:
   ```
   {"info":{"subdir":"noarch"},"packages":{},"packages.conda":{},"removed":[],"repodata_version":1}
   ```
2. Substitute the job attachments bucket name into the following command to upload and initialize the channel:
   ```
   aws s3api put-object --body empty_channel_repodata.json --key Conda/Default/noarch/repodata.json --bucket <JOB_ATTACHMENTS_BUCKET>
   ```

#### Option 2: To initialize the channel by building a conda package:

The `deadline` package recipe used by this option depends on other packages in the `conda-forge` channel, so will work best if you
added `conda-forge` to the ProdCondaChannels parameter to the CloudFormation template.

1. If you don't have a local copy of [deadline-cloud-samples](https://github.com/aws-deadline/deadline-cloud-samples)
   GitHub repository, you can make a git clone or
   [download it as a ZIP](https://github.com/aws-deadline/deadline-cloud-samples/archive/refs/heads/mainline.zip).
2. From the `conda_recipes` directory of `deadline-cloud-samples`, run the following command. If you deployed
   different fleets than the default, you may need to adjust the conda platforms expression. See
   [the conda recipe samples README](https://github.com/aws-deadline/deadline-cloud-samples/tree/mainline/conda_recipes#readme)
   to learn more about this command.
   ```
   $ ./submit-package-build deadline -p "linux-64*"
   ```
3. From Deadline Cloud monitor, navigate to the package build queue to watch the job you submitted.
   When it is running, right click on the task and select "View logs". It may take several minutes as Deadline Cloud
   starts an instance in your fleet to run the job.
4. When the step "ReindexCondaChannel" is complete, the S3 conda channel is initialized
   and the `deadline` package you built is available.

## Submit a test job

This test job runs the `imagemagick identify` command on a directory of images to
extract properties of the images and write them to a text file.

Before proceeding with this test job, make sure the S3 conda channel is initialized according to the instructions above.
An uninitialized conda channel will fail during the "Launch Conda" action.

1. If you don't have a local copy of [deadline-cloud-samples](https://github.com/aws-deadline/deadline-cloud-samples)
   GitHub repository, you can make a git clone or
   [download it as a ZIP](https://github.com/aws-deadline/deadline-cloud-samples/archive/refs/heads/mainline.zip).
2. From the `job_bundles` directory of `deadline-cloud-samples`, run the following command:
   ```
   $ deadline bundle gui-submit cli_job
   ```
3. From the "Shared job settings" tab, give the job a name like "Starter farm test job",
   then enter "imagemagick" into the "Conda Packages" parameter and if it's not already included,
   add "conda-forge" to the "Conda Channels" parameter. These parameters
   are for the conda queue environment that provides applications to the job.
4. From the "Job-specific settings" tab, select the directory `turntable_with_maya_arnold`
   within the samples as the "Input/Output Data Directory". This directory has some .png files to process.
5. Replace the "Bash Script" text box contents with the following script:
   ```
   find . -type f -iname "*.png" -exec magick identify {} \; | tee identified_images.txt
   ```
6. Select "Submit" and accept any prompts to submit the job to your queue.
7. From Deadline Cloud monitor, navigate to the production queue to watch the job you submitted.
   When it is running, right click on the task and select "View logs". It may take several minutes as
   Deadline cloud starts an instance in your fleet to run the job. Within the log, you can find output
   that is similar to:
   ```
   + find . -type f -iname '*.png' -exec magick identify '{}' ';'
   + tee identified_images.txt
   ./screenshots/turntable_job_bundle_submitter_gui.png PNG 657x844 657x844+0+0 8-bit sRGB 59671B 0.
   ./screenshots/windows_desktop_submitter_bat_file.png PNG 237x231 237x231+0+0 8-bit sRGB 29790B 0.
   ./screenshots/turntable_job_output_video_screenshot.png PNG 962x693 962x693+0+0 8-bit sRGB 674715B 0.000u 0:00.000
   ```
8. When it is complete, download the output of the job. The custom script you entered populates a text file
   with image metadata. The output is written to the provided input/output directory, so look in the
   `turntable_with_maya_arnold` directory to find a file `identified_images.txt` with contents matching
   the logged output from the job:
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
      -p DataDir=./turntable_with_maya_arnold \
      -p 'BashScript=find . -type f -iname "*.png" -exec magick identify {} \; | tee identified_images.txt'
```

## Use the farm for production

### Set up more users and groups with farm access

Use the [AWS IAM Identity Center management console](https://aws.amazon.com/iam/identity-center/)
to create more users and groups, then give them permission to access the farm
from the [AWS Deadline Cloud management console](https://us-west-2.console.aws.amazon.com/deadlinecloud/home).

### Build more conda packages

See the [conda recipe samples](../../../conda_recipes/README.md) to learn about the package building
queue deployed by the template. If you write custom tools and plugins, you can write your own conda package recipes
to provide them to the farm.

### Run jobs from job bundles

Run jobs from the [job bundle samples](../../../job_bundles/README.md). Make copies of the code and build your own.

### Run jobs from DCC integrated submitters

Run the submitter installer in the downloads section of the
[AWS Deadline Cloud management console](https://console.aws.amazon.com/deadlinecloud/home),
or start from the [submitter source code on GitHub](https://github.com/aws-deadline/).

## Customize the farm<a id='a-customizing'></a>

### Select fleets to deploy

By deploying fleets with multiple different hardware configurations, you can create a farm that supports
a wide variety of jobs. The starter farm CloudFormation template comes with three different fleet configurations:
a CPU Linux fleet, a CPU Windows fleet, and a CUDA Linux fleet. Each fleet that you name will be deployed,
and if you set its name to be empty, it will be skipped.

When different steps of your jobs have different requirements, you can edit your job template to have
[`<HostRequirements>`](https://github.com/OpenJobDescription/openjd-specifications/wiki/2023-09-Template-Schemas#33-hostrequirements)
that control the operating system, memory requirements, or whether a GPU is available for each step.
You can make a job that exports .vrscene files on Windows using Autodesk 3ds Max, and then renders
them with standalone Chaos V-Ray on Linux. You can make jobs that prepare data on lower cost CPU-only
fleets, and then train NeRF or Gaussian splatting on a CUDA fleet.

### Customize the CloudFormation template parameters

Each fleet has parameters to control the maximum number of workers, whether to use spot or on-demand
instances, and control the vCPUs and RAM of worker hosts. If you use spot instances, you generally want
to include wider ranges of these properties when possible to increase the available instance types you
can get.

The default conda channels that come after the S3 conda channel are controlled by a parameter
that defaults to "deadline-cloud". You can modify this to include [conda-forge](https://conda-forge.org/) or
such as [bioconda](https://bioconda.github.io/).

### Modify the conda queue environment for the production queue

The CloudFormation template includes a queue environment that creates conda virtual environments for jobs
to use. By default, this is the sample queue environment
[conda_queue_env_improved_caching.yaml](https://github.com/aws-deadline/deadline-cloud-samples/blob/mainline/queue_environments/conda_queue_env_improved_caching.yaml). You can run the provided Python script
[apply-conda-queue-env.py](../apply-conda-queue-env.py) to substitute a different queue environment.
For example, the following command would switch it to the sample
[conda_queue_env_from_console.yaml](https://github.com/aws-deadline/deadline-cloud-samples/blob/mainline/queue_environments/conda_queue_env_from_console.yaml):

```
$ python ../apply-conda-queue-env.py \
      deadline-cloud-starter-farm-template.yaml \
      ../../../queue_environments/conda_queue_env_from_console.yaml \
      's3://${JobAttachmentsBucketName}/Conda/Default ${ProdCondaChannels}'
```

### Create a CloudFormation template for your own farm

If you want to organize the queues in your farm differently from this starter sample, or you need a different
set of fleet configurations, you can copy this CloudFormation template and start editing it. We recommend
you follow Infrastructure as Code best practices, such as keeping your templates in version control and
strictly making changes by editing the template and deploying it instead of mixing CloudFormation together
with manual infrastructure updates from the AWS console. See the
[AWS Well-Architected guidance on Infrastructure as Code](https://docs.aws.amazon.com/wellarchitected/latest/devops-guidance/dl.eac.1-organize-infrastructure-as-code-for-scale.html)
to dive deeper into this topic.

When you strike out on your own from the starter farm sample, you may find it helpful to first delete the
`Metadata` section that controls the user interface, and remove the `Conditions` along with where they are used.
These sections make a single template more flexible, but when you're using the code to define one particular
farm, they add unnecessary complexity.