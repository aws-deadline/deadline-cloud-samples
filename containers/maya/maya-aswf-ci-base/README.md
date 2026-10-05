# Maya container for AWS Deadline Cloud

This example builds a Docker image that packages Autodesk Maya 2027 with the [deadline-cloud-for-maya](https://github.com/aws-deadline/deadline-cloud-for-maya) adaptor and, optionally, the Arnold, V-Ray and Redshift renderers for rendering on AWS Deadline Cloud. It mirrors the [Blender container sample](../../blender/blender-aswf-ci-base/) with one important difference: Maya and the renderers are commercial software, so you supply your own licensed installers and the image is built from them locally.

## Use cases

- Render Maya scenes with the `Render` command line or the `maya-openjd` adaptor on Deadline Cloud service-managed fleets, with the exact Maya, Arnold, V-Ray and Redshift builds you qualified.
- Bake studio Maya modules, plug-ins and scripts into the image at build time.
- Keep one Dockerfile for every variant, from Maya alone to Maya with all three renderers. The variants share the same Maya layer.

## What's included

| Component | Description |
|-----------|-------------|
| Base image | `aswf/ci-base:2026` (Rocky Linux 8 with CUDA 12.9 and VFX Platform 2026, an industry standard that matches Maya's Linux build target) |
| Maya | Maya 2027 for Linux, installed from your Autodesk Account download, with the ADP SDK and legacy thin-client licensing configured |
| Adaptor | `deadline-cloud-for-maya`: the OpenJD adaptor that Deadline Cloud invokes to drive renders (`maya-openjd`, `MayaAdaptor`) |
| Arnold (optional) | Arnold for Maya (MtoA) from the bundle inside the Maya download, or a newer standalone MtoA installer; includes `kick` |
| V-Ray (optional) | V-Ray for Maya, Linux rhel8 build, from your Chaos download; includes the `vray` standalone renderer |
| Redshift (optional) | Redshift and its Maya plug-in from your Maxon download; includes `redshiftCmdLine` |
| Plugins | Optional Maya modules, plug-ins and scripts placed in a plugins directory are installed at build time |
| `build.sh` | Validates the installers in the directory you give it and runs `docker build` with the right build contexts and arguments |
| CloudFormation | `cloudformation.yaml`: deploys the queue, fleet, and queue environment in one stack |

## Project structure

```
maya-aswf-ci-base/
├── Dockerfile
├── build.sh                      # Build (and optionally push) the image
├── cloudformation.yaml           # One-click deploy (queue + fleet + queue env)
├── scripts/
│   ├── common.sh                 # Installer file patterns and helpers shared by build.sh and the image
│   ├── install_maya.sh           # Maya RPM, ADP SDK, thin-client licensing, launchers
│   ├── install_arnold.sh         # MtoA (no-op unless WITH_ARNOLD=1)
│   ├── install_vray.sh           # V-Ray for Maya (no-op unless WITH_VRAY=1)
│   ├── install_redshift.sh       # Redshift (no-op unless WITH_REDSHIFT=1)
│   ├── install_plugins.sh        # Copies the plugins directory into the image
│   └── verify.sh                 # License-free build-time checks, including an ldd scan
├── installers/                   # Put your downloaded installers here (ignored by git)
└── plugins/                      # Optional Maya modules, plug-ins and scripts (ignored by git)
```

## Prerequisites

- **Docker 23 or later with BuildKit** ([Get Docker](https://docs.docker.com/get-docker/)). The build uses `# syntax=docker/dockerfile:1` features: named build contexts and bind mounts.
- **About 35 GB of free disk space** for the full image with all three renderers, plus temporary space for the Docker build cache (see [Image size](#image-size)).
- **AWS CLI** configured with credentials ([Install AWS CLI](https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html))
- **An ECR repository** to store the built image ([Creating an ECR repository](https://docs.aws.amazon.com/AmazonECR/latest/userguide/repository-create.html))
- **An S3 bucket** for job attachments ([Job attachments storage](https://docs.aws.amazon.com/deadline-cloud/latest/userguide/storage-job-attachments.html))
- **A Deadline Cloud farm** ([Getting started with Deadline Cloud](https://docs.aws.amazon.com/deadline-cloud/latest/userguide/getting-started.html))
- **IAM roles** for the queue and fleet ([Deadline Cloud IAM roles](https://docs.aws.amazon.com/deadline-cloud/latest/userguide/security-iam.html))
- **Your own installers**, described next.

### Bring your own installers

Unlike Blender, Maya, Arnold, V-Ray and Redshift are **not freely redistributable**. This sample does not download anything from Autodesk, Chaos or Maxon. You download the Linux installers with your own vendor accounts and point `build.sh` at the directory that holds them:

| Component | Where to download | Expected file name | Required |
|-----------|-------------------|--------------------|----------|
| Maya 2027 for Linux | [Autodesk Account](https://manage.autodesk.com/) (Products and Services) | `Autodesk_Maya_2027*_Linux_64bit.tgz` | Yes |
| Arnold for Maya (MtoA) | [Autodesk Account](https://manage.autodesk.com/) (Arnold is an entitlement of the Maya subscription) | `MtoA-*-linux-2027.run` | No. The Maya archive bundles an MtoA release that `--arnold` installs when no `.run` is supplied |
| V-Ray for Maya 2027 | [Chaos downloads](https://download.chaos.com/) (Linux, rhel8 build) | `vray_*_maya2027*` (a Linux executable with no file extension) | Only with `--vray` |
| Redshift | [Maxon downloads](https://www.maxon.net/en/downloads) (Linux) | `redshift_*_linux_x64.run` | Only with `--redshift` |

`build.sh` looks for these files directly in the installers directory or exactly one subdirectory deep, so a layout like the following works:

```
~/maya-installers/
├── Maya2027/Autodesk_Maya_2027_Linux_64bit.tgz
├── MtoA/MtoA-5.6.3-linux-2027.run
├── Vray/vray_74004_maya2027_dr2_rhel8
└── Redshift/redshift_2026.8.1_2741261432_linux_x64.run
```

Handle the installers and the resulting image as licensed material:

- **Never commit installers.** The sample's `.gitignore` excludes `installers/` and `plugins/` (apart from their `.gitkeep` placeholders), and the repository's root `.gitignore` excludes `*.tgz`, `*.run` and `*.zip`.
- **Never push an image that contains Maya or a renderer to a public registry.** Push only to a private Amazon ECR repository in your own account.
- The installers are never copied into an image layer. They are bind mounted read-only into the build while each component installs. The image only contains the installed software.
- You are responsible for complying with the Autodesk, Chaos and Maxon license terms for the software you install.

## Building the image

```bash
# Maya and the adaptor only (Maya software renderer) -> maya-aswf:2027
./build.sh --installers-dir ~/maya-installers

# Maya + Arnold -> maya-aswf:2027-arnold
./build.sh --installers-dir ~/maya-installers --arnold

# Maya + Arnold + V-Ray + Redshift -> maya-aswf:2027-arnold-vray-redshift
./build.sh --installers-dir ~/maya-installers --all-renderers

# Bake in studio modules, plug-ins and scripts (see "Adding plugins")
./build.sh --installers-dir ~/maya-installers --all-renderers --plugins-dir ~/maya-plugins

# Build, then tag and push to ECR in one go
./build.sh --installers-dir ~/maya-installers --all-renderers \
    --push 123456789012.dkr.ecr.us-west-2.amazonaws.com/maya-aswf-ci-base

# Show the docker command without building
./build.sh --installers-dir ~/maya-installers --all-renderers --dry-run
```

`build.sh` checks that Docker with BuildKit is available and that the installers for the requested components exist before it starts the build, prints which file it will use for each component, and then runs `docker build` with the `installers` and `plugins` build contexts and the `WITH_ARNOLD`, `WITH_VRAY` and `WITH_REDSHIFT` build arguments. Run `./build.sh --help` for all options, including `--maya-version`, `--vfx-platform-year`, `--adaptor-version`, `--tag` and `--no-cache`.

Each renderer is installed in its own layer and each install script is a no-op when its renderer is not requested, so the Maya layer (the slow one) is shared between variants. The default tag encodes the variant: `maya-aswf:<maya version>` followed by `-arnold`, `-vray` and `-redshift` for each renderer that is included, in that order.

The Dockerfile needs the two named build contexts, so a plain `docker build .` does not work. Use `build.sh` or copy the command it prints with `--dry-run`.

### Image size

Approximate sizes of the image layers on disk (`docker history`). Measured values for the tested configuration are in [Tested with](#tested-with).

| Layer | Approximate size |
|-------|------------------|
| `aswf/ci-base:2026` | 9.4 GB |
| System libraries for Maya and the renderers | 0.2 GB |
| Maya 2027 + adaptor | 3.3 GB |
| Arnold (MtoA) | 0.9 GB |
| V-Ray for Maya | 2.9 GB |
| Redshift | 2.0 GB |

The install scripts leave out the Maya `Examples` and documentation and strip the debug information that the installers include (`strip --strip-debug`). Maya alone carries about 4.5 GB of it, and removing it roughly halves the Maya layer without changing how anything runs. The Autodesk licensing libraries are exempt because their loaders check the files (see [Troubleshooting](#troubleshooting)). The images are about half this size once compressed in ECR.

BuildKit also keeps a copy of the `installers` build context in its cache after the first build. Reclaim that space with `docker builder prune` once the image is pushed.

### Push to ECR

`build.sh --push <repository URI>` logs in to ECR with the AWS CLI, tags the image as `<repository URI>:<tag>` and pushes it. The equivalent manual steps are:

```bash
ECR_REPO=<your-account-id>.dkr.ecr.<region>.amazonaws.com/<your-repo-name>
ECR_REGISTRY=$(echo $ECR_REPO | cut -d/ -f1)
aws ecr get-login-password --region <region> | docker login --username AWS --password-stdin $ECR_REGISTRY
docker tag maya-aswf:2027-arnold-vray-redshift $ECR_REPO:2027-arnold-vray-redshift
docker push $ECR_REPO:2027-arnold-vray-redshift
```

Keep the ECR repository private: the image contains licensed software.

## IAM permissions for ECR access

The queue role must have permission to pull images from the ECR repository used for the container image. At minimum, the role needs these statements for ECR:

```json
        {
            "Effect": "Allow",
            "Action": "ecr:GetAuthorizationToken",
            "Resource": "*"
        },
        {
            "Effect": "Allow",
            "Action": [
                "ecr:BatchGetImage",
                "ecr:GetDownloadUrlForLayer"
            ],
            "Resource": "arn:aws:ecr:<REGION>:<ACCOUNT>:repository/<REPOSITORY>"
        }
```

If the ECR repository is in a different account, you also need a repository policy granting cross-account access.

See [Private repository policies](https://docs.aws.amazon.com/AmazonECR/latest/userguide/repository-policies.html) and [Using Amazon ECR images with Amazon ECS](https://docs.aws.amazon.com/AmazonECR/latest/userguide/ECR_on_ECS.html) for details on configuring ECR access.

## Deploying to Deadline Cloud

Use the provided CloudFormation template to deploy everything in one command:

```bash
aws cloudformation deploy \
    --template-file cloudformation.yaml \
    --stack-name maya-aswf-ci-base-stack \
    --parameter-overrides \
        FarmId=farm-... \
        ECRImageURI=$ECR_REPO:2027-arnold-vray-redshift \
        FleetRoleArn=arn:aws:iam::...:role/FleetRole \
        QueueRoleArn=arn:aws:iam::...:role/QueueRole \
        JobAttachmentsBucket=my-deadline-bucket
```

The stack creates:
- A **queue** with job attachment settings and the container queue environment attached
- A **fleet** with GPU instances, Docker host configuration, and NVIDIA Container Toolkit
- A **queue-fleet association** connecting the two

The fleet definition is the same as the Blender sample's (L40S or RTX PRO 6000 instances). Arnold renders on the CPU, so for an Arnold-only queue you can remove `AcceleratorCapabilities` from the fleet in the template to use CPU instances.

Submit a job from the [Maya CLI render](../../../job_bundles/maya_cli_render/) job bundle to try the queue: its `Render -r sw ...` command runs inside the container through the wrapper that the queue environment installs. The [Maya V-Ray render](../../../job_bundles/maya_vray_render/), [Maya Redshift render](../../../job_bundles/maya_redshift_render/) and [Maya Arnold turntable](../../../job_bundles/turntable_with_maya_arnold/) bundles exercise the renderers; the turntable bundle uses the `maya-openjd` adaptor, but its last step encodes a video with `ffmpeg`, which is neither in the image nor wrapped by the queue environment, so expect that step to fail unless you add `ffmpeg` to the worker. These bundles declare a `CondaPackages` parameter for Conda-based queues. This queue ignores it because no Conda queue environment is attached.

### Updating the container image

After pushing a new image tag to ECR, update the stack so the queue environment's default `ContainerImage` parameter points to the new tag. This way users submitting jobs don't have to manually change the image URI in the submitter dialog.

```bash
aws cloudformation deploy \
    --template-file cloudformation.yaml \
    --stack-name maya-aswf-ci-base-stack \
    --parameter-overrides \
        FarmId=farm-... \
        ECRImageURI=$ECR_REPO:2027-arnold-vray-redshift \
        FleetRoleArn=arn:aws:iam::...:role/FleetRole \
        QueueRoleArn=arn:aws:iam::...:role/QueueRole \
        JobAttachmentsBucket=my-deadline-bucket
```

### Tearing down

```bash
aws cloudformation delete-stack --stack-name maya-aswf-ci-base-stack
```

The ECR repository and its images are not part of the stack. Delete them separately when you no longer need them.

## Licensing

The image contains no license server configuration. Maya is set up for legacy thin-client licensing (`MAYA_LEGACY_THINCLIENT=1`, `AUTODESK_ADLM_THINCLIENT_ENV`, a `ProductInformation.pit` file), which means it reads the license server from environment variables at run time instead of requiring the Autodesk Licensing service to be installed. Arnold, V-Ray and Redshift also read their license servers from environment variables.

You can provide licenses in either of these ways:

- **Deadline Cloud usage-based licensing (recommended on service-managed fleets).** Maya, Arnold, V-Ray and Redshift are available through [software licensing for service-managed fleets](https://docs.aws.amazon.com/deadline-cloud/latest/userguide/smf-licensing.html). The worker exports `ADSKFLEX_LICENSE_FILE` (Maya and Arnold), `VRAY_AUTH_CLIENT_SETTINGS` and `VRAY_AUTH_CLIENT_FILE_PATH` (V-Ray), `redshift_LICENSE` (Redshift) and `FLEXLM_TIMEOUT`, and the queue environment in `cloudformation.yaml` forwards exactly those variables (plus `g_licenseServerRLM`, `foundry_LICENSE`, `SESI_LMHOST` and `PIXAR_LICENSE_FILE`) into every `docker exec` through an `--env-file`. The license endpoint is reachable from inside the container without any network changes.
- **Your own license servers.** Set the same variables in a queue environment of your own (such as `ADSKFLEX_LICENSE_FILE=2080@licenses.example.com`), or on the workers of a customer-managed fleet. The queue environment forwards whatever values are set. See [Using software licenses with Deadline Cloud](https://docs.aws.amazon.com/deadline-cloud/latest/developerguide/license.html).

Do not bake `ADSKFLEX_LICENSE_FILE`, `redshift_LICENSE` or `VRAY_AUTH_CLIENT_*` into the Dockerfile. `scripts/verify.sh` fails the build if they are set in the image.

## How it works

1. **Build**: `build.sh` validates the installers and runs `docker build` with two named build contexts. The Dockerfile bind mounts the `installers` context read-only while `scripts/install_maya.sh` installs the Maya RPM, the ADP SDK and the thin-client licensing files, `pip` installs the adaptor, and the renderer scripts install whichever renderers were requested. The `plugins` context is copied to `/opt/maya-plugins`. `scripts/verify.sh` then checks the result. It imports Maya in `mayapy` and renders one frame to PNG with it (the adaptor's code path). It runs the adaptor's `--help` and the renderer executables. It confirms that the Autodesk licensing libraries are unmodified (with `kick` when Arnold is installed). It runs `ldd` over every binary and plug-in. The build fails if any of these checks fail or a shared library is missing. Finally a `jobuser` account is created and made the default user.
2. **Environment**: `docker exec` starts from a clean environment, and the Dockerfile sets everything a render needs: `PATH` with the Maya and renderer `bin` directories and launchers for `maya`, `mayapy`, `Render`, `kick`, `vray` and `redshiftCmdLine` in `/usr/local/bin`; `MAYA_MODULE_PATH` including `/usr/autodesk/modules/maya/2027` (where the renderer modules are) and `/opt/maya-plugins`; `MAYA_APP_DIR=/var/tmp/maya-app-dir` and `REDSHIFT_LOCALDATAPATH=/var/tmp/redshift-cache`, which are world-writable so Maya works whether the container runs as root or as an arbitrary host user ID with no home directory.
3. **Host config**: When a fleet instance launches, the host configuration script installs Docker and the NVIDIA Container Toolkit.
4. **Queue environment**: On each session, the enter script pulls the image and starts the container with the session working directory bind mounted at the same path. It writes the license variables that are set on the worker to a file, then installs wrappers for `maya-openjd`, `MayaAdaptor`, `Render`, `maya`, `mayapy`, `kick`, `vray` and `redshiftCmdLine` that forward calls into the container with `docker exec --env-file`.
5. **Render**: A job's `Render ...` command or the Deadline Cloud worker's `maya-openjd` call resolves to the wrapper and runs inside the container, with GPU access when the host has an NVIDIA GPU. The exit script stops the container and removes the wrappers and the license file.

## Adding plugins

Put Maya modules, plug-ins and scripts in a directory and pass it with `--plugins-dir` (the default is this sample's `plugins/` directory, which is ignored by git). `scripts/install_plugins.sh` copies the directory to `/opt/maya-plugins` in the image, extracting `.zip`, `.tar.gz` and `.tgz` archives there, and the Dockerfile puts these locations on Maya's search paths:

```
plugins/
├── myModule.mod          # Maya module file; its path field points at the module directory,
│                         # for example:  + myModule 1.0 ./myModule
├── myModule/             # The module itself (plug-ins/, scripts/, icons/, presets/ ...)
├── plug-ins/             # Loose plug-ins (*.so, *.py): added to MAYA_PLUG_IN_PATH
└── scripts/              # Loose MEL and Python scripts, userSetup.mel / userSetup.py:
                          # added to MAYA_SCRIPT_PATH and PYTHONPATH
```

Module files must sit at the top level of the plugins directory: Maya reads `.mod` files only in the directories listed in `MAYA_MODULE_PATH`, not in their subdirectories. A relative path in a module file is resolved relative to the module file, so `./myModule` works wherever the image puts it. See [Maya module paths, folders and versions](https://help.autodesk.com/cloudhelp/2022/ENU/Maya-SDK/Distributing-Maya-Plug-ins/DistributingUsingModules/Maya-module-paths-folders-and.html) for the module file format. The install script prints what it installed and warns about module files it finds below the top level. Because `/opt/maya-plugins/scripts` is on `PYTHONPATH`, avoid naming scripts after Python standard library modules.

Do not redistribute proprietary plugins in public images. Users must supply their own licensed copies.

## Renderer notes

- **Arnold** renders on the CPU, so it works on CPU-only fleets. `--arnold` installs the MtoA release bundled inside the Maya archive unless an `MtoA-*-linux-2027.run` download is present in the installers directory, in which case that release is installed instead. Arnold's Autodesk licensing components are not installed; licensing comes from `ADSKFLEX_LICENSE_FILE` like Maya's. `kick` is on `PATH` for `.ass` renders and diagnostics.
- **V-Ray** renders on the CPU by default and uses the GPU when the scene's production engine is set to V-Ray GPU (CUDA) and the fleet has NVIDIA GPUs. The `vray` standalone renderer (for `.vrscene` files) is on `PATH`. Only the Linux rhel8 build of the installer works. `build.sh` rejects a Windows installer that matches the file pattern.
- **Redshift** renders on the GPU when NVIDIA GPUs are available and falls back to its CPU renderer on CPU-only fleets, with the limits described in [Tested with](#tested-with) (memory budget taken from free memory, dome lights render black). Redshift's own `setup.sh` downloads additional GPU kernel files during the build if the installer contains only one, which means the build needs internet access. Plug-ins for other applications (Cinema 4D, Houdini, Katana, Solaris) and other Maya versions are removed from the image to save space. `redshiftCmdLine` is on `PATH`.

## Troubleshooting

- **Maya or `Render` exits with status 255 without printing anything.** The ADP SDK is missing or cannot be loaded. Maya 2027 loads `AdpSDKCore.so` from `$MAYA_LOCATION/lib` at startup even with `MAYA_DISABLE_ADP=1`. `scripts/install_maya.sh` installs it from `Packages/AdpSdk/adp-desktop-sdk.zip` in the Maya archive and `scripts/verify.sh` checks for it; if you changed the install script, run `ldd /usr/autodesk/maya2027/lib/AdpSDKCore.so` inside the container to find the missing dependency.
- **License errors** (Maya `License was not obtained`, Arnold `[clm] ... error (44)`, `could not initialize license` or `rendering with watermarks because of failed authorization`, V-Ray `Could not obtain a license`, Redshift `Maxon licensing error` followed by a request to update the Maxon App, which is how Redshift reports that no license server answered). Check that the variables listed in [Licensing](#licensing) are set in the session log and that the license endpoint accepts connections from your fleet. With usage-based licensing, the product must be enabled for the farm. `FLEXLM_TIMEOUT` is forwarded so that FlexNet does not give up too early.
- **Arnold reports `[clm.v1] error loading a library (4)` although `ADSKFLEX_LICENSE_FILE` is set.** The Autodesk licensing library (`libadlmint.so`) was modified in the image: its loader checks the file and refuses a stripped or patched copy, so Arnold never contacts the license server (`ADCLMHUB_LOG_LEVEL=DEBUG` makes it log `Init() failed to load ADLM` in `/tmp/AdClmHub-*.log`). `strip_debug_info` in `scripts/common.sh` skips the Autodesk licensing, identity and analytics libraries for this reason, and `scripts/verify.sh` fails the build if `rpm -V` shows one of them changed or if `kick` cannot load the library. A `generic license checkout error` or `LICENSE_CHECKOUT_ERROR` instead means the library is fine and the server was simply unreachable.
- **`mayapy` (the `maya-openjd` adaptor) fails to write a PNG with `libpng error: Invalid IHDR data` and `double free or corruption`, then hangs**, while `Render` works. Maya's bundled `lib/libfreetype.so.6` embeds its own libpng and exports its symbols; under `mayapy` they interpose the system libpng that Maya's PNG plug-in uses. `scripts/install_maya.sh` replaces that library with symlinks to the distribution's FreeType and `scripts/verify.sh` renders a frame to PNG through `mayapy` to prove it. If you see this, `ls -l /usr/autodesk/maya2027/lib/libfreetype.so.6` inside the container should point at `/usr/lib64/libfreetype.so.6.*`.
- **Redshift aborts on a CPU-only worker with `There's less than 128MB of free VRAM once fixed data (...) are considered. Aborting the render`** right after `License acquired`. Redshift's CPU renderer treats a share of the host's *free* memory as its "VRAM" and reads `MemFree`, not `MemAvailable`: directly after a multi-gigabyte image pull the page cache leaves little free memory even on a 32 GiB host, so the budget (`Redshift can use up to N MB` in the Redshift log) ends up below 128 MB and the render stops before it starts. Use workers with more memory (the same scene rendered as soon as a 64 GiB worker picked it up), use a GPU fleet, or give the task a retry budget so that it runs on another worker (`deadline bundle submit --max-retries-per-task 10 ...`).
- **Arnold renders of a scene set up for the Maya software renderer come out almost black.** Arnold applies physically based inverse-square light decay, while Maya's software renderer lights default to no decay, so point and spot lights that look right in `Render -r sw` are far too weak in Arnold. Raise the light intensities or the exposure, or light the scene with Arnold lights; a licensing problem looks different (`rendering with watermarks because of failed authorization`, or the render aborts).
- **`MayaAdaptor daemon start` fails with `Permission denied: '/.deadline'`** (or `'/.openjd'`). The adaptor runtime writes to `~/.deadline` and `~/.openjd`, and `docker exec` takes `HOME` from the container's `/etc/passwd`: a user ID without an entry gets `HOME=/`, which is not writable. The image's `jobuser` account has UID 1001 (the `JOB_USER_UID` build argument in the Dockerfile) and a home directory; if the user the wrappers run as has a different UID, build with a matching `JOB_USER_UID` (add `--build-arg JOB_USER_UID=<uid>` to the command `build.sh --dry-run` prints) or add `--env HOME={{Session.WorkingDirectory}}` to the `docker exec` in the queue environment's wrappers. `Render` and `mayapy` are not affected because `MAYA_APP_DIR` points at a world-writable directory.
- **`verify.sh` fails with `has unresolved shared libraries`.** A system library that Maya or a renderer needs is not in the image. Add the package that provides the library listed after `not found` to the `dnf install` line in the Dockerfile (`dnf provides '*/libname.so.N'` on Rocky Linux 8 tells you which) and rebuild.
- **`docker build` fails with an error about `docker.io/library/installers` or `docker.io/library/plugins`.** The build was started without the `installers` and `plugins` build contexts, and BuildKit tried to pull images with those names instead. Use `build.sh`, or pass `--build-context installers=DIR --build-context plugins=DIR` yourself.
- **Build runs out of disk space.** The full image is about 19 GB on disk, BuildKit keeps a copy of the installers context (as large as the installers, about 8 GB for all four), and the Maya step temporarily uses about 12 GB above the base image (its finished layer is 3.3 GB) while the RPM is unpacked and before the debug information is stripped. Build on a host with at least 35 GB free, and run `docker builder prune` and `docker image prune` between builds.
- **Where are the logs?** Session logs are in the Deadline Cloud monitor and in CloudWatch under `/aws/deadline/<farm-id>/<queue-id>`. Lines prefixed `[container-wrapper]` show the `docker exec` command the wrapper ran. Everything after it is the output of Maya or the renderer inside the container.

## Tested with

| Component | Version |
|-----------|---------|
| Base image | `aswf/ci-base:2026` (Rocky Linux 8, CUDA 12.9) |
| Maya | 2027.0 (`Autodesk_Maya_2027_Linux_64bit.tgz`, RPM `Maya2027_64-2027.0-16168`) |
| deadline-cloud-for-maya | 0.15.13 |
| Arnold | MtoA 5.6.3 with Arnold 7.5.3.0 (`MtoA-5.6.3-linux-2027.run`) |
| V-Ray | V-Ray 7 for Maya 2027, update 4 DR2, 7.40.04 (`vray_74004_maya2027_dr2_rhel8`) |
| Redshift | 2026.8.1 (`redshift_2026.8.1_2741261432_linux_x64.run`) |
| Build host | Docker 25 with buildx 0.12 |
| Deadline Cloud fleet | Service-managed, Linux x86_64, 16 vCPU, 32 or 64 GiB memory, no GPU |

The resulting images: `maya-aswf:2027` is 12.9 GB on disk and 6.0 GB compressed in ECR. `maya-aswf:2027-arnold-vray-redshift` is 18.7 GB on disk and 9.1 GB compressed.

The full image was pushed to a private ECR repository and exercised on the CPU-only fleet above with Deadline Cloud usage-based licensing, through a queue environment that works like the one in `cloudformation.yaml`: it pulls the image, starts the container with the session directory bind mounted and runs every command through `docker exec` with the license variables forwarded. Each test rendered one 320x180 frame of a scene from this repository's job bundles:

- `Render -r sw` (Maya software renderer): 9-14 s per task, including Maya startup.
- `Render -r arnold`: Arnold checked out a usage-based license (`[network] authorized ...` in 0.7 s) and rendered. 12-13 s per task.
- `Render -r vray`: V-Ray obtained a usage-based license, logged `V-Ray: Render complete` and wrote the EXR. 13 s per task.
- `Render -r redshift` with Redshift's CPU renderer: `License acquired` on every attempt, and the frame rendered on a 64 GiB worker (1.6 s render, 16 s task). See the caveats below.
- The `maya-openjd` adaptor (`MayaAdaptor daemon start`, `maya-openjd daemon run`, `MayaAdaptor daemon stop`) with the Maya software renderer: PNG written. 7.5 s to start Maya, 5 s for the frame, 8 s to stop.

Redshift on CPU-only workers came with two caveats:

- On 32 GiB workers, immediately after the image pull, Redshift aborted with `There's less than 128MB of free VRAM once fixed data (photon map, irradiance point cloud, irradiance cache) are considered. Aborting the render`. Redshift's CPU renderer sizes its memory budget from the kernel's *free* memory rather than the memory available after dropping caches, and a fresh 9 GB pull leaves only about 3 GB free. Deadline Cloud retried the task on a worker with free memory and it succeeded. See [Troubleshooting](#troubleshooting).
- A `RedshiftDomeLight` did not illuminate the scene with the CPU renderer (the geometry rendered black, while Maya directional and point lights rendered correctly). Use GPU fleets for Redshift. They were not part of these tests.

Timing on the test fleet, which had a minimum size of 0 so that a worker started for each job:

- Worker start after submitting a job: 47-107 s.
- Queue environment enter with a fresh pull of the full image: 293-342 s (about 5-6 minutes for 9.1 GB). With the image already on the worker: 2-3 s.

Not covered by these tests:

- GPU rendering (V-Ray GPU and Redshift GPU).
- Deploying `cloudformation.yaml` itself. The test queue environment ran the container as root, while the template runs it as the worker's job user.
- `--plugins-dir` with real content.
- Maya versions other than 2027.

## Related resources

- [Container samples index](../../README.md) and the [Blender container sample](../../blender/blender-aswf-ci-base/) this one mirrors
- Conda recipes with the same Linux install knowledge for service-managed fleets without containers: [maya-2027](../../../conda_recipes/maya-2027/), [maya-mtoa-2027](../../../conda_recipes/maya-mtoa-2027/), [maya-vray-2027](../../../conda_recipes/maya-vray-2027/), [maya-redshift-2026](../../../conda_recipes/maya-redshift-2026/), [maya-openjd](../../../conda_recipes/maya-openjd/)
- [Custom software delivery on Deadline Cloud](https://docs.aws.amazon.com/deadline-cloud/latest/developerguide/deploy-custom-software.html)
- [deadline-cloud-for-maya](https://github.com/aws-deadline/deadline-cloud-for-maya) adaptor and submitter
