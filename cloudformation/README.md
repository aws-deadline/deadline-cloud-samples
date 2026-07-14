# AWS Deadline Cloud sample CloudFormation templates

With [AWS CloudFormation](https://aws.amazon.com/cloudformation/), you can use infrastructure as code to deploy infrastructure
such as a Deadline Cloud farm to your AWS account. Use the samples provided here directly or as a starting point
to create your own custom templates.

## Starter farm

The [starter_farm](farm_templates/starter_farm/) sample CloudFormation template deploys a Deadline Cloud farm you can use to run jobs that render images,
reconstruct 3D scenes, or transform your data in custom ways. Sample jobs to submit are available in the deadline-cloud-samples on GitHub, Deadline Cloud
provides many integrated submitter plugins for applications, and you can build your own jobs. The deployed farm includes the ability to
[build custom conda packages](../conda_recipes/README.md) for providing additional application support.

## Service-managed fleet with VPC resource endpoint

The [smf_vpc_fsx](farm_templates/smf_vpc_fsx/) sample CloudFormation template demonstrates how to connect
a service-managed fleet to private VPC resources using VPC Lattice. It deploys an FSx for OpenZFS file system
and configures workers to mount it via a VPC resource endpoint. This pattern is useful for accessing shared
storage, license servers, or other private resources from Deadline Cloud workers.

## Service-managed fleet capacity manager

The [smf_capacity_manager](farm_templates/smf_capacity_manager/) sample CloudFormation template implements automated
capacity management for hybrid fleet setups that combine Wait and Save and Spot fleets. It uses AWS Lambda and
Amazon EventBridge Scheduler to dynamically balance fleet sizes while maintaining constant total capacity,
optimizing for cost-effective Wait and Save capacity while ensuring any deficit is covered by Spot instances.

## Budget events notification

The [budget_events_notification](notification_templates/budget_events_notification/) CloudFormation template sets up an integration
to receive notifications via email and Slack when a budget threshold is reached in the aws.deadline service. It creates an SNS topic,
an EventBridge rule, and a Chatbot configuration to send the notifications.

## Job event Slack notifications with Lambda

The [job_events_slack_lambda](notification_templates/job_events_slack_lambda/) CloudFormation template demonstrates
how to connect an AWS Lambda function to Deadline Cloud job events through Amazon EventBridge. It creates an
EventBridge rule that matches job completion and failure events and invokes a Lambda function that posts a
notification to a Slack channel via an incoming webhook. Use it as a starting point for reacting to job events
in your own automation.

## Scheduled standby workers

The [fleet_standby_scheduling](farm_templates/fleet_standby_scheduling/) sample CloudFormation template schedules
standby worker count changes on a Deadline Cloud fleet based on a time schedule. It sets a warm standby pool
during business hours and resets it outside business hours to save cost. Works with any existing fleet created
via the console, CLI, or CloudFormation.

## Customer-managed fleet health checks

The [cmf_templates](farm_templates/cmf_templates/) collection includes a fleet health check CloudFormation template that sets up
continuous health check monitoring for a single Deadline Cloud customer-managed fleet with autoscaling. It creates a Lambda function,
an EventBridge rule, and a CloudWatch alarm that can be configured with an SNS topic.
