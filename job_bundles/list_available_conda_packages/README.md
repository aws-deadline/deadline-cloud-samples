# List Available Conda Packages Job Bundle

This job bundle lists all available conda packages in the deadline-cloud-v2 channel using `conda search -c deadline-cloud-v2 '*'` and prints the list into the logs.

The deadline-cloud-v2 channel is the current channel for service-managed fleets. It has every version in the legacy deadline-cloud channel, plus newer versions such as Houdini 22.0 and Maya 2027. To list the legacy channel instead, set the `CondaChannel` parameter to `deadline-cloud`.

In the [AWS Deadline Cloud docs](https://docs.aws.amazon.com/deadline-cloud/latest/userguide/create-queue-environment.html#conda-queue-environment), you can find a list of the available Conda packages with their major and minor versions and why pinning only up to the minor version is recommended.
