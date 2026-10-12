# AWS Deadline Cloud farm for NVIDIA Isaac Sim

## Introduction

This CloudFormation template deploys an AWS Deadline Cloud farm for running
[NVIDIA Isaac Sim](https://developer.nvidia.com/isaac/sim) in a container on a
GPU service-managed fleet. It is the fastest route from an empty account to
running the [`isaacsim_replicator_sdg` job bundle](../../../job_bundles/isaacsim_replicator_sdg/README.md).

Like [cuda_farm](../cuda_farm/README.md), this is an example of specializing the
[starter_farm sample](../starter_farm/README.md). The differences are:

* One Linux GPU fleet, with the **Docker software add-on** so workers have a
  container runtime.
* The accelerator selections are narrowed to RT-capable GPUs, because Isaac
  Sim's RTX renderer needs RT Cores.
* A 500 GiB root volume by default, because Docker stores images on the root
  volume and the Isaac Sim image is large.
* The queue role can pull from one Amazon ECR repository.
* No Conda queue environment. Isaac Sim arrives in the container image, not as
  a Conda package.

## How the container pieces fit

Two things are needed and the stack creates both:

* The fleet declares `softwareAddOns: [{ name: docker }]`, which installs
  rootless Docker at `/opt/deadline/docker-rootless`.
* The queue gets a [Docker container queue environment](../../../queue_environments/docker_queue_env.yaml),
  whose enter action starts that daemon, authenticates to Amazon ECR, pulls your
  image, and runs each task inside a session container.

This combination is verified: a fleet with the add-on and **no host
configuration script** started the daemon, pulled a 9 GB Isaac Sim image, and
rendered to completion.

The image URI is a queue environment parameter rather than a stack parameter, so
pass it per job:

```bash
deadline bundle submit . -p DockerImage=<ECR_IMAGE_URI>
```

The embedded template is not wrapped in `!Sub`, because its scripts use 19 shell
`${VAR}` references that CloudFormation would try to interpolate.

## Prerequisites

1. **An S3 bucket** for job attachments. You need the name to deploy.
2. **A Deadline Cloud monitor**, so you can watch jobs. From the
   [Deadline Cloud console](https://console.aws.amazon.com/deadlinecloud/home),
   choose "Go to Monitor setup".
3. **GPU service quota above zero.** This one catches people out, so read the
   next section before deploying.
4. **An NVIDIA NGC account**, to pull the Isaac Sim base image. See
   [containers/isaacsim-replicator](../../../containers/isaacsim-replicator/README.md).

### Raise your GPU quota first

The default quota for GPUs on service-managed fleets is **zero**, for both Spot
and On-Demand. A new account cannot start a single GPU worker until an increase
is approved, and approval is not instant. Request it before you need it.

In the [Service Quotas console](https://console.aws.amazon.com/servicequotas/home)
choose **AWS Deadline Cloud** and request an increase for whichever you plan to
use:

| Quota | Code |
|---|---|
| Spot G Instance GPUs per region | `L-2CCF07BF` |
| OnDemand G instance GPUs per region | `L-5D6BA491` |

Two things about how the quota is consumed:

* It counts a fleet at its **worst case** — `MaxWorkerCount` multiplied by the
  maximum GPUs per instance — summed across every service-managed fleet in the
  Region, **whether or not any worker is running**. A fleet with
  `MaxWorkerCount: 8` holds 8 GPUs of quota while idle.
* Spot and On-Demand are **separate** quotas. Exhausting one leaves the other
  untouched, which is a useful fallback when Spot capacity is scarce.

So request at least `MaxWorkerCount` GPUs for the market type you choose, plus
whatever your existing fleets already hold.

## Setup instructions

### 1. Deploy the template

```bash
aws cloudformation deploy \
    --template-file deadline-cloud-isaacsim-farm-template.yaml \
    --stack-name deadline-cloud-isaacsim-farm \
    --capabilities CAPABILITY_NAMED_IAM \
    --parameter-overrides JobAttachmentsBucketName=YOUR_BUCKET_NAME
```

Useful overrides: `InstanceMarketType=on-demand` if Spot GPU capacity is scarce
in your Region, and `MaxWorkerCount` to match your approved quota.

### 2. Build and push the container image

Follow [containers/isaacsim-replicator](../../../containers/isaacsim-replicator/README.md).
It is a short Dockerfile over NVIDIA's NGC base image. Note the resulting image
URI; you need it in the next step.

The `EcrRepositoryName` parameter scopes the queue role's pull permission, so
use the same repository name in both places. Deploy again with a new value if
you push somewhere else.

### 3. Submit a job

```bash
deadline config set defaults.farm_id <FarmId from the stack outputs>
deadline config set defaults.queue_id <QueueId from the stack outputs>

cd ../../../job_bundles/isaacsim_replicator_sdg
deadline bundle submit . -p DockerImage=<ECR_IMAGE_URI>
```

A first run on a cold worker spends roughly two and a half minutes pulling the
image and around six minutes compiling the Kit shader cache before the first
frame, so budget about ten minutes. Later runs on a warm worker start in
seconds.

## Clean up

```bash
aws cloudformation delete-stack --stack-name deadline-cloud-isaacsim-farm
```

The ECR repository, its images, and the job attachments bucket survive the
stack.

## Troubleshooting

**The job sits in READY and no worker appears.** Check the fleet's
`autoScalingStatus`. `GROWING` with `workerCount: 0` means Deadline Cloud wants
a worker and EC2 will not give it one: either your GPU quota is exhausted (see
above) or Spot capacity is scarce. Spot starvation for a GPU fleet can last tens
of minutes; redeploy with `InstanceMarketType=on-demand` to use the separate
On-Demand quota.

**Every session fails in the queue environment's enter action.** Confirm the
fleet reports the `docker` software add-on, and that the queue role can reach
the repository named in `EcrRepositoryName`. An image URI that does not exist,
or a tag that was never pushed, fails here rather than at task run.

**Tasks fail immediately with a Python or Kit error.** The Docker queue
environment never runs the image's `ENTRYPOINT`, so environment variables the
base image's entrypoint would normally set — `EXP_PATH`, `CARB_APP_PATH` — are
not present. Job scripts must not depend on them. The SDG bundle passes its Kit
experience file explicitly for this reason.
