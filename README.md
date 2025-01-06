## Deadline Cloud samples

This repository contains a set of samples to use with [AWS Deadline Cloud](https://aws.amazon.com/deadline-cloud/).

## CloudFormation template samples

The [cloudformation](cloudformation) directory contains sample CloudFormation templates you can use to
deploy a Deadline Cloud farm or other infrastructure to work with your farm. The [starter_farm sample](cloudformation/farm_templates/starter_farm/)
is a good place to start. Other samples include event notification and health checks for customer-managed fleets.

## Job bundle samples

The [job_bundles](job_bundles) directory contains sample jobs that you can submit to your Deadline Cloud queue. You can use the
[Deadline Cloud CLI](https://github.com/aws-deadline/deadline-cloud) to submit these jobs to your queues.

The [Open Job Description Specifications](https://github.com/OpenJobDescription/openjd-specifications) repository
has more samples that you can use with [AWS Deadline Cloud](https://aws.amazon.com/deadline-cloud/).

### CLI job submission

```
$ deadline bundle submit job_bundles/cli_job -p DataDir=~/data_dir
```

### GUI job submission
```
$ deadline bundle gui-submit job_bundles/gui_control_showcase
```

![deadline bundle gui-submit showcase](.images/deadline-bundle-gui-submit-showcase.png)

## Conda recipes

The [conda_recipes](conda_recipes) directory contains samples and tooling for building conda packages for your
Deadline Cloud queues. You can use the `submit-package-job` tool to submit
build jobs to your queue. See [this blog post](https://aws.amazon.com/blogs/media/create-a-conda-package-and-channel-for-aws-deadline-cloud/)
for instructions on how to configure your Deadline Cloud farm for building and
using an Amazon S3 conda channel.

## Queue environment samples

The [queue_environments](queue_environments) directory contains
sample [queue environments](https://docs.aws.amazon.com/deadline-cloud/latest/userguide/create-queue-environment.html)
you can attach to your Deadline Cloud queue, to provide software applications to your jobs from
[Conda](https://docs.conda.io/projects/conda/) or [Rez](https://rez.readthedocs.io/).

## Additional resources

* [AWS Deadline Cloud user guide](https://docs.aws.amazon.com/deadline-cloud/latest/userguide/index.html)
* [AWS Deadline Cloud developer guide](https://docs.aws.amazon.com/deadline-cloud/latest/developerguide/index.html)
* [AWS Deadline Cloud API reference](https://docs.aws.amazon.com/deadline-cloud/latest/APIReference/index.html)
* [Open Job Description](https://github.com/OpenJobDescription/openjd-specifications/wiki)

## Security

We take all security reports seriously. When we receive such reports, we will
investigate and subsequently address any potential vulnerabilities as quickly
as possible. If you discover a potential security issue in this project, please
notify AWS/Amazon Security via our [vulnerability reporting page](http://aws.amazon.com/security/vulnerability-reporting/)
or directly via email to [AWS Security](aws-security@amazon.com). Please do not
create a public GitHub issue in this project.

## License

This library is licensed under the MIT-0 License. See the LICENSE file.
