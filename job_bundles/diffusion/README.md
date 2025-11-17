# Diffusers LoRA Training and Image Generation

AWS Deadline Cloud job bundles for training custom LoRA (Low-Rank Adaptation) adapters and generating images with Stable Diffusion using the [Hugging Face Diffusers library](https://huggingface.co/docs/diffusers/index). LoRA allows you to fine-tune Stable Diffusion models on custom subjects or styles.

To train a LoRA adapter and generate images from it:

1. **Prepare Training Data** - Collect images of your subject in a directory
2. **Train LoRA** - Submit training job using the `lora_training` bundle which will build the LoRA
3. **Download Training Output** - Download the trained LoRA weights from the training job
4. **Generate Images** - Submit generation job using the `image_generation` bundle with your trained LoRA

See detailed instructions and parameters for each job bundle below.

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
```bash
deadline bundle submit ./lora_training \
  --parameter DatasetPath=./sample_data \
  --parameter InstancePrompt="a photo of sks dog" \
  --parameter OutputDir=/tmp/lora_output \
  --parameter MaxTrainSteps=500 \
  --parameter LoRARank=4 \
  --parameter LoRAAlpha=16
```

**Output:** LoRA weights saved as `pytorch_lora_weights.safetensors` in Diffusers-compatible format

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
- **Base Model**: SD 1.4, SD 1.5, SD 2.1, or SDXL
- **LoRA Path**: Path to trained LoRA `.safetensors` file
- **LoRA Rank**: Must match the rank used during training
- **Prompt**: Text description of image to generate
- **Negative Prompt**: What to avoid in generation
- **Number of Images**: Total images to generate (parallelized)
- **Width/Height**: Output dimensions (default: 512x512)
- **Inference Steps**: Denoising steps (default: 50)
- **Seed**: Random seed for reproducibility (-1 for random)

**Example:**
```bash
deadline bundle submit ./image_generation \
  --parameter ModelName=runwayml/stable-diffusion-v1-5 \
  --parameter LoRAPath=/tmp/lora_output/pytorch_lora_weights.safetensors \
  --parameter Prompt="a photo of sks dog frowning" \
  --parameter OutputDir=/tmp/dog_images \
  --parameter NumImages=10
```

**Output:** PNG images saved as `image_0001.png`, `image_0002.png`, etc.

**Note:** After job completion, download outputs with:
```bash
deadline job download-output --job-id <job-id>
```

---

## Example: Pokemon dataset
You can use official Pokemon artwork from PokeAPI to train a LoRA adapter.

**Download Instructions:**
1. Clone the PokeAPI sprites repository:
   ```bash
   cd /tmp
   git clone --depth 1 --filter=blob:none --sparse https://github.com/PokeAPI/sprites.git
   cd sprites
   git sparse-checkout set sprites/pokemon/other/official-artwork
   ```

2. Copy up to 500 Pokemon images to your training directory:
   ```bash
   mkdir -p /tmp/pokemon_images
   find /tmp/sprites/sprites/pokemon/other/official-artwork -name "*.png" | head -500 | xargs -I {} cp {} /tmp/pokemon_images/
   ```
   
**Training Parameters (Recommended):**
```bash
deadline bundle submit ./lora_training \
  --parameter DatasetPath=/tmp/pokemon_images \
  --parameter InstancePrompt="sks pokemon" \
  --parameter OutputDir=/tmp/lora_pokemon \
  --parameter Resolution=512 \
  --parameter MaxTrainSteps=10000 \
  --parameter LearningRate=0.0001 \
  --parameter LoRARank=8 \
  --parameter LoRAAlpha=8
```

Note: Use a unique trigger word (e.g., "sks") to help the model distinguish your LoRA. Training 500 diverse images requires more steps (10000) and a lower learning rate (1e-4) for good results. LoRAAlpha of 8 (1x rank) provides balanced effects.

After training completes, download the LoRA weights:
```bash
deadline job download-output --job-id <training-job-id>
```

**Generation Parameters (Recommended):**
```bash
deadline bundle submit ./image_generation \
  --parameter ModelName=runwayml/stable-diffusion-v1-5 \
  --parameter LoRAPath=/tmp/lora_pokemon/pytorch_lora_weights.safetensors \
  --parameter Prompt="sks pokemon, fire type" \
  --parameter NegativePrompt="blurry, low quality" \
  --parameter OutputDir=/tmp/pokemon_output \
  --parameter NumImages=500 \
  --parameter Width=512 \
  --parameter Height=512 \
  --parameter NumInferenceSteps=50 \
  --parameter GuidanceScale=7.5 \
  --parameter LoRARank=8
```

Note: Include the trigger word from training ("sks") in your generation prompt for the LoRA to take effect.
