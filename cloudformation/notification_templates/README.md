# AWS Deadline Cloud event notification templates

AWS Deadline Cloud sends events to the account's default EventBridge event bus. See
[Monitoring Deadline Cloud events with EventBridge](https://docs.aws.amazon.com/deadline-cloud/latest/userguide/monitoring-eventbridge.html)
for service behavior. These CloudFormation templates route selected events to email or Slack integrations.

## Sample index

This table covers every immediate deployable sample directory in `notification_templates/`.

| Sample | What it demonstrates | Start here when |
|---|---|---|
| [Budget event notifications](budget_events_notification/) | Sending Deadline Cloud budget threshold events through SNS and AWS Chatbot | You need email or Slack budget alerts |
| [Job event Slack notifications](job_events_slack_lambda/) | Matching job events in EventBridge and invoking a Slack-posting Lambda | You need an example service-event integration for job completion or failure |

## Setup

Each sample README documents its parameters and integration-specific setup. In general:

1. Download the sample YAML template.
2. In the AWS CloudFormation console, choose **Create stack** and upload the template.
3. Supply the parameters required by that sample, such as notification destinations or credentials.
4. Confirm that matching Deadline Cloud events reach the configured destination.
