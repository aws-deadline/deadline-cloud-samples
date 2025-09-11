# List Available Conda Packages Job Bundle

This job bundle lists all available conda packages in the deadline-cloud channel using `conda search -c deadline-cloud '*'` and prints the list into the logs.

In the [AWS Deadline Cloud docs](https://docs.aws.amazon.com/deadline-cloud/latest/userguide/create-queue-environment.html#conda-queue-environment), you can find a list of the available Conda packages with their major and minor versions and why pinning only up to the minor version is recommended.
