# AWS Deadline Cloud sample CloudFormation templates

With [AWS CloudFormation](https://aws.amazon.com/cloudformation/), you can use infrastructure as code to deploy infrastructure
such as a Deadline Cloud farm to your AWS account. Use the samples provided here directly or as a starting point
to create your own custom templates.

## Starter farm

The [starter_farm](farm_templates/starter_farm/) sample CloudFormation template deploys a Deadline Cloud farm you can use to run jobs that render images,
reconstruct 3D scenes, or transform your data in custom ways. Sample jobs to submit are available in the deadline-cloud-samples on GitHub, Deadline Cloud
provides many integrated submitter plugins for applications, and you can build your own jobs. The deployed farm includes the ability to
[build custom conda packages](../conda_recipes/README.md) for providing additional application support.

## Budget events notification

The [budget_events_notification](notification_templates/budget_events_notification/) CloudFormation template sets up an integration
to receive notifications via email and Slack when a budget threshold is reached in the aws.deadline service. It creates an SNS topic,
an EventBridge rule, and a Chatbot configuration to send the notifications.

## Customer-managed fleet health checks

The [cmf_templates](farm_templates/cmf_templates/) collection includes a fleet health check CloudFormation template that sets up
continuous health check monitoring for a single Deadline Cloud customer-managed fleet with autoscaling. It creates a Lambda function,
an EventBridge rule, and a CloudWatch alarm that can be configured with an SNS topic.
