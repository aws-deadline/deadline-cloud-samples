# ComfyUI conda package recipe

This [rattler-build](https://rattler.build/) recipe packages [ComfyUI](https://github.com/Comfy-Org/ComfyUI)
installed by [comfy-cli](https://github.com/Comfy-Org/comfy-cli), the official ComfyUI command line
tool. The package is called `comfy`.

| | |
|---|---|
| **Application** | ComfyUI 0.44.0, installed by comfy-cli 1.22.0 |
| **Platform** | linux-64 |
| **PyTorch** | 2.11.0 from the CUDA 13.0 (`cu130`) index |
| **Fleet GPU driver** | `latest` (the default) or `grid:r580` |
| **Build worker** | Linux, at least 24 GiB of memory, outbound internet |

## Build process

The build installs the pinned PyTorch release from the CUDA index, then runs:

```
comfy --workspace "$PREFIX/opt/comfyui" install --version 0.44.0 --nvidia --skip-torch-or-directml --skip-manager
```

comfy-cli clones the ComfyUI release and installs ComfyUI's `requirements.txt`. That file lists
`torch` without a version, and the pinned release already satisfies it. The build fails if anything
replaces it. Each build records the installed versions in `$COMFYUI_LOCATION/pip-freeze.txt`.

### Pinned versions

- **ComfyUI and comfy-cli** are pinned in [recipe.yaml](recipe/recipe.yaml), so the package version
  says which ComfyUI it contains.
- **PyTorch 2.11.0**, torchvision 0.26.0 and torchaudio 2.11.0, built for **CUDA 13.0**, are pinned
  in [recipe.yaml](recipe/recipe.yaml).
  - Without a pin, comfy-cli chooses the PyTorch CUDA build from the NVIDIA driver on the build
    worker, and falls back to CUDA 12.6 when there is no GPU. The package would then depend on which
    worker built it, and CUDA 12.6 doesn't support Blackwell GPUs such as the RTX PRO 6000. CUDA 13
    needs NVIDIA driver 580 or later, which Deadline Cloud's default `latest` GPU driver provides.
  - torchaudio releases lag behind torch and don't declare which torch they were built for, so the
    three are pinned to one matching release.
- **`setuptools <82`** is a conda requirement, because torch 2.11 requires it and conda installs
  setuptools too. Jobs that add custom nodes run `pip check`, which rejects a newer setuptools.
- **ComfyUI's other dependencies aren't pinned.** Each build installs the newest versions that
  ComfyUI's `requirements.txt` allows, so two builds of the same recipe can differ. A build is fixed
  once it's published, and `pip-freeze.txt` records what it contains. Test a new build before jobs
  use it.

### Changing versions

To move to a new ComfyUI, comfy-cli or PyTorch release, change the versions in the `context` of
[recipe.yaml](recipe/recipe.yaml). The PyTorch versions must be one release that exists on the
[CUDA index](https://download.pytorch.org/whl/cu130): torch, torchvision and torchaudio with the
same release, such as 2.11.0, 0.26.0 and 2.11.0. Check torch's `setuptools` requirement too. Then
build the package and run a workflow before jobs use it.

The package also includes **the `comfy` command** and **ComfyUI's git history**
(`$COMFYUI_LOCATION/.git`), because comfy-cli works with a git checkout. `COMFY_NO_TELEMETRY=1` is
set, so `comfy` never prompts for analytics.

ComfyUI-Manager isn't installed. Don't use `comfy install`, `comfy update` or `comfy node` in jobs,
because they change the shared, cached conda environment.

## Using the package in a job

Start ComfyUI as a local server with `comfy`, run workflows on it, then stop it:

```
mkdir -p "$SESSION_DIR/comfyui/custom_nodes"
comfy --skip-prompt --workspace "$COMFYUI_LOCATION" launch --background -- \
    --listen 127.0.0.1 --port "$PORT" \
    --base-directory "$SESSION_DIR/comfyui" \
    --output-directory "$OUTPUT_DIR" \
    --extra-model-paths-config extra_model_paths.yaml

comfy --skip-prompt run --workflow workflow.json --where local --host 127.0.0.1 --port "$PORT" --wait

comfy --skip-prompt stop --port "$PORT"
```

- **Always pass `--base-directory`.** Without it, ComfyUI writes `models/`, `user/`, `input/`,
  `output/` and `temp/` into the shared, cached conda environment, where they stay for later jobs.
- **Create `custom_nodes/` in the base directory first.** ComfyUI can fail to start on a base
  directory without one.
- **Always pass `--wait` to `comfy run`.** Without it, `comfy run` submits the workflow and exits
  before the workflow finishes.
- **Use `--where local`**, so that `comfy` never sends the workflow to Comfy Cloud.
- `comfy run` accepts workflows in API format or the regular UI format, which it converts.
- Use `--extra-model-paths-config` to point ComfyUI at model folders and `custom_nodes` folders
  on shared storage or in a cache.

The recipe's tests run this sequence with a small workflow that doesn't need any models
([test_comfy.sh](recipe/test_comfy.sh)), and check that `comfy run` fails for a broken
workflow.

## Building the package

From the `conda_recipes` directory:

```
$ ./submit-package-job comfy
```

The recipe has no source archive. comfy-cli downloads ComfyUI from GitHub during the build.

## License

ComfyUI and comfy-cli are distributed under the GPL-3.0 license. The package also bundles PyTorch
(BSD-3-Clause), the NVIDIA CUDA redistributable libraries (NVIDIA license) and other wheels from
PyPI under their own licenses. Review them before you distribute the package outside your
organization.
