# After Effects Render - one task

## Use case for this job

This After Effects job bundle allows the user
to submit a job that uses aerender to render a frame range
as a single task. The entire workload renders
on one worker as one command.

It accepts the following job parameters that modify the render:
* Project file
* Comp name
* Input directory
* Output directory
* Start frame
* End frame

This job bundle expects a user to specify an input directory that
contains all the file references that are required to render.
Generally, the project file should be within this directory to
ensure relative paths are preserved.
