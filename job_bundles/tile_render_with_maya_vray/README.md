# Tile Render with Maya/V-Ray and OpenImageIO

## Introduction

This job bundle will submit a tile rendering job using Maya and V-Ray to create EXRs as output. It'll then use the [Open Image IO tool](https://github.com/AcademySoftwareFoundation/OpenImageIO) to assemble them into a single image.

This job bundle relies on a customized V-Ray render handler in the Maya adaptor. The template defines a number of X and Y tiles which is used to split the output into evenly sized tiles that can be distributed across multiple render nodes.

See also the job bundle [tiled_region_render_with_maya_arnold](https://github.com/aws-deadline/deadline-cloud-samples/tree/mainline/job_bundles/tile_render_with_maya_arnold) for an example using Maya and Arnold and using FFMPG to assemble PNG files into the final image.

## V-Ray Render Handler Modifications

As of 2025/10 modifications to the Deadline Cloud Maya adaptor are nessessary to create the tiles for this job.
To do this, a local copy of the [deadline-cloud-for-maya](https://github.com/aws-deadline/deadline-cloud-for-maya/tree/mainline)
repository can be used to create a development version of the Maya adaptor. The following code can be added to
the `start_render` function in [vray_renderer.py](https://github.com/aws-deadline/deadline-cloud-for-maya/blob/mainline/src/deadline/maya_adaptor/MayaClient/render_handlers/vray_handler.py)
after setting the log message level. This is repeated in the below sample to help find where in the file to make changes. 

After making changes,
[rebuild the wheels](https://github.com/aws-deadline/deadline-cloud-for-maya/blob/mainline/DEVELOPMENT.md#application-interface-adaptor-development-workflow)
for the package.

```
        # Set the log message level to 3 (report errors, warnings and general information) if needed
        if maya.cmds.getAttr("vraySettings.sys_message_level") < 3:
            maya.cmds.setAttr("vraySettings.sys_message_level", 3)

        # Perform setup for region rendering if needed, otherwise just use the output size from the submission
        region = [
            data.get(field) 
            for field in ("region_min_x", "region_min_y", "region_max_x", "region_max_y")
        ]
        if any(v is not None for v in region):
            print(f"MayaClient: Region bounds {region} specified.", flush=True)

            region_minX, region_minY, region_maxX, region_maxY = region
            region_str = f"(minX={region_minX}, minY={region_minY}, maxX={region_maxX}, maxY={region_maxY})"
            if any(v is None for v in region):
                raise RuntimeError(
                    f"MayaClient: Region bounds {region_str} must be fully defined or all empty, but were partially specified."
                )

            # Set the output filename
            maya.mel.eval(f'''setAttr -type "string" "vraySettings.fileNamePrefix" "{data.get("output_file_prefix")}";''')

            # Set to allow region in batch rendering
            maya.cmds.setAttr("vraySettings.vfbRgnOffBatch", 0)

            # Set to use VFB
            maya.cmds.setAttr("vraySettings.vfbOn", 1)

            # Set the image format to EXR - This is needed to make sure image is properly cropped
            print("Ensuring output is set to EXR for compatibility with region rendering in Vray", flush=True)
            maya.cmds.setAttr("vraySettings.imageFormatStr", "exr", type="string")

            # Set the region to render
            region_cmd = f"vray vfbControl -setregion {region_minX} {region_minY} {region_maxX} {region_maxY}; vraySetBatchDoRegion {region_minX} {region_minY} {region_maxX} {region_maxY};"
                        
            print(f"Setting render region: {region_cmd}")
            maya.mel.eval(region_cmd)

            get_region_cmd = "vray vfbControl -getregion"
            print(f"Checking the region is set: {maya.mel.eval(get_region_cmd)}", flush=True)

```