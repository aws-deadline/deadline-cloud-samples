# AWS Deadline Cloud queue environments

## Introduction

This directory holds sample queue environments you can use with Deadline Cloud. Queue environments
follow the environment template specification from
[Open Job Description](https://github.com/OpenJobDescription/openjd-specifications/wiki/2023-09-Template-Schemas).

The Conda and Rez queue environments let you provide software applications to jobs in your
Deadline Cloud queue, so each job only needs a parameter value for `CondaPackages` or `RezPackages`
to tell it the list of packages to use.

## Create a queue environment for your queue

Here are steps to set up one of the sample queue environments.

1. For the queue environment sample you wish to use, modify the default value for the parameter `CondaChannels`
   or `RezRepositories` to be the source of your packages. Both Conda and Rez support shared file system
   paths for this, while Conda also supports channels hosted on [Anaconda.org](https://anaconda.org),
   web servers, and S3 buckets.
2. In Deadline Cloud, create a queue environment for your queue using the template you have modified. Read the topic
   [create a queue environment](https://docs.aws.amazon.com/deadline-cloud/latest/userguide/create-queue-environment.html)
   in the user guide to learn how to create or update them in your queue. You can also create a queue environment with a
   CLI command similar to:
      ```
      $ aws deadline create-queue-environment \
         --farm-id FARM_ID \
         --queue-id QUEUE_ID \
         --priority 1 \
         --template-type YAML \
         --template file://conda_queue_env_improved_caching.yaml
      ```

## Install git bash on Windows worker hosts

The sample queue environments are written using bash script code that is portable to Windows.
You can use them with Windows customer-managed fleets by installing [Git for Windows](https://gitforwindows.org/)
on the worker hosts. Make sure that the git binary is in the PATH.

## Install Conda and Rez on worker hosts

To use the queue environment samples from customer-managed fleets, you need to
provide [Conda](https://conda.io/projects/conda/en/latest/user-guide/install/index.html)
or [Rez](https://rez.readthedocs.io/en/stable/installation.html) on worker hosts,
for example by installing them on your Amazon machine image (AMI).

For Conda you must also apply the following setup steps so that `conda activate` and `conda deactivate`
are available within non-interactive bash shells. The scripts assume an `/opt/conda` install location
on Linux and `C:\Programs\Conda` install location on Windows.

Here is example bash script that does this for Amazon Linux 2023:

```bash
# Turn on pam_env so that `/etc/environment` is used in non-interactive scripts
echo 'auth            required        pam_env.so' >> /etc/pam.d/su
# Enable `conda activate <env>` in non-interactive scripts,
echo 'BASH_ENV=/etc/bash_env' >> /etc/environment
echo 'source /opt/conda/etc/profile.d/conda.sh' > /etc/bash_env
```

Here is example bash script that does this for Ubuntu:

```bash
# Enable `conda activate <env>` in non-interactive scripts,
echo 'source /opt/conda/etc/profile.d/conda.sh' >> /usr/share/modules/init/bash
```

Here is example powershell script that does this for Windows:

```bash
# Set BASH_ENV so that it sources the conda command
[Environment]::SetEnvironmentVariable("BASH_ENV", "/etc/bash_env", "Machine")
$Env:BASH_ENV = [Environment]::GetEnvironmentVariable("BASH_ENV", "Machine")
echo @'
echo 'source "/c/Programs/Conda/etc/profile.d/conda.sh"' > /etc/bash_env
'@ | & "C:\Programs\Git\bin\bash"

```

## Submit Jobs

One of the cool parts of queue environments and the Deadline Cloud submitters, such as
[deadline-cloud-for-blender](https://github.com/aws-deadline/deadline-cloud-for-blender), is that the submitters
will automatically add parameters in the queue environment for selecting the right Conda or Rez packages.

When you write your own job bundles, you can get the same result by including parameter definitions
for `CondaPackages` and/or `RezPackages` with a default value of the needed packages.
The [blender_render](https://github.com/aws-deadline/deadline-cloud-samples/blob/mainline/job_bundles/blender_render/template.yaml)
job bundle sample illustrates this by providing them both with a default value `blender`.

When your jobs run, these parameter values get passed to the queue environment, which creates
and activates a Conda or Rez virtual environment containing the requested packages and their dependencies.
The script commands for the job should run application binaries like `blender` without specifying
absolute paths. Entering the environment updates the `PATH` environment variable to provide
the correct binaries.

## The sample queue environments

### Console Conda queue environment

The file [conda_queue_env_from_console.yaml](conda_queue_env_from_console.yaml) is a copy of the queue environment
added by Deadline Cloud console onboarding flows. Its onEnter and onExit actions run the commands
`conda-queue-env-enter` and `conda-queue-env-exit` respectively. These commands that are provided on
Deadline Cloud service-managed fleets.

To use this functionality on customer-managed fleets, you can look at the next sample that provides
equivalent functionality.

### Console-equivalent Conda queue environment

The file [conda_queue_env_console_equivalent.yaml](conda_queue_env_console_equivalent.yaml) has the same behavior
as the console Conda queue environment, but directly runs Conda to create the virtual environment. You can refer
to this example to understand the behavior of the console queue environment.

The behavior of this queue environment is to create a new Conda virtual environment for every Open Job
Description session that runs on a worker host, and then delete the environment when it is done.
Conda keeps a cache of the downloaded packages, and the expanded form of those packages, so it will not
repeatedly re-download the same applications, but each session will have the overhead of linking all
packages into the virtual environment. Look at the sample with improved caching to reuse virtual
environments across multiple jobs.

### Rez queue environment

The file [rez_queue_env.yaml](rez_queue_env.yaml) provides the same functionality as
the above Conda queue environments, but for the Rez package manager. The queue environment will work in a
farm using customer-managed fleets that have a shared file system for the Rez package repository.

### Conda queue environment with improved caching

The file [conda_queue_env_improved_caching.yaml](conda_queue_env_improved_caching.yaml) extends the
capabilities of the Conda queue environment with a mechanism to reuse Conda virtual environments
across multiple jobs. This additional cache management is more complex, but the performance benefits
from environment reuse can be significant when running many jobs with the same package requirements.

The core enhancement of this queue environment is to use named Conda environments that can be shared across
jobs. The default environment name uses the hash of the Conda channels and packages, or you can explicitly
set the name in the job. It also includes a parameter for how long to use an environment without running a package
update, so that most of the time it will take seconds to activate an environment that's being reused.
