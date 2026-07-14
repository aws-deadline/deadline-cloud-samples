# Pip Package Job

This job bundle demonstrates providing a job's Python dependencies with
[pip](https://pip.pypa.io/) through a **queue environment**. The job itself only
declares the `PipPackages`, `PipIndexUrl`, and `PipExtraIndexUrls` parameters —
the [`pip_queue_env.yaml`](../../queue_environments/pip_queue_env.yaml) queue
environment reads those parameters, builds a Python virtual environment, installs
the packages, and puts the environment on the `PATH` before the step runs.

This is the pip analogue of the Conda samples that pass `CondaPackages` to a
Conda queue environment (see [`monte_carlo_simulation`](../monte_carlo_simulation)).
Use this style when you want to define the pip environment once and share it
across many jobs on a queue.

## Prerequisites

- A queue with the [`pip_queue_env.yaml`](../../queue_environments/pip_queue_env.yaml)
  queue environment added to it. See the
  [queue_environments README](../../queue_environments/README.md) for how to
  create a queue environment.
- A Linux worker with `python3` available on the `PATH`. Deadline Cloud
  service-managed fleets satisfy this.

## Submit the job

```bash
deadline bundle submit job_bundles/pip_package_job
```

By default it installs the [`cowsay`](https://pypi.org/project/cowsay/) package
and prints a message. Override the parameters to install your own packages, for
example:

```bash
deadline bundle submit job_bundles/pip_package_job \
  -p PipPackages="requests rich" \
  -p Message="Hello from pip"
```

To install from a private index such as AWS CodeArtifact, set `PipIndexUrl` (and
optionally `PipExtraIndexUrls`) to the index endpoint.

## Test it locally

You can run the job with the queue environment locally using the
[Open Job Description CLI](https://github.com/OpenJobDescription/openjd-cli):

```bash
openjd run job_bundles/pip_package_job/template.yaml \
  --step SayHello \
  --environment queue_environments/pip_queue_env.yaml \
  --job-param PipPackages=cowsay
```
