# KNFSD cross-region NFS cache for a service-managed fleet (Terraform)

## What this sample demonstrates

This Terraform configuration deploys an [AWS Deadline Cloud](https://aws.amazon.com/deadline-cloud/)
**service-managed fleet (SMF)** whose workers read from a **distant NFS filer through a
[KNFSD](https://github.com/awslabs/knfsd-file-cache) read cache**, connected with a
[VPC resource endpoint](https://docs.aws.amazon.com/deadline-cloud/latest/developerguide/smf-vpc.html).

The filer — an [Amazon FSx for OpenZFS](https://docs.aws.amazon.com/fsx/latest/OpenZFSGuide/what-is-fsx.html)
file system — is deployed in a **second AWS region** and reached over a VPC peering
connection. That cross-region distance stands in for an **on-premises or otherwise-distant
filer**, and is what makes a cache worth having: cache misses pay cross-region latency and
inter-region data-transfer cost, while cache hits are served from the KNFSD proxy's RAM and
local NVMe next to the workers.

```
   Region A (compute)                                   Region B (origin)
 +-----------------------------+                      +----------------------+
 | Deadline Cloud SMF workers  |   resource endpoint  |                      |
 |   (AWS-managed VPC)         |  (Deadline-managed   |                      |
 |        | mount NFS          |   private DNS)       |                      |
 |        v                    |                      |                      |
 |  VPC Lattice resource gw ---+-- VPC Lattice -------+  (your compute VPC)  |
 |        |                    |                      |        |             |
 |        v                    |                      |        | VPC peering |
 |  KNFSD proxy (RAM L1 +      |---- NFSv3 over ------+--------+-----------> | FSx for OpenZFS
 |   local NVMe L2 cache)      |     peering link     |        |             |  (distant filer)
 +-----------------------------+                      +----------------------+
```

> **When is this pattern worth it?** KNFSD earns its place when the origin is **distant or
> bandwidth-limited** (on-premises, cross-region, or a throughput-capped filer) **and** many
> workers repeatedly read the same data (render/simulation asset libraries). For a filer in
> the *same* region and AZ as the fleet, a cache adds a hop for little benefit — mount the
> file system directly instead. This sample deploys cross-region specifically so the cache has
> something to do; it is the reproducible stand-in for the on-premises case you cannot ship in
> a repository.

## Prerequisites

1. [Terraform](https://www.terraform.io/downloads) >= 1.5 and `git` (Terraform clones the
   KNFSD module from GitHub during `terraform init`).
2. AWS credentials for an account where Deadline Cloud is available, with permissions across
   **both** the compute and origin regions.
3. [Packer](https://www.packer.io/) to build the KNFSD proxy AMI (see Setup step 1). There is
   no public or managed KNFSD AMI.
4. The [`deadline` CLI](https://pypi.org/project/deadline/) (`pip install deadline`) to submit
   the seed and benchmark jobs.
5. A Deadline Cloud monitor to view jobs (optional but recommended); see the
   [starter farm README](../starter_farm/README.md).

## How it works

Service-managed fleet workers run in an AWS-managed VPC. The
[VPC resource endpoints](https://docs.aws.amazon.com/deadline-cloud/latest/developerguide/smf-vpc.html)
feature lets them reach a resource in your VPC through VPC Lattice. This sample places a KNFSD
caching proxy behind that endpoint, and points KNFSD at an FSx for OpenZFS filer in another
region across a VPC peering connection.

| Resource | Region | Description |
|----------|--------|-------------|
| `aws_vpc` / subnets / NAT / IGW (x2) | A + B | Non-overlapping compute and origin VPCs |
| `aws_vpc_peering_connection` (+ accepter, routes) | A and B | Cross-region link the cache reads over |
| `aws_fsx_openzfs_file_system` | B | The distant origin filer (NFSv3) |
| `module.knfsd` (ASG + NLB and more) | A | KNFSD NFS caching proxy cluster |
| `aws_vpclattice_resource_gateway` / `aws_vpclattice_resource_configuration` | A | The resource endpoint into the compute VPC |
| `awscc_ram_resource_share` | A | Shares the resource configuration to `fleets.deadline.amazonaws.com` |
| `awscc_deadline_farm` / `awscc_deadline_queue` / `awscc_deadline_fleet` / `awscc_deadline_queue_fleet_association` | A | The Deadline Cloud farm, queue, and SMF |
| `aws_iam_role` (x2) + policies | A | Fleet and queue roles (see Troubleshooting for the required logs permission) |

Some behaviors are load-bearing and easy to get wrong:

- **The fleet role must grant `logs:CreateLogStream`** (plus `PutLogEvents` / `GetLogEvents`)
  scoped to `/aws/deadline/<farmId>/*`. Without it, SMF workers register but the agent cannot
  create its log stream, so workers get stuck in `CREATED`, never run jobs, and emit no logs.
  The `AWSDeadlineCloud-FleetWorker` managed policy does **not** include CloudWatch Logs. This
  sample adds the inline policy, mirroring the
  [starter-farm fleet role](../../../cloudformation/farm_templates/starter_farm/deadline-cloud-starter-farm-template.yaml).
- **Workers reach the share via a Deadline-managed name**, not the KNFSD or FSx DNS name:
  `<resource_config_id>.resource-endpoints.deadline.<region>.amazonaws.com`.
- **KNFSD re-exports the origin's export path verbatim.** FSx for OpenZFS exports `/fsx`, so
  workers mount `<endpoint>:/fsx` — mounting `/` returns `access denied by server`.
- **Cross-region wiring:** KNFSD points at the FSx file system's **private IP** (the primary
  network interface's IP; `endpoint_ip_address` is only populated for Multi-AZ deployments) and
  reads over the peering link, because the FSx private DNS name does not resolve across regions.
  Traffic through the resource endpoint is one-way NAT, so the NFS mount uses
  `nfsvers=3,proto=tcp,noresvport,nolock`.
- Deadline Cloud resources are only in the **AWSCC** provider; in-place fleet configuration
  updates can fail validation, so change fleet configuration with `terraform apply -replace`.

## Setup

### 1. Build the KNFSD proxy AMI (one-time, in the compute region)

```bash
git clone https://github.com/awslabs/knfsd-file-cache.git
cd knfsd-file-cache/image
cat > image.pkrvars.hcl <<EOF
REGION = "us-west-2"   # your compute_region
ARCH   = ["amd64"]     # match the fleet's x86_64 workers
EOF
packer init .
packer build -var-file=image.pkrvars.hcl .
# Note the resulting AMI ID for knfsd_proxy_ami.
```

### 2. Deploy the infrastructure

```bash
cp terraform.tfvars.example terraform.tfvars
# edit: compute_region, origin_region, knfsd_proxy_ami

terraform init      # clones the pinned KNFSD module from GitHub
terraform apply
```

## Run or submit

Seed the origin once, then run the fan-out read benchmark:

```bash
FARM=$(terraform output -raw farm_id)
QUEUE=$(terraform output -raw queue_id)

# Populate the distant filer with a synthetic asset library (run once).
deadline bundle submit ./job_bundles/seed --farm-id "$FARM" --queue-id "$QUEUE"

# Fan-out read benchmark: N concurrent tasks read the shared library.
deadline bundle submit ./job_bundles/benchmark --farm-id "$FARM" --queue-id "$QUEUE" \
  -p FanoutTasks=16 -p ReadFilesPerTask=200
```

### Measuring the cache benefit

The cache's value shows up in three ways; measure at least the first two:

1. **Origin offload (the clearest signal).** In CloudWatch, watch the FSx origin's
   `DataReadBytes` as you increase `FanoutTasks`. With the cache, origin reads stay **flat**
   after the working set is warm — the fleet's read fan-out is absorbed by KNFSD, not paid
   cross-region every time.
2. **Cold versus warm.** The first benchmark run (or first task on a fresh KNFSD node) pays
   cross-region misses; re-running reads the same files from cache. Compare `throughput_MiBps`
   and `seconds` in the task logs between the cold and warm runs.
3. **Fan-out scaling.** Aggregate read throughput across tasks rises with `FanoutTasks` when
   cached, but is capped by the origin's cross-region bandwidth when not.

To compare **against no cache**, deploy a second fleet whose resource endpoint targets the FSx
IP directly (skip the `module.knfsd` layer) and run the same benchmark; the direct-mount fleet
reads cross-region on every access.

#### Measured results

A run of this sample (compute in `us-west-2`, origin FSx for OpenZFS in `us-east-1`, one
`i3en.2xlarge` KNFSD node, a 2-worker Spot fleet, 16 tasks x 150 files x 16 MiB = 38.4 GiB of
reads over the shared library):

- **Per-task read throughput (cold to warm):** the first task to touch the working set ran at
  about **19 MiB/s** (paying cross-region latency on every miss); once the set was warm in
  KNFSD, tasks ran at about **230-600 MiB/s** — roughly a **13x-30x speedup** on the cached path.
- **Origin offload:** during the benchmark window the FSx origin in `us-east-1` served about
  **0 MiB** of `DataReadBytes` while the fleet read 38.4 GiB, because KNFSD absorbed the fan-out
  from its RAM and NVMe cache.

Your numbers will vary with region pair, instance type, working-set size, and fan-out width.
The point is the *shape*: cold reads are slow and hit the distant origin; warm reads are fast
and local, and the origin stays quiet.

## Parameters and outputs

Key input variables (see [`variables.tf`](variables.tf) for the full set and defaults):

| Variable | Default | Purpose |
|---|---|---|
| `compute_region` | `us-west-2` | Region A: KNFSD, resource endpoint, and the SMF |
| `origin_region` | `us-east-1` | Region B: the FSx for OpenZFS origin (must differ) |
| `knfsd_proxy_ami` | (required) | KNFSD AMI built in Setup step 1 |
| `knfsd_instance_type` | `i3en.2xlarge` | KNFSD proxy instance (local NVMe for the L2 cache) |
| `fleet_market_type` | `spot` | Fleet EC2 market type |

Seed and benchmark job parameters are documented in
[`job_bundles/seed/template.yaml`](job_bundles/seed/template.yaml) and
[`job_bundles/benchmark/template.yaml`](job_bundles/benchmark/template.yaml).

Outputs (see [`outputs.tf`](outputs.tf)) include `farm_id`, `queue_id`, `fleet_id`, the KNFSD
NLB address, and the worker-facing `worker_resource_endpoint_dns_name`.

## Security, cost, and cleanup

This is an **advanced** sample and is not free to run: two regions, two VPCs with NAT gateways,
a cross-region peering connection, an FSx for OpenZFS file system, a KNFSD EC2 instance
(`i3en`/`i4i` for local NVMe), a Network Load Balancer, VPC Lattice, **and inter-region data
transfer** for every cache miss.

The example NFS export options (`no_root_squash`, world-writable demo mount) favor simplicity;
tighten ownership and export ACLs on the origin for production use.

```bash
# Drain fleet workers first (set min/max to 0 via the console or update-fleet), then:
terraform destroy
```

Deleting the VPC Lattice resource configuration can briefly fail while a Deadline-managed
endpoint association is still releasing; re-run `terraform destroy` once and it completes.

## Troubleshooting

- **Workers stay in `CREATED` and never run jobs, with no logs.** The fleet role is missing
  `logs:CreateLogStream`. This sample includes it; if you adapt the role, keep that permission.
- **`mount.nfs: access denied by server`.** You are mounting the wrong export path. KNFSD
  re-exports `/fsx`; mount `<endpoint>:/fsx`, not `/`.
- **KNFSD exports nothing (`showmount -e localhost` is empty).** The proxy discovered the
  origin at boot before the origin IP was available; terminate the KNFSD instance so the Auto
  Scaling group relaunches one with the correct configuration.
- **Fleet configuration change fails to apply in place.** Use `terraform apply -replace='awscc_deadline_fleet.this'`.

## Related resources

- [Connect VPC resources to your SMF with VPC resource endpoints](https://docs.aws.amazon.com/deadline-cloud/latest/developerguide/smf-vpc.html)
- [CloudFormation `smf_vpc_fsx` reference](../../../cloudformation/farm_templates/smf_vpc_fsx/)
- [Terraform starter farm](../starter_farm/)
- [KNFSD (awslabs/knfsd-file-cache)](https://github.com/awslabs/knfsd-file-cache) — Apache-2.0, referenced here and not vendored
