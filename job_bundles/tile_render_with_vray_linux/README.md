# V-Ray Region Render Sample Job Bundle

This job bundle renders a V-Ray scene by dividing the image into configurable regions, rendering each region as a separate task, and then merging them into a final image.

## Features

- **Parallel Region Rendering**: Divides the image into a grid of regions (configurable rows and columns)
- **Separate Tasks**: Each region renders as an independent task that can run in parallel
- **Automatic Merging**: A final step merges all regions into the complete image
- **Configurable Grid**: Control the number of rows and columns to balance parallelism and overhead

## How It Works

1. **RenderRegions Step**: Creates tasks for each region based on `RegionColumns × RegionRows`
   - Each task calculates its region bounds (left, top, right, bottom)
   - Renders only that region using V-Ray's `-region` flag
   - Outputs to a separate file: `output_region_0.png`, `output_region_1.png`, etc.

2. **MergeRegions Step**: Combines all region files into the final image
   - Uses ImageMagick's `montage` command to stitch regions together
   - Creates the final output file specified in parameters

## Prerequisites

- V-Ray conda package hosted on a conda channel
  - Read more about creating V-Ray conda package [here](../../conda_recipes/vray/README.md)
- A sample `.vrscene` file and its dependencies
- ImageMagick (for the merge step) - typically available via conda: `conda install imagemagick`

## Parameters

### Render Parameters
- **Vray Scene File**: The `.vrscene` file to render
- **Output Directory**: Where to save rendered images (default: `./output`)
- **Output File Name**: Name of the final merged image (default: `output.png`)
- **Image Width**: Width of the output image in pixels (default: 1920)
- **Image Height**: Height of the output image in pixels (default: 1080)

### Region Settings
- **Region Columns**: Number of columns to divide the image into (default: 2, range: 1-10)
- **Region Rows**: Number of rows to divide the image into (default: 2, range: 1-10)

### Software Environment
- **Conda Packages**: Conda packages to install (default: `vray imagemagick`)

## Path Remapping

This job bundle automatically handles path remapping for assets using the session's path mapping rules. When you add files via Job Attachments, the paths are automatically translated from your local workstation to the worker machines, and V-Ray's `-remapPath` parameter is configured accordingly.

For example, if your `.vrscene` file references textures at `/shared/projects/project1/textures/`, and Job Attachments maps this to `/mnt/projects/project1/textures/` on the workers, V-Ray will automatically use the correct paths.

## Example Usage

For a 1920×1080 image with 2 columns and 2 rows:
- Creates 4 tasks (2×2 grid)
- Task (col=1, row=1): Renders region [0,0,960,540] (top-left)
- Task (col=2, row=1): Renders region [960,0,1920,540] (top-right)
- Task (col=1, row=2): Renders region [0,540,960,1080] (bottom-left)
- Task (col=2, row=2): Renders region [960,540,1920,1080] (bottom-right)
- Final task merges all 4 regions into the complete image

## Performance Considerations

- **More regions = more parallelism** but also more overhead
- For small images, fewer regions may be faster
- For large images or complex scenes, more regions can significantly reduce total render time
- Consider your worker pool size when choosing region count

## Customization

All V-Ray command line flags can be found in the [Chaos V-Ray Standalone documentation](https://docs.chaos.com/display/VNS/V-Ray+Standalone+Command+Line+Options).

Additional flags can be added to the `vray` command in the template's embedded script.
