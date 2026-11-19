# MuJoCo 4.0 on Rocky Linux 9 for NVIDIA GPUs

The image behind the GPU example of the [MuJoCo 4.0 feature sweeps](../README.md#run-on-a-gpu-fleet).
It runs the same `mj4-sweep` and `mj4-summarize` commands as the CPU image,
[`../mujoco4-rocky9/`](../mujoco4-rocky9/), and renders on the worker's NVIDIA GPU through EGL.

The image is about 1.4 GB, or 475 MB compressed in Amazon ECR.

## How it differs from the CPU image

| | CPU image | GPU image |
|---|---|---|
| Base | `rockylinux:9` | `nvidia/cuda:13.0.3-base-rockylinux9` |
| `NVIDIA_DRIVER_CAPABILITIES` | not set | `graphics,compute,utility` |
| `MJ4_RENDERER` | not set: `--renderer` defaults to `any` | `gpu`: a task fails if it renders on Mesa |
| MuJoCo, Python packages, models, commands | same | same |

The NVIDIA driver isn't in the image. When the container starts with `--gpus all`, the host's NVIDIA
container runtime mounts the driver libraries, including `libEGL_nvidia` and its glvnd vendor file.
The runtime only mounts the libraries for the capabilities in `NVIDIA_DRIVER_CAPABILITIES`. The CUDA
base image lists `compute,utility`, and EGL rendering also needs `graphics`, so this image adds it.

The CUDA 13.0 base needs NVIDIA driver 580 or later. The tested workers ran driver 595. The sweeps
don't call CUDA. The base image is there for the NVIDIA container settings and for jobs you add later
that do use CUDA.

## Build

Build from `containers/mujoco-4`, one level up. The image copies its commands from
`mujoco4-rocky9/scripts/`, so both images run the same code.

```console
cd containers/mujoco-4
docker build --platform linux/amd64 -f mujoco4-rocky9-gpu/Dockerfile -t mujoco4-rocky9-gpu:4.0.0 .
```

The build runs a short point of each sweep with `--renderer any`, because a build host often has no
GPU. Mesa stays in the image for that check. In a job, `MJ4_RENDERER=gpu` makes `mj4-sweep` fail
instead of using it.

## Test on a GPU host

```console
docker run --rm --gpus all mujoco4-rocky9-gpu:4.0.0 nvidia-smi -L
mkdir -p output
docker run --rm --gpus all --user "$(id -u):$(id -g)" -e HOME=/tmp -v "$PWD/output:/output" \
  mujoco4-rocky9-gpu:4.0.0 \
  mj4-sweep torsion --yield-strain 0.05 --width 1920 --height 1080 --out-dir /output/yield0.05 --label yield0.05
```

The second command prints the GL renderer, such as `NVIDIA A10G/PCIe/SSE2`. Its `metrics.json`
records it under `render.gl_renderer`. On a host without a GPU, the same command exits non-zero with
`--renderer gpu, but EGL picked the CPU rasterizer`. Pass `--renderer any` to run it on Mesa anyway.

For how `mj4-sweep` applies each parameter to the compiled model, see
[`../mujoco4-rocky9/README.md`](../mujoco4-rocky9/README.md#how-mj4-sweep-applies-parameters).
