# AWS Deadline Cloud container samples

These samples provide Dockerfiles and related resources for building container images compatible with [AWS Deadline Cloud](https://aws.amazon.com/deadline-cloud/) worker environments.

## Sample index

This table covers both user-selectable container samples below `containers/`; supporting scripts and image assets remain with their sample.

| Sample | What it demonstrates | Start here when |
|---|---|---|
| [AL2023 worker-equivalent image](al2023-deadline/) | Reproducing a point-in-time service-managed fleet package set on Amazon Linux 2023 | You need to test packages or software against worker-compatible system libraries |
| [Blender application container](blender/blender-aswf-ci-base/) | Packaging Blender, the Deadline Cloud adaptor, and GPU support in an application image | You want to render Blender workloads from a purpose-built container |

The worker-equivalent image is useful for local compatibility work and package builds. The Blender image is an application-container example and includes its own deployment resources and instructions.
