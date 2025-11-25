# Diffusers LoRA Training and Image Generation

Train your own AI image models with just 10-100 photos, then generate unlimited new images.

## What can you do with this?

**Train on your pet:** Collect ~50 photos of your dog from different angles, train a LoRA for 30 minutes, then generate images of your dog surfing, wearing a tuxedo, or sitting on the moon.

**Capture an art style:** Gather 20-30 images in a specific illustration style, train a LoRA, then apply that style to any prompt—"a cyberpunk city in [your style]" or "portrait of a knight in [your style]."

**Product photography:** Train on photos of your product, then generate it in various settings, lighting conditions, or contexts without expensive photo shoots.

## How it works

These AWS Deadline Cloud job bundles use [Hugging Face Diffusers](https://huggingface.co/docs/diffusers/index) to fine-tune Stable Diffusion with LoRA (Low-Rank Adaptation)—a technique that creates small, efficient model adapters from your images.

**Workflow:**
1. **Prepare Training Data** - Collect images of your subject in a directory
2. **Train LoRA** - Submit training job using the `lora_training` bundle
3. **Download Training Output** - Download the trained LoRA weights
4. **Generate Images** - Submit generation job using the `image_generation` bundle with your trained LoRA

## Job bundles

### 1. lora_training
Train custom LoRA adapters for Stable Diffusion models using your own image datasets.

**Fleet requirements:**
- GPU with 16GB+ VRAM (or CPU for testing)
- Linux OS

**Key Parameters:**
- **Base Model**: SD 1.4, SD 1.5, SD 2.1, or SDXL
- **Dataset Path**: Local directory containing training images (.jpg, .png, .jpeg)
- **Instance Prompt**: Text describing your training images
- **Max Training Steps**: Number of training iterations
- **LoRA Rank**: Rank of LoRA matrices
- **LoRA Alpha**: Scaling factor for LoRA strength
- **Output Directory**: Where to save trained LoRA weights

**Example:**
Use the job bundle GUI submitter to select parameters values:

```bash
deadline bundle gui-submit ./lora_training
```

Or, use the CLI submitter:

```bash
deadline bundle submit ./lora_training \
  --parameter DatasetPath=./sample_data \
  --parameter InstancePrompt="a photo of Luna, my dog" \
  --parameter OutputDir=/tmp/lora_output \
  --parameter MaxTrainSteps=500 \
  --parameter LoRARank=4 \
  --parameter LoRAAlpha=16
```

**Output:** LoRA weights saved as `pytorch_lora_weights.safetensors` with embedded metadata (base model, rank, alpha, instance prompt). The generation job reads this metadata automatically—no need to re-enter training parameters.

**Download Output:**
After training completes, download the LoRA weights to use in generation:
```bash
deadline job download-output --job-id <training-job-id>
```

---

### 2. image_generation
Generate images using Stable Diffusion with trained LoRA adapters.

**Fleet requirements:**
- Linux worker
- GPU recommended for faster generation (CPU will work but be slow)
- Trained LoRA adapter from lora_training job

**Key Parameters:**
- **LoRA Path**: Path to trained LoRA `.safetensors` file (base model and rank are read from embedded metadata)
- **Prompt**: Text description of image to generate
- **Negative Prompt**: What to avoid in generation
- **Number of Images**: Total images to generate (parallelized)
- **Width/Height**: Output dimensions (default: 512x512)
- **Inference Steps**: Denoising steps (default: 50)
- **Seed**: Random seed for reproducibility (-1 for random)

**Example:**
Use the job bundle GUI submitter to select parameters values:

```bash
deadline bundle gui-submit ./image_generation
```

Or, use the CLI submitter:

```bash
deadline bundle submit ./image_generation \
  --parameter LoRAPath=/tmp/lora_output/pytorch_lora_weights.safetensors \
  --parameter Prompt="Luna, my dog, wearing a tuxedo" \
  --parameter OutputDir=/tmp/dog_images \
  --parameter NumImages=10
```

**Output:** PNG images saved as `image_0001.png`, `image_0002.png`, etc.

**Note:** After job completion, download outputs with:
```bash
deadline job download-output --job-id <job-id>
```
