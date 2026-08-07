# Sample conda package recipes and package build infrastructure for AWS Deadline Cloud

## Summary

This directory contains sample tools for creating an S3 conda channel and
building new packages for either Linux or Windows into it on AWS Deadline Cloud.

* The job bundle [conda_build_linux_package](conda_build_linux_package) defines a job that
  is cross-platform but configured for Linux.
* The submission command `submit-package-job` submits a job for running
  a provided rattler-build recipe on a specified set of conda platforms. It takes the job
  bundle, and edits it to match the arguments provided.
* A set of rattler-build and conda-build recipes with the metadata needed by `submit-package-job`
  provide a starting point for packages.
* Supports [rattler-build](https://prefix-dev.github.io/rattler-build/),
  and (as deprecated) [conda-build](https://docs.conda.io/projects/conda-build/).

## Recipe index

This table covers all 51 immediate user-selectable recipe directories in `conda_recipes/`.

| Sample | What it demonstrates | Start here when |
|---|---|---|
| [After Effects 25.1](aftereffects-25.1/) | Packaging Adobe After Effects for Windows workers | You need the base After Effects 25 application |
| [After Effects plugin bundle](aftereffects-plugin-bundle/) | Bundling multiple supplied After Effects plugins | You want one versioned package for a studio plugin set |
| [After Effects Saber](aftereffects-saber/) | Installing the Saber plugin into an After Effects package | You need a small single-plugin recipe example |
| [AutoDock Vina 1.2.5](autodock-vina-1.2.5/) | Building the AutoDock Vina molecular docking application | You run virtual-screening or docking jobs |
| [AYON Launcher](ayon-launcher/) | Packaging the AYON pipeline runtime for headless publishing | Deadline Cloud workers must participate in an AYON pipeline |
| [Blender 4.2](blender-4.2/) | Packaging Blender 4.2 for Linux and Windows | Your jobs require Blender 4.2 |
| [Blender 4.3](blender-4.3/) | Packaging Blender 4.3 for Linux and Windows | Your jobs require Blender 4.3 |
| [Blender 4.4](blender-4.4/) | Packaging Blender 4.4 for Linux and Windows | Your jobs require Blender 4.4 |
| [Blender 4.5](blender-4.5/) | Packaging Blender 4.5 for Deadline Cloud | Your jobs require Blender 4.5 |
| [Blender 5.0](blender-5.0/) | Packaging Blender 5.0 with plugin-sync support | Your jobs require Blender 5.0 |
| [Blender 5.1](blender-5.1/) | Packaging Blender 5.1 with tested plugin-sync scripts | Your jobs require Blender 5.1 |
| [Blender FLIP Fluids](blender-flipfluids/) | Installing the FLIP Fluids add-on into Blender | You need a Blender simulation add-on recipe |
| [Blender plugin bundle](blender-plugin-bundle/) | Packaging multiple Blender add-on ZIP files together | You deliver a changing studio collection of Blender plugins |
| [Cinema 4D 2024](cinema4d-2024/) | Packaging Cinema 4D 2024 with Plugin Sync for Windows | Your jobs require Cinema 4D 2024 |
| [Cinema 4D 2025](cinema4d-2025/) | Packaging Cinema 4D 2025 with Plugin Sync for Windows | Your jobs require Cinema 4D 2025 |
| [Cinema 4D 2026](cinema4d-2026/) | Packaging Cinema 4D 2026.3.3 with Plugin Sync for Windows | Your jobs require Cinema 4D 2026 |
| [Arnold for Cinema 4D 2025](cinema4d-c4dtoa-2025/) | Packaging the C4DtoA renderer plugin | Cinema 4D 2025 jobs render with Arnold |
| [INSYDIUM for Cinema 4D 2025](cinema4d-insydium-2025/) | Packaging supplied INSYDIUM plugin files | Cinema 4D jobs use X-Particles or related plugins |
| [Cinema 4D OpenJD adaptor](cinema4d-openjd/) | Packaging the Cinema 4D integration adaptor | Cinema 4D jobs need OpenJD session integration |
| [V-Ray for Cinema 4D 2025](cinema4d-vray-2025/) | Packaging the V-Ray plugin for Cinema 4D | Cinema 4D 2025 jobs render with V-Ray |
| [Deadline Cloud CLI](deadline/) | Building the `deadline` Python package and command line tools | Another package or worker environment needs the Deadline client |
| [Houdini 20.5](houdini-20.5/) | Packaging Houdini 20.5 with plugin activation support | Your jobs require Houdini 20.5 |
| [Houdini 21.0](houdini-21.0/) | Packaging Houdini 21.0 with Plugin Sync activation | Your jobs require Houdini 21 or frequently updated plugins |
| [Redshift for Houdini 2025](houdini-redshift-2025/) | Packaging Redshift for Houdini 2025 | Houdini 20.5 jobs render with Redshift |
| [Redshift for Houdini 2026](houdini-redshift-2026/) | Packaging Redshift for Houdini 2026 | Houdini 21 jobs render with Redshift |
| [V-Ray 7 for Houdini](houdini-vray-7/) | Packaging V-Ray for Houdini | Houdini jobs render with V-Ray 7 |
| [Infinigen 1.19.0](infinigen-1.19.0/) | Packaging the procedural scene generator and dependencies | You generate synthetic indoor or outdoor scenes |
| [KeyShot 2025](keyshot-2025/) | Packaging KeyShot 2025.2 for Windows | Your jobs render with KeyShot |
| [Maya 2025](maya-2025/) | Packaging Maya and configuring module/plugin search paths | Your jobs require Maya 2025 |
| [Maya 2026](maya-2026/) | Packaging Maya with Plugin Sync activation | Your jobs require Maya 2026 or frequently updated plugins |
| [Maya 2027](maya-2027/) | Packaging Maya with Plugin Sync activation | Your jobs require Maya 2027 |
| [Bifrost for Maya 2026](maya-bifrost-2026/) | Packaging Autodesk Bifrost for Maya | Maya 2026 jobs use Bifrost graphs or simulations |
| [Arnold for Maya 2025](maya-mtoa-2025/) | Packaging MtoA against the Maya 2025 package | Maya 2025 jobs render with Arnold |
| [Arnold for Maya 2026](maya-mtoa-2026/) | Packaging MtoA against the Maya 2026 package | Maya 2026 jobs render with Arnold |
| [Maya OpenJD adaptor](maya-openjd/) | Packaging the Maya integration adaptor | Maya jobs need OpenJD session integration |
| [Redshift for Maya 2025](maya-redshift-2025/) | Packaging Redshift 2025 for supported Maya versions | Maya jobs use Redshift 2025 |
| [Redshift for Maya 2026](maya-redshift-2026/) | Packaging Redshift 2026 for supported Maya versions | Maya jobs use Redshift 2026 |
| [V-Ray for Maya 2025](maya-vray-2025/) | Packaging V-Ray for Maya 2025 | Maya 2025 jobs render with V-Ray |
| [V-Ray for Maya 2026](maya-vray-2026/) | Packaging V-Ray for Maya 2026 | Maya 2026 jobs render with V-Ray |
| [V-Ray 7.2 for Maya 2025](maya-vray-7.2-2025/) | Pinning V-Ray 7.20.02 to Maya 2025 | You need the exact V-Ray 7.2/Maya 2025 combination |
| [V-Ray 7.2 for Maya 2026](maya-vray-7.2-2026/) | Pinning V-Ray 7.20.02 to Maya 2026 | You need the exact V-Ray 7.2/Maya 2026 combination |
| [Nerfstudio](nerfstudio/) | Packaging Nerfstudio and Gaussian Splatting extras | You train NeRF or Gaussian Splatting models |
| [Nuke 16.0](nuke-16.0/) | Packaging Nuke 16 with plugin activation support | Your compositing jobs require Nuke 16 |
| [Nuke 17.0](nuke-17.0/) | Packaging Nuke 17 with Plugin Sync activation | Your compositing jobs require Nuke 17 or changing plugins |
| [Nuke DENoise](nuke-denoise/) | Packaging the DENoise plugin for Nuke | Nuke jobs need the DENoise node on workers |
| [OpenJD adaptor runtime](openjd-adaptor-runtime/) | Packaging the shared runtime used by DCC adaptors | You are building adaptor packages such as Maya or Cinema 4D |
| [Unreal Engine](unreal-engine/) | Packaging Unreal Engine, including custom source builds | Unreal workloads need an engine package on workers |
| [Unreal Engine OpenJD adaptor](unreal-engine-openjd/) | Packaging the Unreal integration adaptor | Unreal jobs need OpenJD session integration |
| [V-Ray standalone](vray/) | Packaging the standalone V-Ray renderer | Jobs render `.vrscene` files without a DCC |
| [VRED Core 2025](vredcore-2025/) | Packaging Autodesk VRED Core 2025 for Linux | Automotive visualization jobs require VRED 2025 |
| [VRED Core 2026](vredcore-2026/) | Packaging Autodesk VRED Core 2026 for Linux | Automotive visualization jobs require VRED 2026 |

## Build and archive support

[`conda_build_linux_package/`](conda_build_linux_package/) is the reusable OpenJD package-build job,
not a package recipe, so it is intentionally excluded from the recipe table. The top-level
`submit-package-job`, `submit-package-job.bat`, `submit-package-job-script.py`, and
`conda_platform_host_requirements.yaml` files are its submission and platform-support tooling.
[`archive_files/`](archive_files/) stores source or generated package archives and is also excluded;
it is not a user-selectable recipe.

## Infrastructure setup prerequisites

See the Deadline Cloud developer guide documentation
[Create a conda channel using S3](https://docs.aws.amazon.com/deadline-cloud/latest/developerguide/configure-jobs-s3-channel.html)
for instructions on how to set up a Deadline Cloud farm for building packages into an Amazon S3 conda channel.
Name your package build queue "Package Build Queue" for the job submission command to select it by default.

To make this process faster and simpler, you can use our provided [starter farm CloudFormation template](../cloudformation/farm_templates/starter_farm/) to deploy your Deadline infrastructure along with
a configured package build queue as documented in the Deadline Cloud developer guide linked above.

To submit package build jobs, you will need the
[Deadline Cloud CLI](https://docs.aws.amazon.com/deadline-cloud/latest/developerguide/submit-jobs-how.html)
installed on your workstation, along with a Python interpreter that has the `deadline`
library available. Installing the CLI with `pip install deadline` satisfies both requirements.
See [Python interpreter requirement](#python-interpreter-requirement) below if you installed
the CLI using the standalone submitter installer.

## Submitting package build jobs

The `submit-package-job` command submits package-build jobs from this `conda_recipes` directory. It runs the script [submit-package-job-script.py](submit-package-job-script.py) using the Python
for the Deadline Cloud CLI so it can rely on the `deadline` library dependency being available without additional setup.

By default it will submit the job to a queue whose name starts with "Package", and will
use the job attachments bucket of that queue to form the conda channel `s3://<my-job-attachments-bucket>/Conda/Default`.

Run the command `submit-package-job --help` to get a listing of available CLI arguments.

### Python interpreter requirement

The `submit-package-job` command is a thin wrapper that runs
[submit-package-job-script.py](submit-package-job-script.py) with a Python interpreter that
has the `deadline` library installed. How it finds that interpreter depends on how you
installed the Deadline Cloud CLI:

* **`pip install deadline`** (recommended for this workflow): the wrapper discovers the
  interpreter automatically from the `deadline` entry point script, so no extra setup is
  needed.
* **Standalone submitter installer**: the installer includes a self-contained `deadline`
  executable and does not bundle a reusable Python interpreter. In this case the wrapper
  cannot find a Python to use on its own, and you must point it at one yourself by setting
  the `DEADLINE_PYTHON` environment variable to a Python that has the `deadline` library
  installed (`pip install deadline`):

  ```
  $ DEADLINE_PYTHON=python3 ./submit-package-job blender-4.2
  ```

  On Windows:

  ```
  > set DEADLINE_PYTHON=python
  > submit-package-job blender-4.2
  ```

  If you run the command without a usable interpreter, it exits with an explanatory error
  rather than a cryptic failure.

### Basic job submission

To submit a package build job for Blender 4.2, enter this `conda_recipes` directory and run the following
from your POSIX shell:

```
$ ./submit-package-job blender-4.2
```

or the following from your Windows cmd shell:

```
> submit-package-job blender-4.2
```

### Submitting a job for specific conda platforms

The `submit-package-job` command reads the file `deadline-cloud.yaml` that lives in the recipe's outer directory.
The file contains a list of conda platforms that the recipe supports along with metadata such as whether to
build a package for the platform by default.

The queue you submit the job to will need to have an associated fleet with the operating system and cpu architecture
for each conda platform of the job. If a fleet is missing, your job will enter a status of NOT_COMPATIBLE. To resolve it,
either submit again with a more restricted list of conda platforms or deploy the additional fleets to your farm.

To submit the Linux x86 64-bit platform:

```
$ ./submit-package-job blender-4.2 -p linux-64
```

To submit both Windows and Linux x86 64-bit platforms:

```
$ ./submit-package-job blender-4.2 -p win-64 -p linux-64
```

To submit all the platforms specified in `deadline-cloud.yaml`, including the non-default ones:

```
$ ./submit-package-job blender-4.2 --all-platforms
```

The `-p` option accepts glob wildcards that are useful for submitting variant builds.
To submit all the 64-bit Windows variants:

```
$ ./submit-package-job deadline -p win-64*
```

To submit all platforms for the `py312` variant:

```
$ ./submit-package-job deadline -p *-py312
```

### Submitting a job to a specific queue

By default, the `submit-package-job` command submits to a queue whose name starts with "Package" in
the default configured farm. You can pass the `-q` or `--queue` option to select a different queue.
If you set the default queue of the Deadline Cloud CLI to your production queue, you can
use `submit-package-job` to submit package jobs and use `deadline bundle submit` to submit test jobs
without changing configuration in between.

```
$ ./submit-package-job blender-4.2 -q "Different Package Build Queue"
```

### Submitting a job for a different S3 channel

The default S3 channel that `submit-package-job` builds to is `s3://<my-job-attachments-bucket>/Conda/Default`,
where the job attachments bucket comes from the selected queue.

You can provide different names to build to different channels within the same S3 bucket. The following submits
to `s3://<my-job-attachments-bucket>/Conda/AnotherChannel`:

```
$ ./submit-package-job blender-4.2 --s3-channel AnotherChannel
```

Use the following to fully control the S3 channel URL. For this to work, ensure that the
IAM role of the queue you're submitting to includes permissions for the S3 bucket.

```
$ ./submit-package-job blender-4.2 --s3-channel s3://<another-s3-bucket>/channel/prefix
```

### Enabling fast build optimizations

You can enable fast build optimizations to create faster builds
by adding the `--fast-build` or `-f` flag:

```
$ ./submit-package-job blender-4.2 --fast-build
```

The fast-build flag enables:
- **rattler-build**: Uses `--package-format conda:min` for optimized package format
- **conda-build** (deprecated): Uses `--zstd-compression-level 1` for faster compression with a larger package size

The fast build optimization is particularly beneficial for packages with many files or large binaries,
as it reduces package size and can speed up both the build process and package installation.

### Adding custom build arguments

You can pass additional arguments to the conda-build or rattler-build command using the `--extra-build-tool-args` or `-a` option:

```
$ ./submit-package-job blender-4.2 --extra-build-tool-args "--no-test --quiet"
```

Any supported conda-build or rattler-build argument works here:
- **conda-build**: Examples include `--no-test`, `--quiet`, `--debug`
- **rattler-build**: Examples include `--quiet`, `--debug`, `--skip-existing`

The build arguments are parsed as space-separated values and added to the build command. Use quotes to group arguments that contain spaces.

## Recipe directory structure for `submit-package-job`

The `submit-package-job` command expects rattler-build recipes in a specific directory structure. It's inspired by the
[conda-forge feedstock repository structure](https://conda-forge.org/docs/maintainer/adding_pkgs/#feedstock-repository-structure).

**recipe**

This folder contains the rattler-build recipe, including `recipe.yaml` and package build scripts.

**deadline-cloud.yaml**

This file is used by the `submit-package-job` command to configure how it submits package build jobs
to Deadline Cloud.

**other files**

You can add more files, like a LICENSE.txt to document the license of the recipe.

### Contents of the `deadline-cloud.yaml` file

The file `deadline-cloud.yaml` file provides metadata for how to submit the package build
job to Deadline Cloud.

#### The buildTool option

You can select the default build tool between rattler-build and conda-build (deprecated) for the whole recipe
by setting this option. [Rattler build](https://prefix-dev.github.io/rattler-build/)
is a newer tool built with rust and using a new package build recipe format established
in conda enhancement proposals [CEP 13](https://github.com/conda/ceps/blob/main/cep-0013.md)
and [CEP 14](https://github.com/conda/ceps/blob/main/cep-0014.md). [Conda build](https://docs.conda.io/projects/conda-build/)
(support in this sample is deprecated) is the original package building tool implemented for conda. Rattler build typically
builds packages faster, especially when the package has many and/or large files.

```
buildTool: rattler-build
```

#### The condaPlatforms list

The file's main entry is a list of conda platforms to submit for. Common platforms
are linux-64 for 64-bit x86 Linux, linux-aarch64 for 64-bit ARM Linux, and win-64
for 64-bit x86 Windows. A minimal configuration looks like this:

```
condaPlatforms:
  - platform: linux-64
    defaultSubmit: true
```

You can select the build tool separately for a platform by adding a buildTool entry:

```
condaPlatforms:
  - platform: linux-64
    defaultSubmit: true
    buildTool: rattler-build
```

If the source for the package is not available for download from the internet, you
can specify a filename and human-readable instructions for where to get it.

```
condaPlatforms:
  - platform: linux-64
    defaultSubmit: true
    buildTool: rattler-build
    sourceArchiveFilename: internal-animation-tool-1.3.tar.gz
    sourceDownloadInstructions: 'Copy from internal drive /mnt/tools/internal/source'
```

To define multiple builds for one platform, such as CUDA and CPU-only variants, add a
`variant` field. The `additionalHostRequirements` field appends the worker capabilities
needed by that variant.
You can also control the value of a `variant_config.yaml` file to provide parameter
values to the conda variants (See [conda-build variants](https://docs.conda.io/projects/conda-build/en/latest/resources/variants.html)
or [rattler-build variants](https://prefix-dev.github.io/rattler-build/latest/variants/)).
In this example, the conda platforms the `submit-package-job` will build for are linux-64-cuda
and linux-64-cpu-only.

```
condaPlatforms:
  - platform: linux-64
    variant: cuda
    defaultSubmit: true
    additionalHostRequirements:
      amounts:
      - name: amount.worker.gpu
        min: 1
    variantConfig:
      cuda_compiler_version:
      - 12.1
  - platform: linux-64
    variant: cpu-only
    defaultSubmit: true
    additionalHostRequirements:
      amounts:
      - name: amount.worker.gpu
        max: 0
    variantConfig:
      cuda_compiler_version:
      - None
```

#### The jobParameters list

This list lets the recipe provide parameter values to the job bundle that the `submit-package-job` command uses.
The format is the same as the
[parameter_values.yaml](https://docs.aws.amazon.com/deadline-cloud/latest/developerguide/build-job-bundle-parameters.html)
file of a job bundle.

If the package recipe depends on packages from conda-forge or defaults, you can
specify the value of the CondaChannels parameter to include it while building.

```
jobParameters:
- name: CondaChannels
  value: conda-forge
```

Alternatively, you may require that it build with a shorter prefix path length
than default.

```
jobParameters:
  - name: OverridePrefixLength
    value: 200
```

Look through the job parameter definitions in the [conda_build_linux_package](conda_build_linux_package/template.yaml)
job bundle to see the parameters it defines. If you need to pass another argument to the `rattler-build`
command, you can modify the job bundle template with a new job parameter and wire it into the package building CLI command.

### Contents of the `recipe` directory

The `recipe` directory contains a rattler build recipe. You can read the official
[rattler-build recipe documentation](https://rattler.build/dev/reference/recipe_file/)
to learn more.

To find example recipes available licensed under Apache-2.0 or similar, you can search
the [list of conda-forge packages](https://conda-forge.org/packages/) and follow the
link to a package's feedstock git repository. You can also use the
[grayskull conda recipe generator](https://github.com/conda/grayskull) to automatically
generate starting point recipes for Python packages in PyPI.

Read [Creating a conda package for an application](https://docs.aws.amazon.com/deadline-cloud/latest/developerguide/conda-package.html)
in the Deadline Cloud developer guide to learn how you can create package recipes for packaging entire applications.

## Tasks

### Create a new recipe from PyPI

1. (Prerequisite) Create and activate a Conda or venv virtual environment to work with
   recipes.
    1. With conda: `conda create -n recipe-env python` and then `conda activate recipe-env`.
    2. With venv: `python -m venv /path/to/venv` and then `source /path/to/venv/bin/activate`.

2. Install the [grayskull](https://github.com/conda/grayskull) conda recipe creator,
    by running `pip install grayskull` or `conda install grayskull`.
3. In the `conda_recipes` directory, create a new subdirectory named as the PyPI package,
    then run `grayskull` to create the recipe within. Grayskull downloads the sdist from PyPI
    to analyze its metadata, and then creates the recipe. Here's an example for `deadline`.
    ```
    $ mkdir deadline
    $ cd deadline
    $ grayskull pypi deadline
    #### Initializing recipe for deadline (pypi) ####
    ...
    Build requirements:
      <none>
    Host requirements:
      - python >=3.8
      - hatchling
      - hatch-vcs
      - pip
    Run requirements:
      - python >=3.8
      - boto3 >=1.34.75
      - click >=8.1.7
      - pyyaml >=6.0
      - typing-extensions ==4.7.*  # [py==37]
      - python-xxhash ==3.4.*
      - jsonschema ==4.17.*
      - pywin32-on-windows ==306  # [win]
      - qtpy ==2.4.*
    ...
    ```
4. We found we needed to change `{{ PYTHON }}` to `python`, because during the build it was producing a path that didn't contain
   the Python binary. In some cases, we also had to change some of the dependency rules.
5. If the package name is different from the module name, such as when it adds to a namespace package,
   you'll need to update the `imports` tests it creates.

### Create a patch for a recipe

Sometimes the source code has bugs, or won't build without modifications. You can create
patch files to include in the recipe.

The source tarballs we generate on GitHub do not work with this process,
so the recipes generated by grayskull fail during the build process.

Here is a procedure for generating a patch and adding it to the recipe.

1. Acquire the source archive, and commit it into a new ephemeral git repository.
    ```
    $ curl -OL https://github.com/aws-deadline/deadline-cloud/releases/download/0.47.3/deadline-0.47.3.tar.gz
    $ tar zxvf deadline-0.47.3.tar.gz
    $ cd deadline-0.47.3
    $ git init .
    $ git add .
    $ git commit -m "initial"
    ```
2. Apply your bug fixes.
    ```
    $ vim pyproject.toml
    ...
    $ git diff
    warning: in the working copy of 'pyproject.toml', LF will be replaced by CRLF the next time Git touches it
    diff --git a/pyproject.toml b/pyproject.toml
    index 893cbcd..94c0c50 100644
    --- a/pyproject.toml
    +++ b/pyproject.toml
    @@ -68,24 +68,6 @@ artifacts = [
    "*_version.py",
    ]

    -[tool.hatch.version]
    -source = "vcs"
    -
    -[tool.hatch.version.raw-options]
    -version_scheme = "post-release"
    -
    -[tool.hatch.build.hooks.vcs]
    -version-file = "_version.py"
    -
    -[tool.hatch.build.hooks.custom]
    -path = "hatch_custom_hook.py"
    -
    -[tool.hatch.build.hooks.custom.copy_version_py]
    -destinations = [
    -  "src/deadline/client",
    -  "src/deadline/job_attachments",
    -]
    -
    [tool.hatch.build.targets.sdist]
    include = [
    "src/*",
    ```
3. Commit the changes, and produce a diff file.
    ```
    $ git add -u
    $ git commit -m "patched"
    $ git format-patch -1
    0001-patched.patch
    ```
4. Add the generated patch to the recipe, beside the `meta.yaml` or `recipe.yaml` file.
    ```
    $ mv 0001-patched.patch /path/to/recipe/0001-Remove-version-build-hook.patch
    $ cd /path/to/recipe
    $ ls
    0001-Remove-version-build-hook.patch  meta.yaml
    $ vim meta.yaml
    ...
    $ git diff meta.yaml
    diff --git a/conda_recipes/deadline/deadline/meta.yaml b/conda_recipes/deadline/deadline/meta.yaml
    index 0d6bb1e..9b6621c 100644
    --- a/conda_recipes/deadline/deadline/meta.yaml
    +++ b/conda_recipes/deadline/deadline/meta.yaml
    @@ -8,6 +8,8 @@ package:
     source:
       url: https://pypi.io/packages/source/{{ name[0] }}/{{ name }}/deadline-{{ version }}.tar.gz
       sha256: fafc727d3e20aeb5c87b303b26a45801d5db8e97cc88997bec4bf76232035443
    +  patches:
    +    - 0001-Remove-version-build-hook.patch

     build:
       skip: true  # [py<38]
    ```
