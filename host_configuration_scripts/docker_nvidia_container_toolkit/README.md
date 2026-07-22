# Docker and NVIDIA Container Toolkit

Install Docker and the NVIDIA Container Toolkit on Linux service managed fleet workers, enabling GPU-accelerated container workloads.

## Why Docker on Deadline Cloud Workers?

Many GPU workloads are distributed as container images, such as ComfyUI, Stable Diffusion inference servers, and custom ML pipelines. Running these on Deadline Cloud workers requires Docker with GPU passthrough. This host config script sets everything up so jobs can `docker run` GPU containers directly.

Containers also provide a clean way to package complex dependency stacks (CUDA, Python, application-specific libraries) without polluting the host or conflicting with other jobs on the same fleet.

## Installation steps

1. Installs Docker via `dnf` and starts the service
2. Adds `job-user` to the `docker` group so jobs can run containers without sudo
3. Installs the NVIDIA Container Toolkit from the official repository
4. Configures the Docker daemon to use the NVIDIA runtime
5. Generates the CDI (Container Device Interface) spec for GPU access
6. Restarts Docker and verifies the setup

## Prerequisites

- The fleet AMI must have NVIDIA GPU drivers already installed (Deadline Cloud GPU AMIs include these)
- The fleet must use a GPU instance type (e.g. g6.xlarge, g6e.xlarge, p4d.24xlarge)

## Usage

1. Open the AWS Deadline Cloud console
2. Navigate to your fleet
3. Go to the "Host configuration" section
4. Copy and paste the contents of `linux.sh` into the script field
5. Save the configuration

New fleet instances will automatically install Docker and the NVIDIA Container Toolkit on startup.

## Example: Running a GPU Container from a Job

Once the host config has run, jobs can launch GPU containers. This example runs ComfyUI with GPU access and host networking, passing through license environment variables:

```bash
docker run --rm \
  --runtime=nvidia \
  --gpus all \
  --network host \
  -e ADSKFLEX_LICENSE_FILE \
  -e FLEXLM_TIMEOUT \
  -e foundry_LICENSE \
  -e PIXAR_LICENSE_FILE \
  -e g_licenseServerRLM \
  -e redshift_LICENSE \
  -e SESI_LMHOST \
  -e VRAY_AUTH_CLIENT_FILE_PATH \
  -e VRAY_AUTH_CLIENT_SETTINGS \
  your-image:latest
```

Key flags:
- `--runtime=nvidia --gpus all`: passes the GPU through to the container
- `--network host`: uses the host network stack (required for license servers and service discovery)
- `-e VAR`: passes the environment variable from the worker into the container (when used without `=value`, Docker forwards the host's current value)

### License Environment Variables

Deadline Cloud queue environments typically set license server endpoints as environment variables. Using `-e` without a value forwards whatever the worker has set. Common variables:

| Variable | Product |
|----------|---------|
| `ADSKFLEX_LICENSE_FILE` | Autodesk (Maya, 3ds Max, etc.) |
| `FLEXLM_TIMEOUT` | FlexLM license timeout |
| `foundry_LICENSE` | Foundry (Nuke, Mari, etc.) |
| `PIXAR_LICENSE_FILE` | Pixar RenderMan |
| `g_licenseServerRLM` | Maxon Cinema 4D |
| `redshift_LICENSE` | Maxon Redshift / Red Giant |
| `SESI_LMHOST` | SideFX Houdini |
| `VRAY_AUTH_CLIENT_FILE_PATH` | Chaos V-Ray auth client file |
| `VRAY_AUTH_CLIENT_SETTINGS` | Chaos V-Ray license endpoint |
