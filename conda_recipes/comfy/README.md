# ComfyUI (comfy-cli install) conda package recipe

This [rattler-build](https://rattler.build/) recipe packages [ComfyUI](https://github.com/Comfy-Org/ComfyUI)
installed by [comfy-cli](https://github.com/Comfy-Org/comfy-cli), the official ComfyUI command line
tool. The package is called `comfy`. It's an alternative to the [comfyui](../comfyui/README.md)
recipe, which installs ComfyUI's dependencies itself with pinned PyTorch versions.

| | |
|---|---|
| **Application** | ComfyUI 0.38.0, installed by comfy-cli 1.22.0 |
| **Platform** | linux-64 |
| **PyTorch** | Chosen by comfy-cli from the CUDA 13.0 (`cu130`) index |
| **Fleet GPU driver** | `latest` (the default) or `grid:r580` |
| **Build worker** | Linux, at least 24 GiB of memory, outbound internet |

## How it differs from the comfyui recipe

The build runs:

```
comfy --workspace "$PREFIX/opt/comfyui" install --version 0.38.0 --nvidia --cuda-version 13.0 --skip-manager
```

comfy-cli clones the ComfyUI release, then installs `torch`, `torchvision` and `torchaudio` from the
CUDA index and ComfyUI's `requirements.txt`. Nothing pins torch, so comfy-cli installs the newest
torch that has a matching torchaudio. That can be older than the newest torch, because torchaudio
releases lag behind. Each build records the exact versions in `$COMFYUI_LOCATION/pip-freeze.txt`.

The package also includes **the `comfy` command** (comfy-cli) and **ComfyUI's git history**
(`$COMFYUI_LOCATION/.git`), because comfy-cli works with a git checkout. `COMFY_NO_TELEMETRY=1` is
set, so comfy-cli never prompts for analytics.

ComfyUI-Manager isn't installed. Don't use `comfy install`, `comfy update` or `comfy node` in jobs,
because they change the shared, cached conda environment.

## Using the package in a job

Start ComfyUI as a local server with comfy-cli, run workflows on it, then stop it:

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
- **Create `custom_nodes/` in the base directory first.** ComfyUI 0.38.0 fails to start on a base
  directory without one.
- **Always pass `--wait` to `comfy run`.** Without it, `comfy run` submits the workflow and exits
  before the workflow finishes.
- **Use `--where local`**, so that comfy-cli never sends the workflow to Comfy Cloud.
- `comfy run` accepts workflows in API format or the regular UI format, which it converts.
- Use `--extra-model-paths-config` to point ComfyUI at model folders and `custom_nodes` folders
  on shared storage or in a cache.

The recipe's tests run this sequence with a small workflow that needs no models
([test_comfy_cli.sh](recipe/test_comfy_cli.sh)), and check that `comfy run` fails for a broken
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
