# Service-managed fleet capacity manager

## Introduction

This CloudFormation template implements automated capacity management for hybrid fleet setups that combine
Wait and Save and Spot fleets. It uses AWS Lambda and Amazon EventBridge Scheduler to dynamically balance
fleet sizes while maintaining constant total capacity. The capacity manager monitors your Wait and Save fleet's active worker count and automatically adjusts your Spot fleet's maximum worker count to maintain your desired total capacity, optimizing for cost-effective Wait and Save capacity while ensuring any deficit is covered by
Spot instances.

```
Total Capacity = Wait and Save Workers + Spot Workers (adjusted automatically)
```

For example, with a target max worker count of 20 workers:
- Wait and Save has 15 workers → Spot fleet max is set to 5
- Wait and Save scales down to 8 → Spot fleet max increases to 12
- Wait and Save scales up to 18 → Spot fleet max decreases to 2

Workers are only terminated upon task completion, ensuring fleets balance for cost-effectiveness without
losing rendering work.

## Prerequisites

Before deploying this CloudFormation template, ensure you have the following resources in your AWS Account
in the same region where you'll deploy the template:

1. **Deadline Cloud Farm**: An existing farm. Copy the Farm ID from the farm details page in the
   [AWS Deadline Cloud management console](https://console.aws.amazon.com/deadlinecloud/home).

2. **Wait and Save Fleet**: A Wait and Save service-managed fleet with `maxWorkerCount` set to your
   target max worker count (e.g., 20 workers). Copy the Fleet ID from the fleet details page.

3. **Spot Fleet**: A Spot service-managed fleet with the same worker capabilities as your Wait and Save fleet.

   Set `minWorkerCount` to 0 to allow the capacity manager to scale down to zero when Wait and Save fleet
   is at full capacity. The `maxWorkerCount` will be automatically managed. Copy the Fleet ID from the fleet details page.

4. **Queue Configuration**: Both fleets should be associated with the same queue.

## Setup Instructions

### Using the CloudFormation Console

1. Download the [deadline-cloud-smf-capacity-manager-template.yaml](deadline-cloud-smf-capacity-manager-template.yaml)
   CloudFormation template.
2. From the [CloudFormation management console](https://console.aws.amazon.com/cloudformation/),
   navigate to **Create Stack > With new resources (standard)**.
3. Upload the template file.
4. Enter a stack name like "DeadlineCloudCapacityManager" and provide the parameters:
   - **FarmId**: Your Deadline Cloud farm ID
   - **WaitAndSaveFleetId**: Your Wait and Save fleet ID
   - **SpotFleetId**: Your Spot fleet ID
   - **TargetMaxWorkerCount**: Target maximum total worker count across both fleets (must match Wait and Save fleet's `maxWorkerCount`). Note that actual worker count may briefly exceed this target during scaling operations.
   - **CapacityCheckRateMinutes**: Interval between capacity checks (default: 2 minutes)
5. Check "I acknowledge that AWS CloudFormation might create IAM resources" and create the stack.

### Using the CLI

1. In your CLI, set the following environment variables with the values you have copied from the Prerequisites section.
   ```bash
   export FARM_ID=<your-farm-id>
   export WAIT_AND_SAVE_FLEET_ID=<your-wait-and-save-fleet-id>
   export SPOT_FLEET_ID=<your-spot-fleet-id>
   export TARGET_MAX_WORKER_COUNT=<total-target-workers>
   ```

2. Deploy the Deadline Cloud capacity manager template with the parameters you specified in Step 1.

   ```bash
   aws cloudformation deploy \
     --template-file deadline-cloud-smf-capacity-manager-template.yaml \
     --stack-name DeadlineCloudCapacityManager \
     --capabilities CAPABILITY_NAMED_IAM \
     --parameter-overrides \
       FarmId=$FARM_ID \
       WaitAndSaveFleetId=$WAIT_AND_SAVE_FLEET_ID \
       SpotFleetId=$SPOT_FLEET_ID \
       TargetMaxWorkerCount=$TARGET_MAX_WORKER_COUNT
   ```

## Monitoring and Management

### CloudWatch Metrics

The capacity manager automatically publishes CloudWatch metrics to track fleet scaling over time. These metrics
are published to the `AWS/DeadlineCloud` namespace:

**Available Metrics:**
- **WaitAndSaveWorkerCount**: Current worker count in the Wait and Save fleet
  - Dimensions: FarmId, FleetId (Wait and Save)
- **SpotWorkerCount**: Current worker count in the Spot fleet
  - Dimensions: FarmId, FleetId (Spot)
- **TotalWorkerCount**: Combined worker count across both fleets
  - Dimensions: FarmId

**Viewing Metrics:**

From the [CloudWatch console](https://console.aws.amazon.com/cloudwatch/):
1. Navigate to **Metrics > All metrics**
2. Select the **AWS/DeadlineCloud** namespace
3. View metrics by FarmId and FleetId dimensions

### View Lambda Logs

Monitor the capacity manager's operation from the [AWS Lambda console](https://console.aws.amazon.com/lambda/).
Select the `FleetCapacityManager` function, click the **Monitor** tab, and select **View CloudWatch logs**
to see capacity adjustments and worker counts.

### Pause Capacity Management

When not actively rendering, disable the EventBridge Scheduler to stop automated capacity management and
avoid Lambda invocation costs:

1. Navigate to the [Amazon EventBridge Scheduler console](https://console.aws.amazon.com/scheduler/home#schedules)
2. Find the `FleetCapacityManager` schedule
3. Select **Actions > Disable**

Since `minWorkerCount` is 0 in the fleet configurations, no workers will start without jobs. To resume,
simply enable the schedule again.

## Cleanup

To delete all resources created by this template:

```bash
aws cloudformation delete-stack --stack-name DeadlineCloudCapacityManager
```

## Related Documentation

- [AWS Deadline Cloud Service-Managed Fleets](https://docs.aws.amazon.com/deadline-cloud/latest/userguide/smf-manage.html)
- [AWS Deadline Cloud Pricing](https://aws.amazon.com/deadline-cloud/pricing/)
- [AWS Lambda Pricing](https://aws.amazon.com/lambda/pricing/)
- [Amazon EventBridge Scheduler](https://docs.aws.amazon.com/scheduler/latest/UserGuide/what-is-scheduler.html)
