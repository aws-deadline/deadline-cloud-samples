import argparse
import os
import torch
from diffusers import StableDiffusionPipeline
from safetensors import safe_open
from safetensors.torch import load_file
from peft import LoraConfig, PeftModel, set_peft_model_state_dict

# Set cache directory
cache_dir = os.path.expanduser("~/.models/huggingface")
os.makedirs(cache_dir, exist_ok=True)
os.environ["HF_HOME"] = cache_dir
os.environ["TRANSFORMERS_CACHE"] = cache_dir
os.environ["HF_DATASETS_CACHE"] = cache_dir

parser = argparse.ArgumentParser()
parser.add_argument("--lora-path", required=True)
parser.add_argument("--prompt", required=True)
parser.add_argument("--negative-prompt", required=True)
parser.add_argument("--width", type=int, required=True)
parser.add_argument("--height", type=int, required=True)
parser.add_argument("--num-inference-steps", type=int, required=True)
parser.add_argument("--guidance-scale", type=float, required=True)
parser.add_argument("--seed", type=int, required=True)
parser.add_argument("--image-index", type=int, required=True)
parser.add_argument("--output-dir", required=True)
args = parser.parse_args()


def load_lora_with_metadata(filepath):
    """Load LoRA weights and extract embedded metadata from safetensors file."""
    if not os.path.isfile(filepath):
        raise ValueError(f"LoRA weights file not found: {filepath}")

    with safe_open(filepath, framework="pt") as f:
        metadata = f.metadata()

    if not metadata:
        raise ValueError(
            f"No metadata found in LoRA file '{filepath}'. "
            "This file may have been created with an older version of the training script."
        )

    required_keys = ["base_model", "lora_rank"]
    missing = [k for k in required_keys if k not in metadata]
    if missing:
        raise ValueError(f"LoRA file missing required metadata: {missing}")

    state_dict = load_file(filepath)
    return state_dict, metadata


# Load LoRA weights and metadata
lora_state_dict, lora_metadata = load_lora_with_metadata(args.lora_path)
base_model = lora_metadata["base_model"]
lora_rank = int(lora_metadata["lora_rank"])
lora_alpha = int(lora_metadata.get("lora_alpha", lora_rank))

print(f"Loaded LoRA metadata: base_model={base_model}, rank={lora_rank}, alpha={lora_alpha}")
print(f"Loaded {len(lora_state_dict)} LoRA tensors from file")

device = torch.accelerator.current_accelerator().type if torch.accelerator.is_available() else "cpu"
print(f"Using device: {device}")

pipe = StableDiffusionPipeline.from_pretrained(
    base_model,
    torch_dtype=torch.float16 if device == "cuda" else torch.float32,
    safety_checker=None,
    requires_safety_checker=False,
).to(device)

lora_config = LoraConfig(
    r=lora_rank, lora_alpha=lora_alpha, target_modules=["to_k", "to_q", "to_v", "to_out.0"]
)
pipe.unet = PeftModel(pipe.unet, lora_config)

set_peft_model_state_dict(pipe.unet, lora_state_dict)

lora_params_loaded = len(
    [k for k in pipe.unet.state_dict().keys() if "lora" in k.lower()]
)
if lora_params_loaded == 0:
    raise RuntimeError("FAILED: 0 LoRA parameters loaded into model!")

print(f"Successfully loaded {lora_params_loaded} LoRA parameters into UNet")
print(f"LoRA scale: {lora_alpha / lora_rank}")

if args.seed == -1:
    seed = args.image_index * 12345
else:
    seed = args.seed

generator = torch.Generator(device=device).manual_seed(seed)

image = pipe(
    prompt=args.prompt,
    negative_prompt=args.negative_prompt,
    width=args.width,
    height=args.height,
    num_inference_steps=args.num_inference_steps,
    guidance_scale=args.guidance_scale,
    generator=generator,
).images[0]

filename = f"image_{args.image_index:04d}.png"
output_path = os.path.join(args.output_dir, filename)
os.makedirs(os.path.dirname(output_path), exist_ok=True)
image.save(output_path)
print(f"Generated image saved to {output_path}")
