# Blender — DCC-specific guide

This guide supplements the top-level [`SKILL.md`](../SKILL.md) with Blender-specific
details: download URLs, hash sources, required system libraries, and smoke test
commands.

## Download URLs

| Item | URL pattern |
|------|-------------|
| Release index | `https://download.blender.org/release/BlenderX.Y/` |
| Linux archive | `https://download.blender.org/release/BlenderX.Y/blender-X.Y.Z-linux-x64.tar.xz` |
| Windows archive | `https://download.blender.org/release/BlenderX.Y/blender-X.Y.Z-windows-x64.zip` |
| SHA256 hashes | `https://download.blender.org/release/BlenderX.Y/blender-X.Y.Z.sha256` |

### Find the latest patch release

Fetch the release index (`https://download.blender.org/release/BlenderX.Y/`) and
identify the latest `blender-X.Y.Z-linux-x64.tar.xz` and
`blender-X.Y.Z-windows-x64.zip`.

### Get SHA256 hashes

Fetch the `.sha256` file and extract the hashes for the `linux-x64.tar.xz` and
`windows-x64.zip` archives. Do not compute or guess hashes.

## Recipe specifics

- Blender archives are self-contained — no dependency resolution needed
- The `build.sh` script copies Blender into `$PREFIX/opt/blender`, creates
  symlinks, and sets environment variables via `env_vars.d` JSON files
- `build.sh` and `build_win.sh` use `$PKG_VERSION` and `$BLENDER_VERSION`, so they
  are version-agnostic and can be copied from the previous recipe unchanged

Key fields to update in `recipe.yaml`:
- `context.version` — full version (e.g., `"5.2.0"`)
- `context.major_minor_version` — `"X.Y"` (e.g., `"5.2"`)
- Both `sha256` values (linux and windows)

## Required runtime libraries

Blender requires X11 and EGL libraries even in headless mode (`-b`). These are
**already installed** in the `al2023-deadline-worker` image built from
[`containers/al2023-deadline/Dockerfile.worker-equivalent`](../../../containers/al2023-deadline/Dockerfile.worker-equivalent)
(Layer 3), so no extra install step is needed when using that image.

If you're building outside that image for some reason, install these manually:

```bash
yum install -y \
    libX11 libXi libXrender libXxf86vm libXfixes libXext \
    libSM libICE libXrandr libXinerama libXcursor \
    mesa-libGL mesa-libGLU mesa-libEGL libglvnd-egl libxkbcommon
```

Without them, `blender --version` fails with `libX11.so.6: cannot open shared
object file`. On Deadline Cloud's service-managed fleet workers these are
pre-installed on the AMI — which is exactly what the worker-equivalent Dockerfile
replicates.

## Smoke test

After creating the conda environment, verify Blender runs and the environment
variables are set:

```bash
docker exec al2023-conda-build bash -c '
    export PATH=/opt/conda/bin:$PATH
    eval "$(/opt/conda/bin/conda shell.bash hook)"
    conda activate blender-test
    blender --version
    env | grep BLENDER
'
```

You **MUST** see the correct Blender version and all `BLENDER_*` environment
variables set.

## Test render

If the user provides a `.blend` scene file, use it. Otherwise, download the
[Blender 3.5 Cozy Kitchen](https://www.blender.org/download/demo-files/) demo
scene (~7 MB, CC-BY-SA by [Nicole Morena](https://www.artstation.com/nickyblender))
— it renders quickly and works across Blender versions:

```bash
docker exec al2023-conda-build bash -c '
    curl -fsSL https://download.blender.org/demo/splash/blender-3.5-splash.blend \
        -o /workspace/cozy_kitchen.blend
'
```

Render frame 1 at 640x480 with 8 Cycles samples and no denoising:

```bash
docker exec al2023-conda-build bash -c '
    export PATH=/opt/conda/bin:$PATH
    eval "$(/opt/conda/bin/conda shell.bash hook)"
    conda activate blender-test
    mkdir -p /workspace/render-output
    blender -b /workspace/cozy_kitchen.blend \
        -o /workspace/render-output/frame_#### \
        -E CYCLES \
        --python-expr "
import bpy
bpy.context.scene.render.resolution_x = 640
bpy.context.scene.render.resolution_y = 480
bpy.context.scene.render.resolution_percentage = 100
bpy.context.scene.cycles.samples = 8
bpy.context.scene.cycles.use_denoising = False
" \
        -f 1
'
```

Verify the output file exists in `render-output/`. With the Cozy Kitchen scene
this test takes ~10 seconds (varies by machine).

After the test, ask the user: "The Cozy Kitchen render completed successfully.
Would you like to test with another scene?"

## openjd-cli end-to-end test (optional)

```bash
docker exec al2023-conda-build bash -c '
    export PATH=/opt/conda/bin:$PATH
    pip install openjd-cli "py-rattler>=0.18,<0.19" "pyyaml>=6,<7"
'

docker exec al2023-conda-build bash -c '
    export PATH=/opt/conda/bin:$PATH
    mkdir -p /workspace/openjd-output
    cd /workspace/deadline-cloud-samples/job_bundles
    openjd run blender_render/template.yaml \
        --environment ../queue_environments/conda_queue_env_pyrattler.yaml \
        -p CondaPackages="blender=X.Y" \
        -p CondaChannels="file:///my-conda-channel" \
        -p BlenderSceneFile=/workspace/cozy_kitchen.blend \
        -p OutputDir=/workspace/openjd-output \
        -p Frames=1 \
        -p ResolutionX=640 \
        -p ResolutionY=480 \
        -p Samples=8
'
```

## Blender-specific common mistakes

- Missing X11/EGL packages in the container — `blender --version` fails with
  `libX11.so.6: cannot open shared object file`. The worker-equivalent image
  includes these; only an issue if you're not using that image.
- Wrong SHA256 — fetch from the official `.sha256` file, don't guess
- Using `rattler-build publish` on older versions — `publish` was added in 0.35+;
  use `build` + manual copy + `conda index` instead
