# VRED Renderer Job Bundle

## Overview

This job bundle is for rendering VRED scenes using either VRED Core or VRED Pro in headless mode. It uses VRED's Python API through the `VRED_RenderScript_DeadlineCloud.py` script, which:
- Controls and executes the actual rendering process
- Converts job template parameters into VRED API calls
- Manages all rendering settings (quality, resolution, tiling, etc.)
- Handles file references and error management

## Available Templates

This job bundle provides two template options:
- **Basic Template** (`template.yaml`): Standard rendering functionality
- **Tiling Template**: Additional support for region/tile-based rendering
  - Includes all features of basic template plus tile-based rendering capability
    - Adds a "Tile Assembly" step that combines rendered tiles into final images
  - To use this template, rename `template_tiling.yaml` to `template.yaml`

## Requirements

### For Service-Managed Fleets (SMF)
- Access to 'deadline-cloud' conda channel
- GPU-enabled worker
- (Optional) For tile assembly when using the `template_tiling.yaml` template, ImageMagick must be available in the rendering environment. The easiest way is to add the `imagemagick` conda package from the `conda-forge` channel to your Queue Environment. For detailed instructions on configuring conda packages, see the [Configure jobs using queue environments](https://docs.aws.amazon.com/deadline-cloud/latest/developerguide/configure-jobs.html).

### For Custom-Managed Fleets (CMF)
- VRED Core or VRED Pro (2025.X/17.X or 2026.X/18.X)
- Windows or Linux operating system
- GPU with appropriate drivers
  - Please review the [system requirements and software dependencies](https://www.autodesk.com/support/technical/article/caas/sfdcarticles/sfdcarticles/System-requirements-for-Autodesk-VRED-products.html).
- Environment variable setup:
  - `VREDCORE` pointing to VRED Core executable, or
  - `VREDPRO` pointing to VRED Pro executable
- (Optional) If using the `template_tiling.yaml` template, ImageMagick must be available in the rendering environment for tile assembly.

### Required Files
- A job template (yaml) file named `template.yaml`
- `scripts/VRED_RenderScript_DeadlineCloud.py`: a controller script that must be present in job bundle with the provided job template
- VRED scene file (.vpb) and/or its referenced files

## Job Submission Examples

### CLI Submission

Submit with default parameters:
```bash
deadline bundle submit .
```

Submit with custom parameters:
```bash
deadline bundle submit . \
  -p SceneFile="path/to/scene.vpb" \
  -p OutputDir="path/to/output" \
  -p ImageWidth=1920 \
  -p ImageHeight=1080
```

### GUI Submission
Launch the GUI submitter to interactively configure parameters:

```bash
deadline bundle gui-submit .
```

## Job Parameters

### Input/Output
- **SceneFile**: VRED scene file (.vpb) to render (must be relative path)
- **OutputDir**: Directory for downloading rendered outputs (must be relative path)
- **OutputFileNamePrefix**: Prefix for output filenames (default: "output")
- **OutputFormat**: Image format (default: PNG, supports multiple formats including EXR, JPG, etc.)

Note: All `PATH` type parameters must use relative paths from the current working directory. Absolute paths are not supported.

### Render Settings
- **ImageWidth**: Output width in pixels (default: 800)
- **ImageHeight**: Output height in pixels (default: 600)
- **DPI**: Resolution in dots per inch (default: 72)
- **RenderQuality**: Quality preset (Analytic Low/High, Realistic Low/High, Raytracing, NPR)
- **View**: Specific viewpoint/camera to render from
- **GPURaytracing**: Enable GPU-accelerated ray tracing

### NVIDIA DLSS Options
- **DLSSQuality**: Deep Learning Super Sampling quality setting (Off, Performance, Balanced, Quality, Ultra Performance)
- **SSQuality**: Supersampling quality setting (Off, Low, Medium, High, Ultra High)

### Frame Control Settings
- **StartFrame**: First frame to render (default: 0)
- **EndFrame**: Last frame to render (default: 20)
- **FrameStep**: Frame increment - e.g., 2 for rendering every second frame (default: 1)
- **FramesPerTask**: Number of consecutive frames to render in a single Task (default: 1)
    Batching frames can improve rendering efficiency by reducing overhead from task initialization.
    Example with `FramesPerTask=5`:
    - Task 1 renders frames 1-5
    - Task 2 renders frames 6-10
    - And so on...

### Animation Settings
- **RenderAnimation**: Enable animation rendering (true/false)
- **AnimationType**: Animation type (Clip/Timeline)
- **AnimationClip**: Name of animation clip to render

### (Optional) Region/Tile-based Rendering
This feature is available when using the tiling template (`template_tiling.yaml`).
Tile-based rendering divides each frame into smaller tiles that are rendered independently and later assembled into the final image.

When using tile-based rendering, **GPURaytracing** must also be enabled to prevent solid black tile outputs.

- **RegionRendering**: Enable tile-based rendering (true/false)
- **NumXTiles**: Number of tiles to divide the image horizontally (default: 1)
- **NumYTiles**: Number of tiles to divide the image vertically (default: 1)

#### Process
1. Image is divided into tiles based on NumXTiles and NumYTiles
2. Each tile is rendered as a separate task
3. After all tiles are rendered, a final "Tile Assembly" step combines them into the final image

## Expected Output
The renderer produces image files in the specified output directory following this naming pattern:
- Single images: `<OutputFileNamePrefix>.<OutputFormat>`
- Animation frames: `<OutputFileNamePrefix>-#####.<OutputFormat>`
- Region rendering temporary files (Individual tiles): `<OutputFileNamePrefix>_YxX_AxB.<OutputFormat>` Where:
  - Y: Vertical tile number
  - X: Horizontal tile number
  - A: Total number of horizontal tiles
  - B: Total number of vertical tiles

## Notes

- When using conda environments, ensure your queue has access to the required conda channels (e.g., `deadline-cloud`, `conda-forge`)
- For optimal performance with large images, consider enabling region rendering
- GPU ray tracing requires compatible hardware
- DLSS features require NVIDIA RTX GPUs
- **Tile rendering**: Requires GPURaytracing to be enabled. Scene files must be properly configured (such as adding sufficient lighting) to support ray tracing, otherwise rendered images may appear black.
