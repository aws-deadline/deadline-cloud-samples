# Sample host configuration scripts for AWS Deadline Cloud service-managed fleets

Host configuration scripts run with elevated privileges on service-managed fleet workers. Use them for administrative tasks such as software installation, system tuning, GPU container setup, and worker restart behavior.

## Sample index

This table covers every immediate user-selectable group or leaf directory in `host_configuration_scripts/`. The application groups link to their own installer examples; implementation scripts remain inside each sample.

| Sample | What it demonstrates | Start here when |
|---|---|---|
| [3ds Max](3dsmax/) | Windows installation for multiple 3ds Max, renderer, and plugin combinations | You need 3ds Max on service-managed workers |
| [After Effects and Red Giant](aftereffects/) | Installing After Effects with optional Red Giant plugins | You need Adobe and Maxon software installed as administrator |
| [Cinema 4D and Red Giant](cinema4d/) | Installing Cinema 4D with Red Giant plugins | You need Cinema 4D and Maxon plugins on Windows workers |
| [Docker and NVIDIA Container Toolkit](docker_nvidia_container_toolkit/) | Installing Docker and the NVIDIA runtime on Linux GPU workers | Jobs run GPU-accelerated containers |
| [Linux font installation](linux_font_installation/) | Downloading fonts from S3 and registering them system-wide | Render applications need studio fonts |
| [Memory overcommit override](overcommit_override_for_smf/) | Changing `vm.overcommit_memory` on Linux workers | Large attachments or allocations fail despite free memory |
| [Passwordless sudo for job user](sudo_for_job_user/) | Granting `job-user` unrestricted sudo | A trusted workload requires root commands during tasks |
| [Swap for SMF](swap_for_smf/) | Creating and enabling a Linux swap file | A workload can temporarily exceed physical memory |
| [Worker configuration](worker_configuration/) | Windows system configuration such as page-file sizing | Workers need OS-level tuning before jobs start |
| [Worker reboot](worker_reboot/) | Rebooting Linux or Windows after host setup | Drivers, domain joins, or other changes require restart |

## Common uses

* Install software that requires administrator access.
* Install and configure container runtimes.
* Configure GPU support for containerized workloads.
* Tune memory, swap, fonts, or other host-wide settings.

## Setup

Copy the selected script into the Deadline Cloud console or use the Deadline Cloud CLI to update the fleet. Follow [Run scripts as an administrator to configure workers](https://docs.aws.amazon.com/deadline-cloud/latest/developerguide/smf-admin.html) and the [`update-fleet` CLI reference](https://docs.aws.amazon.com/cli/latest/reference/deadline/update-fleet.html). Review every script and replace its configuration values before deployment because it runs with administrator privileges.

## Debugging

### CloudWatch Logs

Host configuration logs are streamed to the fleet log group and a stream dedicated to each worker. For example, `/aws/deadline/farm-12345/fleet-09876` can contain a `worker-13579` stream. Look for the “Running Host Configuration Script” and “Finished running Host Configuration Script, exit code: 0” banners.

### CloudWatch Logs Insights

This query extracts host configuration exit codes in reverse chronological order:

```text
fields @timestamp, @message, @logStream, @log
| filter @message like /Finished running Host Configuration Script/
| parse @message /exit code: (?<exit_code>\d+)/
| display @timestamp, exit_code
| sort @timestamp desc
```
