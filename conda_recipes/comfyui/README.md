# ComfyUI conda package recipe

## Package Information

This directory holds a [rattler-build](https://rattler.build/) recipe for
[ComfyUI](https://github.com/Comfy-Org/ComfyUI), the node-based diffusion model GUI, API
and backend. If you build this package, you can run ComfyUI workflows on AWS Deadline Cloud
CUDA GPU workers.

| | |
|---|---|
| **Application** | ComfyUI 0.38.0 |
| **Platform** | linux-64 |
| **Source** | [Comfy-Org/ComfyUI v0.38.0](https://github.com/Comfy-Org/ComfyUI/releases/tag/v0.38.0) |
| **License** | GPL-3.0-only (see [License](#license)) |
| **Build tool** | rattler-build |
| **Python** | 3.12 |
| **PyTorch** | torch 2.14.1 and torchvision 0.29.1, CUDA 13.0 (`cu130`) wheels |
| **Fleet GPU driver** | `latest` (the default) or `grid:r580` |

The package you build from this recipe includes the following:

1. The ComfyUI source, copied into `$CONDA_PREFIX/opt/comfyui`.
2. ComfyUI's Python dependencies from its `requirements.txt`, installed with pip, including
   the PyTorch CUDA wheels from `download.pytorch.org` and the NVIDIA CUDA libraries they
   depend on.
3. A `comfyui` command that runs ComfyUI's `main.py` with the environment's Python. See
   [Directories](#directories) for its defaults.
4. `$CONDA_PREFIX/opt/comfyui/pip-freeze.txt`, which records the exact Python packages in the
   build.
5. The environment variables `COMFYUI_LOCATION`, `COMFYUI_VERSION` and `PYTHONUNBUFFERED`.

The recipe targets the GPUs in Deadline Cloud
[service-managed fleets](https://docs.aws.amazon.com/deadline-cloud/latest/userguide/smf-gpu.html):
T4, A10G, L4 and L40S. It doesn't install models, custom nodes or ComfyUI-Manager.

## Building the Package

### Download the source archive

From the `conda_recipes` directory, download the ComfyUI source archive:

```
curl -L -o archive_files/ComfyUI-0.38.0.tar.gz https://github.com/Comfy-Org/ComfyUI/archive/refs/tags/v0.38.0.tar.gz
```

ComfyUI doesn't publish a checksum file, so the `sha256` in [recipe.yaml](recipe/recipe.yaml)
is the checksum of the GitHub tag archive. GitHub has changed the checksums of generated
archives before. If a build fails on the checksum, download the archive again and compare
it to the tag before you update the `sha256`.

### Build on Deadline Cloud

You can build this package on a Deadline Cloud farm that is configured for package build
jobs that update an S3 conda channel. Nothing is compiled, so the build doesn't need a GPU.
See the AWS Deadline Cloud developer guide
[Create a conda channel using S3](https://docs.aws.amazon.com/deadline-cloud/latest/developerguide/configure-jobs-s3-channel.html)
for setup instructions.

Submit a build job from the [conda_recipes](..) directory as follows. If you need to
customize this, see the [conda recipe samples README](../README.md).

```
$ ./submit-package-job comfyui
```

To choose the queue by a prefix of its name (the default is `Package`), or the S3 conda
channel to publish to, add the `-q` or `--s3-channel` options:

```
$ ./submit-package-job comfyui -q MyPackageQueue
$ ./submit-package-job comfyui --s3-channel s3://amzn-s3-demo-bucket/Conda/Default
```

### Build locally

You can also build the recipe directly with
[rattler-build](https://rattler.build/latest/#installation) on a Linux host. You don't need
a GPU. From the `conda_recipes` directory:

```
rattler-build publish comfyui/recipe/recipe.yaml \
    --to file://$HOME/my-conda-channel \
    -c conda-forge \
    --build-number=+1
```

## Testing the package

Create an environment from the channel and run ComfyUI's CI quick test on the CPU:

```
conda create -n comfyui -c file://$HOME/my-conda-channel -c conda-forge comfyui
conda activate comfyui
comfyui --cpu --quick-test-for-ci --base-directory "$(mktemp -d)"
```

On a GPU worker, leave out `--cpu`.

## Runtime notes

### Fleet GPU driver

The `cu130` PyTorch wheels need NVIDIA driver r580 or newer, so the fleet's runtime driver
must be `latest` (the default) or `grid:r580`. For fleets that pin `grid:r570` or
`grid:r535`, change `torch_cuda_index` in [recipe.yaml](recipe/recipe.yaml) to `cu128` and
rebuild.

### Directories

By default, ComfyUI writes `models/`, `user/`, `input/`, `output/`, `temp/` and
`custom_nodes/` next to its `main.py`. That location is inside the shared, cached conda env,
so the `comfyui` command instead passes `--base-directory` set to `$COMFYUI_BASE_DIRECTORY`,
or to the current directory if that variable isn't set. For an OpenJD task, the current
directory is the session directory, so any models put there are downloaded again every
session. The `comfyui` command also creates `custom_nodes/` in the base directory, because
ComfyUI fails to start without it.

- The `COMFYUI_USER_DIRECTORY`, `COMFYUI_TEMP_DIRECTORY`, `COMFYUI_INPUT_DIRECTORY` and
  `COMFYUI_OUTPUT_DIRECTORY` variables redirect individual directories, for example from a
  queue environment. They pass the matching `--*-directory` options.
- ComfyUI requires `--user-directory` to be an absolute path to a directory that already
  exists, so create it before ComfyUI starts.
- Options that you pass to `comfyui` override both the defaults and the variables.
- To use models from job attachments or shared storage, pass `--extra-model-paths-config`
  with an `extra_model_paths.yaml` file that points at them. See
  `$COMFYUI_LOCATION/extra_model_paths.yaml.example`.

### Logging

The package sets `PYTHONUNBUFFERED=1`, so ComfyUI's output streams to the task logs as it
happens. The `comfyui` command also sets it, for when the environment isn't activated.

### Keep ComfyUI in its own environment

ComfyUI must be the only Python library package in its environment. The package contains
pip-installed copies of numpy, Pillow, scipy, transformers, torch and other libraries in
`site-packages`, and conda doesn't know about them. If you add a conda-forge Python library
to the same environment, for example `CondaPackages="comfyui numpy"`, it overwrites those
files. The only Python libraries the package installs from conda-forge are `packaging` and
`setuptools`, which some of the pip-installed libraries need at runtime.

### Outbound internet at build time

The build worker needs outbound internet access to reach PyPI and `download.pytorch.org`.
Service-managed fleets have it by default, but fleets attached to a VPC without a NAT
gateway don't.

### Reproducibility

`pip-freeze.txt` records exactly what each build contains, but it doesn't make rebuilds
reproducible. Most upstream dependencies are unpinned, so rebuilding the same ComfyUI
version later can resolve newer dependencies. Increase the build number whenever you
rebuild, and compare `pip-freeze.txt` between builds.

### Package size

The `.conda` package is about 3.1 GB, and the installed environment is about 7 GB, mostly
PyTorch and the NVIDIA libraries. A build
uses about 19 GB of extra disk space at its peak, for the build environment, the package and
the test environment. We recommend
that you use the sample queue environment
[conda_queue_env_improved_caching.yaml](../../queue_environments/conda_queue_env_improved_caching.yaml)
so that the environment is reused between jobs.

### Custom nodes

The package doesn't include custom nodes. Custom nodes share `site-packages` with this
package, so deliver them as their own conda package built against this one, not with
`pip install` at job time.

### Memory-heavy workflows

For workflows that need more memory than the worker has, see
[swap_for_smf](../../host_configuration_scripts/swap_for_smf/README.md).

## Updating to a new ComfyUI release

The recipe directory isn't versioned. To update it in place:

1. In [recipe.yaml](recipe/recipe.yaml), update `version` and `sha256`. In
   [deadline-cloud.yaml](deadline-cloud.yaml), update `sourceArchiveFilename` and
   `sourceDownloadInstructions`.
2. Compare the new release's `requirements.txt` with the previous one.
3. Check `torch_version`, `torchvision_version` and `torch_cuda_index` against the
   [ComfyUI README](https://github.com/Comfy-Org/ComfyUI#readme) and the service-managed fleet
   driver list.
4. Rebuild the package.

## Recipe Structure

```
comfyui/
├── README.md
├── deadline-cloud.yaml          # Platform and source archive metadata for submit-package-job
└── recipe/
    ├── recipe.yaml              # rattler-build recipe, with the version and torch pins
    ├── build.sh                 # Copies ComfyUI into the prefix and pip installs its dependencies
    └── comfyui-launcher.sh      # Installed as the comfyui command
```

## License

[ComfyUI](https://github.com/Comfy-Org/ComfyUI/blob/master/LICENSE) is distributed under the
GNU General Public License v3.0 only (GPL-3.0-only). The package you build from this recipe
also bundles PyTorch (BSD-3-Clause), the NVIDIA CUDA redistributable libraries (NVIDIA
license) and other wheels from PyPI under their own licenses. Review those licenses before
you distribute the built package outside your organization.
