# Deadline Budget Threshold Reached Event Integration with Email and Slack

This CloudFormation template sets up an integration to receive notifications via email and Slack when a budget threshold is reached in the `aws.deadline` service. It creates an SNS topic, an EventBridge rule, and a Chatbot configuration to send the notifications.

## Resources Created

1. **SNS Topic**: An SNS topic named `DeadlineBudgetsSNSTopic` is created, and an email subscription is added to it using the provided email address.
2. **SNS Topic Policy**: A policy `DeadlineBudgetsSNSTopicPolicy` is attached to the SNS topic to allow AWS services (like EventBridge) to publish messages to the topic.
3. **IAM Role**: An IAM role `ChatbotRole` is created, which grants the necessary permissions for the Chatbot service to publish messages using Chatbot
4. **Chatbot**: A Chatbot `DeadlineBudgetsChatbot` is configured to send notifications to the specified Slack channel. It is subscribed to the SNS topic created earlier.
5. **EventBridge Rule**: An EventBridge rule `DeadlineBudgetsEventRule` is created to capture events of type `Budget Threshold Reached` from the `aws.deadline` service. When an event matches this rule, it triggers the SNS topic target, which publishes a notification to the topic.

## Prerequisites

Before deploying this CloudFormation template, check you have the following as per your chosen method of notifications:

1. An email address to receive notifications (if setting up email integration).
2. A Slack channel ID and workspace ID where you want to receive notifications (if setting up Slack integration).
3. The AWS CLI installed and configured with your AWS credentials (if setting up using CLI option).

##### Optional pre-requisite setup steps for Slack integration:
If you are setting up notifications to Slack, you need to configure the Slack client with the following steps:

1. Add AWS Chatbot to the Slack workspace:

   a. In Slack, on the left navigation pane, choose Automations.
   ###### Note: If you do not see Automations in the left navigation pane, choose More, then choose Automations.

   b. If AWS Chatbot is not listed, choose the Browse Apps Directory button.
   Browse the directory for the AWS Chatbot app and then choose Add to add AWS Chatbot to your workspace.

   c. Next create a slack channel in your workspace.
   d. Add AWS Chatbot to the channel by typing `/invite` in the channel and clicking on *Add apps to this channel*
   e. Right click on the channel, click *View channel details*, copy and keep the *Channel ID* at the bottom

2. Open the AWS Chatbot console at https://console.aws.amazon.com/chatbot/.

3. Under Configure a chat client, choose Slack, then choose Configure. After choosing Configure, you'll be redirected to Slack's authorization page to request permission for AWS Chatbot to access your information. For more information, see Chat client application permissions.

4. On the authorization page you can choose to change the Slack workspace that you want to use with AWS Chatbot from the dropdown list at the top right
   There's no limit to the number of workspaces that you can set up for AWS Chatbot, but you can set up only one at a time.

5. Choose Allow.
6. Copy and keep the *Workspace ID* from the configured slack client.

## Deployment

You can use either of the below methods for deployment - AWS Console or AWS CLI.

### AWS Console

To deploy this CloudFormation template via the AWS Console, follow these steps:

1. Save the CloudFormation template to a local file (e.g., `/Users/<your-username/Downloads/email_slack_integration_template.yaml`).
2. Open the AWS CloudFormation console.
3. Click on "Create Stack" and select "With new resources (standard)".
4. Under "Specify template", choose "Upload a template file" and select the CloudFormation template file saved from location.
5. Click "Next".
6. On the "Specify stack details" page, provide values for the following parameters:
   - `Email`: Enter the email address where you want to receive notifications (if setting up email integration).
   - `SlackChannelId`: Enter the ID of the Slack channel where you want to receive notifications (if setting up slack integration).
   - `SlackWorkspaceId`: Enter the ID of the Slack workspace containing the channel (if setting up slack integration).
   - `EventRuleSource`: Keep it as is (`aws.deadline`) by default.
7. Click "Next" through the remaining steps, and finally, click "Create Stack" to deploy the CloudFormation template.

### AWS CLI

To deploy this CloudFormation template using the AWS CLI, follow these steps:

1. Save the CloudFormation template to a local file (e.g., `/Users/<your-username/Downloads/email_slack_integration_template.yaml`).
2. Open a terminal or command prompt, and navigate to the directory containing the template file.
3. Run the following AWS CLI command to create the CloudFormation stack:

    ```
    aws cloudformation create-stack \
    --stack-name DeadlineNotificationIntegration \
    --template-body file://email_slack_integration_template.yaml \
    --parameters \
    ParameterKey=Email,ParameterValue=your-email@example.com \
    ParameterKey=SlackChannelId,ParameterValue=your-slack-channel-id \
    ParameterKey=SlackWorkspaceId,ParameterValue=your-slack-workspace-id
    ```

   Replace `your-email@example.com`, `your-slack-channel-id`, and `your-slack-workspace-id` with your actual values.

4. Wait for the stack creation to complete. You can monitor the progress using the `aws cloudformation describe-stacks` command.
5. You might need to check your email inbox to confirm subscription to notifications. The subject would likely be of the form *AWS Notification - Subscription Confirmation*

After successful deployment & confirmation, you should start receiving notifications in the specified email and Slack channel whenever a budget threshold is reached in the `aws.deadline` service.
