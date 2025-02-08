# Deadline Custom Job Balancer

This CloudFormation template deploys a Lambda function that controls the maxWorkerCount for each job within a Queue to implement functionality similar to the Deadline10 Balancer options.
It implements a modified version of the Deadline 10 weighting algorithm: https://docs.thinkboxsoftware.com/products/deadline/10.4/1_User%20Manual/manual/job-scheduling.html#weighted-scheduling

## Resources Created
1. **Lambda Function**: An AWS Lambda function named `DeadlineWeightedJobBalancer` is created. This is the main driver which calculates and controls the `maxWorkerCount` setting for jobs.
2. **EventBridge Schedule**: A schedule is created to trigger the Lambda function once every minute.
3. **IAM Role**: An IAM role `BalancerSchedulerRole` is created and used by the Schedule to trigger the Lambda function.
4. **SQS Queue**: An SQS Queue `deadline-unprocessed-balancing-events` is created to act as a DeadLetterQueue for the Schedule.
5. **IAM Role**: An IAM role `DeadlineWeightedJobBalancerRole` is created to be used as the Lambda execution role for our `DeadlineWeightedJobBalancer`.

## Prerequisites

Before deploying this CloudFormation template, check you have the following as per your chosen method of notifications:

1. The AWS CLI installed and configured with your AWS credentials (if setting up using CLI option).
2. A Deadline Cloud Farm and Queue deployed in your account.

## Deployment

You can use either of the below methods for deployment - AWS Console or AWS CLI.

### AWS Console

To deploy this CloudFormation template via the AWS Console, follow these steps:

1. Save the CloudFormation template to a local file (e.g., `/Users/<your-username/Downloads/custom_queue_job_balancer.yaml`).
2. Open the AWS CloudFormation console.
3. Click on "Create Stack" and select "With new resources (standard)".
4. Under "Specify template", choose "Upload a template file" and select the CloudFormation template file saved from location.
5. Click "Next".
6. On the "Specify stack details" page, provide values for the following parameters:
   - `FarmId`: Enter your Deadline Cloud Farm ID which contains the Queue you'd like to have the balancer target.
   - `QueueId`: Enter the Deadline Cloud Queue ID that you would like to have the balancer target.
7. Click "Next" through the remaining steps, and finally, click "Create Stack" to deploy the CloudFormation template.

### AWS CLI

To deploy this CloudFormation template using the AWS CLI, follow these steps:

1. Save the CloudFormation template to a local file (e.g., `/Users/<your-username/Downloads/custom_queue_job_balancer.yaml`).
2. Open a terminal or command prompt, and navigate to the directory containing the template file.
3. Run the following AWS CLI command to create the CloudFormation stack:

    ```
    aws cloudformation create-stack \
    --stack-name DeadlineCustomBalancer<QueueId> \
    --template-body file://custom_queue_job_balancer.yaml \
    --parameters \
    ParameterKey=FarmId,ParameterValue=farm-XXXXXXXXX \
    ParameterKey=QueueId,ParameterValue=queue-XXXXXXXXX
    ```

   Replace `farm-XXXXXXXXX`, and `queue-XXXXXXXXX` with your actual values.

4. Wait for the stack creation to complete. You can monitor the progress using the `aws cloudformation describe-stacks` command.

After successful deployment & confirmation, you should start seeing the `maxWorkerCount` get automatically modified for each job in your queue.
