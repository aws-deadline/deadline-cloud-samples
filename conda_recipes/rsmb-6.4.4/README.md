# Adobe After Effects Plugin Support for Deadline Cloud

## Description

This workflow describes how to set up plugin support for After Effects rendering in a service-managed fleet (SMF) environment on Deadline Cloud.

- Uses Conda channels for modular, reusable, and flexible environment setup

- Supports plugins with floating licenses handled through a networked license manager, e.g. RLM, RVL

## Getting Started

This workflow assumes an S3 bucket with appropriate Conda channel and a build queue environment are available. Please refer to the following links to set up the channel and queue.

[Create a conda channel using S3](https://docs.aws.amazon.com/deadline-cloud/latest/developerguide/configure-jobs-s3-channel.html#s3-channel-add-channel)

[Create a conda package and channel for AWS Deadline Cloud](https://aws.amazon.com/blogs/media/create-a-conda-package-and-channel-for-aws-deadline-cloud/)

[AWS Deadline Cloud queue environments](https://github.com/aws-deadline/deadline-cloud-samples/blob/mainline/queue_environments/README.md)

## Building a plugin package into S3

This workflow covers the creation of a conda package and build job for `ReelSmart Motion Blur` (RSMB).

This section describes how to set up a build job for a plugin package and build it into a specified S3 bucket. This enables render jobs with conda packages specified to be able to get these from the Conda channel on the S3 bucket.

### Prerequisites
1. Clone the [deadline-cloud-samples](https://github.com/aws-deadline/deadline-cloud-samples/blob/mainline/conda_recipes/README.md) repository and copy the `rsmb-6-4-4` folder into the `conda_recipes` folder.

2. Install `RSMB` through their download link at: https://revisionfx.com/products/rsmb/after-effects/

### Windows

1. The `RSMB` installer will add 3 `.aex` files to `C:\Program Files\Adobe\Common\Plug-ins\7.0\MediaCore\RSMB6AE`. Zip these up into `RSMB_6_4_4_aex.zip`.

  You can run the following PowerShell command to zip up the plugin files, replacing `C:\full_archive_files_path\` with the full path to your `conda_recipes\archive_files`:

  ```
  Compress-Archive -Path 'C:\Program Files\Adobe\Common\Plug-ins\7.0\MediaCore\RSMB6AE' -DestinationPath C:\full_archive_files_path\RSMB_6_4_4_aex.zip
  ```

2. Generate the `sha256` hash for this file with the following command in a PowerShell terminal, replacing `C:\full_archive_files_path\` as above:
   
   ```
   (Get-FileHash -Path "C:\full_archive_files_path\RSMB_6_4_4_aex.zip" -Algorithm SHA256).Hash.ToLower()
   ```
   
3. In the recipe's `rsmb-6-4-4/meta.yaml` file, update the `source > sha256` field with the hash output from above.

4. Send the build job to the farm with the following command inside the `conda_recipes` folder:
   
   ```
   submit-package-job rsmb-6.4.4 -q "Your queue name"
   ```

5. A build job should now be running on your farm. Once completed, you can view your package by navigating to your S3 bucket, with its default location:
   
   `Buckets/bucket_name/Conda/Default/win-64/pkg_name`

### Mac

1. The `RSMB` installer will add 3 `.aex` files to `/Library/Application Support/Adobe/Common/Plug-ins/7.0/MediaCore/RSMB6AE`. Run the following command in a Terminal window to zip up the plugin files, replacing `/path/to/archive_files/` with the path to your `conda_recipes/archive_files`:

  ```
  zip -r /path/to/archive_files/RSMB_6_4_4_aex.zip /Library/Application\ Support/Adobe/Common/Plug-ins/7.0/MediaCore/RSMB6AE
  ```

2. Generate the `sha256` hash for this file with the following command:
   
   ```
   shasum -a 256 /path/to/archive_files/RSMB_6_4_4_aex.zip
   ```

3. In the recipe's `rsmb-6-4-4/meta.yaml` file, update the `source > sha256` field with the hash output from above.

4. Send the build job to the farm with the following command inside the `conda_recipes` folder:
   
   ```
   submit-package-job rsmb-6.4.4 -q "Your queue name"
   ```

5. A build job should now be running on your farm. Once completed, you can view your package by navigating to your S3 bucket, with its default location:
   
   `Buckets/bucket_name/Conda/Default/win-64/pkg_name`

### Troubleshooting `submit-package-job` errors
- First, ensure your `deadline` CLI package is up to date: `pip install deadline`

- Login error: Be sure to log into the Deadline Cloud Monitor before sending a job.

- Specified queue error: Deadline will look at the default farm in the deadline config file to check if the specified queue is available.
  
  This can be resolved by switching queues through the GUI or changing the farm in the config file.
  
  The following command is available when the Deadline Cloud Monitor has been installed:
  
  ```
  # Open GUI to adjust default farm and queue if necessary
  deadline config gui
  ```

- `--output not defined` error: Check if multiple Python versions are installed. Uninstall `deadline` packages from all but one Python installation, or remove the unwanted Python versions.

- `Failed to import PySide2` error: Run `pip install PySide2`. Please note that `PySide2` is unavailable for Python 3.11.
   
## Setting up licensed plugins through a queue environment and AWS SSM proxy server

When working with licensed plugins like RSMB, a floating network license is required. For consistent performance and security, you can use AWS Session Manager to get cloud workers connected to your networked license server. The license server can run anywhere: in a VPC or over the Internet. Additional information about the BYOL can be found here: [Connect service-managed fleets to a custom license server](https://docs.aws.amazon.com/deadline-cloud/latest/developerguide/smf-byol.html)

### Queue environment setup

#### Create a queue

1. Go to your AWS Deadline Cloud Console, navigate to your desired farm, and click the `Create queue` button.

2. Enter a name and optional description for the queue.

3. For Job Attachments, create your S3 bucket by providing a name and root folder name. Example:
   
   S3 bucket `example-job-attachments-ae` and root folder `DeadlineCloud`.

4. Do not allow association with CMF.

5. Associate with your `WindowsFleet`. This can be adjusted later on in `Edit queue`.

6. For the `Queue service role`, select `Create and use a new service role`. Provide a role name and description.
   
   If you used the CloudFormation [starter_farm example template](https://github.com/aws-deadline/deadline-cloud-samples/blob/mainline/cloudformation/farm_templates/starter_farm/deadline-cloud-starter-farm-template.yaml), you can use your existing service role called `ProdQueueRole`.

7. No optional queue environments are necessary.

8. Make sure the checkbox is enabled under "Default Conda queue environment" to create a Conda queue environment.

9. Add optional tags if necessary.

#### Edit queue environments

The default Conda queue environment must be edited for the queue to use the newly built plugin packages.

1. Go into your queue and select the Conda queue environment in the `Queue environments` tab, then on the top right of the `Environments` section, click `Edit`.
   
   - Adjust the `- name: CondaPackages` `default` section from `""` to `"aftereffects rsmb"`.
   
   - Adjust the `- name: CondaChannels` `default` section from `"deadline-cloud"` to `"s3://example-deadline-cloud-package-build/Conda/Default deadline-cloud conda-forge"`. Update name in `s3://example-deadline-cloud-package-build/Conda/Default` with your own conda channel used to build packages.

2. Add a new queue environment through `Actions > Create new with YAML`, in the Environments section of the queue.
   
3. Copy and paste the contents from the environment template provided below into the YAML editor:
   
   ```yaml
   specificationVersion: "environment-2023-09"
   parameterDefinitions:
     - name: LicenseInstanceId
       type: STRING
       description: >
         The Instance ID of the license server/proxy instance
       default: "i-01234567890abcdef"
     - name: LicenseInstanceRegion
       type: STRING
       description: >
         The region containing this farm
       default: "us-east-1"
     - name: LicensePorts
       type: STRING
       description: >
         Comma-separated list of ports to be forwarded to the license server/proxy instance.
         Example: "2700,2701,2702"
       default: "9412"
   environment:
     name: BYOL License Forwarding for RSMB
     variables:
       RVL_SERVER: example.hostname.of.your.server
     script:
       actions:
         onEnter:
           command: powershell
           args: [ "{{Env.File.BYOL_Enter}}"]
         onExit:
           command: powershell
           args: [ "{{Env.File.BYOL_Exit}}" ]
       embeddedFiles:
         - name: BYOL_Enter
           filename: BYOL_Enter.ps1
           type: TEXT
           runnable: True
           data: |
             $ZIP_NAME="SessionManagerPlugin.zip"
             Invoke-WebRequest -Uri "https://s3.amazonaws.com/session-manager-downloads/plugin/latest/windows/$ZIP_NAME" -OutFile $ZIP_NAME
             Expand-Archive -Path $ZIP_NAME
             Expand-Archive -Path .\SessionManagerPlugin\package.zip
             python {{Env.File.StartSession}} {{Session.WorkingDirectory}}\package\bin\session-manager-plugin.exe
         - name: BYOL_Exit
           filename: BYOL_Exit.ps1
           type: TEXT
           runnable: True
           data: |
             Write-Output "Killing SSM Manager Plugin PIDs: $env:BYOL_SSM_PIDS"
             "$env:BYOL_SSM_PIDS".Split(",") | ForEach {
               Write-Output "Killing $_"
               Stop-Process -Id $_ -Force
             }
         - name: StartSession
           type: TEXT
           data: |
             import boto3
             import json
             import subprocess
             import sys
   
             instance_id = "{{Param.LicenseInstanceId}}"
             region = "{{Param.LicenseInstanceRegion}}"
             license_ports_list = "{{Param.LicensePorts}}".split(",")
   
             ssm_client = boto3.client("ssm", region_name=region)
             pids = []
   
             for port in license_ports_list:
               session_response = ssm_client.start_session(
                 Target=instance_id,
                 DocumentName="AWS-StartPortForwardingSession",
                 Parameters={"portNumber": [port], "localPortNumber": [port]}
               )
   
               cmd = [
                 sys.argv[1],
                 json.dumps(session_response),
                 region,
                 "StartSession",
                 "",
                 json.dumps({"Target": instance_id}),
                 f"https://ssm.{region}.amazonaws.com"
               ]
   
               process = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
               pids.append(process.pid)
               print(f"SSM Port Forwarding Session started for port {port}")
   
             print(f"openjd_env: BYOL_SSM_PIDS={','.join(str(pid) for pid in pids)}")
             
   ```
   
3. Adjust the template's `LicenseInstanceId`, `LicenseInstanceRegion`, and `RVL_SERVER` to match your infrastructure.

4. Set a larger priority number for this environment than the Conda environment, so that this BYOL environment loads after Conda. 0 is the highest priority number.

A render queue with its supporting queue environment is now set up and ready to accept jobs using the package you built.

## Sending a test render job with specified conda packages

1. With Deadline Cloud for After Effects installed, open a project and open the Deadline Cloud submitter.

2. Select a composition containing at least one of the `RSMB` plugins added as an effect, and click Submit.
   - If no composition is available with RSMB, you can add the effect before clicking Submit:
     - Select the layer in the composition to which you want to add the effect
     - Open the `Effect` menu
     - Open `RE:Vision Plug-ins` and select one of the available RSMB effects. Your selected effect is then applied to the layer.
     - Note: Be aware of the `Use GPU` setting on the effect. If `Use GPU` is enabled, your render queue must be associated with a GPU-accelerated fleet.

3. In the submitter dialog, specify the following conda packages: `aftereffects rsmb`.

4. Adjust any needed settings and click `Submit` to submit the job to the farm.

5. The After Effects render job will run with the `RSMB` plugin added to the worker machine's render environment.

### RSMB rendering note: CPU vs. GPU

Be sure to match the `Use GPU` setting in RSMB to your farm's capabilities. If you try to render a GPU-accelerated layer on a CPU-only fleet, your render job may freeze or render a green placeholder instead of the expected elements. Disabling the `Use GPU` option on the layer's effect, or enabling GPU usage on the fleet will resolve this.

You can adjust the `Use GPU` setting in the effect's properties:
- In the After Effects timeline for your composition, expand the layer containing the RSMB effect you would like to adjust
- Expand the Effects section
- Expand the RSMB section
- Set the `Use GPU` option to OFF or ON depending on your fleet settings.

GPU rendering only works correctly when you match the `Use GPU` setting to the capabilities of your fleet:
- `Use GPU` set to OFF and a CPU-only or GPU fleet: This will render on the CPU.
- `Use GPU` set to ON and a GPU fleet: This will render on the GPU.
- `Use GPU` set to ON and a CPU-only fleet: Your render job may freeze or render a green placeholder instead of the expected elements.

### Queue setup for GPU acceleration
To render GPU-accelerated jobs on a queue, the given queue must be associated with at least one GPU-accelerated fleet.

If you create a queue with a single GPU fleet, all jobs on that queue will run on the given fleet. You can also associate multiple fleets with a single queue, and then specify host requirements on the render step in the job template to have those render steps run on only the desired GPU-accelerated machines.

For example, setting a step's requirement for `amount.worker.gpu` to a minimum of `1` will cause that step to run only on a GPU-accelerated machine.

Additional information about job scheduling can be found here: [Schedule jobs in Deadline Cloud](https://docs.aws.amazon.com/deadline-cloud/latest/userguide/jobs-scheduling.html)

