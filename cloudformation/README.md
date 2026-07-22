# AWS Deadline Cloud sample CloudFormation templates

With [AWS CloudFormation](https://aws.amazon.com/cloudformation/), you can deploy Deadline Cloud infrastructure as code. Use these samples directly or as starting points for custom templates.

## Sample index

This table covers all deployable leaf samples below `cloudformation/`. The subcategory READMEs provide the same samples grouped by purpose.

| Sample | What it demonstrates | Start here when |
|---|---|---|
| [Starter farm](farm_templates/starter_farm/) | A farm, queue, service-managed fleets, and package-build support | You need a general-purpose Deadline Cloud starting environment |
| [CUDA farm](farm_templates/cuda_farm/) | A farm with a CUDA-capable fleet and package-build queue | You need GPU compute for CUDA jobs |
| [SMF with VPC and FSx](farm_templates/smf_vpc_fsx/) | VPC resource endpoints and FSx for OpenZFS shared storage | Service-managed workers need private VPC resources |
| [SMF capacity manager](farm_templates/smf_capacity_manager/) | Balancing Wait and Save and Spot capacity with Lambda and EventBridge Scheduler | A hybrid fleet should maintain target capacity cost-effectively |
| [Fleet standby scheduling](farm_templates/fleet_standby_scheduling/) | Time-based changes to a fleet's warm standby worker count | You want faster business-hours starts without full-time idle capacity |
| [CMF fleet health check](farm_templates/cmf_templates/) | Lambda, EventBridge, CloudWatch alarms, and optional SNS for fleet health | A customer-managed autoscaling fleet needs continuous monitoring |
| [Budget event notifications](notification_templates/budget_events_notification/) | Deadline budget events delivered through SNS and AWS Chatbot | You need email or Slack alerts when budget thresholds are reached |
| [Job event Slack notifications](notification_templates/job_events_slack_lambda/) | EventBridge invoking Lambda to post completion and failure messages | Studio automation should react to Deadline Cloud job state changes |

Browse the [farm templates](farm_templates/) or [notification templates](notification_templates/) category for a focused index and setup context.
