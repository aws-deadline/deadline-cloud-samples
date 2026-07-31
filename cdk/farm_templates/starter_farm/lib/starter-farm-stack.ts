// Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

import * as cdk from 'aws-cdk-lib';
import { Construct } from 'constructs';

import {
  CondaChannel,
  CpuLinuxFleet,
  CpuWindowsFleet,
  CudaLinuxFleet,
  Farm,
  JobAttachmentsBucket,
  Queue,
  ServiceManagedFleet,
} from './deadline';

/** The fleet hardware shapes this stack can deploy, each a preset construct. */
const FLEET_PRESETS = {
  'cpu-linux': { id: 'CpuLinuxFleet', constructor: CpuLinuxFleet },
  'cpu-windows': { id: 'CpuWindowsFleet', constructor: CpuWindowsFleet },
  'cuda-linux': { id: 'CudaLinuxFleet', constructor: CudaLinuxFleet },
} as const;

/** The name of one of this stack's preset fleets. */
export type FleetPreset = keyof typeof FLEET_PRESETS;

/** Every preset name, for callers that want to deploy all of them. */
export const ALL_FLEET_PRESETS = Object.keys(FLEET_PRESETS) as FleetPreset[];

export interface StarterFarmStackProps extends cdk.StackProps {
  /**
   * The fleets to deploy, each associated with both queues.
   *
   * @default ['cpu-linux']
   */
  readonly fleets?: readonly FleetPreset[];
  /**
   * The public Conda channels the production queue's jobs install packages
   * from, after the farm's own S3 channel.
   *
   * Add `'conda-forge'` to also install packages built by the
   * {@link https://conda-forge.org/ conda-forge community}.
   *
   * @default ['deadline-cloud']
   */
  readonly condaChannels?: readonly string[];
}

/**
 * An AWS Deadline Cloud farm that can build the software its jobs run.
 *
 * This is the AWS CDK equivalent of the
 * {@link https://github.com/aws-deadline/deadline-cloud-samples/tree/mainline/cloudformation/farm_templates/starter_farm starter farm CloudFormation template}.
 * It adds two things to {@link SimpleFarmStack}: a private Conda channel on the
 * job attachments bucket, and a second queue whose jobs publish packages to it.
 * Together those let you run software the `deadline-cloud` channel does not
 * provide, such as your own tools and plugins, or an application at a version
 * you pin yourself.
 *
 * Only the package build queue can write to the channel. A production job can
 * read it, so it cannot modify the packages other jobs depend on.
 *
 * If you do not need custom packages yet, deploy {@link SimpleFarmStack}
 * instead: the private channel has to be initialized before Conda jobs can use
 * it, and that is setup you can skip until you need it.
 */
export class StarterFarmStack extends cdk.Stack {
  /** The Deadline Cloud farm. */
  public readonly farm: Farm;
  /** The S3 bucket holding job attachments and the private Conda channel. */
  public readonly jobAttachmentsBucket: JobAttachmentsBucket;
  /** The farm's private Conda channel, on the job attachments bucket. */
  public readonly condaChannel: CondaChannel;
  /** The queue for running production jobs. */
  public readonly productionQueue: Queue;
  /** The queue for building Conda packages to publish to {@link condaChannel}. */
  public readonly packageBuildQueue: Queue;
  /** The fleets deployed in the farm, in the order they were added. */
  public readonly fleets: ServiceManagedFleet[] = [];

  constructor(scope: Construct, id: string, props: StarterFarmStackProps = {}) {
    super(scope, id, props);

    this.farm = new Farm(this, 'Farm', {
      displayName: 'Starter Deadline Cloud Farm',
      description:
        'Deadline Cloud farm deployed by the StarterFarm stack of the starter_farm CDK sample.',
    });

    this.jobAttachmentsBucket = new JobAttachmentsBucket(this, 'JobAttachmentsBucket');
    this.condaChannel = new CondaChannel({ bucket: this.jobAttachmentsBucket });

    // The production queue, where rendering and other production jobs are
    // submitted. Passing the private channel puts it ahead of the public ones in
    // the queue environment, and grants this queue's role read access to it.
    this.productionQueue = new Queue(this, 'ProductionQueue', {
      farm: this.farm,
      displayName: 'Production Job Queue',
      description: 'The Deadline Cloud queue for running production jobs.',
      jobAttachmentsBucket: this.jobAttachmentsBucket,
      jobAttachmentsPrefix: 'DeadlineCloud',
      condaChannels: [this.condaChannel, ...(props.condaChannels ?? ['deadline-cloud'])],
    });

    // The package build queue, where jobs built from the repository's Conda
    // recipes publish packages to the farm's channel.
    this.packageBuildQueue = new Queue(this, 'PackageBuildQueue', {
      farm: this.farm,
      displayName: 'Package Build Queue',
      description: 'The Deadline Cloud queue for building conda packages.',
      jobAttachmentsBucket: this.jobAttachmentsBucket,
      // Its own prefix, so the permissions on this queue's role do not reach
      // the production queue's job attachments.
      jobAttachmentsPrefix: 'DeadlineCloudPkgBld',
      // No Conda queue environment on this queue. The package build job bundles
      // in conda_recipes/ carry their own `Package Build Env` job environment,
      // which installs the conda-build toolchain themselves, and they define a
      // `CondaChannels` job parameter of their own naming the channels a recipe
      // builds against. A queue environment here would define that same
      // parameter, leaving one name meaning two things. This also matches the
      // CloudFormation and Terraform starter farms, which attach a queue
      // environment only to the production queue.
      addDefaultCondaQueueEnvironment: false,
    });
    this.condaChannel.grantReadWrite(this.packageBuildQueue);

    for (const preset of props.fleets ?? ['cpu-linux']) {
      const { id, constructor: FleetConstructor } = FLEET_PRESETS[preset];
      this.addFleet(new FleetConstructor(this, id, { farm: this.farm }));
    }

    new cdk.CfnOutput(this, 'FarmId', {
      value: this.farm.farmId,
      description: 'The Deadline Cloud farm ID.',
    });
    new cdk.CfnOutput(this, 'ProductionQueueId', {
      value: this.productionQueue.queueId,
      description: 'The production queue ID.',
    });
    new cdk.CfnOutput(this, 'PackageBuildQueueId', {
      value: this.packageBuildQueue.queueId,
      description: 'The package build queue ID.',
    });
    new cdk.CfnOutput(this, 'JobAttachmentsBucketName', {
      value: this.jobAttachmentsBucket.bucketName,
      description: 'The S3 bucket holding job attachments and the private Conda channel.',
    });
    new cdk.CfnOutput(this, 'CondaChannelUrl', {
      value: this.condaChannel.url,
      description: "The farm's private S3 Conda channel URL.",
    });
  }

  /**
   * Add a fleet to the farm, associated with both of its queues.
   *
   * Use this to add a fleet the presets do not cover:
   *
   * ```ts
   * farmStack.addFleet(
   *   new ServiceManagedFleet(farmStack, 'ArmLinuxFleet', {
   *     farm: farmStack.farm,
   *     displayName: 'ARM Linux Fleet',
   *     osFamily: 'LINUX',
   *     cpuArchitecture: 'arm64',
   *     maxWorkerCount: 20,
   *     vCpuCount: { min: 4, max: 16 },
   *     memoryMiB: { min: 8192 },
   *   }),
   * );
   * ```
   */
  public addFleet(fleet: ServiceManagedFleet): ServiceManagedFleet {
    this.fleets.push(fleet);
    this.productionQueue.associateFleet(fleet);
    this.packageBuildQueue.associateFleet(fleet);

    new cdk.CfnOutput(this, `${outputNameFor(fleet)}Id`, {
      value: fleet.fleetId,
      description: `The fleet ID of "${fleet.cfnFleet.displayName}".`,
    });
    return fleet;
  }
}

/**
 * The stack output name for a fleet's ID, derived from its construct ID.
 *
 * CloudFormation output names are alphanumeric, so an ID containing anything
 * else is rejected here. Without this, two fleets whose IDs differ only in
 * punctuation -- `render-gpu` and `render.gpu` -- would both want the output
 * `rendergpuId`, and CDK would report the collision without saying which
 * constructs caused it.
 */
function outputNameFor(fleet: ServiceManagedFleet): string {
  const id = fleet.node.id;
  if (!/^[A-Za-z0-9]+$/.test(id)) {
    throw new Error(
      `The fleet construct ID ${JSON.stringify(id)} is used to name a stack output, ` +
        'so it must contain only letters and digits. Rename the fleet, for example to ' +
        `${JSON.stringify(id.replace(/[^A-Za-z0-9]/g, '') || 'MyFleet')}.`,
    );
  }
  return id;
}
