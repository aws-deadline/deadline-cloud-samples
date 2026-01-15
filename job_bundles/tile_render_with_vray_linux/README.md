# V-Ray Region Render Sample Job Bundle

This job bundle renders a V-Ray scene by dividing the image into configurable regions, rendering each region as a separate task, and then merging them into a final image. Optionally creates a movie from rendered frames.

## Features

- **Parallel Region Rendering**: Divides the image into a grid of regions (configurable rows and columns)
- **Separate Tasks**: Each region renders as an independent task that can run in parallel
- **Automatic Merging**: Merges all regions into the complete image using ImageMagick
- **Optional Movie Creation**: Creates an MP4 movie from rendered frames using ffmpeg
- **Path Remapping**: Automatically handles asset path translation between workstation and workers

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

## Prerequisites

### 1. Build the V-Ray Conda Package

Follow the instructions in the [V-Ray conda recipe README](../../conda_recipes/vray/README.md) to build and publish the V-Ray conda package to your S3 channel.

Read more about creating V-Ray conda package [here](../../conda_recipes/vray/README.md).

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
You'll need a `.vrscene` file and its dependencies. The [Chaos ENVISION documentation samples](https://docs.chaos.com/display/ENVISION/Sample+Scenes) include vrscene files you can use for testing.

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

## Path Remapping

This job bundle automatically handles path remapping for assets using the session's path mapping rules. When you add files via Job Attachments, the paths are automatically translated from your local workstation to the worker machines, and V-Ray's `-remapPath` parameter is configured accordingly.

For example, if your `.vrscene` file references textures at `/shared/projects/project1/textures/`, and Job Attachments maps this to `/mnt/projects/project1/textures/` on the workers, V-Ray will automatically use the correct paths.

The job also sets `VRAY_PATH_REMAPPING_CASE_SENSITIVE=1` to ensure proper path matching on Linux workers when source paths come from Windows.

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

All V-Ray command line flags can be found in the [Chaos V-Ray Standalone documentation](https://docs.chaos.com/display/VNS/V-Ray+Standalone+Command+Line+Options).

Additional flags can be added to the `vray` command in the template's embedded script.