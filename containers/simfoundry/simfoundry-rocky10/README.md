# SimFoundry on Rocky Linux 10 (CUDA 12.8)

The image behind the [SimFoundry real-to-sim](../README.md) sample.
It holds [SimFoundry](https://github.com/NVlabs/SimFoundry)'s four core conda environments,
built by SimFoundry's own install scripts. Together they run the reconstruction (A),
augmentation (B) and application (C) pipelines. The optional auto-background environments
(`void`, `nerfstudio_simfoundry`, `3dgrut`) and the articulation environments are not included.

The build doesn't need a GPU. A Deadline Cloud GPU worker runs the image through the Docker queue
environment, and `verify-simfoundry --isaac` passes there. The [job sample](../README.md) runs
pipeline A's depth stages and OmniGibson rollouts in it. The stages that need Gemini have not been
run in the image.

## What's in the image

| Path | Contents |
|---|---|
| `/opt/conda/envs/simfoundry` | Runs most stages and the Gemini calls, with OmniGibson 3.8.0 and Isaac Sim 5.1 |
| `/opt/conda/envs/hunyuan` | Hunyuan3D-2.1 mesh generation, for A stage 7 and B stage 3 |
| `/opt/conda/envs/any6d` | Any6D and FoundationPose pose matching, for A stage 8 |
| `/opt/conda/envs/da3` | Depth Anything 3, for A stage 2 |
| `/opt/SimFoundry` | SimFoundry at a pinned commit, with every pinned dependency checked out under `deps/` |
| `/opt/SimFoundry/checkpoints`, `deps/*/` | The public FoundationStereo, FoundationPose, SAM 2.1, Depth Pro and RealESRGAN checkpoints, unless `BAKE_CHECKPOINTS=0` |
| `/usr/local/cuda-12.8` | The CUDA 12.8.1 toolkit, at the path the installers expect |
| `/usr/local/bin/verify-simfoundry` | The GPU checks a build can't run |
| `/simfoundry-refs.txt` | The SimFoundry commit, every `deps/` commit, the CUDA arch list, the PyPI cutoff and the Isaac Sim and torch versions |

SimFoundry finds `Data/`, `checkpoints/` and `deps/` relative to its own package, so the
checkout has to stay at `/opt/SimFoundry`.

## Why Rocky Linux 10

Isaac Sim 5.1 links `hypot@GLIBC_2.35` (in `omni.usd.libs` and `lula`). Rocky Linux 9 has glibc
2.34 and Rocky Linux 8 has 2.28, so Rocky Linux 10, with glibc 2.39, is the one Rocky release
that can load it.

NVIDIA publishes Rocky Linux 10 images for CUDA 13 alone, and its Rocky Linux 10 package
repository has no CUDA 12 toolkit. The image starts from `nvidia/cuda:13.0.1-base-rockylinux10`
and installs the CUDA 12.8.1 toolkit from NVIDIA's runfile, which the build checks against
NVIDIA's published md5. `NVIDIA_REQUIRE_CUDA` is reset to `cuda>=12.8`, since nothing in the
image uses CUDA 13.

## Build

The build takes about 2 hours and doesn't need a GPU. The image is 103 GB, or 49.4 GiB compressed in
Amazon ECR. Its largest layer is the `simfoundry` env at 35.9 GB, under ECR's 52,000 MiB layer
limit. Leave at least 250 GB free for Docker.

```console
docker build --platform linux/amd64 -t simfoundry:9e34ebe-rocky10 .
```

| Build argument | Default | Meaning |
|---|---|---|
| `SIMFOUNDRY_REF` | `9e34ebe...` | The SimFoundry commit to build. The installers pin everything they clone |
| `PYPI_CUTOFF` | `2026-08-27T02:13:06Z` | Install PyPI packages as they were at this time. Set it to the commit time of `SIMFOUNDRY_REF` |
| `CUDA_ARCH_LIST` | `8.6;8.9` | GPU architectures to compile CUDA extensions for: A10G (g5), L4 (g6) and L40S (g6e) |
| `MAX_JOBS` | `4` | Parallel compile jobs. Each can take 8 GB of RAM or more |
| `BAKE_CHECKPOINTS` | `1` | Download the public checkpoints into the image. `0` skips them |
| `MINIFORGE_VERSION` | `26.9.4-2` | The Miniforge release that provides `mamba` |

Time per step on a 16 vCPU, 64 GB build host:

| Step | Time |
|---|---|
| `simfoundry` env, with OmniGibson and Isaac Sim | 27 min |
| `hunyuan` env | 9 min |
| `any6d` env | 22 min |
| `da3` env | 47 min |
| Checkpoints | 1 min |

The build changes SimFoundry's installers in four places, so they run unattended on a host with no GPU:

- **GPU architectures.** The installers read compute capabilities from `nvidia-smi`. The build
  passes `CUDA_ARCH_LIST` instead. A GPU outside the list fails at its first kernel launch with
  `no kernel image is available`. `verify-simfoundry` checks for this before anything else.
- **FAISS check.** Upstream's check runs a search on the GPU. During the build a stand-in checks
  that FAISS has its GPU symbols. The upstream file is restored afterwards, and the build
  fails if the SimFoundry checkout differs from its commit.
- **PyPI versions.** Most of the installers' PyPI requirements are unpinned. Without a cutoff,
  the build picks up pyarrow 26, which refuses the numpy 1.26 that the `simfoundry` env pins, and
  OmniGibson fails to import. `scripts/pypi_cutoff_proxy.py` serves a local PyPI index that
  hides files uploaded after `PYPI_CUTOFF`. The PyTorch and NVIDIA indexes are unaffected.
- **evdev.** evdev generates its constants from `/usr/include`, but compiles against conda's
  older kernel headers. Rocky Linux 10's headers define constants that conda's don't, so the
  build installs evdev with the system gcc before SimFoundry's installer runs.

Each env is its own layer. A failure rebuilds from that env onward. The checkpoint step
downloads from Google Drive through `gdown`, which is rate-limited. If it fails, run the build
again.

## Run on Deadline Cloud

You need a Linux service-managed fleet with the Docker software add-on. You also need a queue
with the Docker default queue environment, and a queue role that can pull from Amazon ECR. See
[Container support for fleets](https://docs.aws.amazon.com/deadline-cloud/latest/userguide/fleet-container-support.html).

**Pin the fleet's GPU runtime to `grid:r580`.** Isaac Sim 5.1 segfaults in `librtx.scenedb` at
startup on 595-series drivers ([isaac-sim/IsaacSim#677](https://github.com/isaac-sim/IsaacSim/issues/677)).
The `latest` runtime gave driver 595.91.07 in November 2026, and Isaac Sim crashed on both an
A10G and an L4. With `grid:r580` the worker got driver 580.178.04, and Isaac Sim rendered.
Changing the runtime doesn't replace workers that are already running.

The fleet configuration used for testing:

```json
{
  "serviceManagedEc2": {
    "instanceCapabilities": {
      "vCpuCount": {"min": 8, "max": 16},
      "memoryMiB": {"min": 65536, "max": 131072},
      "osFamily": "LINUX",
      "cpuArchitectureType": "x86_64",
      "rootEbsVolume": {"sizeGiB": 500, "iops": 6000, "throughputMiB": 500},
      "acceleratorCapabilities": {
        "selections": [
          {"name": "a10g", "runtime": "grid:r580"},
          {"name": "l4", "runtime": "grid:r580"}
        ],
        "count": {"min": 1, "max": 1}
      },
      "softwareAddOns": [{"name": "docker"}]
    },
    "instanceMarketOptions": {"type": "on-demand"}
  }
}
```

The 500 GiB root volume holds the 103 GB image after it is pulled and unpacked. The A10G and
L4 have 24 GiB, so pass `s7_mesh.low_vram=true` to pipeline A.

Use workers with at least 64 GiB of memory. Service-managed fleet workers use strict memory
accounting (`vm.overcommit_memory=2`), and Isaac Sim commits enough memory that on a 32 GiB worker
it can't start another process. The sample's rollout video failed there when ffmpeg started,
with `OSError: [Errno 12] Cannot allocate memory` and 19 GB still available. The
[overcommit override](../../../host_configuration_scripts/overcommit_override_for_smf/) host
configuration script is an alternative that we haven't tested.

## Test on a GPU host

```console
docker run --rm --gpus all simfoundry:9e34ebe-rocky10 verify-simfoundry --isaac
```

| Check | Passes when |
|---|---|
| GPU architecture | The GPU's compute capability is in the image's `CUDA_ARCH_LIST` |
| CUDA in each env | torch runs a kernel on the GPU in all four envs |
| FAISS GPU search | Upstream's FAISS check passes in `simfoundry`, `any6d` and `da3` |
| `--isaac` | Isaac Sim boots headless and renders a lit cube to a frame that isn't black |

To run pipeline A on one of SimFoundry's example videos, writing to `./Data`:

```console
mkdir -p Data
docker run --rm --gpus all -v "$PWD/Data:/data" \
  -e GEMINI_API_KEY -e HF_TOKEN \
  simfoundry:9e34ebe-rocky10 \
  bash /opt/SimFoundry/scripts/pipeline/A_reconstruction/run.sh \
    --root-dir /data --scene-name fruits \
    --video-fpath /opt/SimFoundry/docs/assets/example_videos/Fruits.mp4 \
    -- s7_mesh.low_vram=true
```

## Credentials and caches

No credentials are in the image. The pipeline needs two at run time:

| Service | Used by | Pass as |
|---|---|---|
| Gemini | A stages 3, 5, 6 and 10, and all of B | `GEMINI_API_KEY`, or `GCLOUD_PROJECT` with Vertex AI credentials |
| Hugging Face | Gated SAM3, RMBG-2.0 and DINOv3 weights | `HF_TOKEN`, from an account that has been granted access |

The Deadline Cloud Docker queue environment forwards no environment variables except known
license variables, so a job has to fetch these itself, such as from AWS Secrets Manager.

Hugging Face weights download on first use into `HF_HOME`, which is
`/opt/simfoundry-cache/huggingface`. Mount persistent storage there so each run doesn't
download them again.

## Licences

Building this image accepts the NVIDIA Omniverse License Agreement, which covers Isaac Sim, and
the BEHAVIOR-1K dataset terms. SimFoundry's installers accept both for you. Some baked-in
components, such as the FoundationPose, FoundationStereo and Hunyuan3D-2.1 weights, are licensed
for non-commercial or research use, and Hunyuan3D-2.1 doesn't grant rights in the EU, the UK or
South Korea. Keep the image in a private repository. Read SimFoundry's
[THIRD_PARTY_LICENSES.md](https://github.com/NVlabs/SimFoundry/blob/main/THIRD_PARTY_LICENSES.md)
before you use it.

## Tested with

SimFoundry `9e34ebe`, built on a 16 vCPU `linux/amd64` host with no GPU, in November 2026.
`verify-simfoundry --isaac` passed on a Deadline Cloud service-managed fleet with the Docker
software add-on: an NVIDIA L4 (g6) with the `grid:r580` runtime and driver 580.178.04. Isaac
Sim rendered a 320x240 frame with every pixel lit. On an A10G (g5) with the `latest` runtime and
driver 595.91.07, the CUDA and FAISS checks passed and Isaac Sim crashed. Deadline Cloud CLI
0.60.11.
