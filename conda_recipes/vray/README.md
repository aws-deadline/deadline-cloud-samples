# V-Ray conda package recipe

This is a [rattler-build](http://rattler.build/) recipe for
the [VRay standalone renderer](https://docs.chaos.com/display/VNS/V-Ray+Standalone+Home).
See the [sample conda recipes README](../README.md) to learn more about the structure
of the recipe, and [Create a conda channel using S3](https://docs.aws.amazon.com/deadline-cloud/latest/developerguide/configure-jobs-s3-channel.html) in the AWS Deadline Cloud developer guide.

## Download the archive file

- Download the `vraystd_adv_71000_rhel8_clang-gcc-11.2` (x86) or `vraystd_adv_71000_rhel8_arm64_clang-gcc-11.2` (ARM) full download file from [Chaos](https://download.chaos.com/?platform=47&product=47). Note that you will need a Chaos account to access the link. Place the file in
the `conda_recipes/archive_files` directory in your git clone of the
[deadline-cloud-samples](https://github.com/aws-deadline/deadline-cloud-samples) repository.

## Build the package on Deadline Cloud

From the `conda_recipes` directory, run the following command to submit a package build job to your package build farm.

```sh
$ ./submit-package-job vray
```

The `submit-package-job` command can be run from any platform (macOS, Windows, or Linux) - it submits a job to Deadline Cloud where a Linux worker builds the package and uploads it to your S3 conda channel.

**Note**: The queue's IAM role needs `s3:PutObject` permission for the `Conda/*` prefix in the job attachments bucket to publish the built package.
