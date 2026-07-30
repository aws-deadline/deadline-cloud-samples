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
| [Rez shim environment](rez_queue_env_shim.yaml) | Wrapping each task in a resolved Rez context through `PATH` shims | Rez software needs shell functions, aliases, or ordered `PATH` edits |
| [Rez demo setup](rez_demo_setup_queue_env.yaml) | Installing Rez and building a demo package as test scaffolding | You want to try the shim environment without preparing a worker or repository |
| [Pip environment](pip_queue_env.yaml) | Creating a Python `venv` and installing job-selected pip packages | Jobs need Python packages without Conda or Rez |
| [Disconnect UBL](disconnect_ubl_queue_env.yaml) | Removing Deadline Cloud Usage Based License environment variables | A queue must use only a custom license server |

## Create a queue environment for your queue

1. In the selected sample, change `CondaChannels`, `RezRepositories`, or package-index defaults to your package source. Conda and Rez support shared file-system paths. Conda also supports Anaconda.org, web, and S3 channels.
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

Customer-managed fleets must provide [Conda](https://conda.io/projects/conda/en/latest/user-guide/install/index.html) or [Rez](https://rez.readthedocs.io/en/stable/installation.html), such as in the AMI.

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

The py-rattler sample provides similar behavior through [py-rattler](https://conda.github.io/rattler/py-rattler/). It generally solves faster, but `pip` is not automatically included with `python`, it rejects some syntax accepted by Conda (such as `colmap=*=gpu*`), and solver errors can include less diagnostic detail.

### Conda queue environment with improved caching

The service-managed cached sample stores reusable environments under `~/.persistent_envs` by default. Change both enter and exit actions if you choose another path.

### Conda queue environment with improved caching using Conda written inline

The cached inline sample implements the same idea with Conda environments identified by name on customer-managed fleets. Its default name hashes channels and packages, and jobs can also specify a name. Separate settings control how long an environment is reused before package refresh and when stale environments are deleted.

### Rez environment

The Rez sample resolves software from a shared package repository. Use it with customer-managed fleets that can access that repository.

### Rez shim environment

The Rez sample activates a context during `onEnter` and then publishes the resulting environment variables with `openjd_env`. A queue environment action runs in its own subprocess, so only variables can cross into later actions. Shell functions, aliases, and ordered `PATH` edits are lost, which matters for software distributed with Rez.

The shim sample keeps the resolve out of that path. It saves the resolved context to a `.rxt` file once, then writes one small executable per tool into the session directory and prepends that directory to `PATH`. Job templates still call tools by bare name, such as `command: mayapy`, and each call re-enters the saved context in its own shell. Job bundles need no changes.

Tool names come from `rez context -t` on the saved context, so no list of executables is hard-coded. Set `RezExtraTools` for commands a package provides without declaring them in its `tools` list.

Consider these tradeoffs:

* Only bare command names are intercepted. A template invoking an absolute path bypasses the shims.
* Linux and macOS only. The shims are POSIX shell scripts that depend on a shebang line, which does not work on Windows, so the environment fails immediately there. Use [rez_queue_env.yaml](rez_queue_env.yaml) for Windows workers.
* Place this environment after any other environment that edits `PATH`, such as a higher priority number than a Conda environment, because the last writer wins.

### Rez demo setup

This environment is test scaffolding, not a production sample. It installs Rez into the session directory and builds a small `demotool` package, so the shim environment above can be exercised on a worker that has neither Rez nor a package repository.

Attach it at a lower priority number than the shim environment so it runs first, and pass the same directory as both its `RezDemoRepository` and the shim environment's `RezRepositories`. The shim environment is used unmodified, so what you test is what a farm would run. Pair it with the [Rez shim demo job](../job_bundles/rez_shim_demo/).

```console
openjd run job_bundles/rez_shim_demo/template.yaml \
  --environment queue_environments/rez_demo_setup_queue_env.yaml \
  --environment queue_environments/rez_queue_env_shim.yaml \
  -p RezDemoRepository=/tmp/rez-demo-repository \
  -p RezPackages=demotool \
  -p RezRepositories=/tmp/rez-demo-repository \
  --step VerifyEnvironment
```

### Pip environment

The pip sample uses Python's standard-library `venv` module to install `PipPackages` and activate the environment for subsequent steps. If `PipPackages` is empty it does nothing, allowing mixed queues. `PipIndexUrl` and `PipExtraIndexUrls` support private indexes such as [AWS CodeArtifact](https://docs.aws.amazon.com/codeartifact/).

Workers need `python3` or `python` on `PATH`. Service-managed fleets provide one. Compare the [pip package job](../job_bundles/pip_package_job/) with the [self-contained pip job](../job_bundles/pip_self_contained_job/) when deciding whether configuration belongs on the queue or in one bundle.

### Disconnect UBL

The disconnect environment unsets Deadline Cloud Usage Based License variables so jobs use a custom license server. Give it a higher-precedence position than other environments, such as priority `0`, so later licensing setup is not removed. Review [Bring Your Own License](https://docs.aws.amazon.com/deadline-cloud/latest/developerguide/smf-byol.html). Additional UBL variables can be introduced over time, so review the template against current service behavior before deployment.
