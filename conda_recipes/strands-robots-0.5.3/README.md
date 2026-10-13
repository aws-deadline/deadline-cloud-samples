# `strands-robots` conda package recipe

## Package contents

This directory holds a [rattler-build](http://rattler.build/) recipe for
[`strands-robots`](https://strands-labs.github.io/robots/) with the MuJoCo
simulation and [LeRobot](https://github.com/huggingface/lerobot) training
dependencies the [`mujoco_sim_to_policy`](../../job_bundles/mujoco_sim_to_policy/)
job bundle needs. Jobs run entirely inside the package, so no step installs
software or downloads a model while it runs.

The package you build from this recipe will include the following:

1. [`strands-robots` 0.5.3](https://pypi.org/project/strands-robots/), with the
   dependencies of its `sim-mujoco` and `lerobot` extras.
2. [mink 1.3.0](https://pypi.org/project/mink/), the inverse-kinematics library
   the MuJoCo simulation uses.
3. MuJoCo, LeRobot, CUDA PyTorch, FFmpeg and the rest of the dependency closure,
   from conda-forge.
4. The `trs_so_arm100` so100 arm model from
   [MuJoCo Menagerie](https://github.com/google-deepmind/mujoco_menagerie), at the
   commit `robot_descriptions` pins, with `ROBOT_DESCRIPTIONS_CACHE` pointed at it.
5. The ImageNet `resnet18` weights that the LeRobot ACT policy builds its vision
   backbone from, with `TORCH_HOME` pointed at them.

Items 4 and 5 are the two things training would otherwise fetch over the network
on every worker: a `git clone` of Menagerie, and a `torch.hub` download from
`download.pytorch.org`. With both bundled, a job doesn't need access to GitHub, PyPI
or `download.pytorch.org`.

`strands-robots` and `mink` are not on conda-forge. The recipe downloads their
PyPI wheels as sources pinned by SHA256, and the build installs them with
`pip install --no-deps --no-index`. `mink` publishes a compiled wheel for each
platform, and the recipe lists one wheel per platform. Every other dependency is
a conda run requirement and is resolved by the solver.

## Version pins

* **`av >=15,<16`**, the range LeRobot's `av-dep` extra asks for. Later `av`
  releases drop the `av.option` module that LeRobot's video encoder reads codec
  options from. An unpinned solve picks a version that fails on import.
* **`accelerate` and `wandb`**, from LeRobot's `training` extra. `lerobot-train`
  refuses to start without `accelerate`, and imports `wandb` even when the job
  passes `--wandb.enable=false`. Neither arrives through the `strands-robots`
  extras.
* **`pytorch-gpu`**, applied on Linux only. Jobs get CUDA PyTorch, and the
  recipe still builds on a developer machine.
* The **LeRobot `feetech` extra is left out**. It drives real Feetech servos, and
  this package targets simulation.

## Building the package on Deadline Cloud

You can build this package on a Deadline Cloud farm that is configured for
package build jobs that update an S3 conda channel. See the AWS Deadline Cloud
developer guide
[Create a conda channel using S3](https://docs.aws.amazon.com/deadline-cloud/latest/developerguide/configure-jobs-s3-channel.html)
for setup instructions.

Submit a build job from the [conda_recipes](..) directory of the Deadline
Cloud samples repository as follows. If you need to customize this, see the
[conda recipe samples README](../README.md).

```
$ ./submit-package-job strands-robots-0.5.3
```

Everything in the package is pure Python or comes from conda-forge. The build
doesn't need a GPU.

## Building the package locally

You can also build the recipe directly with
[`rattler-build`](https://rattler.build/latest/#installation). From the
`conda_recipes` directory:

```
rattler-build publish strands-robots-0.5.3/recipe/recipe.yaml \
    --to s3://amzn-s3-demo-bucket/Conda/Default \
    -c conda-forge \
    --build-number=+1
```

The recipe's tests import the Python packages, resolve the bundled so100 model,
check the bundled `resnet18` weights, and run `lerobot-train --help`.

## Use with the companion job bundle

See the [mujoco_sim_to_policy](../../job_bundles/mujoco_sim_to_policy/) job
bundle for submitting sim-to-policy jobs against the package built from this
recipe. That bundle's `CondaPackages` parameter defaults to
`strands-robots=0.5.3`. It takes its channels from the queue environment, whose
default `CondaChannels` must list the S3 channel this package is published to
and conda-forge, which provides its dependencies:

```yaml
default: "s3://amzn-s3-demo-bucket/Conda/Default conda-forge deadline-cloud"
```

## Licensing

[`strands-robots`](https://github.com/strands-labs/robots) is distributed under
the Apache-2.0 license, [mink](https://github.com/kevinzakka/mink) under
Apache-2.0, and the
[MuJoCo Menagerie](https://github.com/google-deepmind/mujoco_menagerie) models
under the licenses recorded in each model directory. The `trs_so_arm100` model
this recipe bundles is Apache-2.0. The `resnet18` weights come from
[torchvision](https://github.com/pytorch/vision), which is BSD-3-Clause.

**Note on the package you build from this recipe:** review the licenses of
everything in the dependency closure before redistributing the result. This
repository redistributes no binaries. The recipe fetches them at build time.
