# Maya Redshift sample job bundle

Use this job bundle to render a Maya scene with the Redshift renderer, using the Maya CLI
`Render` command. Read more about job bundles and how to use them with AWS Deadline Cloud
[here](../README.md).

## Prerequisites

- Have `maya` and `maya-redshift` conda packages hosted on a conda channel. Read more about
  how to create the Redshift package [here](../../conda_recipes/maya-redshift-2026/README.md).
- A GPU worker. Redshift is GPU accelerated, so the step requires `amount.worker.gpu`. A
  Deadline Cloud Linux GPU service-managed fleet works with no further configuration and
  supplies Redshift licensing.

## The scene must contain Redshift nodes

`Render` reads the scene, then runs Redshift's `melheader`, which needs the redshift4maya
plugin already loaded. The `maya-redshift` package installs redshift4maya as a Maya module
and does not enable plugin autoload, so the scene has to pull the plugin in through its
`requires "redshift4maya"` statement, which Maya writes for any scene containing Redshift
nodes.

Rendering a scene with no Redshift nodes fails with `Unknown object type: RedshiftOptions`
and `Cannot find procedure "rsDefines"`. Assign Redshift materials and render settings to
the scene and save it again, or load the plugin yourself before rendering.

The included `redshift_spheres.ma` is three spheres on a ground plane with `RedshiftMaterial`
shaders, a `RedshiftDomeLight`, and a camera named `renderCamera`. It was saved from Maya
2025 so that it opens in every Maya version the `maya-redshift` package supports.

Maya records the Redshift version the scene was saved with in that `requires` statement, but
the version is informational: any Redshift release that supports the Maya version you render
with will load the plugin and render the scene.

## Job submission

```sh
$ deadline bundle gui-submit maya_redshift_render
```

```sh
$ deadline bundle submit maya_redshift_render \
    -p MayaSceneFile=/path/to/my_scene.ma \
    -p CameraName=myCamera \
    -p Frames=1-10
```

## Job bundle customization

Redshift accepts a different set of flags than the Maya software renderer, so flags such as
`-fnc` are rejected with `Invalid flag`. Run `Render -r redshift -help` to list the
supported flags.
