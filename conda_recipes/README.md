# Sample conda build recipes and package build infrastructure for AWS Deadline Cloud

## Summary

This directory contains sample tools for creating an S3 conda channel and
building new packages for either Linux or Windows into it on AWS Deadline Cloud.

* The job bundle [conda_build_linux_package](conda_build_linux_package) defines a job that
  is cross-platform but configured for Linux.
* The submission command `submit-package-job` submits a job for running
  a provided conda build recipe on a specified set of conda platforms. It takes the job
  bundle, and edits it to match the arguments provided.
* A set of conda build recipes with the metadata needed by `submit-package-job`
  provide a starting point for packages.
* Supports both [conda-build](https://docs.conda.io/projects/conda-build/)
  and [rattler-build](https://prefix-dev.github.io/rattler-build/). Only Linux works
  with rattler-build currently.

## Infrastructure setup prerequisites

See the Deadline Cloud developer guide documentation
[Create a conda channel using S3](https://docs.aws.amazon.com/deadline-cloud/latest/developerguide/configure-jobs-s3-channel.html)
for instructions on how to set up a Deadline Cloud farm for building packages into an Amazon S3 conda channel.
Name your package build queue "Package Build Queue" for the job submission command to select it by default.

To submit package build jobs, you will need the
[Deadline Cloud CLI](https://docs.aws.amazon.com/deadline-cloud/latest/developerguide/submit-jobs-how.html)
installed on your workstation.

## Submitting package build jobs

The command `submit-package-job` is a CLI command for submitting package job provided in this `conda_recipes`
directory. It runs the script [submit-package-job-script.py](submit-package-job-script.py) using the Python
for the Deadline Cloud CLI so it can rely on the `deadline` library dependency being available without additional setup.

By default it will submit the job to a queue whose name starts with "Package", and will
use the job attachments bucket of that queue to form the conda channel `s3://<my-job-attachments-bucket>/Conda/Default`.

Run the command `submit-package-job --help` to get a listing of available CLI arguments.

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

## Recipe directory structure for `submit-package-build`

The `submit-package-build` command expects conda build recipes in a specific directory structure. It's inspired by the
[conda-forge feedstock repository structure](https://conda-forge.org/docs/maintainer/adding_pkgs/#feedstock-repository-structure).

**recipe**

This folder contains the conda build recipe, including `meta.yaml` and package build scripts.

**deadline-cloud.yaml**

This file is used by the `submit-package-build` command to configure how it submits package build jobs
to Deadline Cloud.

**other files**

You can add more files, like a LICENSE.txt to document the license of the recipe.

### Contents of the `deadline-cloud.yaml` file

The file `deadline-cloud.yaml` file provides metadata for how to submit the package build
job to Deadline Cloud.

#### The buildTool option

You can select the default build tool between conda-build and rattler-build for the whole recipe
by setting this option. [Conda build](https://docs.conda.io/projects/conda-build/) is
the original package building tool implemented for conda, and [rattler build](https://prefix-dev.github.io/rattler-build/)
is a newer tool built with rust and using a new package build recipe format established
in conda enhancement proposals [CEP 13](https://github.com/conda/ceps/blob/main/cep-0013.md)
and [CEP 14](https://github.com/conda/ceps/blob/main/cep-0014.md). Rattler build typically
builds packages faster, especially when the package has many and/or large files.

NOTE: This sample tool only supports rattler build on Linux.

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

If you want to build different variants on a platform, for instance with CUDA support
and without, you can add a variant field along with additional host requirements to append.
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

This list lets the recipe provide parameter values to the job bundle that the `submit-package-job` comamnd uses.
The format is the same as the
[parameter_values.yaml](https://docs.aws.amazon.com/deadline-cloud/latest/developerguide/build-job-bundle-parameters.html)
file of a job bundle.

If the conda build recpe depends on packages from conda-forge or defaults, you can
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
job bundle to see the parameters it defines. If you need to pass another argument to the `conda build`
command, you can modify the job bundle template with a new job parameter and wire it into the conda build CLI command.

### Contents of the `recipe` directory

The `recipe` directory contains a conda build recipe. You can read the official
[conda build recipe documentation](https://docs.conda.io/projects/conda-build/en/stable/concepts/recipe.html)
to learn more.

To find example recipes available licensed under Apache-2.0 or similar, you can search
the [list of conda-forge packages](https://conda-forge.org/packages/) and follow the
link to a package's feedstock git repository. You can also use the
[grayskull conda recipe generator](https://github.com/conda/grayskull) to automatically
generate starting point recipes for Python packages in PyPI.

Read [Creating a conda package for an application](https://docs.aws.amazon.com/deadline-cloud/latest/developerguide/conda-package.html)
in the Deadline Cloud developer guide to learn how you can create conda build recipes for packaging entire applications.

## Tasks

### Create a new recipe from PyPI

1. (Prerequisite) Create and activate a Conda or venv virtual environment to work with
   recipes.
    1. With conda: `conda create -n recipe-env python` and then `conda activate recipe-env`.
    2. With venv: `python -m venv /path/to/venv` and then `source /path/to/venv/bin/activate`.

2. Install the [grayskull](https://github.com/conda/grayskull) conda recipe creator,
    by running `pip install grayskull` or `conda install grayskull`.
3. In the `conda_recipes` directory, create a new subdirectory named as the PyPI package,
    then run `grayskull` to create the recipe within. This will download the sdist from PyPI
    to analyze its metadata, and then create the recipe. Here's an example for `deadline`.
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
5. If the package name is different from the module name, for example because it adds to a namespace package,
   you'll need to update the `imports` tests it creates.

### Create a patch for a recipe

Sometimes the source code has bugs, or won't build without modifications. You can create
patch files to include in the recipe.

For example, the source tarballs we generate on GitHub do not work with this process,
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
4. Add the generated patch to the recipe, beside the `meta.yaml` file.
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
