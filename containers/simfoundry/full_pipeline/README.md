# SimFoundry full pipeline with Claude on Amazon Bedrock and FLUX

Run all of [SimFoundry](https://github.com/NVlabs/SimFoundry)'s reconstruction pipeline A on a video,
then a robot rollout in the scene it builds, with no Google account. The result is an OmniGibson scene
of your tabletop: a textured 3D mesh, pose and friction for each object.

| SimFoundry uses | This sample uses instead |
|---|---|
| Gemini for detection, frame choice and physics estimates | Claude Opus 5.5 and Sonnet 5.5 on Amazon Bedrock |
| Gemini's image model to erase and clean up objects | FLUX.1 Kontext dev, run on the worker's GPU |
| SAM 3 for text-prompted segmentation | SAM 3, or SAM 2.1 grounded by Claude if your account can't get SAM 3 |

On one NVIDIA L4, the default `Fruits.mp4` video with six objects took 96 minutes.

## Files

| Path | Contents |
|---|---|
| [`simfoundry-bedrock-sam2.patch`](simfoundry-bedrock-sam2.patch) | Patch for SimFoundry `9e34ebe`. Adds `simfoundry/models/bedrock.py` and `sam2_grounded.py`, and hooks them into SimFoundry's Gemini and SAM 3 wrappers. Environment variables switch them on, so stage code and configs don't change |
| [`Dockerfile`](Dockerfile) | Builds on the [`simfoundry-rocky10`](../simfoundry-rocky10/) image: applies the patch and adds SAM 2.1 |
| [`queue_environment.yaml`](queue_environment.yaml) | The default Docker queue environment, plus queue-role credentials for code in the container |
| [`job_bundle/template.yaml`](job_bundle/template.yaml) | The job: pipeline A, then pipeline C's random-action rollout |

## Prerequisites

Everything in the [sample's prerequisites](../README.md#prerequisites), including a GPU fleet with
the `grid:r580` runtime, and also:

- **Fleet workers with at least 128 GiB of memory.** On a 24 GiB GPU, FLUX's 24 GB transformer is
  offloaded to CPU memory layer by layer.
- **Claude Opus 5.5 and Sonnet 5.5 enabled in Amazon Bedrock** in the fleet's Region.
- **A Hugging Face token** from an account that has accepted the
  [FLUX.1 Kontext dev](https://huggingface.co/black-forest-labs/FLUX.1-Kontext-dev) licence. For
  `Segmenter=sam3`, the account also needs access to [SAM 3](https://huggingface.co/facebook/sam3).
- **A queue that uses [`queue_environment.yaml`](queue_environment.yaml)** in place of the default
  Docker queue environment. Its queue role also needs this statement:

```json
{
  "Effect": "Allow",
  "Action": ["bedrock:InvokeModel", "bedrock:InvokeModelWithResponseStream"],
  "Resource": [
    "arn:aws:bedrock:<region>:<account-id>:inference-profile/us.anthropic.claude-opus-5-5",
    "arn:aws:bedrock:<region>:<account-id>:inference-profile/us.anthropic.claude-sonnet-5-5",
    "arn:aws:bedrock:*::foundation-model/anthropic.claude-opus-5-5",
    "arn:aws:bedrock:*::foundation-model/anthropic.claude-sonnet-5-5"
  ]
}
```

## Build and submit

Build the base image first, then this one from `containers/simfoundry/full_pipeline`, and push it
as the [sample README](../README.md#build-and-push-the-image) describes.

```console
docker build --tag simfoundry:9e34ebe-rocky10-bedrock .
```

Pass your Hugging Face token at submission:

```console
deadline bundle submit job_bundle --farm-id <farm-id> --queue-id <queue-id> \
  -p DockerImage=<account-id>.dkr.ecr.<region>.amazonaws.com/simfoundry:9e34ebe-rocky10-bedrock \
  -p HfToken="${HF_TOKEN}"
```

> [!WARNING]
> Deadline Cloud stores job parameters in plain text. Anyone who can read the job, in the API or in
> Deadline Cloud Monitor, can read the token. Use a fine-grained, read-only token and rotate it.
> The job's `HuggingFace` environment sets `HF_TOKEN` with `openjd_redacted_env`, which masks it in
> the session logs. To keep the token out of the job record, store it in AWS Secrets Manager, set the
> queue environment's `SecretId` parameter to the secret's name, and leave `HfToken` empty.

| Parameter | Default | Meaning |
|---|---|---|
| `HfToken` | empty | Hugging Face token for the gated models |
| `Segmenter` | `sam3` | `sam3`, or `sam2-bedrock` for SAM 2.1 grounded by Claude Sonnet 5.5 |
| `Video` | `.../example_videos/Fruits.mp4` | The video to reconstruct, as a path inside the image |
| `ImgIdx` | `auto` | The frame the scene is built from. `auto` scores the frames and asks Claude to choose |
| `KeepOutputOnFailure` | `true` | Exit 0 when a stage fails, so the partial output still uploads |

## What you get

`output/<scene>/s14_og/reconstructed_og_scene.json` and `reconstructed_scene.png` hold the
OmniGibson scene. `s7_mesh/textured_mesh/hunyuan/` holds one `.glb` mesh per object, and
`application_smoke/random_action_smoke.mp4` holds the rollout. `run_status.json` records each
pipeline's exit status.

## How it works

The patch checks `SIMFOUNDRY_VLM_BACKEND` in SimFoundry's `Gemini` class. For a text model, it
sends the same prompt and images to the Bedrock Converse API and returns the reply as a Gemini stream
chunk. The stages read it unchanged. Image-model calls raise, and the job sets the
image stages to `flux`. With `SIMFOUNDRY_SEGMENTER=sam2-bedrock`, a text prompt goes to Claude for
boxes, and SAM 2.1 segments inside each box.

The default Docker queue environment never gives the container AWS credentials. This one exports
the queue role's credentials to a file in the session directory, refreshes it every 5 minutes, and
points the container's AWS configuration at it through `credential_process`.

## Troubleshooting

| Symptom | Fix |
|---|---|
| `403` or `GatedRepo` downloading FLUX or SAM 3 | Accept the model's terms on Hugging Face with the token's account, or check `HfToken` |
| `AccessDeniedException` on `bedrock:InvokeModel` | Add the statement above to the queue role, and enable the models in Bedrock |
| `The Flux backend requires a diffusers version...` | Build from this Dockerfile, which sets `XFORMERS_IGNORE_FLASH_VERSION_CHECK=1` |
| `got tilted floor` in stage 3 | The pinned frame's camera is rolled too far. Use `ImgIdx=auto` |

## Licences

FLUX.1 Kontext dev's licence is non-commercial. The patch is Apache 2.0, like SimFoundry. See the
[image README](../simfoundry-rocky10/README.md#licences) for the image's components.
