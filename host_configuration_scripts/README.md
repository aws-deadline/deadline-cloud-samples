# Sample Host Configuration Scripts for AWS Deadline Cloud Service Managed Fleets

## Summary

This directory contains sample scripts for configuring Service Managed Fleets on Windows and Linux.

Host Configuration Scripts allow you to perform administrative tasks, such as software installation, on your service-managed fleet workers. These scripts run with elevated privileges, giving you the flexibility to configure your workers for your system.

## Common Uses
- Installing software that requires administrator access
- Installing Docker containers

## Setup

Copy and paste the sample scripts into the AWS Deadline Cloud console or use the AWS Deadline Cloud CLI to update your fleet. Follow [Run scripts as an administrator to configure workers](https://docs.aws.amazon.com/deadline-cloud/latest/developerguide/smf-admin.html) or reference the [AWS Deadline Cloud update-fleet CLI](https://docs.aws.amazon.com/cli/latest/reference/deadline/update-fleet.html) for more details.

## Debugging

### CloudWatch Logs 
Fleet Host Configuration logs are streamed to the Fleet’s log group, and specifically to a worker’s log stream. For example, `/aws/deadline/farm-12345/fleet-09876` is the log group for farm-12345, fleet-09876. Each worker will provision a dedicated log stream, for example worker-13579. Notice in the logs the log banner “Running Host Configuration Script” and “Finished running Host Configuration Script, exit code: 0”. The exit code of the script is included in the finished banner, and can be queried using CloudWatch tools.

### CloudWatch Log Insights

CloudWatch Log Insights offers advanced capabilities to datamine the log information. For example, the following log insight query parses for the host configuration exit code, sorted by time.

```
fields @timestamp, @message, @logStream, @log
| filter @message like /Finished running Host Configuration Script/
| parse @message /exit code: (?<exit_code>\d+)/
| display @timestamp, exit_code
| sort @timestamp desc
```
