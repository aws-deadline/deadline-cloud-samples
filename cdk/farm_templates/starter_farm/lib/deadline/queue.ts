// Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

import * as cdk from 'aws-cdk-lib';
import * as deadline from 'aws-cdk-lib/aws-deadline';
import * as iam from 'aws-cdk-lib/aws-iam';
import * as s3 from 'aws-cdk-lib/aws-s3';
import { Construct } from 'constructs';

import { CondaChannel, ICondaChannelGrantee } from './conda-channel';
import { Farm } from './farm';
import { ServiceManagedFleet } from './fleet';
import { CondaQueueEnvironment, IQueueEnvironment } from './queue-environment';

export interface QueueProps {
  /** The farm the queue belongs to. */
  readonly farm: Farm;
  /** The queue's display name in Deadline Cloud. */
  readonly displayName: string;
  /** The queue's description. */
  readonly description?: string;
  /**
   * The bucket the queue stores job attachments in.
   *
   * Omit it for a queue whose jobs pass no input or output files, such as one
   * that only reads from and writes to shared storage.
   *
   * @default no job attachments are configured
   */
  readonly jobAttachmentsBucket?: s3.IBucket;
  /**
   * The S3 prefix the queue stores job attachments under.
   *
   * Give each queue on a bucket its own prefix, so one queue's role cannot read
   * or write another queue's job attachments. Note that `s3:ListBucket` is
   * authorized against the bucket rather than its objects, so a queue can still
   * enumerate key names outside its prefix; this matches what the CloudFormation
   * and Terraform starter farms grant.
   *
   * @default 'DeadlineCloud'
   */
  readonly jobAttachmentsPrefix?: string;
  /**
   * Whether to add a Conda queue environment, so jobs can name the applications
   * they need in the `CondaPackages` parameter.
   *
   * Set this to `false` for a queue whose jobs bring their own software, such as
   * one that runs only shell scripts, or when you want to add a differently
   * configured {@link CondaQueueEnvironment} with {@link addEnvironment}
   * yourself.
   *
   * @default true
   */
  readonly addDefaultCondaQueueEnvironment?: boolean;
  /**
   * The Conda channels the queue's jobs install packages from, in order of
   * preference.
   *
   * Pass a {@link CondaChannel} for a private channel holding the farm's own
   * packages, and a string for a named public channel. Setting this alongside
   * `addDefaultCondaQueueEnvironment: false` is an error, since there would be no
   * environment to apply the channels to.
   *
   * @default ['deadline-cloud'], the applications Deadline Cloud provides
   */
  readonly condaChannels?: readonly (CondaChannel | string)[];
}

/**
 * An AWS Deadline Cloud queue, and the IAM role its jobs run as.
 *
 * Jobs are submitted to a queue and run on the fleets associated with it. Add a
 * fleet with {@link associateFleet}.
 *
 * The queue comes with a {@link CondaQueueEnvironment}, so a job can name the
 * applications it needs in the `CondaPackages` parameter and have them installed
 * before its steps run. Point it at a private {@link CondaChannel} with
 * {@link QueueProps.condaChannels}, turn it off with
 * {@link QueueProps.addDefaultCondaQueueEnvironment}, or add more environments of your own
 * with {@link addEnvironment}.
 *
 * The queue's {@link role} starts with access to its own job attachments prefix,
 * its session logs, and the Deadline Cloud provided software, and nothing else.
 * Grant it whatever else the queue's jobs need -- a Conda channel, a shared file
 * system, an asset database -- with the `grant*` methods of the resource in
 * question, or with {@link addToRolePolicy} directly.
 */
export class Queue extends Construct implements ICondaChannelGrantee {
  /** The underlying L1 resource, for properties this construct does not expose. */
  public readonly cfnQueue: deadline.CfnQueue;
  /** The queue ID, such as `queue-1234567890abcdef1234567890abcdef`. */
  public readonly queueId: string;
  /** The farm the queue belongs to. */
  public readonly farm: Farm;
  /** The IAM role the queue's jobs run as. */
  public readonly role: iam.Role;

  /** The policy on the queue's role, which the `grant*` methods add to. */
  private readonly policy: iam.PolicyDocument;
  /** How many environments have been added, which sets the next one's priority. */
  private environmentCount = 0;

  constructor(scope: Construct, id: string, props: QueueProps) {
    super(scope, id);

    this.farm = props.farm;
    this.policy = new iam.PolicyDocument();
    this.role = new iam.Role(this, 'Role', {
      assumedBy: this.farm.deadlinePrincipal('deadline', 'credentials.deadline'),
      inlinePolicies: { QueuePolicy: this.policy },
    });

    // Every queue's jobs read their own session logs and install the Deadline
    // Cloud provided software, so those are granted here rather than left to
    // the caller to remember.
    this.grantReadJobLogs();
    this.grantReadDeadlineSoftware();

    const jobAttachmentsPrefix = props.jobAttachmentsPrefix ?? 'DeadlineCloud';
    if (props.jobAttachmentsBucket) {
      this.grantReadWriteJobAttachments(props.jobAttachmentsBucket, jobAttachmentsPrefix);
    }

    this.cfnQueue = new deadline.CfnQueue(this, 'Resource', {
      displayName: props.displayName,
      description: props.description,
      farmId: this.farm.farmId,
      roleArn: this.role.roleArn,
      jobAttachmentSettings: props.jobAttachmentsBucket
        ? {
            s3BucketName: props.jobAttachmentsBucket.bucketName,
            rootPrefix: jobAttachmentsPrefix,
          }
        : undefined,
    });
    this.queueId = this.cfnQueue.attrQueueId;

    const addDefaultCondaQueueEnvironment = props.addDefaultCondaQueueEnvironment ?? true;
    if (!addDefaultCondaQueueEnvironment && props.condaChannels) {
      throw new Error(
        `The queue ${id} sets condaChannels alongside ` +
          'addDefaultCondaQueueEnvironment: false, so the channels would have no ' +
          'effect. Drop the channels, or let the queue add its Conda environment.',
      );
    }
    if (addDefaultCondaQueueEnvironment) {
      const channels = props.condaChannels ?? ['deadline-cloud'];
      // A private channel is only readable if the queue's role says so, and
      // forgetting that leaves jobs failing at Conda install time rather than at
      // synth. Granting here means passing a channel is all it takes.
      for (const channel of channels) {
        if (channel instanceof CondaChannel) {
          channel.grantRead(this);
        }
      }
      this.addEnvironment(new CondaQueueEnvironment({ channels }));
    }
  }

  /**
   * Add a queue environment, which sets up software or configuration before the
   * steps of every job in the queue run.
   *
   * Environments apply in the order they are added: the first gets priority 1,
   * and a later one can override what an earlier one set.
   */
  public addEnvironment(environment: IQueueEnvironment): deadline.CfnQueueEnvironment {
    this.environmentCount += 1;
    const priority = this.environmentCount;

    return new deadline.CfnQueueEnvironment(this, `Environment${priority}`, {
      farmId: this.farm.farmId,
      queueId: this.queueId,
      priority,
      templateType: 'YAML',
      template: environment.templateYaml,
    });
  }

  /**
   * Let the queue's jobs run on a fleet's worker hosts.
   *
   * A queue can be associated with several fleets, and a fleet with several
   * queues.
   */
  public associateFleet(fleet: ServiceManagedFleet): deadline.CfnQueueFleetAssociation {
    return new deadline.CfnQueueFleetAssociation(this, `${fleet.node.id}Association`, {
      farmId: this.farm.farmId,
      queueId: this.queueId,
      fleetId: fleet.fleetId,
    });
  }

  /** Add a permission to the IAM role the queue's jobs run as. */
  public addToRolePolicy(statement: iam.PolicyStatement): void {
    this.policy.addStatements(statement);
  }

  /** Let the queue's jobs read and write job attachments under their own prefix. */
  private grantReadWriteJobAttachments(bucket: s3.IBucket, prefix: string): void {
    this.addToRolePolicy(
      new iam.PolicyStatement({
        sid: 'JobAttachmentsReadWrite',
        actions: ['s3:GetObject', 's3:PutObject', 's3:ListBucket', 's3:GetBucketLocation'],
        // The bucket itself is included so a job can list the prefix, which S3
        // authorizes against the bucket rather than the objects in it.
        resources: [bucket.bucketArn, `${bucket.bucketArn}/${prefix}/*`],
        conditions: { StringEquals: { 'aws:ResourceAccount': bucket.stack.account } },
      }),
    );
  }

  /** Let the queue's jobs read the session logs they produce. */
  private grantReadJobLogs(): void {
    this.addToRolePolicy(
      new iam.PolicyStatement({
        sid: 'JobLogsReadOnly',
        actions: ['logs:GetLogEvents'],
        resources: [this.farm.logGroupArn],
      }),
    );
  }

  /**
   * Let the queue's jobs install the Deadline Cloud provided software, such as
   * the packages in the `deadline-cloud` Conda channel.
   *
   * The service hosts that software behind S3 access points it owns, so the
   * resource has to be `*` and is narrowed by the access point conditions.
   */
  private grantReadDeadlineSoftware(): void {
    this.addToRolePolicy(
      new iam.PolicyStatement({
        sid: 'DeadlineServiceManagedFleetSoftwareAccess',
        actions: ['s3:GetObject', 's3:ListBucket'],
        resources: ['*'],
        conditions: {
          ArnLike: {
            's3:DataAccessPointArn': `arn:${cdk.Aws.PARTITION}:s3:*:*:accesspoint/deadline-software-*`,
          },
          StringEquals: { 's3:AccessPointNetworkOrigin': 'VPC' },
        },
      }),
    );
  }
}
