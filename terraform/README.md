# AWS Deadline Cloud sample Terraform configurations

With [Terraform](https://www.terraform.io/), you can deploy Deadline Cloud infrastructure as code. These configurations use the [AWS Cloud Control (AWSCC) provider](https://registry.terraform.io/providers/hashicorp/awscc/latest), which supports AWS Deadline Cloud resource types.

## Sample index

This table covers every immediate sample directory below `terraform/farm_templates/`.

| Sample | What it demonstrates | Start here when |
|---|---|---|
| [Starter farm](farm_templates/starter_farm/) | A farm, queue, service-managed fleets, and package-build support using AWSCC resources | Your team manages infrastructure with Terraform |

The starter farm can run rendering, reconstruction, and data-transformation jobs from the [job bundle index](../job_bundles/). It is the Terraform equivalent of the [CloudFormation starter farm](../cloudformation/farm_templates/starter_farm/) and includes support for [building custom Conda packages](../conda_recipes/).

## CloudFormation vs Terraform

Both starter configurations create equivalent infrastructure. Choose based on your team's existing tooling and state-management practices.

| Aspect | CloudFormation | Terraform |
|---|---|---|
| Provider | AWS native | HashiCorp AWSCC |
| Deadline resources | `AWS::Deadline::*` | `awscc_deadline_*` |
| State | Managed by AWS | Local or remote backend |
