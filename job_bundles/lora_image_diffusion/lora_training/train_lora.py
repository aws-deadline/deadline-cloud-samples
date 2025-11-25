import argparse
import os
import torch
from diffusers import (
    AutoencoderKL,
    DDPMScheduler,
    UNet2DConditionModel,
)
from diffusers.optimization import get_scheduler
from transformers import CLIPTextModel, CLIPTokenizer
from peft import LoraConfig, get_peft_model
from accelerate import Accelerator
from torch.utils.data import Dataset, DataLoader
from PIL import Image
from pathlib import Path

# Set cache directory
cache_dir = os.path.expanduser("~/.models/huggingface")
os.makedirs(cache_dir, exist_ok=True)
os.environ["HF_HOME"] = cache_dir
os.environ["TRANSFORMERS_CACHE"] = cache_dir
os.environ["HF_DATASETS_CACHE"] = cache_dir


class SimpleDataset(Dataset):
    def __init__(self, data_dir, tokenizer, prompt, resolution):
        self.data_dir = Path(data_dir)
        self.images = (
            list(self.data_dir.glob("*.jpg"))
            + list(self.data_dir.glob("*.png"))
            + list(self.data_dir.glob("*.jpeg"))
        )
        self.tokenizer = tokenizer
        self.prompt = prompt
        self.resolution = resolution

    def __len__(self):
        return len(self.images)

    def __getitem__(self, idx):
        image = Image.open(self.images[idx]).convert("RGB")
        image = image.resize((self.resolution, self.resolution))
        image = (
            torch.tensor(list(image.getdata()))
            .reshape(self.resolution, self.resolution, 3)
            .float()
            / 127.5
            - 1
        )
        image = image.permute(2, 0, 1)

        tokens = self.tokenizer(
            self.prompt,
            padding="max_length",
            max_length=self.tokenizer.model_max_length,
            truncation=True,
            return_tensors="pt",
        )
        return {"pixel_values": image, "input_ids": tokens.input_ids[0]}


parser = argparse.ArgumentParser()
parser.add_argument("--model-name", required=True)
parser.add_argument("--dataset-path", required=True)
parser.add_argument("--instance-prompt", required=True)
parser.add_argument("--resolution", type=int, required=True)
parser.add_argument("--max-train-steps", type=int, required=True)
parser.add_argument("--learning-rate", type=float, required=True)
parser.add_argument("--lora-rank", type=int, required=True)
parser.add_argument("--output-dir", required=True)
parser.add_argument("--lora-alpha", type=int, required=True)
args = parser.parse_args()

accelerator = Accelerator(gradient_accumulation_steps=4)
print(f"Using device: {accelerator.device}")

print(f"Downloading model components from {args.model_name}...")
tokenizer = CLIPTokenizer.from_pretrained(args.model_name, subfolder="tokenizer")
text_encoder = CLIPTextModel.from_pretrained(args.model_name, subfolder="text_encoder")
vae = AutoencoderKL.from_pretrained(args.model_name, subfolder="vae")
unet = UNet2DConditionModel.from_pretrained(args.model_name, subfolder="unet")
print("Model download complete")

vae.requires_grad_(False)
text_encoder.requires_grad_(False)

lora_config = LoraConfig(
    r=args.lora_rank, lora_alpha=args.lora_alpha, target_modules=["to_k", "to_q", "to_v", "to_out.0"]
)
unet = get_peft_model(unet, lora_config)

optimizer = torch.optim.AdamW(unet.parameters(), lr=args.learning_rate)
noise_scheduler = DDPMScheduler.from_pretrained(args.model_name, subfolder="scheduler")

dataset = SimpleDataset(args.dataset_path, tokenizer, args.instance_prompt, args.resolution)
dataloader = DataLoader(dataset, batch_size=1, shuffle=True)

lr_scheduler = get_scheduler(
    "constant",
    optimizer=optimizer,
    num_warmup_steps=0,
    num_training_steps=args.max_train_steps,
)

unet, optimizer, dataloader, lr_scheduler = accelerator.prepare(
    unet, optimizer, dataloader, lr_scheduler
)
vae.to(accelerator.device)
text_encoder.to(accelerator.device)

for step in range(args.max_train_steps):
    batch = next(iter(dataloader))
    with torch.no_grad():
        latents = (
            vae.encode(
                batch["pixel_values"].to(accelerator.device)
            ).latent_dist.sample()
            * 0.18215
        )
        encoder_hidden_states = text_encoder(batch["input_ids"].to(accelerator.device))[
            0
        ]

    noise = torch.randn_like(latents)
    timesteps = torch.randint(
        0,
        noise_scheduler.config.num_train_timesteps,
        (latents.shape[0],),
        device=latents.device,
    ).long()
    noisy_latents = noise_scheduler.add_noise(latents, noise, timesteps)

    model_pred = unet(noisy_latents, timesteps, encoder_hidden_states).sample
    loss = torch.nn.functional.mse_loss(model_pred, noise)

    accelerator.backward(loss)
    optimizer.step()
    lr_scheduler.step()
    optimizer.zero_grad()

    if step % 25 == 0:
        print(f"Step {step}/{args.max_train_steps}, Loss: {loss.item():.4f}")

accelerator.wait_for_everyone()
if accelerator.is_main_process:
    import os
    from safetensors.torch import save_file

    unet = accelerator.unwrap_model(unet)
    from peft.utils import get_peft_model_state_dict

    unet_lora_state_dict = get_peft_model_state_dict(unet)
    print(f"Saving LoRA keys (first 3): {list(unet_lora_state_dict.keys())[:3]}")
    os.makedirs(args.output_dir, exist_ok=True)
    output_filename = "pytorch_lora_weights.safetensors"
    output_path = os.path.join(args.output_dir, output_filename)

    # Embed training metadata in the safetensors file
    metadata = {
        "base_model": args.model_name,
        "lora_rank": str(args.lora_rank),
        "lora_alpha": str(args.lora_alpha),
        "instance_prompt": args.instance_prompt,
    }
    save_file(unet_lora_state_dict, output_path, metadata=metadata)
    print(f"Training complete! LoRA weights saved to {output_path}")
    print(f"Embedded metadata: {metadata}")
