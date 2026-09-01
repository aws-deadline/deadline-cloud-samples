# V-Ray for Maya conda build recipe

V-Ray 7.40.04 for Maya 2027 on Linux.

## Download the installer file for Linux

Download the `vray_74004_maya2027_dr2_rhel8` installer from
[Chaos](https://download.chaos.com/), which needs a Chaos account, and place it in the
`conda_recipes/archive_files` directory in your git clone of the
[deadline-cloud-samples](https://github.com/aws-deadline/deadline-cloud-samples) repository.

## Use a different V-Ray or Maya version

Update the filename and version in `deadline-cloud.yaml` and `recipe/recipe.yaml`, and the
module name in `recipe/build.sh`. Chaos does not use one naming scheme for every release, so
compare the filename against your download rather than assuming it follows the 2026 pattern.

## Build the package

Build the Maya 2027 package first, since this one depends on it. See the Maya 2027
[README](../maya-2027/README.md) for its installer.

```sh
$ ./submit-package-job maya-2027
$ ./submit-package-job maya-vray-2027
```

## Test it end to end

Render the [maya_vray_render](../../job_bundles/maya_vray_render/) sample. It includes a
V-Ray scene and writes a PNG next to the EXR, so you can confirm the package works by
looking at the output.

```sh
$ deadline bundle submit maya_vray_render
```
