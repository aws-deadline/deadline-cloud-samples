# V-Ray Region Render Sample Job Bundle

This job bundle renders a V-Ray scene by dividing the image into configurable regions, rendering each region as a separate task, and then merging them into a final image. Optionally creates a movie from rendered frames.

## Features

- **Parallel Region Rendering**: Divides the image into a grid of regions (configurable rows and columns)
- **Separate Tasks**: Each region renders as an independent task that can run in parallel
- **Automatic Merging**: Merges all regions into the complete image using ImageMagick
- **Optional Movie Creation**: Creates an MP4 movie from rendered frames using ffmpeg
- **Path Remapping**: Automatically handles asset path translation between workstation and workers
- **Standalone Scripts**: Render and merge logic in separate script files for easy customization
- **Automatic Asset Discovery**: Pre-submission hook parses the vrscene file to find all referenced textures and files, adding them to job attachments automatically

## How It Works

1. **RenderRegions Step**: Creates tasks for each region based on `RegionColumns × RegionRows × Frames`
   - Each task calculates its region bounds (left, top, right, bottom)
   - Renders only that region using V-Ray's `-crop` flag
   - Outputs to a separate file: `output_f1_region_r0_c0.png`, `output_f1_region_r0_c1.png`, etc.

2. **MergeRegions Step**: Combines all region files into the final image for each frame
   - Uses ImageMagick's `convert` command to stitch regions together
   - Creates the final output file: `output.0001.png`, `output.0002.png`, etc.

3. **CreateMovieFile Step** (optional): Creates a movie from the merged frames
   - Uses ffmpeg to encode frames into an MP4 video
   - Only runs if `CreateMovie` parameter is set to `true`

## Bundle Structure

```
tile_render_with_vray_linux/
├── template.yaml                    # Job template definition
├── hooks.yaml                       # Pre-submission hook configuration
├── scripts/
│   ├── render_region.sh             # Renders a single region tile
│   ├── merge_regions.sh             # Merges region tiles into complete frame
│   ├── setup_vray_path_mapping.py   # Generates V-Ray path remapping args
│   └── discover_vrscene_assets.py   # Discovers textures/files in vrscene
└── README.md
```

## Prerequisites

### 1. Build the V-Ray Conda Package

Follow the instructions in the [V-Ray conda recipe README](../../conda_recipes/vray/README.md) to build and publish the V-Ray conda package to your S3 channel.

### 2. Set Up the Queue Environment

Create a Conda queue environment that references your S3 channel and conda-forge (for imagemagick/ffmpeg):

```bash
aws deadline create-queue-environment \
   --farm-id <FARM_ID> \
   --queue-id <QUEUE_ID> \
   --priority 1 \
   --template-type YAML \
   --template file://queue_environments/conda_queue_env_improved_caching.yaml
```

Update the `CondaChannels` default in the queue environment to include both your S3 channel and conda-forge:

```yaml
default: "s3://<job-attachments-bucket>/Conda/Default conda-forge"
```

### 3. Sample Scene Files

## Exporting from 3ds Max

To export a `.vrscene` file from 3ds Max for use with this job bundle:

1. Open your scene in 3ds Max with V-Ray as the active renderer
2. Open the V-Ray Scene Exporter:
   - **V-Ray 6+**: Go to the top menu bar: `V-Ray > .vrscene exporter`
   - **V-Ray 5 & Older**: Right-click in any viewport and select `.vrscene exporter` from the Quad menu
3. Configure export settings:
   - Set the **Export path**
   - For animation, select the correct frame range (e.g., "Single File" or "File Per Frame")
4. Click **Export**

Refer to the [Chaos V-Ray documentation](https://documentation.chaos.com/space/VMAX/113575461/V-Ray+Scene+Exporter) for detailed export options.

## Parameters

### Render Parameters
- **Vray Scene File**: The `.vrscene` file to render
- **Output Directory**: Where to save rendered images (default: `./output`)
- **Output File Name**: Name of the final merged image (default: `output.png`)
- **Image Width**: Width of the output image in pixels (default: 1920)
- **Image Height**: Height of the output image in pixels (default: 1080)
- **Frames**: Frame range to render (default: `1`, supports ranges like `1-10` or `1,5,10`)

### Region Settings
- **Region Columns**: Number of columns to divide the image into (default: 2, range: 1-10)
- **Region Rows**: Number of rows to divide the image into (default: 2, range: 1-10)

### Movie Settings
- **Create Movie**: Whether to create an MP4 from rendered frames (default: `false`)
- **Movie Filename**: Output movie filename (default: `output.mp4`)
- **Frame Rate**: Frame rate for the movie (default: 24)

### Software Environment
- **Conda Packages**: Conda packages to install (default: `vray imagemagick ffmpeg`)

## Job Submission

> **Note:** This bundle includes a pre-submission hook that automatically discovers textures and files referenced in the vrscene. You must enable bundle hooks before submitting:
> ```bash
> deadline config set settings.allow_bundle_hooks true
> ```

Using the GUI:
```bash
deadline bundle gui-submit job_bundles/tile_render_with_vray_linux
```

Using the CLI:
```bash
deadline bundle submit job_bundles/tile_render_with_vray_linux \
    -p VraySceneFile="/path/to/scene.vrscene" \
    -p OutputDir="./output"
```

### Automatic Asset Discovery

The pre-submission hook (`scripts/discover_vrscene_assets.py`) parses the vrscene file before submission and automatically adds all referenced files to the job attachments. It detects:

- **Texture files** referenced via `file="..."` parameters (e.g., in `BitmapBuffer` plugins)
- **Mesh files** referenced via `file="..."` parameters (e.g., in `GeomMeshFile` plugins)
- **Included vrscene files** via `#include "..."` directives

Relative paths in the vrscene are resolved relative to the vrscene file's directory. Files that cannot be found on disk are logged as warnings but do not block submission.

## Path Remapping

This job bundle automatically handles path remapping for assets using the session's path mapping rules.

### How It Works

1. The `setup_vray_path_mapping.py` script reads the session's path mapping rules from `{{Session.PathMappingRulesFile}}`
2. Generates V-Ray `-remapPath` arguments for each source→destination mapping
3. Saves the arguments to `/tmp/vray_remap_paths.txt`
4. The render script applies these arguments to the V-Ray command

### Example

When you add files via Job Attachments, paths are automatically translated:

- **Source path** (your workstation): `C:\Projects\MyProject\textures\`
- **Destination path** (worker): `/sessions/.../assetroot-.../textures/`
- **V-Ray argument**: `-remapPath='C:\Projects\MyProject\textures\=/sessions/.../assetroot-.../textures/'`

## Example Usage

For a 1920×1080 image with 2 columns and 2 rows:
- Creates 4 render tasks (2×2 grid) per frame
- Task (col=0, row=0): Renders region [0,0,960,540] (top-left)
- Task (col=1, row=0): Renders region [960,0,1920,540] (top-right)
- Task (col=0, row=1): Renders region [0,540,960,1080] (bottom-left)
- Task (col=1, row=1): Renders region [960,540,1920,1080] (bottom-right)
- Merge task combines all 4 regions into the complete image

## Performance Considerations

- **More regions = more parallelism** but also more overhead
- For small images, fewer regions may be faster
- For large images or complex scenes, more regions can significantly reduce total render time
- Consider your worker pool size when choosing region count

## Customization

The scripts in the `scripts/` folder can be modified to customize behavior:

- `render_region.sh`: Modify V-Ray command line options
- `merge_regions.sh`: Change merge behavior or add post-processing
- `setup_vray_path_mapping.py`: Customize path mapping logic

All V-Ray command line flags can be found in the [Chaos V-Ray Standalone documentation](https://docs.chaos.com/display/VNS/V-Ray+Standalone+Command+Line+Options).
