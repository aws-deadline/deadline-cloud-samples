# AWS Deadline Cloud sample Terraform configurations

With [Terraform](https://www.terraform.io/), you can deploy Deadline Cloud infrastructure as code. These configurations use the [AWS Cloud Control (AWSCC) provider](https://registry.terraform.io/providers/hashicorp/awscc/latest), which supports AWS Deadline Cloud resource types.

## Sample index

This table covers every immediate sample directory below `terraform/farm_templates/`.

| Sample | What it demonstrates | Start here when |
|---|---|---|
| [Starter farm](farm_templates/starter_farm/) | A farm, queue, service-managed fleets, and package-build support using AWSCC resources | Your team manages infrastructure with Terraform |
| [KNFSD cross-region cache](farm_templates/knfsd_xregion_cache/) | A service-managed fleet reading a distant NFS filer through a KNFSD read cache over a VPC resource endpoint, deployed cross-region to stand in for an on-premises origin | You cache reads from an on-premises or otherwise-distant filer for a render/simulation fleet |

The starter farm can run rendering, reconstruction, and data-transformation jobs from the [job bundle index](../job_bundles/). It is the Terraform equivalent of the [CloudFormation starter farm](../cloudformation/farm_templates/starter_farm/) and includes support for [building custom Conda packages](../conda_recipes/).

## CloudFormation vs Terraform vs AWS CDK

All three starter configurations create equivalent Deadline Cloud infrastructure. Choose based on your team's existing tooling and state-management practices.

| Aspect | CloudFormation | Terraform | [AWS CDK](../cdk/farm_templates/starter_farm/) |
|---|---|---|---|
| Authoring | YAML template | HCL configuration | TypeScript, compiled to CloudFormation |
| Provider | AWS native | HashiCorp AWSCC | AWS native |
| Deadline resources | `AWS::Deadline::*` | `awscc_deadline_*` | `CfnFarm`, `CfnQueue`, `CfnFleet` |
| State | Managed by AWS | Local or remote backend | Managed by AWS |
| Job attachments bucket | You supply an existing bucket | You supply an existing bucket | Created by the app |
