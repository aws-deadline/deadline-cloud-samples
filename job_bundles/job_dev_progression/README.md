# Job Development Progression

When you're developing a job bundle to run on AWS Deadline Cloud, you will likely start with something simple. As you add more options and split the workload into smaller pieces that run in parallel, the complexity of your job will grow.

This directory documents four stages you can take your job bundle through as you develop it. It starts with a single self-contained job template and ends at a Python package bundled with script entry points and unit tests.

This example is built around Python, but the ideas apply to any language. Adapt them to your language toolchain of choice.

## Stage index

This table covers every immediate sample directory in `job_dev_progression/`.

| Sample | What it demonstrates | Start here when |
|---|---|---|
| [Stage 1: self-contained template](stage_1_self_contained_template/) | Keeping parameters and Python commands in one OpenJD template | You are prototyping a small job with minimal files |
| [Stage 2: bundled scripts](stage_2_bundled_scripts/) | Moving executable logic into scripts carried with the bundle | Inline commands are becoming hard to read or reuse |
| [Stage 3: shared script library](stage_3_bundled_scripts_shared_lib/) | Sharing common code across multiple bundled entry points | Multiple steps need the same helper logic |
| [Stage 4: bundled Python package](stage_4_bundled_python_package/) | Packaging modules, entry points, and unit tests together | The workload needs maintainable, testable application structure |

## Running jobs on Deadline Cloud

To run these jobs on Deadline Cloud, you need a farm in your AWS account.
The [quickstart in the Deadline Cloud console](https://docs.aws.amazon.com/deadline-cloud/latest/userguide/getting-started.html)
or the [starter farm CloudFormation sample](../../cloudformation/farm_templates/starter_farm/) are two ways to deploy one.
In both cases, the farm includes a queue environment that can provide a Conda virtual environment for the jobs.

With the Deadline Cloud CLI installed locally (such as with `pip install deadline`), the following command submits the first stage to your farm:

```console
deadline bundle submit stage_1_self_contained_template
```

You can view your job and its log output from [Deadline Cloud monitor](https://docs.aws.amazon.com/deadline-cloud/latest/userguide/working-with-deadline-monitor.html).

## Running jobs locally

You can run jobs locally for development or as a way to use one code base locally and on your farm.
Use the [Open Job Description CLI](https://github.com/OpenJobDescription/openjd-cli#readme), available from `pip install openjd-cli`.

Each job template defines two parameters that specify the software environment it expects. You can install the applications yourself or use an environment template to provide the Conda packages. See the [sample queue environments](../../queue_environments/) and note that you need Conda installed for the inline Conda environments.

If the required software is already in `PATH`, run the job directly. If `polars` is unavailable, the log reports an error such as `ModuleNotFoundError: No module named 'polars'`.

```console
openjd run stage_1_self_contained_template/template.yaml
```

The [console-equivalent Conda queue environment](../../queue_environments/conda_queue_env_from_console.yaml) creates a fresh virtual environment in the job session directory:

```console
openjd run --environment ../../queue_environments/conda_queue_env_from_console.yaml stage_1_self_contained_template/template.yaml
```

The [improved-caching Conda queue environment](../../queue_environments/conda_queue_env_improved_caching.yaml) names environments from a hash of channels and packages, then reuses them and refreshes them after a configurable delay. It eventually removes stale environments:

```console
openjd run --environment ../../queue_environments/conda_queue_env_improved_caching.yaml stage_1_self_contained_template/template.yaml
```
