# Pip Self-Contained Job

This job bundle demonstrates managing [pip](https://pip.pypa.io/) packages
entirely **within the job bundle**, with no queue environment required. The
template defines its own Open Job Description
[job environment](https://github.com/OpenJobDescription/openjd-specifications/wiki/2023-09-Template-Schemas#4-environment)
that creates a Python virtual environment, installs the requested packages into
it, and adds it to the `PATH` for all steps of the job.

Use this style when you want a self-contained bundle that runs on any Linux
worker with `python3` available, without configuring anything on the queue. If
you would rather define the pip environment once and share it across many jobs,
see the [`pip_package_job`](../pip_package_job) sample and the
[`pip_queue_env.yaml`](../../queue_environments/pip_queue_env.yaml) queue
environment instead.

This is the pip analogue of an inline job environment; compare it with the
[`job_env_with_new_command`](../job_env_with_new_command) sample.

## Prerequisites

- A Linux worker with `python3` available on the `PATH`. Deadline Cloud
  service-managed fleets satisfy this.

## Submit the job

```bash
deadline bundle submit job_bundles/pip_self_contained_job
```

By default it installs the [`cowsay`](https://pypi.org/project/cowsay/) package
and prints a message. Override the parameters to install your own packages:

```bash
deadline bundle submit job_bundles/pip_self_contained_job \
  -p PipPackages="requests rich" \
  -p Message="Hello from pip"
```

## Test it locally

You can run the job locally using the
[Open Job Description CLI](https://github.com/OpenJobDescription/openjd-cli):

```bash
openjd run job_bundles/pip_self_contained_job/template.yaml --step SayHello
```
