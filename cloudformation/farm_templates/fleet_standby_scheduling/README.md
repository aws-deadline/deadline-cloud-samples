# Scheduled Standby Workers for Deadline Cloud Fleets

## Overview

This CloudFormation template schedules [standby worker count](https://docs.aws.amazon.com/deadline-cloud/latest/userguide/auto-scaling-configuration.html)
changes on a Deadline Cloud fleet based on a time schedule. Standby workers are a warm pool of idle workers
that can start processing jobs immediately without waiting for new instances to launch. By scheduling
standby workers only during business hours, you reduce job start latency when your team is active
while avoiding the cost of idle workers overnight and on weekends.

For example, with the default settings this template sets the standby worker count to 2 at 8:00 AM UTC
Monday through Friday, and resets it to 0 at 5:00 PM UTC.

This template works with any existing Deadline Cloud fleet — whether it was created via the AWS console,
CLI, or another CloudFormation template. It supports both
[service-managed fleets](https://docs.aws.amazon.com/deadline-cloud/latest/userguide/smf-manage.html) and
[customer-managed fleets](https://docs.aws.amazon.com/deadline-cloud/latest/userguide/manage-cmf.html).
Use this sample as a starting point and modify it to fit your own scheduling and cost optimization needs.

## Resources Created

1. **Lambda Function** — Updates the fleet's standby worker count by calling the Deadline Cloud
   `UpdateFleet` API. It reads the fleet's current configuration first to avoid overwriting other settings.
2. **IAM Roles** — A Lambda execution role with `deadline:GetFleet` and `deadline:UpdateFleet` permissions
   scoped to the specified fleet, and a scheduler role to invoke the Lambda.
3. **EventBridge Schedules** — Two schedules that trigger the Lambda at the start and end of business hours.

## Prerequisites

1. An existing Deadline Cloud farm and fleet. The fleet can be service-managed or customer-managed.
2. The Farm ID and Fleet ID. You can find these in the
   [Deadline Cloud console](https://console.aws.amazon.com/deadlinecloud/home) or by using the AWS CLI:
   ```
   aws deadline list-farms
   aws deadline list-fleets --farm-id <FARM_ID>
   ```

## Customization

- To schedule a different time window, update the `BusinessHoursStartCron` and `BusinessHoursEndCron`
  parameters. For example, to run every day (including weekends) from 9 AM to 6 PM Pacific time:
  - `BusinessHoursStartCron`: `cron(0 9 * * ? *)`
  - `BusinessHoursEndCron`: `cron(0 18 * * ? *)`
  - `ScheduleTimezone`: `US/Pacific`
- To schedule multiple fleets, deploy one stack per fleet.

## Deployment

### AWS Console

1. Download the [deadline-cloud-standby-scheduling-template.yaml](deadline-cloud-standby-scheduling-template.yaml)
   CloudFormation template.
2. From the [CloudFormation console](https://console.aws.amazon.com/cloudformation/), choose
   Create Stack > With new resources (standard).
3. Upload the template file and click Next.
4. Enter a stack name (e.g. `StandbyScheduling`), your Farm ID, Fleet ID, and adjust the schedule
   parameters as needed:
   - **BusinessHoursStandbyWorkerCount** — Workers to keep warm during business hours (default: 2).
   - **OffHoursStandbyWorkerCount** — Workers to keep warm outside business hours (default: 0).
   - **BusinessHoursStartCron / BusinessHoursEndCron** — Cron expressions for the schedule.
     Default is weekdays 8 AM–5 PM. Uses
     [EventBridge Scheduler cron syntax](https://docs.aws.amazon.com/scheduler/latest/UserGuide/schedule-types.html#cron-based).
   - **ScheduleTimezone** — Timezone for the cron expressions (default: UTC). Accepts any
     [IANA timezone name](https://en.wikipedia.org/wiki/List_of_tz_database_time_zones) such as
     `US/Pacific` or `Europe/London`.
5. Click Next, acknowledge IAM resource creation, and create the stack.

### AWS CLI

```bash
aws cloudformation create-stack \
  --stack-name StandbyScheduling \
  --template-body file://deadline-cloud-standby-scheduling-template.yaml \
  --capabilities CAPABILITY_IAM \
  --parameters \
    ParameterKey=FarmId,ParameterValue=farm-0123456789abcdef0123456789abcdef \
    ParameterKey=FleetId,ParameterValue=fleet-0123456789abcdef0123456789abcdef
```

## Cleanup

```bash
aws cloudformation delete-stack --stack-name StandbyScheduling
```

Deleting the stack removes the Lambda, IAM roles, and schedules. It does not modify your fleet's
current standby worker count — the fleet retains whatever value was last set.
