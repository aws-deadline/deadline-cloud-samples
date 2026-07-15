# AWS Deadline Cloud queue environments

Queue environments follow the [Open Job Description environment template specification](https://github.com/OpenJobDescription/openjd-specifications/wiki/2023-09-Template-Schemas) and prepare software or licensing once per worker session. Jobs select packages through parameters such as `CondaPackages`, `RezPackages`, or `PipPackages`.

## Sample index

This table covers every queue environment YAML file in `queue_environments/`.

| Sample | What it demonstrates | Start here when |
|---|---|---|
| [Console Conda environment](conda_queue_env_from_console.yaml) | Service-managed fleet `conda-queue-env` commands backed by Rattler | You want the environment created by console onboarding |
| [Inline Conda environment](conda_queue_env_inline.yaml) | Creating and deleting a Conda environment with portable bash | A customer-managed fleet has Conda but not service-provided helper commands |
| [Py-rattler Conda environment](conda_queue_env_pyrattler.yaml) | Solving and activating packages with the `py-rattler` library | You want faster solving and can accept its compatibility differences |
| [Cached Conda environment](conda_queue_env_improved_caching.yaml) | Reusing hash-named environments with service-managed fleet commands | Repeated package sets should avoid relinking on every job |
| [Cached inline Conda environment](conda_queue_env_inline_improved_caching.yaml) | Portable named-environment reuse and expiration logic | Customer-managed fleets need reusable Conda environments |
| [Rez environment](rez_queue_env.yaml) | Resolving packages from a shared Rez repository | Your studio already distributes software with Rez |
| [Pip environment](pip_queue_env.yaml) | Creating a Python `venv` and installing job-selected pip packages | Jobs need Python packages without Conda or Rez |
| [Disconnect UBL](disconnect_ubl_queue_env.yaml) | Removing Deadline Cloud Usage Based License environment variables | A queue must use only a custom license server |

## Create a queue environment for your queue

1. In the selected sample, change `CondaChannels`, `RezRepositories`, or package-index defaults to your package source. Conda and Rez support shared file-system paths; Conda also supports Anaconda.org, web, and S3 channels.
2. Follow [Create a queue environment](https://docs.aws.amazon.com/deadline-cloud/latest/userguide/create-queue-environment.html) to add or update it. A CLI invocation looks like:

   ```console
   aws deadline create-queue-environment \
       --farm-id FARM_ID \
       --queue-id QUEUE_ID \
       --priority 1 \
       --template-type YAML \
       --template file://conda_queue_env_improved_caching.yaml
   ```

## Install Git Bash on Windows worker hosts

These samples use bash that is portable to Windows. On Windows customer-managed fleets, install [Git for Windows](https://gitforwindows.org/) and put its Git binary on `PATH`.

## Install Conda and Rez on worker hosts

Customer-managed fleets must provide [Conda](https://conda.io/projects/conda/en/latest/user-guide/install/index.html) or [Rez](https://rez.readthedocs.io/en/stable/installation.html), for example in the AMI.

For Conda, also make `conda activate` and `conda deactivate` available in non-interactive bash. The samples assume `/opt/conda` on Linux and `C:\Programs\Conda` on Windows.

Amazon Linux 2023:

```bash
# Use /etc/environment in non-interactive scripts.
echo 'auth            required        pam_env.so' >> /etc/pam.d/su
echo 'BASH_ENV=/etc/bash_env' >> /etc/environment
echo 'source /opt/conda/etc/profile.d/conda.sh' > /etc/bash_env
```

Ubuntu:

```bash
echo 'source /opt/conda/etc/profile.d/conda.sh' >> /usr/share/modules/init/bash
```

Windows PowerShell:

```powershell
[Environment]::SetEnvironmentVariable("BASH_ENV", "/etc/bash_env", "Machine")
$Env:BASH_ENV = [Environment]::GetEnvironmentVariable("BASH_ENV", "Machine")
echo @'
echo 'source "/c/Programs/Conda/etc/profile.d/conda.sh"' > /etc/bash_env
'@ | & "C:\Programs\Git\bin\bash"
```

## Submit jobs

Deadline Cloud submitters can add the package-selection parameters defined by a queue environment automatically. Custom bundles can get the same behavior by defining `CondaPackages`, `RezPackages`, or `PipPackages` with suitable defaults. The [Blender render template](../job_bundles/blender_render/template.yaml) demonstrates both Conda and Rez package parameters.

The queue environment creates and activates the selected virtual environment, so task commands should invoke applications such as `blender` from `PATH` instead of using absolute paths.

## Environment behavior details

### Console Conda environment

The console environment runs `conda-queue-env-enter` and `conda-queue-env-exit`, which are available on service-managed fleet workers and implemented with [Rattler](https://github.com/conda/rattler). Their relevant options are:

```text
Usage: conda-queue-env-enter [OPTIONS] [ENV_DIR]

Arguments:
  [ENV_DIR]  The location of the environment to be created

Options:
  -p, --packages <PACKAGES>              Space-separated packages
  -c, --channels <CHANNELS>              Space-separated channels
      --channel-priority <PRIORITY>      "strict" or "disabled"
      --persist-envs-hashed <ROOT>        Reuse hash-named environments
      --update-after-minutes <MINUTES>    Refresh age; default 600
  -v, --verbose...                        Increase logging verbosity
      --windows-activation-shell <SHELL>  "bash" or "cmd"
      --print-env0                        Print null-delimited environment values
  -h, --help
```

```text
Usage: conda-queue-env-exit [OPTIONS]

Options:
      --persist-envs-hashed <ROOT>      Root containing persistent environments
      --cleanup-after-hours <HOURS>     Stale cleanup age; default 96
  -v, --verbose...                      Increase logging verbosity
  -h, --help
```

Persistent reuse is not enabled in the console template by default. The cached Conda sample enables it.

### Inline Conda environment

The inline sample directly runs Conda and works on customer-managed fleets. It creates one environment per OpenJD session and deletes it afterward. Conda still caches downloaded and expanded packages, but each session pays the cost of linking a new environment. Unlike the console environment's strict channel priority, it uses Conda's flexible priority for multiple channels.

### Py-rattler Conda environment

The py-rattler sample provides similar behavior through [py-rattler](https://conda.github.io/rattler/py-rattler/). It generally solves faster, but `pip` is not automatically included with `python`, it rejects some syntax accepted by Conda (for example `colmap=*=gpu*`), and solver errors can include less diagnostic detail.

### Conda queue environment with improved caching

The service-managed cached sample stores reusable environments under `~/.persistent_envs` by default. Change both enter and exit actions if you choose another path.

### Conda queue environment with improved caching using Conda written inline

The cached inline sample implements the same idea with named Conda environments on customer-managed fleets. Its default name hashes channels and packages; jobs can also specify a name. Separate settings control how long an environment is reused before package refresh and when stale environments are deleted.

### Rez environment

The Rez sample resolves software from a shared package repository. Use it with customer-managed fleets that can access that repository.

### Pip environment

The pip sample uses Python's standard-library `venv` module, installs `PipPackages`, and activates the environment for subsequent steps. If `PipPackages` is empty it does nothing, allowing mixed queues. `PipIndexUrl` and `PipExtraIndexUrls` support private indexes such as [AWS CodeArtifact](https://docs.aws.amazon.com/codeartifact/).

Workers need `python3` or `python` on `PATH`; service-managed fleets provide one. Compare the [pip package job](../job_bundles/pip_package_job/) with the [self-contained pip job](../job_bundles/pip_self_contained_job/) when deciding whether configuration belongs on the queue or in one bundle.

### Disconnect UBL

The disconnect environment unsets Deadline Cloud Usage Based License variables so jobs use a custom license server. Give it a higher-precedence position than other environments, for example priority `0`, so later licensing setup is not removed. Review [Bring Your Own License](https://docs.aws.amazon.com/deadline-cloud/latest/developerguide/smf-byol.html). Additional UBL variables can be introduced over time, so review the template against current service behavior before deployment.
