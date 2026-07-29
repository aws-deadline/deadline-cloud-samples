# AWS Deadline Cloud sample AWS CDK apps

With the [AWS Cloud Development Kit](https://aws.amazon.com/cdk/), you can define Deadline Cloud infrastructure in a general-purpose programming language and synthesize it to CloudFormation. These apps are written in TypeScript and use the `aws-cdk-lib/aws-deadline` constructs.

## Sample index

This table covers every immediate sample directory below `cdk/farm_templates/`.

| Sample | What it demonstrates | Start here when |
|---|---|---|
| [Farm templates](farm_templates/starter_farm/) | Example farms assembled from reusable `Farm`, `Queue`, and fleet constructs, from a single-fleet starting point up to farms specialized for package building or GPU work | Your team writes infrastructure in TypeScript and wants unit tests over the synthesized template |

These farms run rendering, reconstruction, and data-transformation jobs from the [job bundle index](../job_bundles/). They mirror the [CloudFormation farm templates](../cloudformation/farm_templates/) and include support for [building custom Conda packages](../conda_recipes/).

The reusable constructs (`Farm`, `Queue`, `ServiceManagedFleet`, `CondaChannel`, and more) live in [`farm_templates/starter_farm/lib/deadline/`](farm_templates/starter_farm/lib/deadline/), with one stack file per example farm composing them. Deploy the example closest to what you need, or copy that directory into your own CDK app and write a stack of your own.

## Choosing between CloudFormation, Terraform, and the CDK

The starter farm in each of the three creates equivalent Deadline Cloud infrastructure. Choose based on your team's existing tooling and state-management practices.

| Aspect | CloudFormation | Terraform | AWS CDK |
|---|---|---|---|
| Authoring | YAML template | HCL configuration | TypeScript, compiled to CloudFormation |
| Provider | AWS native | HashiCorp AWSCC | AWS native |
| Deadline resources | `AWS::Deadline::*` | `awscc_deadline_*` | `Farm`, `Queue`, and fleet constructs over `CfnFarm`, `CfnQueue`, and `CfnFleet` |
| State | Managed by AWS | Local or remote backend | Managed by AWS |
| Job attachments bucket | You supply an existing bucket | You supply an existing bucket | Created by the app |
| Testing | `cfn-lint` | `terraform validate` | Jest assertions over the synthesized template, plus `cfn-lint` |

## Validation

CDK apps synthesize with real npm dependencies, so their checks need network access and live in a workflow of their own: [`.github/workflows/cdk_checks.yml`](../.github/workflows/cdk_checks.yml). The workflow discovers every directory below `cdk/` that holds a `cdk.json`, then runs `npm ci`, `tsc`, `jest`, `cdk synth`, and `cfn-lint` over the synthesized templates. A bare `cdk synth` renders every stack an app defines, so adding another CDK app or another example stack needs no workflow change.

The offline [static validation suite](../tests/README.md) contributes two things: `openjd check` over any OpenJD template inside a CDK app, and a check that a queue environment copied from [`queue_environments/`](../queue_environments/) has not drifted from the original.
