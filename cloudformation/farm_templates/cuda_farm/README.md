# AWS Deadline Cloud farm for running CUDA jobs

## Introduction

This CloudFormation template deploys an AWS Deadline Cloud farm that you can use to run CUDA jobs. Its
default configuration includes a queue for CUDA jobs, a second queue for building conda packages,
and a CUDA-capable fleet.

This is an example of how you can take the [starter_farm sample](../starter_farm/README.md)
and specialize it to your requirements. The differences are:

* Updated the default names and descriptions for the CUDA job use case.
* Changed the default CondaChannels from "deadline-cloud" to "deadline-cloud conda-forge" to
  make the CUDA compilers, frameworks like pytorch, and applications like COLMAP available.
* Made the Linux CUDA fleet required, and removed the Windows and Linux CPU fleets.

A CUDA workload you can run on this farm is a Gaussian Splatting pipeline. See the
[nerfstudio conda package README](../../../conda_recipes/nerfstudio/README.md)
and the  [gsplat_pipeline job bundle README](../../../job_bundles/gsplat_pipeline/README.md) for
instructions on how to capture a subject on video and turn it into Gaussian splats you
can view in your web browser.

## Prerequisites

Before deploying this CloudFormation template, check that you have the following resources created in
your AWS Account.

1. An Amazon S3 bucket to hold job attachments and your conda channel. From the
   [Amazon S3 management console](https://s3.console.aws.amazon.com/s3/home), create an S3 bucket.
   You will need the bucket name to deploy the CloudFormation template.
2. A Deadline Cloud monitor to view and manage the jobs you will submit to your queues. From the
   [AWS Deadline Cloud management console](https://console.aws.amazon.com/deadlinecloud/home),
   select the "Go to Monitor setup" option and follow the steps to enter a name for your monitor URL,
   enable IAM Identity Center, and then create a user login account to access the monitor. Your
   monitor URL will look similar to `https://<ENTERED_MONITOR_NAME>.<AWS_REGION>.deadlinecloud.amazonaws.com/`.
   You will need this URL to log in with the Deadline Cloud monitor desktop application.

## Setup Instructions

### Deploy the CloudFormation template

1. Download the [deadline-cloud-cuda-farm-template.yaml](deadline-cloud-cuda-farm-template.yaml)
   CloudFormation template.
2. From the [CloudFormation management console](https://console.aws.amazon.com/cloudformation/),
   navigate to Create Stack > With new resources (standard).
3. Upload the deadline-cloud-cuda-farm-template.yaml CloudFormation template that you downloaded.
4. Enter a name for the stack, like "CUDAFarm", the S3 bucket name you created or selected during
   prerequisites, and any parameter customizations such as different vCPU or RAM ranges.
5. Follow the CloudFormation console steps to complete stack creation.
6. From the [AWS Deadline Cloud management console](https://us-west-2.console.aws.amazon.com/deadlinecloud/home),
   navigate to the farm that you created, and select the "Access management" tab. Select "Users",
   then "Add user", and then add the user you created for yourself from the prerequisites. Use the "Owner"
   access level to give yourself full access.

### Install the Deadline client tools on your workstation

1. From the [AWS Deadline Cloud management console](https://console.aws.amazon.com/deadlinecloud/home),
   select the "Downloads" page on the left navigation area.
2. Download and install the Deadline Cloud monitor desktop application.
3. Download and install the Deadline Cloud submitter installer for your platform, or install the
   Deadline Cloud CLI into your existing Python installation [from PyPI](https://pypi.org/project/deadline/)
   using a command like `pip install "deadline[gui]"`. You can then use the command
   `deadline handle-web-url --install` to install the job attachments download handler on supported operating systems.
4. Use your monitor URL and the user account from the prerequisites to log in from the Deadline Cloud monitor desktop.
   This also provides AWS credentials to the Deadline Cloud CLI.
5. From the terminal, run the command `deadline config gui`, and select the default farm "CUDA Deadline Cloud Farm"
   and the default queue "CUDA Job Queue". Select OK to apply the settings.

### Initialize the S3 conda channel

1. Create a file `empty_channel_repodata.json` and edit to to contain the following:
   ```
   {"info":{"subdir":"noarch"},"packages":{},"packages.conda":{},"removed":[],"repodata_version":1}
   ```
2. Substitute the job attachments bucket name into the following command to upload and initialize the channel:
   ```
   aws s3api put-object --body empty_channel_repodata.json --key Conda/Default/noarch/repodata.json --bucket <JOB_ATTACHMENTS_BUCKET>
   ```

## Submit a GPU test job

1. Create a directory called `gpu_test_job`, and edit a file `template.yaml` inside of it to contain:
    ```yaml
    specificationVersion: 'jobtemplate-2023-09'
    name: CUDA GPU Test Job
    steps:
    - name: SmiPrint
      script:
         actions:
            onRun:
               command: bash
               args: ['{{Task.File.Run}}']
         embeddedFiles:
         - name: Run
           type: TEXT
           data: |
             set -xeuo pipefail
             nvidia-smi
             nvidia-smi --query-gpu=compute_cap --format=csv
      hostRequirements:
         amounts:
         - name: amount.worker.gpu
           min: 1
    ```
2. From your terminal, run `deadline bundle gui-submit --browse` and select the `gpu_test_job` directory.
   Proceed to submit the job to the queue.
3. From Deadline Cloud monitor, watch the job you submitted, and when it is running, right click on the
   task and select "View logs". It may take several minutes as Deadline cloud starts an instance in your
   fleet to run the job. Within the log, you can find output that is similar to:
   ```
   + nvidia-smi
   Tue Dec 31 00:18:41 2024
   +-----------------------------------------------------------------------------------------+
   | NVIDIA-SMI 550.127.05             Driver Version: 550.127.05     CUDA Version: 12.4     |
   |-----------------------------------------+------------------------+----------------------+
   | GPU  Name                 Persistence-M | Bus-Id          Disp.A | Volatile Uncorr. ECC |
   | Fan  Temp   Perf          Pwr:Usage/Cap |           Memory-Usage | GPU-Util  Compute M. |
   |                                         |                        |               MIG M. |
   |=========================================+========================+======================|
   |   0  NVIDIA L4                      On  |   00000000:31:00.0 Off |                    0 |
   | N/A   32C    P8             16W /   72W |       1MiB /  23034MiB |      0%      Default |
   |                                         |                        |                  N/A |
   +-----------------------------------------+------------------------+----------------------+

   +-----------------------------------------------------------------------------------------+
   | Processes:                                                                              |
   |  GPU   GI   CI        PID   Type   Process name                              GPU Memory |
   |        ID   ID                                                               Usage      |
   |=========================================================================================|
   |  No running processes found                                                             |
   +-----------------------------------------------------------------------------------------+
   + nvidia-smi --query-gpu=compute_cap --format=csv
   compute_cap
   8.9
   ```

## Train your own Gaussian Splatting

To train your own Gaussian Splatting on the farm, the next step is to build a conda package
for [NeRF Studio](https://docs.nerf.studio/). Navigate to the
[nerfstudio conda recipe README.md](../../../conda_recipes/nerfstudio/README.md) to learn more.