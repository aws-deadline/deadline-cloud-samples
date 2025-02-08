# AWS Deadline Cloud Auxiliary Templates

## Introduction
AWS Deadline Cloud sends events to customer's default event bus https://docs.aws.amazon.com/deadline-cloud/latest/userguide/monitoring-eventbridge.html
This directory holds sample Cloud Formation Templates customers can use to customize behaviour based on events received from Deadline Cloud.

## Setup Instructions
Each Cloud Formation Template will have its own instructions on how to set up integrations, but in general they follow the below scheme:

1. Download the specified YAML file
2. On the AWS console, go to CloudFormation, Create Stack, and add the downloaded template.
3. Follow the specific instructions for that file, as you may need to enter specific parameters.
4. After this is set up, Deadline cloud events will reach through your setup mechanism.
