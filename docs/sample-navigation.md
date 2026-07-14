# Choose samples for your Deadline Cloud journey

This page is a routing guide. It helps you choose a delivery and integration boundary, then points
to working samples. For architecture, security, and implementation details, follow the linked
[AWS Deadline Cloud developer guide](https://docs.aws.amazon.com/deadline-cloud/latest/developerguide/index.html) topics.

## Run a new DCC or application

Start with the canonical guidance for
[deploying custom software on workers](https://docs.aws.amazon.com/deadline-cloud/latest/developerguide/deploy-custom-software.html)
and [building jobs](https://docs.aws.amazon.com/deadline-cloud/latest/developerguide/building-jobs.html).
Choose the least privileged delivery method that fits the application:

* **Already available on the worker:** request the existing package from a queue environment and
  focus on the OpenJD job. Compare [Blender render](../job_bundles/blender_render/) with the
  [default Conda queue environment](../queue_environments/conda_queue_env_from_console.yaml).
* **Versioned application or runtime, no administrator install required:** build a Conda package,
  publish it to a channel, and activate it with a queue environment. Start with the
  [Conda recipes guide](../conda_recipes/), [package build job](../conda_recipes/conda_build_linux_package/),
  and [portable inline Conda environment](../queue_environments/conda_queue_env_inline.yaml).
* **Administrator install or machine-level configuration required:** use a
  [host configuration script](https://docs.aws.amazon.com/deadline-cloud/latest/developerguide/smf-admin.html)
  on service-managed fleets. Start with [3ds Max](../host_configuration_scripts/3dsmax/) or use the
  [installer-to-host-config agent skill](../skills/host-config-from-installer/).
* **Container-first application:** use the [Blender container](../containers/blender/blender-aswf-ci-base/)
  as the application-image example and the [AL2023 worker-equivalent image](../containers/al2023-deadline/)
  for local compatibility work. For fully controlled hosts and images, evaluate customer-managed fleets.

Then model the work: use [job development progression](../job_bundles/job_dev_progression/) to choose
parameters, steps, dependencies, and scripts; use [Maya CLI render](../job_bundles/maya_cli_render/)
for a small DCC command-line example. If the application needs a persistent integration process rather
than a simple CLI, review the OpenJD adaptor pattern in the developer guide before designing it.

## Install custom plugins

Read the canonical [Plugin Sync](https://docs.aws.amazon.com/deadline-cloud/latest/developerguide/plugin-sync.html)
and [custom software delivery](https://docs.aws.amazon.com/deadline-cloud/latest/developerguide/deploy-custom-software.html)
guidance first. Choose based on change rate, installation behavior, and privilege:

* **Plugin Sync:** use it for supported DCC packages when plugin files can be staged in the job
  attachments S3 bucket and copied into DCC-specific locations as the software environment activates.
  It avoids rebuilding an application package for frequent plugin-file changes. See the implementations
  in [Houdini 21.0](../conda_recipes/houdini-21.0/), [Blender 5.1](../conda_recipes/blender-5.1/),
  [Maya 2026](../conda_recipes/maya-2026/), and [Nuke 17](../conda_recipes/nuke-17.0/).
* **Conda package:** use it when a plugin can install without administrator access and should be
  versioned, resolved, cached, and activated with the DCC. Start with the
  [Blender plugin bundle](../conda_recipes/blender-plugin-bundle/),
  [After Effects plugin bundle](../conda_recipes/aftereffects-plugin-bundle/), or a renderer recipe
  such as [V-Ray for Maya](../conda_recipes/maya-vray-2026/).
* **Host configuration:** use it when the vendor installer needs administrator privileges, writes
  machine-wide state, installs services or drivers, or cannot be safely repackaged. Start with
  [After Effects and Red Giant](../host_configuration_scripts/aftereffects/aftereffects_redgiant/),
  [Cinema 4D and Red Giant](../host_configuration_scripts/cinema4d/cinema4d_redgiant/), or the
  [3ds Max plugin combinations](../host_configuration_scripts/3dsmax/).

Keep licensing separate from file delivery. The [license-limit submission hook](../submission_hooks/license_limits/)
shows one way to attach schedulable license requirements; the developer guide covers supported licensing models.

## Integrate studio tools into the job lifecycle

Use the canonical guides for [submitting from an application](https://docs.aws.amazon.com/deadline-cloud/latest/developerguide/from-within-applications.html),
[configuring jobs with environments](https://docs.aws.amazon.com/deadline-cloud/latest/developerguide/configure-jobs.html),
and [Deadline Cloud EventBridge events](https://docs.aws.amazon.com/deadline-cloud/latest/developerguide/eventbridge-integration.html).
Pick the narrowest lifecycle boundary that owns the behavior:

* **Pre-submission:** validate policy, discover assets, or enrich the job before it reaches Deadline
  Cloud. Use [submission hooks](../submission_hooks/) for cross-job policy such as
  [license limits](../submission_hooks/license_limits/); use a custom in-application submitter when
  artist context and DCC state are required, as in the [FuzzyPixel Maya submitter](../job_bundles/custom_submitters/fuzzypixel_maya/).
* **Session enter/exit:** initialize a costly runtime once for one or more tasks and tear it down at
  session end. Queue environments apply to all compatible jobs; job environments travel with one
  bundle. Compare the [queue environments](../queue_environments/) with the
  [daemon-process](../job_bundles/job_env_daemon_process/),
  [environment-variable](../job_bundles/job_env_vars/), and
  [command-injection](../job_bundles/job_env_with_new_command/) examples.
* **Step and task actions:** put deterministic workload and publishing commands in OpenJD steps;
  express ordering with step dependencies and parallelism with task parameter spaces. See
  [Maya export then Arnold render](../job_bundles/maya_arnold_ass_export_render/) and
  [Blender render, encode, and publish to Flow](../job_bundles/blender_turntable_to_flow/).
* **Service events:** react outside the worker after jobs or other resources change state. Route
  EventBridge events to a durable integration target; start with
  [job event Slack notifications](../cloudformation/notification_templates/job_events_slack_lambda/).

Use [FFmpeg movie from job output](../job_bundles/ffmpeg_movie_from_job_output/) when post-processing
should be an explicitly submitted downstream job, and [the job attachments uploader](../utility_scripts/upload_to_job_attachments/)
when an external tool needs to stage assets before submission.
