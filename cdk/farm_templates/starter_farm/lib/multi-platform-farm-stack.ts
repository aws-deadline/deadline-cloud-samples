// Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

import * as cdk from 'aws-cdk-lib';
import { Construct } from 'constructs';

import {
  CpuLinuxFleet,
  CpuWindowsFleet,
  CudaLinuxFleet,
  Farm,
  JobAttachmentsBucket,
  Queue,
  ServiceManagedFleet,
} from './deadline';

export interface MultiPlatformFarmStackProps extends cdk.StackProps {
}

/**
 * An AWS Deadline Cloud farm whose one queue reaches Linux, Windows, and GPU
 * hardware.
 *
 * A queue can be associated with any number of fleets, and Deadline Cloud sends
 * each step of a job to a fleet whose worker hosts satisfy that step's
 * {@link https://github.com/OpenJobDescription/openjd-specifications/wiki/2023-09-Template-Schemas#33-hostrequirements hostRequirements}.
 * That means one submission can span platforms: render on GPU hosts, run a
 * Windows-only plugin on Windows hosts, and encode the result on cheap CPU
 * hosts.
 *
 * A job step selects hardware by describing what it needs, not by naming a
 * fleet:
 *
 * ```yaml
 * - name: RenderOnGpu
 *   hostRequirements:
 *     attributes:
 *       - name: attr.worker.os.family
 *         anyOf: ["linux"]
 *     amounts:
 *       - name: amount.worker.gpu
 *         min: 1
 * ```
 *
 * A step with no `hostRequirements` can land on any of the three fleets, so
 * constrain the steps that care. That matters more here than on a single-fleet
 * farm: Conda packages are built per platform, so a step asking for
 * `CondaPackages=blender` needs to be pinned to the operating system that has a
 * build of it, or it can be scheduled onto a fleet where the package does not
 * exist and fail while installing.
 */
export class MultiPlatformFarmStack extends cdk.Stack {
  /** The Deadline Cloud farm. */
  public readonly farm: Farm;
  /** The S3 bucket holding job attachments. */
  public readonly jobAttachmentsBucket: JobAttachmentsBucket;
  /** The queue every job is submitted to, whichever platform its steps need. */
  public readonly queue: Queue;
  /** The fleets the queue can send work to. */
  public readonly fleets: ServiceManagedFleet[];

  constructor(scope: Construct, id: string, props: MultiPlatformFarmStackProps = {}) {
    super(scope, id, props);

    this.farm = new Farm(this, 'Farm', {
      displayName: 'Multi-platform Deadline Cloud Farm',
      description:
        'Deadline Cloud farm deployed by the MultiPlatformFarm stack of the ' +
        'starter_farm CDK sample.',
    });

    this.jobAttachmentsBucket = new JobAttachmentsBucket(this, 'JobAttachmentsBucket');

    this.queue = new Queue(this, 'Queue', {
      farm: this.farm,
      displayName: 'Job Queue',
      description: 'The Deadline Cloud queue for jobs that span platforms.',
      jobAttachmentsBucket: this.jobAttachmentsBucket,
      // conda-forge carries the cross-platform build of many tools, which helps
      // when the same job step has to run on both Linux and Windows.
      condaChannels: ['deadline-cloud', 'conda-forge'],
    });

    // One fleet per hardware shape, all on the same queue. Each gets its own IAM
    // role, so a permission the Windows workers need does not reach the others.
    this.fleets = [
      new CpuLinuxFleet(this, 'CpuLinuxFleet', { farm: this.farm }),
      new CpuWindowsFleet(this, 'CpuWindowsFleet', { farm: this.farm }),
      new CudaLinuxFleet(this, 'CudaLinuxFleet', { farm: this.farm }),
    ];
    for (const fleet of this.fleets) {
      this.queue.associateFleet(fleet);

      new cdk.CfnOutput(this, `${fleet.node.id}Id`, {
        value: fleet.fleetId,
        description: `The fleet ID of "${fleet.cfnFleet.displayName}".`,
      });
    }

    new cdk.CfnOutput(this, 'FarmId', {
      value: this.farm.farmId,
      description: 'The Deadline Cloud farm ID.',
    });
    new cdk.CfnOutput(this, 'QueueId', {
      value: this.queue.queueId,
      description: 'The queue ID.',
    });
    new cdk.CfnOutput(this, 'JobAttachmentsBucketName', {
      value: this.jobAttachmentsBucket.bucketName,
      description: 'The S3 bucket holding job attachments.',
    });
  }
}
