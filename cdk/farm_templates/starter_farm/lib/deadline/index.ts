// Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

/**
 * Reusable AWS Deadline Cloud constructs.
 *
 * These wrap the `CfnFarm`, `CfnQueue`, and `CfnFleet` L1 resources from
 * `aws-cdk-lib/aws-deadline` in the shapes a farm is usually built from, with
 * the IAM roles and permissions each resource needs created alongside it. Build
 * a farm by composing them:
 *
 * ```ts
 * const farm = new Farm(this, 'Farm', { displayName: 'My Farm' });
 * const bucket = new JobAttachmentsBucket(this, 'Bucket');
 * const channel = new CondaChannel({ bucket });
 *
 * const queue = new Queue(this, 'RenderQueue', {
 *   farm,
 *   displayName: 'Render Queue',
 *   jobAttachmentsBucket: bucket,
 * });
 * channel.grantRead(queue);
 * queue.addEnvironment(new CondaQueueEnvironment({ channels: [channel, 'deadline-cloud'] }));
 * queue.associateFleet(new CudaLinuxFleet(this, 'GpuFleet', { farm }));
 * ```
 *
 * Anything a construct does not expose is reachable on the L1 resource it
 * wraps -- `farm.cfnFarm`, `queue.cfnQueue`, `fleet.cfnFleet` -- so a farm never
 * has to stop using these to reach a property they left out.
 */

export * from './conda-channel';
export * from './farm';
export * from './fleet';
export * from './job-attachments-bucket';
export * from './queue';
export * from './queue-environment';
