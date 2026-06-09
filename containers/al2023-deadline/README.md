# AL2023 Deadline Cloud worker-equivalent image

This Dockerfile replicates the package set of an April 2026 snapshot of the
AWS Deadline Cloud service-managed fleet (SMF) worker AMI on top of the base
Amazon Linux 2023 image. It is a point-in-time capture — the actual worker AMI
may drift as packages are added or updated.

## Use cases

- Build and test [conda packages](../../conda_recipes/) with the same GLIBC
  version, system libraries, and runtime environment as real workers.
- Reproduce worker-side build or runtime failures locally.
- Validate that your software dependencies are satisfied by the worker
  environment before submitting jobs.

## What's included

The image installs packages in layered groups matching the worker AMI:

| Layer | Contents |
|-------|----------|
| Core system tools | `jq`, `git`, `wget`, `unzip`, `vim`, `sudo`, `rsync`, … |
| Build toolchain | GCC, G++, `binutils`, `kernel-headers`, `glibc-devel`, `zlib-devel` |
| X11 / Mesa / OpenGL | Headless rendering dependencies (`libX11`, `mesa-libGL`, `libglvnd`, …) |
| Image / media libs | `libjpeg-turbo`, `libpng`, `libtiff`, `libwebp` |
| Networking / NFS / security | NFS utils, NSS, SSSD, `openssh-clients`, `iptables-nft` |
| Python 3.11 | `python3.11`, `pip`, `setuptools` |
| Docker / containerd | For container-in-container workflows (host socket mount or `--privileged`) |
| Misc | AWS CLI v2, Boost, jemalloc, TBB, and other libraries present on the worker |

## Building the image

```bash
docker build -f Dockerfile.worker-equivalent -t al2023-deadline:latest .
```

## Running a container

```bash
# Interactive shell
docker run --rm -it al2023-deadline:latest

# Build a conda package inside the container
docker run --rm -v "$PWD":/work -w /work al2023-deadline:latest \
    bash -c "pip3.11 install conda-build && conda build my-recipe/"
```

## GPU support

For NVIDIA GPU support, add the NVIDIA container toolkit repository before
building:

```dockerfile
RUN dnf config-manager --add-repo \
    https://nvidia.github.io/libnvidia-container/stable/rpm/nvidia-container-toolkit.repo \
 && dnf install -y nvidia-container-toolkit
```

Then run the container with `--gpus all`:

```bash
docker run --rm --gpus all al2023-deadline:latest nvidia-smi
```

## Limitations

- This is a **point-in-time snapshot** (April 2026). The actual SMF worker AMI
  may have newer or additional packages.
- Docker-in-Docker is not enabled by default. Mount the host Docker socket or
  use `--privileged` if you need it.
