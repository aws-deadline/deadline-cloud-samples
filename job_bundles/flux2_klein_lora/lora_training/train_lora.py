#!/usr/bin/env python3
"""FLUX.2 Klein LoRA Training Script - uses pipeline for encoding, manual training loop."""
import argparse
import os
from pathlib import Path

import torch
from diffusers import Flux2KleinPipeline
from diffusers.optimization import get_scheduler
from peft import LoraConfig, get_peft_model
from PIL import Image
from safetensors.torch import save_file
from torch.utils.data import DataLoader, Dataset
from torchvision import transforms
from tqdm import tqdm

MODEL_CONFIGS = {
    "flux.2-klein-base-4b": {
        "hf_repo": "black-forest-labs/FLUX.2-klein-base-4B",
        "guidance_scale": 4.0,
    },
    "flux.2-klein-4b": {
        "hf_repo": "black-forest-labs/FLUX.2-klein-4B",
        "guidance_scale": 1.0,
    },
}


class ImageCaptionDataset(Dataset):
    def __init__(self, image_dir, resolution=1024, num_repeats=1):
        self.image_dir = Path(image_dir)
        self.resolution = resolution
        self.num_repeats = num_repeats
        self.image_extensions = {".jpg", ".jpeg", ".png", ".webp"}
        self.image_files = [f for f in self.image_dir.iterdir() if f.suffix.lower() in self.image_extensions]
        self.transform = transforms.Compose([
            transforms.Resize(resolution, interpolation=transforms.InterpolationMode.LANCZOS),
            transforms.CenterCrop(resolution),
            transforms.ToTensor(),
            transforms.Normalize([0.5], [0.5]),
        ])

    def __len__(self):
        return len(self.image_files) * self.num_repeats

    def __getitem__(self, idx):
        img_idx = idx % len(self.image_files)
        img_path = self.image_files[img_idx]
        image = Image.open(img_path).convert("RGB")
        image = self.transform(image)
        caption_path = img_path.with_suffix(".txt")
        caption = caption_path.read_text().strip() if caption_path.exists() else ""
        return {"pixel_values": image, "caption": caption}


def create_captions(dataset_path, instance_prompt):
    image_extensions = {".jpg", ".jpeg", ".png", ".webp"}
    dataset_path = Path(dataset_path)
    for img_file in dataset_path.iterdir():
        if img_file.suffix.lower() in image_extensions:
            caption_file = img_file.with_suffix(".txt")
            if not caption_file.exists():
                print(f"Creating caption for {img_file.name}")
                caption_file.write_text(instance_prompt)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model-version", required=True, choices=list(MODEL_CONFIGS.keys()))
    parser.add_argument("--dataset-path", required=True)
    parser.add_argument("--instance-prompt", required=True)
    parser.add_argument("--resolution", type=int, default=1024)
    parser.add_argument("--max-train-steps", type=int, default=1500)
    parser.add_argument("--learning-rate", type=float, default=1e-5)
    parser.add_argument("--network-dim", type=int, default=16)
    parser.add_argument("--network-alpha", type=int, default=16)
    parser.add_argument("--num-repeats", type=int, default=10)
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()

    config = MODEL_CONFIGS[args.model_version]
    hf_repo = config["hf_repo"]

    print(f"Model: {args.model_version}")
    print(f"Dataset: {args.dataset_path}")
    print(f"Prompt: {args.instance_prompt}")

    create_captions(args.dataset_path, args.instance_prompt)

    print(f"Loading pipeline from {hf_repo}...")
    pipe = Flux2KleinPipeline.from_pretrained(hf_repo, torch_dtype=torch.bfloat16)
    
    vae = pipe.vae.to("cuda")
    transformer = pipe.transformer.to("cuda")
    transformer.enable_gradient_checkpointing()
    
    print("Pre-encoding all captions...")
    pipe.text_encoder.to("cuda")
    dataset = ImageCaptionDataset(args.dataset_path, resolution=args.resolution, num_repeats=args.num_repeats)
    caption_cache = {}
    for i in range(len(dataset.image_files)):
        img_path = dataset.image_files[i]
        caption_path = img_path.with_suffix(".txt")
        caption = caption_path.read_text().strip() if caption_path.exists() else args.instance_prompt
        if caption not in caption_cache:
            with torch.no_grad():
                prompt_embeds, text_ids = pipe.encode_prompt(prompt=caption, device="cuda", num_images_per_prompt=1)
                caption_cache[caption] = (prompt_embeds.cpu(), text_ids.cpu())
    pipe.text_encoder.to("cpu")
    torch.cuda.empty_cache()
    print(f"Cached {len(caption_cache)} unique captions")

    print("Applying LoRA to transformer...")
    lora_config = LoraConfig(
        r=args.network_dim,
        lora_alpha=args.network_alpha,
        target_modules=["to_q", "to_k", "to_v", "to_out.0"],
        lora_dropout=0.0,
    )
    transformer = get_peft_model(transformer, lora_config)
    transformer.print_trainable_parameters()
    
    vae.requires_grad_(False)

    dataloader = DataLoader(dataset, batch_size=1, shuffle=True, num_workers=2)

    trainable_params = [p for p in transformer.parameters() if p.requires_grad]
    optimizer = torch.optim.AdamW(trainable_params, lr=args.learning_rate)
    lr_scheduler = get_scheduler("cosine", optimizer=optimizer, num_warmup_steps=min(100, args.max_train_steps // 10), num_training_steps=args.max_train_steps)

    os.makedirs(args.output_dir, exist_ok=True)
    global_step = 0
    progress_bar = tqdm(total=args.max_train_steps, desc="Training")
    transformer.train()

    while global_step < args.max_train_steps:
        for batch in dataloader:
            if global_step >= args.max_train_steps:
                break

            pixel_values = batch["pixel_values"].to("cuda", dtype=torch.bfloat16)
            captions = batch["caption"]
            caption = str(captions[0]) if isinstance(captions, (list, tuple)) else str(captions)

            with torch.no_grad():
                latent_dist = vae.encode(pixel_values).latent_dist
                latents = latent_dist.sample()
                
                prompt_embeds, text_ids = caption_cache[caption]
                prompt_embeds = prompt_embeds.to("cuda")
                text_ids = text_ids.to("cuda")

            bsz, c, h, w = latents.shape
            
            # FLUX.2 Klein uses 2x2 patchification: (B, C, H, W) -> (B, C*4, H/2, W/2) -> (B, H/2*W/2, C*4)
            latents_packed = latents.view(bsz, c, h // 2, 2, w // 2, 2)
            latents_packed = latents_packed.permute(0, 1, 3, 5, 2, 4)  # (B, C, 2, 2, H/2, W/2)
            latents_packed = latents_packed.reshape(bsz, c * 4, h // 2, w // 2)  # (B, C*4, H/2, W/2)
            latents_flat = latents_packed.permute(0, 2, 3, 1).reshape(bsz, (h // 2) * (w // 2), c * 4)  # (B, seq, C*4)
            
            # U-shaped timestep distribution: focus on t≈0 and t≈1 where training is hardest
            u = torch.rand(bsz, device="cuda", dtype=torch.bfloat16)
            a = 4.0
            timesteps = (torch.exp(a * u) - 1) / (torch.exp(torch.tensor(a)) - 1)
            timesteps = torch.where(torch.rand(bsz, device="cuda") < 0.5, timesteps, 1 - timesteps)
            timesteps = timesteps.clamp(0.001, 0.999)
            
            noise = torch.randn_like(latents_flat)
            noisy_latents = (1 - timesteps.view(-1, 1, 1)) * latents_flat + timesteps.view(-1, 1, 1) * noise
            
            t_ids = torch.zeros(1, device="cuda", dtype=torch.long)
            h_ids = torch.arange(h // 2, device="cuda", dtype=torch.long)
            w_ids = torch.arange(w // 2, device="cuda", dtype=torch.long)
            l_ids = torch.zeros(1, device="cuda", dtype=torch.long)
            img_ids = torch.stack(torch.meshgrid(t_ids, h_ids, w_ids, l_ids, indexing="ij"), dim=-1)
            img_ids = img_ids.reshape(1, -1, 4).expand(bsz, -1, -1).to(torch.bfloat16)
            
            guidance = torch.full((bsz,), config["guidance_scale"], device="cuda", dtype=torch.bfloat16)

            model_pred = transformer(
                hidden_states=noisy_latents,
                encoder_hidden_states=prompt_embeds,
                timestep=timesteps,
                img_ids=img_ids,
                txt_ids=text_ids,
                guidance=guidance,
                return_dict=False,
            )[0]
            
            target = noise - latents_flat
            loss = torch.nn.functional.mse_loss(model_pred, target, reduction="mean")

            loss.backward()
            torch.nn.utils.clip_grad_norm_(trainable_params, 1.0)
            optimizer.step()
            lr_scheduler.step()
            optimizer.zero_grad()

            global_step += 1
            progress_bar.update(1)
            progress_bar.set_postfix(loss=loss.item())

            if global_step % max(100, args.max_train_steps // 5) == 0:
                save_path = Path(args.output_dir) / f"flux2_klein_lora_step{global_step}.safetensors"
                lora_state_dict = {k: v for k, v in transformer.state_dict().items() if "lora" in k.lower()}
                save_file(lora_state_dict, str(save_path))
                print(f"\nCheckpoint: {save_path}")

    progress_bar.close()

    final_path = Path(args.output_dir) / "flux2_klein_lora.safetensors"
    lora_state_dict = {k: v for k, v in transformer.state_dict().items() if "lora" in k.lower()}
    metadata = {
        "model_version": args.model_version,
        "network_dim": str(args.network_dim),
        "network_alpha": str(args.network_alpha),
        "instance_prompt": args.instance_prompt,
        "resolution": str(args.resolution),
    }
    save_file(lora_state_dict, str(final_path), metadata=metadata)
    print(f"\nTraining complete! LoRA saved to {final_path}")


if __name__ == "__main__":
    main()
