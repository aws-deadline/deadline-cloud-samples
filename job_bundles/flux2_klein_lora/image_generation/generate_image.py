#!/usr/bin/env python3
"""FLUX.2 Klein Image Generation Script with LoRA support using official pipeline."""
import argparse
import os
from pathlib import Path

import torch
from diffusers import Flux2KleinPipeline
from peft import LoraConfig, get_peft_model
from safetensors import safe_open
from safetensors.torch import load_file

MODEL_CONFIGS = {
    "flux.2-klein-base-4b": {
        "hf_repo": "black-forest-labs/FLUX.2-klein-base-4B",
        "guidance_scale": 4.0,
        "num_inference_steps": 50,
    },
    "flux.2-klein-4b": {
        "hf_repo": "black-forest-labs/FLUX.2-klein-4B",
        "guidance_scale": 1.0,
        "num_inference_steps": 4,
    },
}


def load_lora_metadata(filepath):
    with safe_open(filepath, framework="pt") as f:
        return f.metadata() or {}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--lora-path", required=True)
    parser.add_argument("--prompt", required=True)
    parser.add_argument("--width", type=int, default=1024)
    parser.add_argument("--height", type=int, default=1024)
    parser.add_argument("--num-inference-steps", type=int, default=None)
    parser.add_argument("--guidance-scale", type=float, default=None)
    parser.add_argument("--seed", type=int, default=-1)
    parser.add_argument("--image-index", type=int, required=True)
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()

    metadata = load_lora_metadata(args.lora_path)
    model_version = metadata.get("model_version", "flux.2-klein-base-4b")
    print(f"LoRA metadata: {metadata}")
    
    config = MODEL_CONFIGS.get(model_version, MODEL_CONFIGS["flux.2-klein-base-4b"])
    hf_repo = config["hf_repo"]
    
    num_inference_steps = args.num_inference_steps or config["num_inference_steps"]
    guidance_scale = args.guidance_scale if args.guidance_scale is not None else config["guidance_scale"]
    
    print(f"Loading pipeline from {hf_repo}...")
    pipe = Flux2KleinPipeline.from_pretrained(hf_repo, torch_dtype=torch.bfloat16)
    pipe.to("cuda")

    print(f"Loading LoRA from {args.lora_path}...")
    lora_state_dict = load_file(args.lora_path)
    
    lora_config = LoraConfig(
        r=int(metadata.get("network_dim", 16)),
        lora_alpha=int(metadata.get("network_alpha", 16)),
        target_modules=["to_q", "to_k", "to_v", "to_out.0"],
        lora_dropout=0.0,
    )
    pipe.transformer = get_peft_model(pipe.transformer, lora_config)
    incompatible = pipe.transformer.load_state_dict(lora_state_dict, strict=False)
    print(f"Loaded LoRA (missing: {len(incompatible.missing_keys)}, unexpected: {len(incompatible.unexpected_keys)})")

    seed = args.image_index * 12345 if args.seed == -1 else args.seed + args.image_index
    generator = torch.Generator(device="cuda").manual_seed(seed)
    
    print(f"Generating image {args.image_index} with seed {seed}...")
    print(f"Prompt: {args.prompt}")
    print(f"Steps: {num_inference_steps}, Guidance: {guidance_scale}")

    image = pipe(
        prompt=args.prompt,
        height=args.height,
        width=args.width,
        guidance_scale=guidance_scale,
        num_inference_steps=num_inference_steps,
        generator=generator,
    ).images[0]

    os.makedirs(args.output_dir, exist_ok=True)
    filename = f"image_{args.image_index:04d}.png"
    output_path = os.path.join(args.output_dir, filename)
    image.save(output_path)
    print(f"Saved: {output_path}")


if __name__ == "__main__":
    main()
