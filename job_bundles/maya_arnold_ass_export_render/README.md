# Maya Arnold Export and Render

## Job summary

This job exports Arnold `.ass` files from a Maya scene and renders them using the
Arnold `kick` command-line renderer. It runs as a two-step pipeline:

1. **Export** (1 task): Opens the Maya scene with `mayapy` and exports all frames
   as `.ass` files using `arnoldExportAss`.
2. **Render** (N tasks): Renders each frame independently with `kick`, distributing
   work across multiple workers.

Job attachments automatically syncs the exported `.ass` files from the export worker
to the render workers.

## Prerequisites

To run this job, you need:

* A Deadline Cloud queue with a **conda queue environment** configured. The job's
  `CondaPackages` parameter defaults to `maya-mtoa`, which provides both `mayapy`
  (for export) and `kick` (for rendering). On service-managed fleets, the
  `deadline-cloud` channel provides this package.
  If you need a specific MtoA version, see the
  [maya-mtoa conda recipe](https://github.com/aws-deadline/deadline-cloud-samples/tree/mainline/conda_recipes/maya-mtoa-2026)
  for building a custom package.
* A Linux fleet associated with the queue (the job specifies `attr.worker.os.family: linux`).

## Submitting the job

### GUI submission

```bash
deadline bundle gui-submit maya_arnold_ass_export_render/
```

### CLI submission

```bash
deadline bundle submit maya_arnold_ass_export_render/ \
    -p MayaSceneFile=/path/to/scene.ma \
    -p Frames=1-100 \
    -p Camera=renderCam \
    -p OutputDir=./output
```

## How it works

### Step 1: Export

A single task runs `mayapy` to open the Maya scene and execute `arnoldExportAss`,
which exports all frames in the range as per-frame `.ass` files. This approach is efficient
because the Maya scene is only opened once regardless of frame count.

The `Camera` parameter is optional. Leave it empty to use the scene's default
renderable camera.

### Step 2: Render

One task per frame runs `kick -i <ass_file> -o <output>`. The render step depends
on the export step, so it only starts after all `.ass` files are exported and
uploaded via job attachments.

## Notes

* Missing optional Maya plugins (V-Ray, USD, etc.) will produce warnings during
  export but won't cause failures unless the scene depends on them for geometry.
* For scenes that are already exported as `.ass` files, use the simpler
  [arnold_standalone_render](../arnold_standalone_render) bundle instead.
