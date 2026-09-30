# Docker Engine for CPU container jobs

This host configuration installs Docker Engine and common job utilities on
Amazon Linux 2023 service-managed fleet workers. Use it for Linux jobs that run
CPU-only application containers, including the
[OpenDroneMap simple job](../../job_bundles/opendronemap_simple_job/).

## Installed components

1. Installs Docker, download/archive tools, Python 3, and `runuser` with `dnf`.
2. Enables and starts the Docker daemon.
3. Adds Deadline Cloud's `job-user` account to the `docker` group.
4. Verifies the daemon as both `root` and `job-user`.

The script fails if the host is not Amazon Linux 2023-compatible, `job-user` is
missing, Docker is inactive, or the job user cannot reach the daemon.

## Security

Membership in the `docker` group is effectively root-equivalent access to the
worker. A job can mount the host filesystem or launch a privileged container.
Use a dedicated fleet for trusted container jobs, restrict who can submit to
its queue, and do not use this configuration as a sandbox for untrusted code.

## Create a compatible fleet

Use the standard Deadline Cloud console workflow to create the farm,
job-attachment queue, S3 bucket, and service roles. You do not need a
CloudFormation template or custom image. To create a fleet:

1. Create or select a farm and a queue with job attachments enabled.
2. Create a service-managed fleet using Linux and `x86_64`. Set its minimum
   worker count to zero, choose a bounded maximum worker count, and configure CPU
   and memory ranges that satisfy the host requirements of jobs using the fleet.
3. Add a custom fleet attribute named `attr.DockerEngine` with the value
   `available`. Container job templates can require this capability so they
   cannot run on a Linux fleet where this configuration was not applied.
   For disk-intensive jobs, also add a custom fleet amount named
   `amount.WorkerScratchGiB`; set its minimum and maximum to the root volume
   size in GiB so Deadline can enforce each job's scratch estimate.
4. In **Host configuration**, paste the complete contents of
   [`linux.sh`](linux.sh) into the script field and set the timeout to at least
   600 seconds. Deadline runs the script as `root` when it launches each new
   worker.
5. Associate the fleet with the queue.
6. Temporarily set the minimum worker count to one. In the fleet's CloudWatch
   host configuration log, confirm the final message is
   `Docker Engine setup complete`.
7. Restore the minimum worker count to zero so the fleet can scale to zero.

Configuration changes apply only to workers launched after the update.

### Apply the script with the AWS CLI

The console is the shortest path for a new fleet because it can create the
required service roles. To apply or update this script on an existing fleet
from the repository root:

```console
python3 -c 'import json, pathlib; print(json.dumps({
    "scriptBody": pathlib.Path(
        "host_configuration_scripts/docker_engine/linux.sh"
    ).read_text(),
    "scriptTimeoutSeconds": 600,
}))' > /tmp/deadline-docker-host-config.json

aws deadline update-fleet \
    --farm-id farm-0123456789abcdef0123456789abcdef \
    --fleet-id fleet-0123456789abcdef0123456789abcdef \
    --host-configuration file:///tmp/deadline-docker-host-config.json \
    --profile my-profile \
    --region us-west-2
```

The fleet must already have the `attr.DockerEngine=available` custom attribute.
Disk-intensive fleets also need `amount.WorkerScratchGiB`, with its minimum and
maximum set to the root volume size in GiB. Scale existing workers to zero
before launching a replacement worker, because an in-service worker does not
rerun the updated host configuration.

## Prerequisites

- Amazon Linux 2023 service-managed fleet workers.
- Outbound access to the configured Amazon Linux package repositories.
- Enough worker disk for Docker layers and job scratch data.

The script does not install an NVIDIA driver or container toolkit. Use the
[Docker and NVIDIA Container Toolkit](../docker_nvidia_container_toolkit/)
configuration for GPU containers.
