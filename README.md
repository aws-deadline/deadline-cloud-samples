# AWS Deadline Cloud samples

Build, submit, and operate real workloads on [AWS Deadline Cloud](https://aws.amazon.com/deadline-cloud/).
Start with the task you want to complete; each sample stays self-contained in its existing directory.

## What do you want to do?

| Goal | Start here |
|---|---|
| Deploy a farm | [CloudFormation starter farm](cloudformation/farm_templates/starter_farm/) or [Terraform starter farm](terraform/farm_templates/starter_farm/) |
| Learn how a job is structured | [Job development progression](job_bundles/job_dev_progression/) or the [minimal job](job_bundles/simple_job/) |
| Render with a DCC | [Blender render](job_bundles/blender_render/), [Maya CLI render](job_bundles/maya_cli_render/), or browse [all job bundles](SAMPLES.md#openjd-job-bundles) |
| Provide applications to workers | [Conda recipes](conda_recipes/), [queue environments](queue_environments/), or [worker containers](containers/) |
| Install software or plugins | [Custom-plugin journey](docs/sample-navigation.md#install-custom-plugins) and [host configuration scripts](host_configuration_scripts/) |
| Connect studio systems | [Studio-integration journey](docs/sample-navigation.md#integrate-studio-tools-into-the-job-lifecycle) |
| Find a specific example | Browse the generated [sample catalog](SAMPLES.md) by goal, type, or journey |
| Create a sample with an AI agent | Use the task-specific guides in [skills](skills/) |

The human-edited [`sample_catalog.json`](sample_catalog.json) is also available for tools and automation.
Its schema is [`sample_catalog.schema.json`](sample_catalog.schema.json).

## Quick start

1. Configure a Deadline Cloud farm and install the
   [Deadline Cloud CLI](https://docs.aws.amazon.com/deadline-cloud/latest/developerguide/submit-jobs-how.html).
   If you need a farm, deploy one of the starter templates above.
2. Clone this repository and open its root directory.
3. Preview a job's submission interface:

   ```console
   deadline bundle gui-submit job_bundles/gui_control_showcase
   ```

4. Submit the minimal job to your configured queue:

   ```console
   deadline bundle submit job_bundles/simple_job
   ```

Read each sample's README before deployment or submission. Samples can create billable AWS resources
or run licensed software; review parameters, IAM permissions, licensing, and cleanup instructions first.

## Featured examples

* **[Job development progression](job_bundles/job_dev_progression/)** grows one OpenJD job through four maintainable stages.
* **[Blender turntable to Flow Production Tracking](job_bundles/blender_turntable_to_flow/)** renders, encodes, and publishes review media as a multi-step studio workflow.
* **[Plugin bundle for Blender](conda_recipes/blender-plugin-bundle/)** packages a collection of add-ons for repeatable delivery.
* **[Cached Conda queue environment](queue_environments/conda_queue_env_improved_caching.yaml)** reuses software environments across sessions.
* **[License-limit submission hook](submission_hooks/license_limits/)** injects host requirements before submission.
* **[After Effects and Red Giant host configuration](host_configuration_scripts/aftereffects/aftereffects_redgiant/)** installs software that needs administrative privileges.

## Recent highlights

This is a curated selection of noteworthy additions and updates, not an exhaustive chronology.

* **2026-07-14 — [After Effects and Red Giant host configuration](host_configuration_scripts/aftereffects/aftereffects_redgiant/):** consolidated application and plugin installation.
* **2026-07-10 — [Job event Slack notifications](cloudformation/notification_templates/job_events_slack_lambda/):** connects Deadline Cloud events to Lambda through EventBridge.
* **2026-07-08 — [Pip package delivery](job_bundles/pip_package_job/):** pairs a job with the new [pip queue environment](queue_environments/pip_queue_env.yaml); a [self-contained variant](job_bundles/pip_self_contained_job/) is included too.
* **2026-07-07 — [Houdini 21.0 recipe](conda_recipes/houdini-21.0/):** adds Plugin Sync support.
* **2026-06-25 — [Blender turntable to Flow Production Tracking](job_bundles/blender_turntable_to_flow/):** demonstrates render-to-review publishing.

See the catalog's curated [recent highlights](SAMPLES.md#recent-highlights) for more.

## Choose a path for a larger journey

The [sample navigation guide](docs/sample-navigation.md) gives short decision paths—not full architecture walkthroughs—for:

* [running a new DCC or application](docs/sample-navigation.md#run-a-new-dcc-or-application);
* [installing custom plugins](docs/sample-navigation.md#install-custom-plugins); and
* [integrating studio tools into the job lifecycle](docs/sample-navigation.md#integrate-studio-tools-into-the-job-lifecycle).

Each path links to the canonical Deadline Cloud developer guide for design details and then routes back
to the strongest implementations in this repository.

## Repository map

| Area | Use it for |
|---|---|
| [CloudFormation](cloudformation/) | Deploy starter farms, fleet support, storage, capacity automation, and notifications. |
| [Terraform](terraform/) | Deploy a starter farm with Terraform. |
| [Job bundles](job_bundles/) | Define OpenJD rendering, simulation, ML, scientific, and utility jobs. |
| [Conda recipes](conda_recipes/) | Build applications, adaptors, renderers, and plugins into versioned packages. |
| [Containers](containers/) | Build worker-compatible or application container images. |
| [Queue environments](queue_environments/) | Prepare Conda, Rez, pip, caching, and licensing once per worker session. |
| [Host configuration scripts](host_configuration_scripts/) | Install privileged software and configure service-managed fleet worker hosts. |
| [Submission hooks](submission_hooks/) | Inspect or modify job bundles immediately before submission. |
| [Utility scripts](utility_scripts/) | Automate supporting tasks such as uploading job attachments. |
| [Agent skills](skills/) | Give coding agents repeatable instructions for authoring jobs, packages, and host configs. |

For every discoverable sample—including explicit support-directory exclusions—use the
[complete generated catalog](SAMPLES.md).

## Documentation

* [AWS Deadline Cloud developer guide](https://docs.aws.amazon.com/deadline-cloud/latest/developerguide/index.html)
* [AWS Deadline Cloud user guide](https://docs.aws.amazon.com/deadline-cloud/latest/userguide/index.html)
* [AWS Deadline Cloud API reference](https://docs.aws.amazon.com/deadline-cloud/latest/APIReference/index.html)
* [Open Job Description specification](https://github.com/OpenJobDescription/openjd-specifications/wiki)
* [Contributing a sample](CONTRIBUTING.md#adding-or-updating-a-sample)

## Security

If you discover a potential security issue, notify AWS Security through the
[vulnerability reporting page](https://aws.amazon.com/security/vulnerability-reporting/) or
[email AWS Security](mailto:aws-security@amazon.com). Do not create a public GitHub issue.

## License

This repository is licensed under the [MIT-0 License](LICENSE).
