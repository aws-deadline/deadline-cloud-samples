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

These job attachments may be attached manually or by using the included `generate_usd_job.py` script.

This script introspects the USD file and find all files required by the USD stage to render.
To use this script you must have the usd-core and deadline python libraries available in your python installation.
`pip3 install usd-core deadline` 
Then run the script to find required files
`python3 generate_usd_job.py my_scene.usd`
This script will generate a new job bundle with job attachment references for required assets and will preset the input USD file to the file you selected.
After running, this script will open the Deadline Cloud job submissions UI. You may select which queue to use and further adjust job parameters such as resolution before submitting.

Please note that husk will not render your scene if no camera is included. the `generate_usd_job.py` script will warn you if this is the case.

Only a few husk parameters are included for demonstration purpose. Please see the [husk documentation](https://www.sidefx.com/docs/houdini/ref/utils/husk.html) for reference.


## Sample Asset

sample.usda is a simple scene containing a cube and a sphere. 
This scene contains no external assets and can be rendered without
using the `generate_usd_job.py` script or attaching any other files

This work by the Deadline Cloud team is marked with [CC0 1.0](https://creativecommons.org/publicdomain/zero/1.0/?ref=chooser-v1)
