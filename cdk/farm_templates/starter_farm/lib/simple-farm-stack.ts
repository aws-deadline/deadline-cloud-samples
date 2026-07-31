// Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

import * as cdk from 'aws-cdk-lib';
import { Construct } from 'constructs';

import { CpuLinuxFleet, Farm, JobAttachmentsBucket, Queue } from './deadline';

export interface SimpleFarmStackProps extends cdk.StackProps {
}

/**
 * The smallest useful AWS Deadline Cloud farm: one queue, one Linux fleet.
 *
 * Start here. Jobs submitted to the queue run on spot Linux instances that
 * Deadline Cloud launches on demand and shuts down when the work is done, and
 * their input and output files travel through job attachments on the S3 bucket
 * this stack creates.
 *
 * The queue's Conda environment installs applications from the
 * {@link https://docs.aws.amazon.com/deadline-cloud/latest/userguide/create-queue-environment.html#conda-queue-environment deadline-cloud channel},
 * so a job can ask for Blender, Maya, Nuke, or Houdini by name with no further
 * setup:
 *
 * ```bash
 * deadline bundle submit blender_render -p CondaPackages=blender
 * ```
 *
 * When you outgrow it:
 *
 * - to build and publish your own Conda packages, see {@link StarterFarmStack},
 *   which adds a package build queue and a private S3 Conda channel
 * - to run GPU work, see {@link CudaFarmStack}
 * - to run Windows jobs, or to route different steps to different hardware, see
 *   {@link MultiPlatformFarmStack}
 */
export class SimpleFarmStack extends cdk.Stack {
  /** The Deadline Cloud farm. */
  public readonly farm: Farm;
  /** The S3 bucket holding job attachments. */
  public readonly jobAttachmentsBucket: JobAttachmentsBucket;
  /** The queue jobs are submitted to. */
  public readonly queue: Queue;
  /** The Linux fleet the queue's jobs run on. */
  public readonly fleet: CpuLinuxFleet;

  constructor(scope: Construct, id: string, props: SimpleFarmStackProps = {}) {
    super(scope, id, props);

    this.farm = new Farm(this, 'Farm', {
      displayName: 'Simple Deadline Cloud Farm',
      description:
        'Deadline Cloud farm deployed by the SimpleFarm stack of the starter_farm CDK sample.',
    });

    this.jobAttachmentsBucket = new JobAttachmentsBucket(this, 'JobAttachmentsBucket');

    // One queue, with the Conda queue environment the construct adds by
    // default. Its channel list is left alone, so jobs install from the
    // deadline-cloud channel and there is no private channel to initialize
    // before the farm is usable.
    this.queue = new Queue(this, 'Queue', {
      farm: this.farm,
      displayName: 'Job Queue',
      description: 'The Deadline Cloud queue for running jobs.',
      jobAttachmentsBucket: this.jobAttachmentsBucket,
    });

    this.fleet = new CpuLinuxFleet(this, 'Fleet', { farm: this.farm });
    this.queue.associateFleet(this.fleet);

    new cdk.CfnOutput(this, 'FarmId', {
      value: this.farm.farmId,
      description: 'The Deadline Cloud farm ID.',
    });
    new cdk.CfnOutput(this, 'QueueId', {
      value: this.queue.queueId,
      description: 'The queue ID. Pass this to `deadline bundle submit --queue-id`.',
    });
    new cdk.CfnOutput(this, 'FleetId', {
      value: this.fleet.fleetId,
      description: 'The fleet ID.',
    });
    new cdk.CfnOutput(this, 'JobAttachmentsBucketName', {
      value: this.jobAttachmentsBucket.bucketName,
      description: 'The S3 bucket holding job attachments.',
    });
  }
}
