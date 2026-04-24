# AWS Deadline Cloud container samples

The container samples in this directory provide Dockerfiles and related resources
for building container images compatible with
[AWS Deadline Cloud](https://aws.amazon.com/deadline-cloud/) worker environments.

Use these to build and test software locally with the same system libraries,
toolchains, and runtime environment as Deadline Cloud workers.

## Samples

### AL2023 worker-equivalent image

The [al2023-deadline](al2023-deadline/) sample provides a Dockerfile that
replicates the package set of the Deadline Cloud service-managed fleet (SMF)
worker AMI on top of the base Amazon Linux 2023 image. Use it to build and test
[conda packages](../conda_recipes/) or other software that must be compatible
with the worker runtime.
