// Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

import * as cdk from 'aws-cdk-lib';
import * as s3 from 'aws-cdk-lib/aws-s3';
import { Construct } from 'constructs';

export interface JobAttachmentsBucketProps {
  /**
   * What to do with the bucket when the stack is deleted.
   *
   * The default deletes it along with the stack, and empties it first, because
   * CloudFormation cannot delete a bucket that still holds objects. That keeps a
   * farm you deployed to try out from leaving storage behind.
   *
   * Pass {@link cdk.RemovalPolicy.RETAIN} for a farm holding work you care
   * about, so a `cdk destroy` cannot take its job attachments or published Conda
   * packages with it.
   *
   * @default cdk.RemovalPolicy.DESTROY
   */
  readonly removalPolicy?: cdk.RemovalPolicy;
}

/**
 * An S3 bucket for a farm's job attachments, and for {@link CondaChannel}s.
 *
 * This is an `s3.Bucket` with the settings a farm's storage should have: public
 * access blocked, server-side encryption on, and TLS required for every
 * request. It is deleted with the stack by default; see
 * {@link JobAttachmentsBucketProps.removalPolicy} before using one for work you
 * need to keep. Access is granted per queue, by {@link Queue} for the job
 * attachments prefix it owns and by {@link CondaChannel.grantRead} or
 * {@link CondaChannel.grantReadWrite} for a Conda channel.
 */
export class JobAttachmentsBucket extends s3.Bucket {
  constructor(scope: Construct, id: string, props: JobAttachmentsBucketProps = {}) {
    const removalPolicy = props.removalPolicy ?? cdk.RemovalPolicy.DESTROY;
    super(scope, id, {
      blockPublicAccess: s3.BlockPublicAccess.BLOCK_ALL,
      encryption: s3.BucketEncryption.S3_MANAGED,
      enforceSSL: true,
      versioned: false,
      removalPolicy,
      autoDeleteObjects: removalPolicy === cdk.RemovalPolicy.DESTROY,
    });
  }
}
