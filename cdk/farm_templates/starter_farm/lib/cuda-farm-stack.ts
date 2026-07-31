// Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

import * as cdk from 'aws-cdk-lib';
import { Construct } from 'constructs';

import { CudaLinuxFleet, Farm, JobAttachmentsBucket, Queue } from './deadline';

export interface CudaFarmStackProps extends cdk.StackProps {
  /**
   * The maximum number of GPU worker hosts the fleet scales up to.
   *
   * GPU instances are expensive, so this defaults to one. Raise it deliberately.
   *
   * @default 1
   */
  readonly maxWorkerCount?: number;
}

/**
 * An AWS Deadline Cloud farm for CUDA jobs.
 *
 * This is {@link SimpleFarmStack} specialized for GPU work, and the CDK
 * equivalent of the
 * {@link https://github.com/aws-deadline/deadline-cloud-samples/tree/mainline/cloudformation/farm_templates/cuda_farm cuda_farm CloudFormation template}.
 * Two things differ from the simple farm:
 *
 * - the fleet is a {@link CudaLinuxFleet}, so worker hosts have an NVIDIA GPU
 * - the queue installs from `conda-forge` as well as `deadline-cloud`, which is
 *   where the CUDA toolchain, frameworks such as PyTorch, and applications such
 *   as COLMAP come from
 *
 * A workload to try on it is a Gaussian splatting pipeline. See the
 * {@link https://github.com/aws-deadline/deadline-cloud-samples/tree/mainline/job_bundles/gsplat_pipeline gsplat_pipeline job bundle}
 * for how to turn a video of a subject into splats you can view in a browser.
 *
 * It reads as short as the simple farm because the difference between a CPU farm
 * and a GPU farm is a fleet preset and a channel, not a different kind of stack.
 */
export class CudaFarmStack extends cdk.Stack {
  /** The Deadline Cloud farm. */
  public readonly farm: Farm;
  /** The S3 bucket holding job attachments. */
  public readonly jobAttachmentsBucket: JobAttachmentsBucket;
  /** The queue CUDA jobs are submitted to. */
  public readonly queue: Queue;
  /** The GPU fleet the queue's jobs run on. */
  public readonly fleet: CudaLinuxFleet;

  constructor(scope: Construct, id: string, props: CudaFarmStackProps = {}) {
    super(scope, id, props);

    this.farm = new Farm(this, 'Farm', {
      displayName: 'CUDA Deadline Cloud Farm',
      description:
        'Deadline Cloud farm deployed by the CudaFarm stack of the starter_farm CDK sample.',
    });

    this.jobAttachmentsBucket = new JobAttachmentsBucket(this, 'JobAttachmentsBucket');

    this.queue = new Queue(this, 'Queue', {
      farm: this.farm,
      displayName: 'CUDA Job Queue',
      description: 'The Deadline Cloud queue for running CUDA jobs.',
      jobAttachmentsBucket: this.jobAttachmentsBucket,
      // conda-forge is where the CUDA compilers and GPU frameworks live.
      condaChannels: ['deadline-cloud', 'conda-forge'],
    });

    this.fleet = new CudaLinuxFleet(this, 'CudaLinuxFleet', {
      farm: this.farm,
      maxWorkerCount: props.maxWorkerCount ?? 1,
    });
    this.queue.associateFleet(this.fleet);

    new cdk.CfnOutput(this, 'FarmId', {
      value: this.farm.farmId,
      description: 'The Deadline Cloud farm ID.',
    });
    new cdk.CfnOutput(this, 'QueueId', {
      value: this.queue.queueId,
      description: 'The CUDA queue ID.',
    });
    new cdk.CfnOutput(this, 'FleetId', {
      value: this.fleet.fleetId,
      description: 'The GPU fleet ID.',
    });
    new cdk.CfnOutput(this, 'JobAttachmentsBucketName', {
      value: this.jobAttachmentsBucket.bucketName,
      description: 'The S3 bucket holding job attachments.',
    });
  }
}
