# AWS Deadline Cloud samples

Build, submit, and operate real workloads on [AWS Deadline Cloud](https://aws.amazon.com/deadline-cloud/).
Start with the task you want to complete; each sample stays self-contained in its existing directory.

## What do you want to do?

| Goal | Start here |
|---|---|
| Deploy a farm | [CloudFormation starter farm](cloudformation/farm_templates/starter_farm/) or [Terraform starter farm](terraform/farm_templates/starter_farm/) |
| Learn how a job is structured | [Job development progression](job_bundles/job_dev_progression/) or the [minimal job](job_bundles/simple_job/) |
| Render with a DCC | [Blender render](job_bundles/blender_render/), [Maya CLI render](job_bundles/maya_cli_render/), or browse the [job bundles](job_bundles/) |
| Run a new DCC or application | Follow the [application delivery path](#run-a-new-dcc-or-application), then browse jobs, packages, host scripts, or containers |
| Deliver custom plugins | Follow the [plugin delivery path](#deliver-custom-plugins), then compare package, Plugin Sync, and host-install examples |
| Connect studio systems | Follow the [job lifecycle path](#integrate-studio-tools-into-the-job-lifecycle) for submission, session, task, and event integrations |
| Find a specific example | Use the [repository map](#repository-map), then browse that area's complete category table |
| Create a sample with an AI agent | Inspect [skills](skills/) for a matching task guide |

### Run a new DCC or application

Read the developer guide on [deploying custom software on workers](https://docs.aws.amazon.com/deadline-cloud/latest/developerguide/deploy-custom-software.html)
and [building jobs](https://docs.aws.amazon.com/deadline-cloud/latest/developerguide/building-jobs.html), then choose the narrowest delivery boundary:
use [Conda recipes](conda_recipes/) and [queue environments](queue_environments/) for versioned user-space software,
[host configuration scripts](host_configuration_scripts/) for privileged installation, or [containers](containers/) for container-first workloads.
Model the work with [job development progression](job_bundles/job_dev_progression/) or start from a DCC example in the
[job bundle table](job_bundles/README.md#job-bundle-index).

### Deliver custom plugins

Start with the developer guide for [Plugin Sync](https://docs.aws.amazon.com/deadline-cloud/latest/developerguide/plugin-sync.html)
and [custom software delivery](https://docs.aws.amazon.com/deadline-cloud/latest/developerguide/deploy-custom-software.html).
Use Plugin Sync for frequently changing supported-DCC files, a [Conda recipe](conda_recipes/) for versioned plugins that install without
administrator access, or a [host configuration script](host_configuration_scripts/) for machine-wide vendor installers.
Compare the [Blender plugin bundle](conda_recipes/blender-plugin-bundle/), [Houdini 21 with Plugin Sync](conda_recipes/houdini-21.0/),
and [3ds Max plugin combinations](host_configuration_scripts/3dsmax/).

### Integrate studio tools into the job lifecycle

Use the canonical guides for [submitting from an application](https://docs.aws.amazon.com/deadline-cloud/latest/developerguide/from-within-applications.html),
[configuring jobs with environments](https://docs.aws.amazon.com/deadline-cloud/latest/developerguide/configure-jobs.html), and
[Deadline Cloud EventBridge events](https://docs.aws.amazon.com/deadline-cloud/latest/developerguide/eventbridge-integration.html).
Choose [submission hooks](submission_hooks/) or a [custom submitter](job_bundles/custom_submitters/) before submission;
[queue environments](queue_environments/) or job environments for session setup; OpenJD steps for task and publishing actions, as in
[Blender turntable to Flow](job_bundles/blender_turntable_to_flow/); and [notification templates](cloudformation/notification_templates/)
for service-event integrations.

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
| [Contributor documentation](docs/) | Use the adaptable sample README starting point. |
| [Repository validation](scripts/) | Run unit, local-link, and live external-link checks. |

Each sample area README declares its tracked scope and provides a complete local index. Nested collection
READMEs provide their own complete tables, while the root routes users to recommended paths rather than
duplicating every sample.

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
