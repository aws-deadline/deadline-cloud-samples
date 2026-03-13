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

You can also export `.ass` files from Maya using Arnold's scene export:
`Arnold > Export Scene...` or via MEL: `arnoldExportAss -f "scene"`.
See the [maya_arnold_ass_export_render](../maya_arnold_ass_export_render) sample for a job
that automates this export step.

## Submitting the job

### GUI submission

```bash
deadline bundle gui-submit arnold_standalone_render/
```

### CLI submission

Single frame (e.g. the included cornell.ass):

```bash
deadline bundle submit arnold_standalone_render/ \
    -p ArnoldFile=cornell.ass \
    -p OutputDir=./output
```

Animation sequence with per-frame .ass files:

```bash
deadline bundle submit arnold_standalone_render/ \
    -p ArnoldFile=scene.####.ass \
    -p Frames=1-100 \
    -p OutputDir=./output
```

## How it works

The job has a single step with a parameter space that creates one task per frame.
Each task:

1. Locates the `kick` binary using the `$MTOA` environment variable set by the
   `maya-mtoa` conda package, with a fallback to searching `$CONDA_PREFIX`.
2. Substitutes `####` in the input path with the zero-padded frame number.
3. Runs `kick -i <input> -o <output>` to render the scene.
4. Outputs files named `<OutputFilePrefix>.<frame>.exr` with zero-padded frame numbers.

For single-frame scenes like the included `cornell.ass`, the default `Frames` value
of `1` creates a single task. For animation sequences, set `Frames` to a range
like `1-100` and each frame will render as a separate task distributed across workers.
