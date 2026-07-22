# AWS Deadline Cloud samples

Build, submit, and operate real workloads on [AWS Deadline Cloud](https://aws.amazon.com/deadline-cloud/).
Start with the task you want to complete. Each sample stays self-contained in its existing directory.

## What do you want to do?

| Goal | Start here |
|---|---|
| Deploy a farm | [CloudFormation starter farm](cloudformation/farm_templates/starter_farm/) or [Terraform starter farm](terraform/farm_templates/starter_farm/) |
| Learn how a job is structured | [Job development progression](job_bundles/job_dev_progression/) or the [minimal job](job_bundles/simple_job/) |
| Render with a DCC | [Blender render](job_bundles/blender_render/), [Maya CLI render](job_bundles/maya_cli_render/), or browse the [job bundles](job_bundles/) |
| Run a new DCC or application | Read about [custom software delivery](https://docs.aws.amazon.com/deadline-cloud/latest/developerguide/deploy-custom-software.html), then browse [Conda recipes](conda_recipes/), [host configuration scripts](host_configuration_scripts/), [containers](containers/), and [job bundles](job_bundles/) |
| Deliver custom plugins | Read about [Plugin Sync](https://docs.aws.amazon.com/deadline-cloud/latest/developerguide/plugin-sync.html), then compare [plugin packages](conda_recipes/), [host installations](host_configuration_scripts/), and [queue environments](queue_environments/) |
| Connect studio systems | Browse [submission hooks](submission_hooks/), [custom submitters](job_bundles/custom_submitters/), [queue environments](queue_environments/), and [event notifications](cloudformation/notification_templates/) |
| Find a specific example | Use the [repository map](#repository-map), then browse that area's complete category table |
| Create a sample with an AI agent | Inspect [skills](skills/) for a matching task guide |

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
