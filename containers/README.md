# AWS Deadline Cloud container samples

These samples provide Dockerfiles and related resources for building container images compatible with [AWS Deadline Cloud](https://aws.amazon.com/deadline-cloud/) worker environments.

## Sample index

This table covers the user-selectable container samples below `containers/`. Supporting scripts and image assets remain with their sample.

| Sample | What it demonstrates | Start here when |
|---|---|---|
| [AL2023 worker-equivalent image](al2023-deadline/) | Reproducing a point-in-time service-managed fleet package set on Amazon Linux 2023 | You need to test packages or software against worker-compatible system libraries |
| [Blender application container](blender/blender-aswf-ci-base/) | Packaging Blender, the Deadline Cloud adaptor, and GPU support in an application image | You want to render Blender workloads from a purpose-built container |
| [Maya application container](maya/maya-aswf-ci-base/) | Packaging Autodesk Maya 2027, the Deadline Cloud adaptor, and optional Arnold, V-Ray and Redshift renderers from your own licensed installers | You want to render Maya workloads from a purpose-built container with the exact DCC and renderer builds you qualified |

The worker-equivalent image is useful for local compatibility work and package builds. The Blender and Maya images are application-container examples and include their own deployment resources and instructions; the Maya sample also shows how to build an image from commercial installers that you supply yourself.
