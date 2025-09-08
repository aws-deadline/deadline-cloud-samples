# Sample Host Configuration scripts to configure Service Managed Fleets for AWS Deadline Cloud

## Summary

This directory contains sample scripts for configuring Service Managed Fleets on Windows and Linux.

[Host Configuration Scripts](https://docs.aws.amazon.com/deadline-cloud/latest/developerguide/smf-admin.html) allow you to perform administrative tasks, such as software installation, on your service-managed fleet workers. These scripts run with elevated privileges, giving you the flexibility to configure your workers for your system.

## Common uses for the script include:
- Installing software that requires administrator access
- Installing Docker containers

## Debugging Host Configuration Scripts:

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
