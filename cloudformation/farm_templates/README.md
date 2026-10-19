# AWS Deadline Cloud farm CloudFormation templates

These deployable CloudFormation samples create farms or add fleet infrastructure and automation to an existing Deadline Cloud deployment.

## Sample index

This table lists the deployable samples below `farm_templates/`.

| Sample | What it demonstrates | Start here when |
|---|---|---|
| [Starter farm](starter_farm/) | A general-purpose farm, queue, service-managed fleets, and package-build support | You need a complete first farm |
| [CUDA farm](cuda_farm/) | A farm with a CUDA-capable fleet and package-build queue | You need GPU workers for CUDA workloads |
| [SMF with VPC and FSx](smf_vpc_fsx/) | Private VPC resource access and FSx for OpenZFS storage | Service-managed workers need shared storage or private services |
| [SMF capacity manager](smf_capacity_manager/) | Automated balancing of Wait and Save and Spot fleet capacity | You operate hybrid service-managed fleets |
| [Fleet standby scheduling](fleet_standby_scheduling/) | Scheduled warm standby worker counts | Worker startup latency matters during predictable hours |
| [CMF fleet health check](cmf_templates/) | Continuous health monitoring for an autoscaling customer-managed fleet | You need alarms for fleet capacity or health problems |
| [macOS CMF with an EC2 Mac worker](cmf_templates/macos_cmf/) | A macOS customer-managed fleet on an EC2 Mac Dedicated Host, with the worker agent bootstrapped from user data | You need macOS render nodes in a customer-managed fleet |

[`apply-conda-queue-env.py`](apply-conda-queue-env.py) is support tooling used to apply a queue environment. It is not a separately deployable sample and is excluded from the table.
