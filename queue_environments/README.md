# AWS Deadline Cloud queue environments

## Introduction

This directory holds sample queue environments you can use with Deadline Cloud. Queue environments
follow the environment template specification from
[Open Job Description](https://github.com/OpenJobDescription/openjd-specifications/wiki/2023-09-Template-Schemas).

The Conda and Rez queue environments let you provide software applications to jobs in your
Deadline Cloud queue, so each job only needs a parameter value for `CondaPackages` or `RezPackages`
to tell it the list of packages to use. The pip queue environment does the same for Python
packages, so a job only needs to provide a value for `PipPackages`.

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

Here is an example bash script that does this for Amazon Linux 2023:

```bash
# Turn on pam_env so that `/etc/environment` is used in non-interactive scripts
echo 'auth            required        pam_env.so' >> /etc/pam.d/su
# Enable `conda activate <env>` in non-interactive scripts,
echo 'BASH_ENV=/etc/bash_env' >> /etc/environment
echo 'source /opt/conda/etc/profile.d/conda.sh' > /etc/bash_env
```

Here is an example bash script that does this for Ubuntu:

```bash
# Enable `conda activate <env>` in non-interactive scripts,
echo 'source /opt/conda/etc/profile.d/conda.sh' >> /usr/share/modules/init/bash
```

Here is an example PowerShell script that does this for Windows:

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
`conda-queue-env-enter` and `conda-queue-env-exit` respectively. These commands are provided on
the workers of Deadline Cloud service-managed fleets. They are written using [Rattler](https://github.com/conda/rattler), which
generally runs faster than equivalent operations with Conda.

Here are the CLI options the enter and exit commands provide:
```
Usage: conda-queue-env-enter [OPTIONS] [ENV_DIR]

Arguments:
  [ENV_DIR]  The location of the environment to be created

Options:
  -p, --packages <PACKAGES>
          Space-separated list of Conda packages to install
  -c, --channels <CHANNELS>
          Space-separated list of Conda channels
      --channel-priority <CHANNEL_PRIORITY>
          Channel priority: "strict" or "disabled" [default: strict]
      --persist-envs-hashed <PERSIST_ENVS_HASHED>
          Persist environments in hash-named subdirectories under this root dir. Enables environment reuse across jobs
      --update-after-minutes <UPDATE_AFTER_MINUTES>
          Minutes before updating a persisted environment (default: 600 = 10 hours) [default: 600]
  -v, --verbose...
          Increase logging verbosity (-v for debug, -vv for trace)
      --windows-activation-shell <WINDOWS_ACTIVATION_SHELL>
          Shell to use for conda activation on Windows: "bash" (default) or "cmd" [default: bash]
      --print-env0
          Print all environment variables as null-delimited KEY=VALUE pairs and exit. Used internally by bash activation to capture native OS paths
  -h, --help
          Print help
```
```
Usage: conda-queue-env-exit [OPTIONS]

Options:
      --persist-envs-hashed <PERSIST_ENVS_HASHED>
          Root directory containing hash-named persisted environments
      --cleanup-after-hours <CLEANUP_AFTER_HOURS>
          Remove persisted environments not updated within this many hours (default: 96) [default: 96]
  -v, --verbose...
          Increase logging verbosity (-v for debug, -vv for trace)
  -h, --help
          Print help
```

The `conda-queue-env` commands on service-managed fleets support creating persistent environments that can be reused across
multiple jobs, but this functionality is not enabled by default on the console queue environment. See the `conda_queue_env_improved_caching.yaml` 
queue environment for a sample that enables this functionality.

To get similar functionality as the `conda_queue_env_from_console.yaml` environment on customer-managed fleets,
see the next sample `conda_queue_env_inline.yaml`.

### Conda queue environment using Conda written inline

The file [conda_queue_env_inline.yaml](conda_queue_env_inline.yaml) has nearly the same behavior
as the console Conda queue environment, but it does not use Rattler and directly runs Conda to create the virtual environment.
There is a small difference in functionality when using multiple conda channels; the console queue environment uses `strict` channel priority,
whereas this queue environment, as well as other queue environments not using Rattler, use `flexible` channel priority.

The behavior of this queue environment is to create a new Conda virtual environment for every Open Job
Description session that runs on a worker host, and then delete the environment when it is done.
Conda keeps a cache of the downloaded packages, and the expanded form of those packages, so it will not
repeatedly re-download the same applications, but each session will have the overhead of linking all
packages into the virtual environment. Look at the samples `conda_queue_env_improved_caching.yaml` and
`conda_queue_env_inline_improved_caching.yaml` for queue environments that can reuse virtual
environments across multiple jobs.

### Conda queue environment using the py-rattler library

The file [conda_queue_env_pyrattler.yaml](conda_queue_env_pyrattler.yaml) provides the same functionality as
the above Conda queue environments, but uses the [py-rattler library](https://conda.github.io/rattler/py-rattler/).
Rattler is a library that provides common functionality used within the conda ecosystem. It's written
in Rust and tries to provide a clean API to its functionalities. The environments it creates are almost the same,
but we found that py-rattler does not include 'pip' alongside 'python' by default, so if you need pip you must
add it explicitly. It also raises an error for a subset of syntax that conda accepts, such as 'colmap=*=gpu*'.

Testing has shown that this queue environment generally runs faster than the above when on the same instance types,
but the error messages it produces when failing to solve for a virtual environment do not include as
much detail to help diagnose what happened.

### Rez queue environment

The file [rez_queue_env.yaml](rez_queue_env.yaml) provides the same functionality as
the above Conda queue environments, but for the Rez package manager. The queue environment will work in a
farm using customer-managed fleets that have a shared file system for the Rez package repository.

### Conda queue environment with improved caching

The file [conda_queue_env_improved_caching.yaml](conda_queue_env_improved_caching.yaml) enables
the same virtual environments to be reused across multiple jobs via additional command line arguments to the `conda-queue-env-enter`,
and `conda-queue-env-exit` commands provided on service-managed fleets. This can give significant performance improvements when
running many jobs with the same package requirements.

The queue environment is configured to store persistent environments under `~/.persistent_envs`. To store persistent environments
under a different directory, the `onEnter` and `onExit` actions can be modified to reference a different path.

To get environment reuse functionality on customer-managed fleets, you can use the following sample.

### Conda queue environment with improved caching using Conda written inline

The file [conda_queue_env_inline_improved_caching.yaml](conda_queue_env_inline_improved_caching.yaml) extends the
capabilities of the Conda queue environment with a mechanism to reuse Conda virtual environments
across multiple jobs. This additional cache management is more complex, but the performance benefits
from environment reuse can be significant when running many jobs with the same package requirements.

The core enhancement of this queue environment is to use named Conda environments that can be shared across
jobs. The default environment name uses the hash of the Conda channels and packages, or you can explicitly
set the name in the job. It also includes a parameter for how long to use an environment without running a package
update, so that most of the time it will take seconds to activate an environment that's being reused.

### Pip queue environment

The file [pip_queue_env.yaml](pip_queue_env.yaml) lets you provide Python packages to jobs using
[pip](https://pip.pypa.io/) and the standard library [venv](https://docs.python.org/3/library/venv.html)
module, rather than a package manager like Conda or Rez. When a job provides a `PipPackages` parameter
value, the queue environment creates a Python virtual environment in the session working directory,
installs the requested packages into it with pip, and activates it so subsequent steps run with those
packages available. If `PipPackages` is empty, the queue environment does nothing, so it is safe to add
to a queue that also runs jobs which do not use it.

The `PipIndexUrl` and `PipExtraIndexUrls` parameters let jobs install from a private package index, such
as an [AWS CodeArtifact](https://docs.aws.amazon.com/codeartifact/) repository, instead of the default
[PyPI](https://pypi.org/) index.

Unlike Conda and Rez, pip and venv are included with Python itself, so worker hosts only need a `python3`
(or `python`) interpreter on the `PATH`. Deadline Cloud service-managed fleets provide one. The
[pip_package_job](../job_bundles/pip_package_job) job bundle shows how to submit a job that uses this
queue environment, and [pip_self_contained_job](../job_bundles/pip_self_contained_job) shows the same
pip environment defined inline in a job bundle when you do not want to configure a queue environment.

### Disconnect UBL queue environment

The file [disconnect_ubl_queue_env.yaml](disconnect_ubl_queue_env.yaml) unsets Deadline Cloud Usage Based
License (UBL) environment variables. Use this queue environment if you want to turn off all connections to
Deadline Cloud UBL for your queue and force the use of a custom license server (see the
[Bring Your Own License documentation](https://docs.aws.amazon.com/deadline-cloud/latest/developerguide/smf-byol.html)).

This queue environment should be run before any other queue environments (for example, by setting the priority to 0)
so that connections to your custom floating licenses (such as RLM) in other queue environments are not
accidentally removed.

Please note that this is a sample, additional UBL environment variables may be
added in the future.
