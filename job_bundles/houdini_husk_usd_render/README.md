# SideFX Houdini Husk USD Render

## Background

Husk is a CLI application provided with SideFX Houdini that renders Universal Scene Description(USD) files.
By default Husk renders using the Houdini Karma renderer but Husk supports any Hydra-compatible USD render delegate. 


## Job Summary

This job bundle renders a USD scene using the Houdini [husk](https://www.sidefx.com/docs/houdini/ref/utils/husk.html) CLI.

To run it, you will need a Houdini/Husk installation available in the PATH in one of the following ways:

* As a conda package when your queue has a conda queue environment set up to provide virtual environments for jobs.
**  For more information see the developer guide section [Provide applications for your jobs.](https://docs.aws.amazon.com/deadline-cloud/latest/developerguide/provide-applications.html)
* Installed on the worker hosts that run the job. You can customize your Deadline Cloud queues, fleets, and this job to fit your own production pipeline.


The core of this job is an embedded template file that invokes
the Houdini  `husk` command. The command is a template that substitutes job parameters and the
frame task parameter.

The `husk` command is part of an Open Job Description step. 
It expands to a task per frame by defining a parameter space using the Frames job parameter. 
It limits the fleets it will run on by including host requirements for Linux. 
The KarmaXPU engine can optionally be used to render on a GPU. 
If you intend to use KarmaXPU you must uncomment the `amount.worker.gpu` host requirement to ensure the job is scheduled on an appropriate worker. 
Please note that when using the Karma rendering engine that a Karma license must be available. Usaged-based Karma license are available automatically from Deadline Cloud when using a service-managed fleet.

The rest of the job template consists of the parameter definitions. This metadata specifies
the names, types, and descriptions of each parameter, along with information on what user
interface controls a GUI should use.
The [Deadline Cloud CLI command `deadline bundle gui-submit`](https://docs.aws.amazon.com/deadline-cloud/latest/developerguide/from-a-terminal.html#with-a-submission-window)
uses this metadata to generate its UI. Please note that if the USD file refers to any external asset files such as textures, models, or materials
these files must be made available to the job. When using a service-managed fleets you must use job attachments. 
When using a customer-managed fleet you may use job attachments or alternatively use [storage profiles](https://docs.aws.amazon.com/deadline-cloud/latest/userguide/storage-shared.html) to use shared storage.

### Automatic Dependency Discovery (Submission Hook)

This job bundle includes a **pre-submission hook** (`hooks.yaml`) that automatically discovers all USD file dependencies (textures, materials, sublayers, references, etc.) and adds them as job attachments before submission. No manual file attachment is needed.

To use the hook:

1. Install the `usd-core` Python package:
   ```
   pip3 install usd-core
   ```

2. Enable bundle hooks in your Deadline Cloud configuration:
   ```
   deadline config set settings.allow_bundle_hooks true
   ```

3. Submit the job bundle directly:
   ```
   deadline bundle gui-submit job_bundles/houdini_husk_usd_render
   ```
   or
   ```
   deadline bundle submit job_bundles/houdini_husk_usd_render
   ```

The hook will introspect the USD scene file specified in the `USDSceneFile` parameter, find all dependent files, and add them as input attachments automatically. It will also warn if no camera is found in the scene.

### Legacy Script (generate_usd_job.py)

Alternatively, you can use the included `generate_usd_job.py` script to manually generate a job bundle with pre-resolved dependencies. This requires both `usd-core` and `deadline` Python packages:
```
pip3 install usd-core deadline
python3 generate_usd_job.py my_scene.usd
```
This script will generate a new job bundle with job attachment references for required assets and open the submission UI.

Please note that husk will not render your scene if no camera is included. Both the hook and the legacy script will warn you if this is the case.

Only a few husk parameters are included for demonstration purpose. Please see the [husk documentation](https://www.sidefx.com/docs/houdini/ref/utils/husk.html) for reference.


## Additional Renderers

In addition to the default Karma renderers (BRAY_HdKarma and BRAY_HdKarmaXPU), this job bundle also supports V-Ray and Redshift renderers through their Hydra render delegates:

* **HdVRayRendererPlugin** - V-Ray for Houdini renderer
* **HdRedshiftRendererPlugin** - Redshift for Houdini renderer

To use these renderers, you must set up V-Ray for Houdini or Redshift for Houdini in your environment. One option to do this is by using the Conda sample recipes available in this repository:

* **V-Ray 7 for Houdini:** [houdini-vray-7](../../conda_recipes/houdini-vray-7/)
* **Redshift 2025 for Houdini:** [houdini-redshift-2025](../../conda_recipes/houdini-redshift-2025/)
* **Redshift 2026 for Houdini:** [houdini-redshift-2026](../../conda_recipes/houdini-redshift-2026/)

These conda recipes can be used to create conda packages that include the necessary renderer plugins. Please refer to the individual recipe README files for specific setup instructions and licensing requirements.


## Sample Asset

sample.usda is a simple scene containing a cube and a sphere. 
This scene contains no external assets and can be rendered without
using the `generate_usd_job.py` script or attaching any other files

This work by the Deadline Cloud team is marked with [CC0 1.0](https://creativecommons.org/publicdomain/zero/1.0/?ref=chooser-v1)
