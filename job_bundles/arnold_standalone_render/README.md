# Arnold Standalone Render

## Job summary

This job bundle renders Arnold `.ass` (Arnold Scene Source) files using the Arnold
`kick` command-line renderer that ships with MtoA (Arnold for Maya).

Point it at a directory of `.ass` files with a naming pattern, and it renders each
frame as a separate task distributed across workers.

## Prerequisites

* A Deadline Cloud queue with a **conda queue environment** configured. The job's
  `CondaPackages` parameter defaults to `maya-mtoa`, which provides the `kick` binary.
  On service-managed fleets, the `deadline-cloud` channel provides this package.
  If you need a specific MtoA version, see the
  [maya-mtoa conda recipe](https://github.com/aws-deadline/deadline-cloud-samples/tree/mainline/conda_recipes/maya-mtoa-2026)
  for building a custom package.
* A Linux fleet associated with the queue (the job specifies `attr.worker.os.family: linux`).

## Getting sample .ass files

A sample `cornell.0001.ass` file is included in the `scene/` directory.

You can download more from the Autodesk Arnold learning scenes page:
**[Arnold Learning Scenes](https://help.autodesk.com/view/MAYAUL/2024/ENU/?guid=arnold_for_maya_tutorials_am_Learning_Scenes_html)**

You can also export `.ass` files from Maya: `Arnold > Export Scene...` or via MEL:
`arnoldExportAss -f "scene" -sf 1 -ef 100`. See the
[maya_arnold_ass_export_render](../maya_arnold_ass_export_render) sample for a job
that automates this export step.

## Submitting the job

### GUI submission

```bash
deadline bundle gui-submit arnold_standalone_render/
```

### CLI submission

```bash
deadline bundle submit arnold_standalone_render/ \
    -p SceneDirectory=/path/to/ass_files \
    -p FilePattern=robot.####.ass \
    -p Frames=1-100 \
    -p OutputDir=./output
```

## How it works

The job has a single step with a parameter space that creates one task per frame.
Each task:

1. Locates the `kick` binary using the `$MTOA` environment variable, with a
   fallback to searching `$CONDA_PREFIX`.
2. Constructs the input path from `SceneDirectory` and `FilePattern`, replacing
   `####` with the zero-padded frame number.
3. Runs `kick -i <input> -o <output>` to render the scene.
4. Outputs files named `<OutputFilePrefix>.<frame>.exr`.
