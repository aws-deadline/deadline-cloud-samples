# Enable Swap on Service Managed Fleet Workers

Create and enable a swap file on Linux service managed fleet workers. Useful for memory-intensive workloads jobs that temporarily exceed physical RAM. For example ComfyUI.

## Why Swap?

Some workloads need to memory-map large files through CPU RAM before loading them onto the GPU. For example, loading a 16GB diffusion model on a g6.xlarge instance (16GB RAM) can OOM-kill the process without swap. A swap file provides overflow capacity so these loads succeed.

## What It Does

1. Creates a 32GB swap file at `/swapfile` (skips if one already exists)
2. Enables the swap file immediately
3. Adds an `/etc/fstab` entry so swap persists across reboots

## Configuration

Edit `linux.sh` to change the swap size:

```bash
SWAP_SIZE="32G"  # Adjust as needed
```

## Usage

1. Open the AWS Deadline Cloud console
2. Navigate to your fleet
3. Go to the "Host configuration" section
4. Copy and paste the contents of `linux.sh` into the script field
5. Save the configuration

New fleet instances will automatically create and enable swap on startup.
