# Arnold Standalone Render

## Job summary

This job bundle renders Arnold `.ass` (Arnold Scene Source) files using the Arnold
`kick` command-line renderer that ships with MtoA (Arnold for Maya).

The `kick` command is Arnold's standalone renderer. It reads `.ass` files and produces
rendered images without requiring a full Maya session, making it ideal for batch rendering
pre-exported scenes.

## Prerequisites

To run this job, you need:

* A Deadline Cloud queue with a **conda queue environment** configured. The job's
  `CondaPackages` parameter defaults to `maya-mtoa`, which provides the `kick` binary.
  On service-managed fleets, the `deadline-cloud` channel provides this package.
  If you need a specific MtoA version, see the
  [maya-mtoa conda recipe](https://github.com/aws-deadline/deadline-cloud-samples/tree/mainline/conda_recipes/maya-mtoa-2026)
  for building a custom package.
* A Linux fleet associated with the queue (the job specifies `attr.worker.os.family: linux`).

## Getting sample .ass files

You can download sample Arnold scene files from the Autodesk Arnold learning scenes page:

**[Arnold Learning Scenes](https://help.autodesk.com/view/MAYAUL/2024/ENU/?guid=arnold_for_maya_tutorials_am_Learning_Scenes_html)**

The page provides scenes like `cornell.ass` (a Cornell box) that work well for testing.

You can also export `.ass` files from Maya using Arnold's scene export:
`Arnold > Export Scene...` or via MEL: `arnoldExportAss -f "scene.ass"`.

## Submitting the job

### GUI submission

```bash
deadline bundle gui-submit arnold_standalone_render/
```

### CLI submission

```bash
deadline bundle submit arnold_standalone_render/ \
    -p ArnoldFile=/path/to/scene.ass \
    -p OutputDir=/path/to/output
```

## How it works

The job has a single step that:

1. Locates the `kick` binary using the `$MTOA` environment variable set by the
   `maya-mtoa` conda package.
2. Prints the Arnold version for reference.
3. Runs `kick -i <input> -o <output>` to render the scene.

The output format is inferred from the `OutputFileName` extension (default: `.exr`).
Arnold supports EXR, PNG, JPEG, TIFF, and other formats.
