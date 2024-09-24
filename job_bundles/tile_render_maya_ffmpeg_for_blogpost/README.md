# Tile Render with Maya/Arnold and Ffmpeg

## Introduction

Read the blog post [Create a tile rendering job with modifications for AWS Deadline Cloud](https://aws.amazon.com/blogs/media/create-a-tile-rendering-job-with-modifications-for-aws-deadline-cloud/)
to learn about how this job was created.

This job is designed to submit a tile rendering job using Maya, Arnold, and ffmpeg. A tile render
divides an image into evenly sized regions for rendering, then assembles the tiles to get the whole image.

This job bundle requires a modified Maya Arnold render handler for Deadline Cloud. It uses a bash script
to call ffmpeg which requires Linux workers and access to the ffmpeg command from the workers. The template
uses job parameter values (NumXTiles and NumYTiles) to specify the number of tiles, which are then used
to define task parameter values (TileNumberX and TileNumberY) for the tile numbers, which are all added
to the runData for the Maya render step. A second step is defined to have a dependency on the render step,
which uses a bash script to call ffmpeg to assemble the tiles.

See also the job bundle [tiled_region_render_with_maya_arnold](tiled_region_render_with_maya_arnold)
that forms the tile bounds in the job and uses region render parameters when calling the Open Job Description
application interface for rendering Maya.

## Arnold Render Handler Modifications

As on 7/2024, modifications to the Deadline Cloud Maya adaptor are needed to render the tiles for this job.
To do this, a local copy of the [deadline-cloud-for-maya](https://github.com/aws-deadline/deadline-cloud-for-maya/tree/mainline)
repository can be used to create a development version of the Maya adaptor. The following code can be added to
the `start_render` function in [arnold_renderer.py](https://github.com/aws-deadline/deadline-cloud-for-maya/blob/mainline/src/deadline/maya_adaptor/MayaClient/render_handlers/arnold_handler.py)
after the width and height of the image are confirmed. After making changes,
[rebuild the wheels](https://github.com/aws-deadline/deadline-cloud-for-maya/blob/mainline/DEVELOPMENT.md#application-interface-adaptor-development-workflow)
for the package.

```
numXTiles = data.get("numXTiles")
numYTiles = data.get("numYTiles")

# Check if this is a tile rendering job (numXTiles and numYTiles are specified as job parameters)
if (numXTiles is not None) and (numYTiles is not None):

    # Check that numXTiles and numYTiles are integers
    if (not isinstance(numXTiles, int)) or (not isinstance(numYTiles, int)):
        raise RuntimeError(
            "numXTiles and numYTiles variables from run-data must be integers"
        )

    # Tile num uses 1 based indexing. First tile (top left) is x=1, y=1
    tileNumX = data.get("tileNumX")
    tileNumY = data.get("tileNumY")

    # Check that tileNumX and tileNumY are integers
    if (not isinstance(tileNumX, int)) or (not isinstance(tileNumY, int)):
        raise RuntimeError("tileNumX and tileNumY variables from run-data must be integers")

    deltaX, widthRemainder = divmod(self.render_kwargs["width"], numXTiles)
    deltaY, heightRemainder = divmod(self.render_kwargs["height"], numYTiles)

    # Calculate the border values for the tile
    # -1 from tilenums for minimums to get the end of the previous tile or 0. This is not done for max values as the max values need to reference the start of the next tile
    # -1 from max values because Maya uses inclusive ranges and 0 based indexing for coordinates
    # minX = left, maxX = right, minY = top, maxY = bottom
    minX = deltaX * (tileNumX - 1)
    maxX = (deltaX * tileNumX) - 1
    minY = deltaY * (tileNumY - 1)
    maxY = (deltaY * tileNumY) - 1

    # Add any remainder to the last row and column
    if tileNumX == numXTiles:
        maxX += widthRemainder
    if tileNumY == numYTiles:
        maxY += heightRemainder

    # Set the border ranges for the tile (left, right, top, bottom)
    maya.cmds.setAttr("defaultArnoldRenderOptions.regionMinX", minX)
    maya.cmds.setAttr("defaultArnoldRenderOptions.regionMaxX", maxX)
    maya.cmds.setAttr("defaultArnoldRenderOptions.regionMinY", minY)
    maya.cmds.setAttr("defaultArnoldRenderOptions.regionMaxY", maxY)
    print(f"minX={minX}, maxX={maxX}, minY={minY}, maxY={maxY}")

    prefix = data.get("output_file_prefix")

    # Set an ffmpeg glob pattern type compatible prefix for the tile (_tile_<y-coord>x<x_coord>_<numYtiles>x<numXtiles>_<prefix>) where x-coord and y-coord use 1-based indexing
    # This command takes inputs in sequential order and assembles them from left to right, top to down which is why the Y value needs to be first
    maya.cmds.setAttr(
        "defaultRenderGlobals.imageFilePrefix",
        f"_tile_{tileNumY}x{tileNumX}_{numYTiles}x{numXTiles}_{prefix}",
        type="string"
    )

    print(f'Output file name: {maya.cmds.getAttr("defaultRenderGlobals.imageFilePrefix")}')
```