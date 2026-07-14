# Tile Render with Maya/V-Ray and OpenImageIO

This job bundle will submit a tile rendering job using Maya and V-Ray to create EXRs as output. It'll then use the [Open Image IO tool](https://github.com/AcademySoftwareFoundation/OpenImageIO) to assemble them into a single image.

This job bundle relies on the V-Ray render handler in the Maya adaptor. The template defines a number of X and Y tiles which is used to split the output into evenly sized tiles that can be distributed across multiple render nodes.

See also the job bundle [tile_render_with_maya_arnold](../tile_render_with_maya_arnold/) for an example using Maya and Arnold and using FFmpeg to assemble PNG files into the final image.
