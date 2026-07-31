// Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

import * as cdk from 'aws-cdk-lib';
import * as deadline from 'aws-cdk-lib/aws-deadline';
import * as iam from 'aws-cdk-lib/aws-iam';
import { Construct } from 'constructs';

export interface FarmProps {
  /** The farm's display name in Deadline Cloud. */
  readonly displayName: string;
  /** The farm's description. */
  readonly description?: string;
}

/**
 * An AWS Deadline Cloud farm.
 *
 * A farm is the container for the queues that hold jobs and the fleets that run
 * them. Create one, then add {@link Queue} and {@link ServiceManagedFleet}
 * constructs that point at it; each of those creates its own IAM role, scoped to
 * this farm by {@link deadlinePrincipal}.
 */
export class Farm extends Construct {
  /** The underlying L1 resource, for properties this construct does not expose. */
  public readonly cfnFarm: deadline.CfnFarm;
  /** The farm ID, such as `farm-1234567890abcdef1234567890abcdef`. */
  public readonly farmId: string;
  /** The farm's ARN. */
  public readonly farmArn: string;
  constructor(scope: Construct, id: string, props: FarmProps) {
    super(scope, id);

    this.cfnFarm = new deadline.CfnFarm(this, 'Resource', {
      displayName: props.displayName,
      description: props.description,
    });
    this.farmId = this.cfnFarm.attrFarmId;
    this.farmArn = this.cfnFarm.attrArn;
  }

  /**
   * The ARN pattern matching every CloudWatch Logs log group of this farm.
   *
   * Deadline Cloud writes worker and session logs to a log group per queue and
   * per fleet, all under the farm's prefix.
   */
  public get logGroupArn(): string {
    const stack = cdk.Stack.of(this);
    return `arn:${cdk.Aws.PARTITION}:logs:${stack.region}:${stack.account}:log-group:/aws/deadline/${this.farmId}/*`;
  }

  /**
   * A principal that lets Deadline Cloud assume a role on behalf of this farm
   * and no other.
   *
   * The source account and source ARN conditions guard against the
   * {@link https://docs.aws.amazon.com/IAM/latest/UserGuide/confused-deputy.html confused deputy problem},
   * so another customer's farm cannot use a role in your account.
   *
   * @param serviceNames the Deadline Cloud service prefixes to trust, such as
   * `deadline` and `credentials.deadline`. The DNS suffix of the partition is
   * appended to each.
   */
  public deadlinePrincipal(...serviceNames: string[]): iam.IPrincipal {
    const principals = serviceNames.map(
      (name) => new iam.ServicePrincipal(`${name}.${cdk.Aws.URL_SUFFIX}`),
    );
    return new iam.CompositePrincipal(...principals).withConditions({
      StringEquals: { 'aws:SourceAccount': cdk.Stack.of(this).account },
      ArnEquals: { 'aws:SourceArn': this.farmArn },
    });
  }
}
