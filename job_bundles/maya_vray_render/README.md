# Maya V-Ray sample job bundle

Use this job bundle to render a Maya scene with the V-Ray renderer, using the Maya CLI
`Render` command. Read more about job bundles and how to use them with AWS Deadline Cloud
[here](../README.md).

## Prerequisites

- Have `maya` and `maya-vray` conda packages hosted on a conda channel. Read more about
  how to create the V-Ray package [here](../../conda_recipes/maya-vray-2027/README.md).
- `conda-forge` in your channel list, for the `openimageio` package.
- A Linux worker. V-Ray renders on CPU, so unlike the Redshift sample this job does not
  request a GPU. A Deadline Cloud Linux service-managed fleet supplies V-Ray licensing.

## Output

V-Ray writes an EXR, then the job writes a PNG beside it so you can confirm the render
looks right without an EXR viewer. Both come back in the output directory.

## The scene must contain V-Ray nodes

`Render -r vray` does not load the V-Ray plugin for you. The scene has to pull it in through
its `requires "vrayformaya"` statement, which Maya writes for any scene containing V-Ray
nodes. Rendering a scene without them fails with `Unrecognized node type 'VRaySettingsNode'`.

The included `vray_spheres.ma` is three spheres on a ground plane with a camera named
`renderCamera` and a `VRaySettingsNode` set to write EXR. It was saved from Maya 2027, so if
you render with an older Maya, save your own scene from that version instead.

## Job submission

```sh
$ deadline bundle submit maya_vray_render
```

```sh
$ deadline bundle submit maya_vray_render \
    -p MayaSceneFile=/path/to/my_scene.ma \
    -p CameraName=myCamera \
    -p Frames=1-10
```

## Job bundle customization

V-Ray rejects `-fnc` with `Invalid flag`, so this bundle does not pass it. Run
`Render -r vray -help` to list the supported flags. The output image format comes from the
scene's `vraySettings.imageFormatStr`, so change it in the scene rather than here.

See also [tile_render_with_maya_vray](../tile_render_with_maya_vray/) for splitting a frame
into tiles across workers, and [maya_redshift_render](../maya_redshift_render/) for the
Redshift equivalent.
