# Job Development Progression

When you're developing a job bundle to run on AWS Deadline Cloud, you will
likely start with something simple. As you add more options and split the workload
into smaller pieces that run in parallel, the complexity of your job
will grow.

This directory documents four stages you can take your job bundle through as
you develop it. It starts with a single self-contained job template, and
ends at a Python package bundled with all the trappings like script entrypoints
and unit tests.

While this example is built around Python, the ideas are not Python-specific.
Feel free to adapt them to your language toolchain of choice.

## Running jobs on Deadline Cloud

To run these jobs on Deadline Cloud, you need a farm in your AWS account.
The [quickstart in the Deadline Cloud console](https://docs.aws.amazon.com/deadline-cloud/latest/userguide/getting-started.html)
or the [starter_farm sample CloudFormation template](https://github.com/aws-deadline/deadline-cloud-samples/tree/mainline/cloudformation/farm_templates/starter_farm#readme)
are two ways to deploy one. In both cases, the farm will include a queue environment that can
provide a conda virtual environment for the jobs.

With the Deadline Cloud CLI installed locally, e.g. from `pip install deadline`,
the following command will submit the first stage to your farm:

```bash
$ deadline bundle submit stage_1_self_contained_template
```

You can view your job and its log output from [Deadline Cloud monitor](https://docs.aws.amazon.com/deadline-cloud/latest/userguide/working-with-deadline-monitor.html).

## Running jobs locally

You can run jobs locally for development or as a way to use one code base locally and on your farm.
Use the [Open Job Description CLI](https://github.com/OpenJobDescription/openjd-cli#readme),
available to install from `pip install openjd-cli`.

In each job template, you'll find two parameters defined that specify the software
environment it expects to run in. You can either provide the necessary applications by
installing them yourself, or you can use an environment template to provide the conda packages.
See the [sample environment templates](https://github.com/aws-deadline/deadline-cloud-samples/tree/mainline/queue_environments#readme),
and note that you will need conda installed in order for them to work.

If you have set up all the required software in the `PATH` environment variable, you can run
the job directly. If `polars` is not installed, the job will fail with an error in the log
like `ModuleNotFoundError: No module named 'polars'`.

```bash
$ openjd run stage_1_self_contained_template/template.yaml
```

If you run the jobs with the [conda_queue_env_console_equivalent](https://github.com/aws-deadline/deadline-cloud-samples/blob/mainline/queue_environments/conda_queue_env_console_equivalent.yaml)
sample, it will create a conda virtual environment within the job's session directory.
This creates a fresh conda environment every time you run the job.

```bash
$ openjd run --environment ../../queue_environments/conda_queue_env_console_equivalent.yaml stage_1_self_contained_template/template.yaml
```

If you run the jobs with the [conda_queue_env_improved_caching](https://github.com/aws-deadline/deadline-cloud-samples/blob/mainline/queue_environments/conda_queue_env_improved_caching.yaml)
sample, it will take the hash of requested channels and packages, and use a named channel based on that hash. When
the named channel already exists, it will reuse it directly. After a configurable delay, it will refresh the packages,
and after a longer delay, it will remove the environment.

```bash
$ openjd run --environment ../../queue_environments/conda_queue_env_improved_caching.yaml stage_1_self_contained_template/template.yaml
```
