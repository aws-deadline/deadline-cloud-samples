# Deploying Deadline Cloud fleet health check

## Introduction
This CloudFormation template sets up continuous health check monitoring for a single Deadline Cloud customer-managed fleet
with autoscaling. It creates a Lambda function, an EventBridge rule, and a CloudWatch alarm that can be configured with an SNS topic.

## Prerequisites
Before deploying this CloudFormation template, check that you have the following resources created in your AWS Account.

1. __Deadline Cloud Farm and Customer-Managed Fleet__: From the [AWS Deadline Cloud management console](https://console.aws.amazon.com/deadlinecloud),
 navigate to the details page of your fleet you want to apply fleet health check monitoring to. Copy the values for Farm ID, Fleet ID, and Fleet Name.

2. __EC2 Autoscaling Group that autoscales the fleet__: From the [EC2 Auto Scaling management console](https://console.aws.amazon.com/ec2/home?#AutoScalingGroups),
 navigate to the details page for the Auto Scaling Group corresponding to your fleet, and copy the value for Auto Scaling Group name.

3. __SNS Topic__: From the [SNS management console](https://console.aws.amazon.com/sns),
 set up an [SNS topic](https://docs.aws.amazon.com/sns/latest/dg/sns-create-topic.html) in your AWS account for the health check alarm.
 Copy the ARN of the SNS topic.

4. __SNS Subscription__: From the [SNS management console](https://console.aws.amazon.com/sns),
 set up an [SNS subscription](https://docs.aws.amazon.com/sns/latest/dg/sns-create-subscribe-endpoint-to-topic.html)
 to connect the SNS topic to your email and your phone via SMS so that you can learn about and investigate issues quickly.
 See the [documentation page](https://docs.aws.amazon.com/AmazonCloudWatch/latest/APIReference/API_PutMetricAlarm.html)
 for the full list of available alarm actions.


## Setup Instructions

### Using the CloudFormation Console
1. Download the `deadline-fleet-health-check.yaml` CloudFormation template.
2. From the [CloudFormation management console](https://console.aws.amazon.com/cloudformation/), navigate to __Create Stack > With new resources (standard)__.
3. Upload the `deadline-fleet-health-check.yaml` CloudFormation template.
4. Specify the name of the stack and parameters you copied from the Prerequisites section.
5. Follow the CloudFormation console steps to complete stack creation.

### Using the CLI
1.  In your CLI, set the following environment variables with the values you have copied from the Prerequisites section.
    ```
    export FARM_ID=<farm_id>
    export FLEET_ID=<fleet_id>
    export FLEET_NAME=<fleet_name>
    export FLEET_AUTOSCALING_GROUP_NAME=<fleet_autoscaling_group_name>
    export HEALTH_CHECK_SNS_TOPIC_ARN=<sns_topic_arn>
    ```

2. Deploy the Deadline Cloud fleet health check template with the parameters you specified in Step 1.

    ```
    aws cloudformation deploy --template-file deadline-fleet-health-check.yaml \
    --stack-name "cmf-${FLEET_NAME}-fleetHealthCheckStack" \
    --capabilities CAPABILITY_NAMED_IAM \
    --parameter-overrides FarmId=$FARM_ID \
        FleetId=$FLEET_ID \
        FleetName=$FLEET_NAME \
        FleetAutoScalingGroupName=$FLEET_AUTOSCALING_GROUP_NAME \
        HealthCheckAlarmActionArn=$HEALTH_CHECK_SNS_TOPIC_ARN
    ```

### [Optional] Customize Health Check Configurations
You can customize the following health check configurations by changing the CloudFormation template parameter values.

| Parameter                      | Default | Description                                                                                                 |
|--------------------------------|---------|-------------------------------------------------------------------------------------------------------------|
| HealthCheckStartupGraceMinutes | 10      | How many minutes of grace time to give new instances before they must join the fleet.                       |
| HealthCheckRateMinutes         | 10      | How many minutes between each health check of all the fleet workers.                                        |
| HealthCheckFailureAlarmSeconds | 900     | How many seconds for each period of evaluating health check failures. Defaults to 1.5x the HealthCheckRate. |