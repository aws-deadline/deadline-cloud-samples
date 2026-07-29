// Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

import * as iam from 'aws-cdk-lib/aws-iam';
import * as s3 from 'aws-cdk-lib/aws-s3';

/** Anything holding an IAM role a Conda channel can be granted access to. */
export interface ICondaChannelGrantee {
  /** Add a statement to the grantee's role. */
  addToRolePolicy(statement: iam.PolicyStatement): void;
}

export interface CondaChannelProps {
  /** The bucket holding the channel. */
  readonly bucket: s3.IBucket;
  /**
   * The S3 prefix holding the farm's Conda channels.
   *
   * @default 'Conda'
   */
  readonly prefix?: string;
  /**
   * The channel's name, which is its directory below {@link prefix}.
   *
   * @default 'Default'
   */
  readonly name?: string;
}

/**
 * A private Conda channel on Amazon S3, holding packages built for a farm.
 *
 * This creates no resources of its own: a channel is a location in a bucket
 * that a package build job publishes to and that jobs install from. See
 * {@link https://docs.aws.amazon.com/deadline-cloud/latest/developerguide/publish-packages-s3-channel.html Publish packages to an Amazon S3 conda channel}
 * for how to initialize one after deploying.
 *
 * Grant a queue access with {@link grantRead} or {@link grantReadWrite}, and
 * pass {@link url} to a {@link CondaQueueEnvironment} so jobs install from it.
 */
export class CondaChannel {
  /** The bucket holding the channel. */
  public readonly bucket: s3.IBucket;
  /** The S3 prefix holding the farm's Conda channels. */
  public readonly prefix: string;
  /** The channel's name. */
  public readonly name: string;

  constructor(props: CondaChannelProps) {
    this.bucket = props.bucket;
    this.prefix = props.prefix ?? 'Conda';
    this.name = props.name ?? 'Default';
  }

  /** The `s3://` URL jobs use to install packages from this channel. */
  public get url(): string {
    return `s3://${this.bucket.bucketName}/${this.prefix}/${this.name}`;
  }

  /** Let the grantee install packages from the channel, but not change it. */
  public grantRead(grantee: ICondaChannelGrantee): void {
    this.grant(grantee, 'ReadOnly', ['s3:GetObject', 's3:ListBucket']);
  }

  /** Let the grantee publish packages to the channel as well as install from it. */
  public grantReadWrite(grantee: ICondaChannelGrantee): void {
    this.grant(grantee, 'ReadWrite', [
      's3:GetObject',
      's3:ListBucket',
      's3:PutObject',
      's3:DeleteObject',
    ]);
  }

  /** The S3 key prefix holding this channel's packages. */
  private get keyPrefix(): string {
    return `${this.prefix}/${this.name}`;
  }

  private grant(grantee: ICondaChannelGrantee, access: string, actions: string[]): void {
    grantee.addToRolePolicy(
      new iam.PolicyStatement({
        // The channel's location is part of the Sid because IAM requires Sids to
        // be unique within a policy document, and a queue can be granted access
        // to more than one channel. Without it, two channels granted to one queue
        // would collide and the deployment would fail with an IAM validation
        // error.
        sid: `CondaChannel${access}${sidFragment(this.keyPrefix)}`,
        actions,
        // Scoped to this channel's own directory, so granting one channel does
        // not reach a sibling channel sharing the prefix. The bucket itself is
        // included because S3 authorizes `ListBucket` against the bucket rather
        // than the objects in it; that listing is bucket-wide, matching what the
        // CloudFormation and Terraform starter farms grant.
        resources: [this.bucket.bucketArn, `${this.bucket.bucketArn}/${this.keyPrefix}/*`],
        conditions: {
          StringEquals: { 'aws:ResourceAccount': this.bucket.stack.account },
        },
      }),
    );
  }
}

/**
 * Turn a channel's key prefix into something an IAM `Sid` accepts.
 *
 * A Sid is limited to letters and digits, so the separators a prefix may contain
 * are dropped. The conventional `Conda/Default` location yields an empty
 * fragment, keeping the common case's Sid as the bare `CondaChannelReadOnly`.
 */
function sidFragment(keyPrefix: string): string {
  const alphanumeric = keyPrefix.replace(/[^A-Za-z0-9]/g, '');
  return alphanumeric === 'CondaDefault' ? '' : alphanumeric;
}
