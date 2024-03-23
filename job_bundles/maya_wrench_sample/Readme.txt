wrench.ma and wrench_turtable.ma have been setup with relative paths.

Each file has a corresponding job bundle, that you can submit using the AWS Deadline Cloud CLI.

$ deadline bundle gui-submit wrench_jobbundle

$ deadline bundle gui-submit wrench_turntable_jobbundle

Relative paths are based upon the location and setting of a workspace.mel file.
The workspace.mel must be included with the assets and the user must set the project to this workspace.mel

The process for setting up relative paths includes
* Changing reference paths in reference editor
* Finding and replacing keys for all absolute paths
* Finding plugs based upon found search keys
* Using path editor to replace a list of found paths that need to be replaced.
