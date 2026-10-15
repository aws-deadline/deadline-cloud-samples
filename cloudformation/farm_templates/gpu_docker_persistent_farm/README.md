# GPU container farm with a persistent model cache

Creates a Deadline Cloud farm for GPU container workloads that download large model weights.
The stack covers a farm, a queue, a Linux GPU fleet with the Docker software add-on and a
persistent EBS volume, and the queue-fleet association.

Deploy this before running the
[Cosmos 3 dream trajectories](../../../job_bundles/cosmos3_dream_trajectories/) job bundle,
which expects this arrangement. Nothing here is specific to that sample. It suits any
containerized GPU job whose image or weights are too large to re-fetch per session.

| Resource | Why it is shaped this way |
|---|---|
| `AWS::Deadline::Farm` | |
| `AWS::Deadline::Queue` | `jobRunAsUser` left unset, so actions run as the worker-agent user the Docker add-on prepares a daemon for |
| `AWS::Deadline::Fleet` | `SoftwareAddOns: [docker]`, one `l40s` GPU, and a `PersistentVolumeConfiguration` for the model cache |
| `AWS::Deadline::QueueFleetAssociation` | |
| Queue IAM role | Job attachments, job logs, and **ECR pull**, which the Docker queue environment needs on the host |
| Fleet IAM role | `AWSDeadlineCloud-FleetWorker` plus farm-scoped CloudWatch Logs |

**The queue environment is not created here.** It lives at
[`queue_environments/docker_queue_env.yaml`](../../../queue_environments/docker_queue_env.yaml)
and is versioned there, so inlining a copy would guarantee the two drift apart. The stack's
`CreateQueueEnvironmentCommand` output prints the command that adds it.

## Request GPU quota first

**A new AWS account has a GPU instance quota of zero.** The stack will deploy fine and the
fleet will simply never start a worker, which looks like a Deadline Cloud problem and is not.
Raise the quota before you deploy, because approval is not always instant.

Service-managed fleets use the same EC2 quotas as any other EC2 usage, and **Spot and
On-Demand are separate quotas**. The `l40s` chip is the `g6e` instance family, which falls
under the G and VT quotas:

```console
# On-Demand, measured in vCPUs
aws service-quotas list-service-quotas --service-code ec2 \
    --query "Quotas[?contains(QuotaName, 'On-Demand G and VT')].[QuotaCode,QuotaName,Value]" \
    --output table

# Spot, measured in vCPUs
aws service-quotas list-service-quotas --service-code ec2 \
    --query "Quotas[?contains(QuotaName, 'G and VT Spot')].[QuotaCode,QuotaName,Value]" \
    --output table
```

Request an increase with the returned quota code:

```console
aws service-quotas request-service-quota-increase \
    --service-code ec2 --quota-code QUOTA_CODE --desired-value 48
```

Or in the console: **Service Quotas** then **AWS services** then **Amazon EC2**, and search
for "G and VT".

This quota behaves in three ways that catch people out:

* **It is consumed at worst case, not by what is running.** The reservation is
  `MaxWorkerCount` times the vCPUs per instance, summed across **every** service-managed
  fleet in the Region, whether or not any worker exists. A forgotten fleet with a high
  `MaxWorkerCount` starves a new one.
* **It is per Region.** Capacity for a GPU chip also varies by Region. A Region with quota
  does not always have capacity.
* **It is counted in vCPUs, not instances.** One `g6e.2xlarge` is 8 vCPUs, so
  `MaxWorkerCount: 2` needs at least 16, and the default `MaxVcpu: 48` lets the fleet pick a
  larger instance that consumes up to 48.

When Spot capacity for your chip is unavailable, the fleet stays at zero workers and reports
no error. Switching `InstanceMarketType` to `on-demand` tests for that, and it is the default
here for that reason.

## Deploy

An S3 bucket for job attachments has to exist already.

```console
aws cloudformation deploy \
    --template-file deadline-cloud-gpu-docker-persistent-farm-template.yaml \
    --stack-name deadline-gpu-docker-farm \
    --capabilities CAPABILITY_NAMED_IAM \
    --parameter-overrides JobAttachmentsBucketName=YOUR_BUCKET
```

Then add the queue environment, from the repository root:

```console
aws cloudformation describe-stacks --stack-name deadline-gpu-docker-farm \
    --query "Stacks[0].Outputs[?OutputKey=='CreateQueueEnvironmentCommand'].OutputValue" \
    --output text
```

Run what it prints, then set the queue environment's `DockerImage` to your ECR image URI and
its `PersistentVolumeMountPath` to the stack's `PersistentVolumeMountPath` output.

## The persistent volume is what makes the cache work

Rootless Docker keeps both its image store and the job user's home under `/home/job-user`,
which this volume re-homes. A cached checkpoint and a pulled container image both outlast
worker replacement.

Whether that helps depends on two parameters:

* **`PersistentVolumeMountPath`** must match the queue environment's parameter of the same
  name. If they disagree, the queue environment finds nothing at the path, prints a warning,
  and falls back to a per-session cache. The job still succeeds, just slowly, so this
  mismatch is easy to miss.
* **`PersistentVolumeLastUsedTtlHours`** defaults to 12 in the service. An idle night deletes
  the volume, and the next job downloads everything again. This template
  defaults it to 168 (one week) instead. A longer TTL keeps an EBS volume billing while idle, so
  raising it trades storage cost for startup time.

`PersistentVolumeSizeGiB` defaults to 250. Size it for every model a queue caches rather than
for one, because one large checkpoint is roughly 35 GB.

## Cost

Both the root and persistent EBS volumes bill while they exist, and the persistent volume is
meant to remain after its workers end. `MinWorkerCount` defaults to 0, which keeps an idle
farm free of GPU instances.

To tear everything down:

```console
aws cloudformation delete-stack --stack-name deadline-gpu-docker-farm
```

Delete the queue environment first if the stack deletion reports the queue as in use, and
note that the job attachments bucket is not managed by this stack.
