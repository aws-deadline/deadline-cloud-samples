# Sample Host Configuration Scripts for AWS Deadline Cloud Service Managed Fleets

## Summary

This directory contains sample scripts for configuring Service Managed Fleets on Windows and Linux.

Host Configuration Scripts allow you to perform administrative tasks, such as software installation, on your service-managed fleet workers. These scripts run with elevated privileges, giving you the flexibility to configure your workers for your system.

## Examples

| Example | Platform | Description |
|---------|----------|-------------|
| [3dsmax](3dsmax/) | Windows | Install and configure Autodesk 3ds Max with various renderer plugins (V-Ray, Corona, tyFlow, AEC) |
| [aftereffects](aftereffects/) | Windows | Install After Effects with Red Giant plugins |
| [cinema4d](cinema4d/) | Windows | Install Cinema 4D with Red Giant plugins |
| [docker_nvidia_container_toolkit](docker_nvidia_container_toolkit/) | Linux | Install Docker and NVIDIA Container Toolkit for GPU-accelerated container workloads |
| [linux_font_installation](linux_font_installation/) | Linux | Install custom fonts from S3 for rendering applications |
| [sudo_for_job_user](sudo_for_job_user/) | Linux | Grant passwordless sudo to `job-user` for workloads that require root access |
| [swap_for_smf](swap_for_smf/) | Linux | Enable swap for memory-intensive workloads like ComfyUI and large diffusion models |
| [worker_configuration](worker_configuration/) | Windows | Configure Windows page file settings |
| [worker_reboot](worker_reboot/) | Linux / Windows | Reboot the worker after host configuration (e.g. after driver installs or domain joins) |

## Common Uses
- Installing software that requires administrator access
- Installing Docker containers
- Configuring GPU runtimes for containerized workloads
- Enabling swap for memory-intensive jobs

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
