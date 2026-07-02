# AWS Deadline Cloud sample Terraform configurations

With [Terraform](https://www.terraform.io/), you can use infrastructure as code to deploy infrastructure
such as a Deadline Cloud farm to your AWS account. Use the samples provided here directly or as a starting point
to create your own custom configurations.

These Terraform configurations use the [AWS Cloud Control (AWSCC) provider](https://registry.terraform.io/providers/hashicorp/awscc/latest)
for Deadline Cloud resources, which offers full support for AWS Deadline Cloud resource types.

## Starter farm

The [starter_farm](farm_templates/starter_farm/) sample Terraform configuration deploys a Deadline Cloud farm you can use to run jobs that render images,
reconstruct 3D scenes, or transform your data in custom ways. This is the Terraform equivalent of the
[CloudFormation starter_farm template](../cloudformation/farm_templates/starter_farm/).
Sample jobs to submit are available in the [deadline-cloud-samples on GitHub](https://github.com/aws-deadline/deadline-cloud-samples).
Deadline Cloud provides many integrated submitter plugins for applications, and you can build your own jobs. The deployed farm includes the ability to
[build custom conda packages](../conda_recipes/README.md) for providing additional application support.

## CloudFormation vs Terraform

Both CloudFormation and Terraform configurations in this repository create equivalent infrastructure.
Choose based on your team's preferences and existing tooling:

| Aspect | CloudFormation | Terraform |
|--------|---------------|-----------|
| Provider | AWS native | HashiCorp |
| Deadline resources | `AWS::Deadline::*` | `awscc_deadline_*` |
| State | Managed by AWS | Local or remote backend |
