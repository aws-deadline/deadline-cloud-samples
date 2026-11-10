# ComfyUI workflow

This job bundle runs a [ComfyUI](https://github.com/Comfy-Org/ComfyUI) workflow headlessly on
AWS Deadline Cloud GPU workers. It runs one task per value, such as a seed, and it uses the `comfy`
conda package, which provides ComfyUI and the `comfy` command
([comfy-cli](https://github.com/Comfy-Org/comfy-cli)).

```
comfy_workflow/
├── README.md
├── template.yaml
└── workflows/
    └── sd15_txt2img_api.json   # Default workflow: Stable Diffusion 1.5 text to image
```

## How it works

1. **The job environment** runs once per session, before the session's first task:
   - It downloads any models listed in `ModelDownloads` that aren't in the model cache yet,
     and verifies them against their SHA-256 checksums.
   - It writes an `extra_model_paths.yaml` that points ComfyUI at the cache.
   - It starts ComfyUI in the background with `comfy launch`, on a free local port, with the
     base directory in the session directory and the output directory set to `OutputDir`.
     If the server doesn't start within `ServerStartTimeout`, it stops the server and fails.
2. **Each task**:
   - runs `comfy run --print-prompt` to get the workflow in API format. `comfy run` converts
     workflows saved in the regular UI format, so you don't have to export them for the API;
   - sets the inputs listed in `ValueInputs` to the task's value, and adds the input and value,
     such as `_seed3`, to each `filename_prefix` so tasks don't overwrite each other's outputs;
   - runs the workflow with `comfy run --wait`, showing its output as it runs, and lists the
     output files.

   Tasks in the same session reuse the running server, so they don't load models again.
3. **When the session ends**, the job environment stops the server with `comfy stop`. Job
   attachments collects the files in `OutputDir`.

## Prerequisites

- **The `comfy` conda package** in an S3 conda channel that your queue can read. Build it from
  the [ComfyUI recipe](../../conda_recipes/comfy/README.md).
- **A conda queue environment** whose `CondaChannels` lists that channel before `conda-forge`.
  The job sets `CondaPackages` to `comfy`. If the queue's default `CondaChannels` doesn't include
  your channel, set it when you submit, as shown below. Otherwise the job fails with
  `No candidates were found for comfy`.
- **A Linux GPU fleet** whose runtime driver is `latest` or `grid:r580`. The job requires one GPU.
- **Outbound internet access** on the workers, to download the default model from Hugging Face.

## Submitting the job

To submit workflows from inside ComfyUI, use the
[ComfyUI submitter](https://github.com/aws-deadline/deadline-cloud-for-comfyui) instead. This
bundle shows how to run ComfyUI workflows with the `comfy` command, and you can submit it in
either of these ways from the `job_bundles` directory.

To choose the workflow and parameters in the Deadline Cloud submitter window, where the queue
environment's settings include `CondaChannels`:

```
deadline bundle gui-submit comfy_workflow
```

To submit the default workflow from the command line, with the S3 conda channel that has the
`comfy` package:

```
deadline bundle submit comfy_workflow \
    -p "CondaChannels=s3://MY_BUCKET/Conda/Default conda-forge"
```

You can leave out `CondaChannels` when the queue environment's default already lists the channel.

or your own workflow, saved normally or exported for the API, with 16 seeds:

```
deadline bundle submit comfy_workflow \
    -p WorkflowFile=/path/to/my_workflow.json \
    -p Values=1-16
```

## Task values

Each task sets the number inputs listed in `ValueInputs` to its value from `Values`. List
inputs separated by spaces, in either form:

- `INPUT`, such as `seed`, sets that input on the nodes that have it, except where the input is
  connected to another node. The default, `seed noise_seed`, sets the seed of every sampler.
- `NODE_ID.INPUT`, such as `3.steps`, sets the input on one node. The node ID is the number
  shown on the node in ComfyUI when you turn on node ID badges, and the key of the node in a
  workflow exported for the API.

To render one image for each step count from 10 to 50 in steps of 10:

```
deadline bundle submit comfy_workflow -p ValueInputs=3.steps -p Values=10-50:10
```

The task fails if a `NODE_ID.INPUT` isn't in the workflow, or if no input matches.

## Parameters

| Parameter | Default | Description |
|---|---|---|
| `WorkflowFile` | `workflows/sd15_txt2img_api.json` | A ComfyUI workflow, in UI or API format. |
| `OutputDir` | `./output` | Where ComfyUI writes the outputs of Save nodes. |
| `Values` | `1-4` | The whole numbers to run, one task per value, such as `1-4`, `1-20:2` or `7,42,100`. |
| `ValueInputs` | `seed noise_seed` | The inputs each task sets to its value, as `INPUT` or `NODE_ID.INPUT`. |
| `ModelDownloads` | Stable Diffusion 1.5 (fp16) | Models to download into the cache, as space-separated `FOLDER/FILE=URL#sha256=HEX` entries. |
| `ModelCacheDir` | empty | The model cache directory on the worker. Empty uses the fleet's persistent volume, or `/var/tmp`. |
| `ExtraModelPathsConfig` | empty | An `extra_model_paths.yaml` on the worker, for model and `custom_nodes` folders on shared storage. |
| `ComfyUIArgs` | empty | Extra arguments for the ComfyUI server, such as `--lowvram`. |
| `ServerStartTimeout` | `600` | Seconds to wait for the server to start. |

## Models and custom nodes

Each worker downloads a model only once. Models are cached in
`$DEADLINE_PERSISTENT_MOUNT/comfyui-models` when the fleet has a
[persistent volume](https://docs.aws.amazon.com/deadline-cloud/latest/developerguide/smf-persistent-storage-dev.html),
and otherwise in `/var/tmp/comfyui-models`. For models and custom nodes on shared storage, write
an `extra_model_paths.yaml` that points at them and pass its path on the worker with
`ExtraModelPathsConfig`.

Don't use `comfy node install` or `comfy model download` into the conda environment in jobs. The
environment is shared and cached between jobs.

## License

ComfyUI and comfy-cli are distributed under the GPL-3.0 license. The default model,
[Stable Diffusion 1.5](https://huggingface.co/Comfy-Org/stable-diffusion-v1-5-archive), is
distributed under the CreativeML OpenRAIL-M license, which restricts some uses. Review the
license of every model you use.
