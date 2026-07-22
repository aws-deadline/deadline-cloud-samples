# FLUX.2 Klein LoRA Training and Image Generation

Train your own AI image models with just 20-50 photos, then generate unlimited new images using Black Forest Labs' fastest model.

## How it works

These AWS Deadline Cloud job bundles use [diffusers](https://github.com/huggingface/diffusers) and [peft](https://github.com/huggingface/peft) to fine-tune FLUX.2 Klein with LoRA (Low-Rank Adaptation), a technique that creates small, efficient model adapters from your images.

**Workflow:**
1. **Prepare Training Data** - Collect images of your subject in a directory (optionally with caption files)
2. **Train LoRA** - Submit training job using the `lora_training` bundle
3. **Download Training Output** - Download the trained LoRA weights
4. **Generate Images** - Submit generation job using the `image_generation` bundle with your trained LoRA

## Prerequisites

- AWS Deadline Cloud farm with a GPU-enabled queue (Linux fleet with NVIDIA GPU)
- [Deadline Cloud CLI](https://github.com/aws-deadline/deadline-cloud) installed

## Job bundle index

This table covers every immediate job bundle in `flux2_klein_lora/`.

| Sample | What it demonstrates | Start here when |
|---|---|---|
| [LoRA training](lora_training/) | Fine-tuning FLUX.2 Klein from an image-and-caption dataset | You need to create a reusable adapter for a subject or style |
| [Image generation](image_generation/) | Parallel inference with a trained LoRA adapter | You have LoRA weights and want to generate a set of images |

## Bundle details

### 1. lora_training

Train custom LoRA adapters for FLUX.2 Klein models using your own image datasets.

**Fleet requirements:**
- GPU with 13GB+ VRAM
- 64 GiB+ system memory (Recommended)
- Linux OS

**Key Parameters:**
- **Model Version**: flux.2-klein-base-4b or flux.2-klein-4b
- **Dataset Path**: Local directory containing training images (.jpg, .png, .jpeg, .webp)
- **Instance Prompt**: Text describing your training images (e.g., "a photo of ohwx dog")
- **Resolution**: Training resolution (default: 512, use 512 for 24GB VRAM)
- **Network Dim**: LoRA rank (default: 16)
- **Network Alpha**: LoRA alpha scaling (default: 16)
- **Max Training Steps**: Number of training iterations (default: 1500)
- **Output Directory**: Where to save trained LoRA weights

**Example:**
Use the job bundle GUI submitter to select parameter values:

```bash
deadline bundle gui-submit ./lora_training
```

Or, use the CLI submitter (specify `--queue-id` for GPU queue):

```bash
deadline bundle submit ./lora_training \
  --queue-id <gpu-queue-id> \
  --parameter DatasetPath=~/training_images \
  --parameter InstancePrompt="a photo of ohwx dog" \
  --parameter OutputDir=/tmp/lora_output \
  --parameter MaxTrainSteps=1500 \
  --parameter Resolution=512
```

**Output:** LoRA weights saved as `flux2_klein_lora.safetensors` with embedded metadata, plus checkpoints every 300 steps.

**Download Output:**
After training completes, download the LoRA weights to use in generation:
```bash
deadline job download-output --job-id <training-job-id> --queue-id <gpu-queue-id>
```

---

### 2. image_generation

Generate images using FLUX.2 Klein with your trained LoRA adapter.

**Fleet requirements:**
- GPU with 13GB+ VRAM
- 64 GiB+ system memory (Recommended)
- Linux OS
- Trained LoRA adapter from lora_training job

**Key Parameters:**
- **LoRA Path**: Path to trained LoRA `.safetensors` file
- **Prompt**: Text description of image to generate (include your trigger word, e.g., "ohwx")
- **Number of Images**: Total images to generate (parallelized across workers)
- **Width/Height**: Output dimensions (default: 1024x1024)
- **Inference Steps**: Denoising steps (default: 50)
- **Guidance Scale**: CFG scale (default: 4.0)

**Example:**
Use the job bundle GUI submitter to select parameter values:

```bash
deadline bundle gui-submit ./image_generation
```

Or, use the CLI submitter:

```bash
deadline bundle submit ./image_generation \
  --queue-id <gpu-queue-id> \
  --parameter LoRAPath=/tmp/lora_output/flux2_klein_lora.safetensors \
  --parameter Prompt="a photo of ohwx dog wearing a tuxedo" \
  --parameter OutputDir=/tmp/generated_images \
  --parameter NumImages=4
```

**Output:** PNG images saved as `image_0001.png`, `image_0002.png`, etc.

**Download Output:**
```bash
deadline job download-output --job-id <job-id> --queue-id <gpu-queue-id>
```

## Model variants

| Model | Parameters | Best For |
|-------|-----------|----------|
| flux.2-klein-base-4b | 4B | Fine-tuning, commercial use |
| flux.2-klein-4b | 4B | Fast inference (4 steps) |

## Captions

Each training image needs a matching `.txt` caption file. You have two options:

**Option 1: Auto-generated (default)**
If no caption files exist, the script creates them using your Instance Prompt. Every image gets the same caption (e.g., "a photo of ohwx dog"). Simple but limited.

**Option 2: Custom captions (recommended for quality)**
Provide your own `.txt` files alongside images:
```
training_images/
├── IMG_001.jpeg
├── IMG_001.txt    # "a photo of ohwx dog sitting on grass"
├── IMG_002.jpeg
├── IMG_002.txt    # "a photo of ohwx dog running on beach"
└── ...
```

Custom captions teach the model more precise associations. Include your trigger word (e.g., "ohwx") in each caption.

## Training tips

1. **Dataset size**: 20-50 high-quality images work well
2. **Resolution**: Use 512 for 24GB VRAM GPUs; higher resolutions require more memory
3. **Steps**: Start with 1500 steps, increase if underfitting
4. **Network dim**: 16 is a good default; increase to 32 for complex concepts
5. **Learning rate**: 1e-4 works well for most cases

## References

- [FLUX.2 Klein on HuggingFace](https://huggingface.co/black-forest-labs/FLUX.2-klein-base-4B)
- [diffusers documentation](https://huggingface.co/docs/diffusers)
- [Black Forest Labs blog](https://bfl.ai/blog/flux2-klein-towards-interactive-visual-intelligence)
