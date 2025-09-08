# NeRF Studio conda package recipe

## Package contents

This is a [rattler-build](http://rattler.build/) recipe for NeRF Studio and some extras. If you build this package, you can
use it to train Gaussian Splatting on AWS Deadline Cloud.

The package you build from this recipe will include the following:

1. [NeRF Studio](https://docs.nerf.studio/).
2. The external model [Splatfacto in the Wild](https://docs.nerf.studio/nerfology/methods/splatw.html).
3. Dependencies of NeRF Studio that don't have packages on [conda-forge](https://conda-forge.org/) yet.
   If you look in [recipe.yaml](recipe/recipe.yaml), the lists of host and run dependencies document many
   of these in comments, including via transitive dependencies.
4. The [nerfstudio/gsplat](https://github.com/nerfstudio-project/gsplat#readme) package's examples, to make its
   simple_trainer.py example available. A wrapper shell script makes it available as a command `gsplat_simple_trainer`.
5. The [KevinXu02/splatfacto-w](https://github.com/KevinXu02/splatfacto-w#readme) package's export_script.py to
   export models from Splatfacto in the Wild to the .ply format. A wrapper shell script makes it available
   as a command `splatfactow_export`.

The specific versions built are selected from recent git commits of the projects. The recipe implementation
[recipe.yaml](recipe/recipe.yaml) and [build.sh](recipe/build.sh) includes comments to explain what it does.

## Building the package

You can build this package on a Deadline Cloud farm that is configured for package build jobs that update
the S3 conda channel and has a CUDA fleet to run the build. This document focuses on building with Deadline
Cloud, but you could [run rattler-build](http://rattler.build/latest/highlevel/#how-to-run-rattler-build)
yourself if you set up a suitable environment.

Deploy [this CloudFormation template](../../cloudformation/farm_templates/cuda_farm/README.md) to get a CUDA Deadline
Cloud farm in your account. Read the AWS Deadline Cloud developer documentation
[create a conda channel using S3](https://docs.aws.amazon.com/deadline-cloud/latest/developerguide/configure-jobs-s3-channel.html)
to learn more about the deployment.

Submit a job to build the package from the [conda_recipes](..) directory of
the Deadline Cloud samples github as follows. If you need to customize this, see the [conda recipe samples README](../README.md).

```
$ ./submit-package-job nerfstudio
```

The recipe pins dependency package versions to ranges around versions that ran correctly together. This should
keep the recipe stable over time as new versions are released, but please open an issue or a pull request if you
try to build it and run into errors.

## Environment caching in your Deadline Cloud queue environment

We recommend that you use the sample queue environment
[conda_queue_env_improved_caching.yaml](../../queue_environments/conda_queue_env_improved_caching.yaml) to reuse conda environments between jobs.
This queue environment can save significant time and bandwidth as the dependency closure of NeRF Studio consists of
many packages containing multiple gigabytes of data.

## Gaussian Splatting on Deadline Cloud

Once you have this package built and indexed in your S3 conda channel, you can use it to train your own Gaussian Splatting.
Learn how to do this in the [gsplat_pipeline job bundle README](../../job_bundles/gsplat_pipeline/README.md).

## Contributing this package recipe to conda-forge

Conda-forge provides community-led recipes, infrastructure, and distributions for conda. NeRF Studio and all of
its dependencies are open source libraries, and great candidates to contribute as conda package recipes
to [conda-forge](https://conda-forge.org/). See the
[conda-forge documentation about contributing packages](https://conda-forge.org/docs/maintainer/adding_pkgs/)
to learn more about the process.

The sample recipe provided here is a good starting point, but is not ready to contribute. It bundles more than
ten library dependencies together with NeRF Studio and uses the ability for a recipe to turn off binary relocation
so that shared object binary dependencies from PyPI will work in the runtime environment. Recipes in conda-forge
feedstocks must follow stricter conventions to inter-operate with the full set of conda-forge packages.
Feel free to take the code here and transform it as necessary if you're interested in making this contribution.