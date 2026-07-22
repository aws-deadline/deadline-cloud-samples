# Infinigen conda package recipe

## Package contents

This directory holds a [rattler-build](http://rattler.build/) recipe for
[Infinigen](https://infinigen.org/), a procedural 3D scene generator from
Princeton Vision & Learning Lab. If you build this package, you can use it to
generate photorealistic indoor and outdoor scenes with ground truth labels on
AWS Deadline Cloud.

The package you build from this recipe will include the following:

1. [Infinigen v1.19.0](https://github.com/princeton-vl/infinigen): the
   procedural scene generation engine.
2. [bpy 4.2.0](https://docs.blender.org/api/current/info_advanced_blender_as_bpy.html):
   Blender as a Python module for headless rendering via Cycles. No standalone
   Blender installation is needed at runtime.
3. Terrain C++ shared libraries (CPU + optional CUDA) compiled from
   Infinigen's source for landscape generation.
4. A patched `gin-config` resource reader to support namespace package path
   resolution in non-editable installs.
5. `setuptools<70` pinned for `pkg_resources` compatibility required by
   `landlab`.

## Building the package on Deadline Cloud

You can build this package on a Deadline Cloud farm that is configured for
package build jobs that update an S3 conda channel and has a CUDA fleet to
run the build. See the AWS Deadline Cloud developer guide
[Create a conda channel using S3](https://docs.aws.amazon.com/deadline-cloud/latest/developerguide/configure-jobs-s3-channel.html)
for setup instructions, and the [CUDA farm CloudFormation template](../../cloudformation/farm_templates/cuda_farm/README.md)
for a quick way to deploy a CUDA-capable farm.

Submit a build job from the [conda_recipes](..) directory of the Deadline
Cloud samples repository as follows. If you need to customize this, see the
[conda recipe samples README](../README.md).

```
$ ./submit-package-job infinigen-1.19.0
```

The build requires a GPU worker (for CUDA terrain compilation) and takes
~6 minutes.

## Building the package locally

You can also build the recipe directly with
[`rattler-build`](https://rattler.build/latest/#installation) on a Linux host,
optionally with CUDA available. From the `conda_recipes` directory:

```
rattler-build publish infinigen-1.19.0/recipe/recipe.yaml \
    --to s3://amzn-s3-demo-bucket/Conda/Default \
    -c conda-forge \
    --build-number=+1
```

If your machine has no CUDA GPU but you still want to build the package, the
terrain compilation step falls back to a CPU-only build automatically. You
will need a GPU at runtime to use the nature (terrain) scene type.

## Use with the companion job bundle

See the [infinigen_scene_gen](../../job_bundles/infinigen_scene_gen/) job
bundle for submitting scene generation jobs against the package built from
this recipe.

The job template's `CondaPackages` parameter defaults to
`infinigen jinja2 pyyaml setuptools`. The extra packages are transitive
dependencies that are not bundled in the conda package itself.

## Licensing

[Infinigen](https://github.com/princeton-vl/infinigen/blob/main/LICENSE) is
distributed under the BSD-3-Clause license. The `bpy` Python module that
Infinigen depends on at runtime is GPL-licensed (Blender). This recipe builds
Infinigen from upstream source and pulls `bpy` from PyPI at install time.
No GPL binaries are redistributed in this samples repository.

**Note on the package you build from this recipe:** the resulting conda
package physically bundles `bpy` (and its Blender components), which are
licensed under the **GNU GPL**. The built package artifact is
subject to GPL terms, even though its `license` metadata records
`BSD-3-Clause` (which reflects Infinigen's own source license only). Building
and using the package to render is unrestricted; however, if you redistribute
the built package to third parties, you are responsible for complying with the
GPL, including making the corresponding source available. Consult your own
legal/open-source guidance before redistributing.

## Known issues

- Infinigen v1.19.0 has a bug in `reptile.py` where `reptile_postprocessing()`
  is called with the wrong arguments. Workaround: disable snakes via
  `-p SceneOverrides="populate_scene.populate_snake_enabled=False"` when
  submitting from the [`infinigen_scene_gen`](../../job_bundles/infinigen_scene_gen/)
  job bundle.
- Nature scenes without `simple.gin` take 30-60+ minutes due to full asset
  generation.
- The intermediate `.blend` files show placeholder bounding boxes in the
  Blender viewport, which is by design. Full geometry is only generated
  during the Cycles render pass.

## Contributing this package recipe to conda-forge

Both Infinigen and `bpy` are open source. Infinigen and its
dependencies are good candidates to contribute as conda package recipes to
[conda-forge](https://conda-forge.org/). See the
[conda-forge documentation about contributing packages](https://conda-forge.org/docs/maintainer/adding_pkgs/)
to learn more about the process. The recipe provided here is a good starting
point, but is not ready to contribute as-is. Recipes in conda-forge
feedstocks must follow stricter conventions to inter-operate with the full
set of conda-forge packages.
