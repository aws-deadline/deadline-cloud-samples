// Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

import * as cdk from 'aws-cdk-lib';
import * as deadline from 'aws-cdk-lib/aws-deadline';
import * as iam from 'aws-cdk-lib/aws-iam';
import { Construct } from 'constructs';

import { Farm } from './farm';

// The hardware ranges and the EBS volume are the L1 property types, aliased
// rather than redeclared: they are already plain `{ min, max? }` and
// `{ sizeGiB?, iops?, throughputMiB? }` structures with the service's own
// documentation on each field, and re-declaring them here would be one more
// place to update when the service adds a property.

/** The acceptable range of vCPU counts on a worker host. */
export type VCpuCountRange = deadline.CfnFleet.VCpuCountRangeProperty;

/** The acceptable range of RAM, in MiB, on a worker host. */
export type MemoryMiBRange = deadline.CfnFleet.MemoryMiBRangeProperty;

/** The acceptable range of GPU accelerator counts on a worker host. */
export type AcceleratorCountRange = deadline.CfnFleet.AcceleratorCountRangeProperty;

/** The root EBS volume of a fleet's worker hosts. */
export type RootEbsVolume = deadline.CfnFleet.Ec2EbsVolumeProperty;

/**
 * The GPU accelerators a fleet's worker hosts must have.
 *
 * Unlike the ranges above, this is not the L1 `AcceleratorCapabilitiesProperty`.
 * That type takes a `selections` list of `{ name, runtime }` pairs, and the
 * service requires every accelerator in a fleet to use the same runtime -- a rule
 * you can break by construction. Taking the names and one shared `runtime`
 * instead makes that impossible, and turns the common case into
 * `names: ['a10g', 'l4']`.
 */
export interface AcceleratorRequirement {
  /**
   * The accelerator chips that satisfy the requirement.
   *
   * Deadline Cloud picks instance types offering any one of them, so naming
   * several widens the pool of instances the fleet can get. See the
   * {@link https://docs.aws.amazon.com/deadline-cloud/latest/APIReference/API_AcceleratorSelection.html AcceleratorSelection API reference}
   * for the supported names.
   */
  readonly names: readonly string[];
  /**
   * How many accelerators a worker host must have.
   *
   * @default exactly one
   */
  readonly count?: AcceleratorCountRange;
  /**
   * The GPU driver runtime to install. Every accelerator in a fleet uses the
   * same one.
   *
   * @default 'latest'
   */
  readonly runtime?: string;
}

export interface ServiceManagedFleetProps {
  /** The farm the fleet belongs to. */
  readonly farm: Farm;
  /** The fleet's display name in Deadline Cloud. */
  readonly displayName: string;
  /** The fleet's description. */
  readonly description?: string;
  /** Whether worker hosts run Linux or Windows. */
  readonly osFamily: 'LINUX' | 'WINDOWS';
  /**
   * The CPU architecture of worker hosts.
   *
   * @default 'x86_64'
   */
  readonly cpuArchitecture?: 'x86_64' | 'arm64';
  /**
   * Which EC2 instance market worker hosts come from, trading cost against how
   * soon a job starts and whether it can be interrupted.
   *
   * - `on-demand` costs the most and is not interrupted. Use it for work that
   *   has to finish by a deadline, and for long tasks.
   * - `spot` uses unreserved capacity at a discount, and can be interrupted by
   *   on-demand requests.
   * - `wait-and-save` costs the least and schedules jobs with a delay, waiting
   *   for cheap capacity rather than starting as soon as work is queued. It can
   *   be interrupted by both on-demand and spot requests. Suited to work with no
   *   deadline, such as an overnight batch.
   *
   * An interruption is not a save: Deadline Cloud retries the interrupted task on
   * another worker from the beginning, so a long task loses its progress. Weigh
   * that against the discount, and prefer `on-demand` as tasks get longer.
   *
   * The service rejects `wait-and-save` together with {@link accelerators}, so a
   * GPU fleet uses `spot` or `on-demand`.
   *
   * @default 'spot'
   */
  readonly instanceMarketType?: 'on-demand' | 'spot' | 'wait-and-save';
  /** The maximum number of worker hosts the fleet scales up to. */
  readonly maxWorkerCount: number;
  /**
   * The number of worker hosts the fleet keeps running even when idle.
   *
   * Leave this at zero unless you need jobs to start without waiting for an
   * instance to launch; an idle worker still costs money.
   *
   * @default 0
   */
  readonly minWorkerCount?: number;
  /** The range of vCPU counts acceptable on a worker host. */
  readonly vCpuCount: VCpuCountRange;
  /** The range of RAM, in MiB, acceptable on a worker host. */
  readonly memoryMiB: MemoryMiBRange;
  /**
   * The GPU accelerators worker hosts must have.
   *
   * @default worker hosts have no GPU requirement
   */
  readonly accelerators?: AcceleratorRequirement;
  /**
   * The root EBS volume of worker hosts.
   *
   * @default 300 GiB at 3000 IOPS and 125 MiB of throughput
   */
  readonly rootEbsVolume?: RootEbsVolume;
  /**
   * An existing IAM role for the fleet's worker hosts to run as.
   *
   * Pass this only to share one role across fleets, or to reuse a role created
   * elsewhere. By default the fleet creates its own, so a permission added for
   * one fleet's workers does not reach another's.
   *
   * @default a role created for this fleet
   */
  readonly role?: iam.IRole;
}

/** The root EBS volume a fleet gets when {@link ServiceManagedFleetProps.rootEbsVolume} is omitted. */
export const DEFAULT_ROOT_EBS_VOLUME: RootEbsVolume = {
  sizeGiB: 300,
  iops: 3000,
  throughputMiB: 125,
};

/**
 * A fleet of worker hosts that AWS Deadline Cloud launches, scales, and patches
 * for you.
 *
 * The fleet describes the hardware a worker host needs rather than naming
 * instance types, and Deadline Cloud picks matching EC2 instances. It scales
 * from {@link ServiceManagedFleetProps.minWorkerCount} up to
 * {@link ServiceManagedFleetProps.maxWorkerCount} with the work queued for it.
 *
 * Associate it with the queues whose jobs should run on it using
 * {@link Queue.associateFleet}. For the common hardware shapes, use
 * {@link CpuLinuxFleet}, {@link CpuWindowsFleet}, or {@link CudaLinuxFleet}
 * instead of configuring this directly.
 *
 * The fleet's {@link role} is created for it and starts with only what every
 * worker host needs: the `AWSDeadlineCloud-FleetWorker` managed policy and
 * permission to write the farm's logs. Grant a fleet's workers anything further
 * with {@link addToRolePolicy}, or with the `grant*` methods of the resource in
 * question, and only that fleet gets it.
 */
export class ServiceManagedFleet extends Construct {
  /** The underlying L1 resource, for properties this construct does not expose. */
  public readonly cfnFleet: deadline.CfnFleet;
  /** The fleet ID, such as `fleet-1234567890abcdef1234567890abcdef`. */
  public readonly fleetId: string;
  /** The IAM role the fleet's worker hosts run as. */
  public readonly role: iam.IRole;

  /** The policy on a role this fleet created, which {@link addToRolePolicy} adds to. */
  private readonly policy?: iam.PolicyDocument;

  constructor(scope: Construct, id: string, props: ServiceManagedFleetProps) {
    super(scope, id);

    if (props.role) {
      this.role = props.role;
    } else {
      this.policy = new iam.PolicyDocument();
      this.role = createWorkerRole(this, props.farm, this.policy);
    }

    const instanceMarketType = props.instanceMarketType ?? 'spot';
    if (instanceMarketType === 'wait-and-save' && props.accelerators) {
      // The service rejects the combination at CreateFleet, which CloudFormation
      // surfaces only partway through a deployment.
      throw new Error(
        `The fleet ${id} asks for GPU accelerators on a wait-and-save fleet, which ` +
          'AWS Deadline Cloud does not support. Use `spot` or `on-demand` for a fleet ' +
          'with accelerators.',
      );
    }

    this.cfnFleet = new deadline.CfnFleet(this, 'Resource', {
      displayName: props.displayName,
      description: props.description,
      farmId: props.farm.farmId,
      roleArn: this.role.roleArn,
      minWorkerCount: props.minWorkerCount ?? 0,
      maxWorkerCount: props.maxWorkerCount,
      configuration: {
        serviceManagedEc2: {
          instanceCapabilities: {
            osFamily: props.osFamily,
            cpuArchitectureType: props.cpuArchitecture ?? 'x86_64',
            vCpuCount: props.vCpuCount,
            memoryMiB: props.memoryMiB,
            rootEbsVolume: props.rootEbsVolume ?? DEFAULT_ROOT_EBS_VOLUME,
            acceleratorCapabilities: acceleratorCapabilities(props.accelerators),
          },
          instanceMarketOptions: { type: instanceMarketType },
        },
      },
    });
    this.fleetId = this.cfnFleet.attrFleetId;
  }

  /**
   * Add a permission to the IAM role this fleet's worker hosts run as.
   *
   * Only this fleet's workers get it. Throws if the fleet was given an existing
   * {@link ServiceManagedFleetProps.role}, since adding to a role the fleet does
   * not own would silently affect whatever else uses it; add to that role
   * directly instead.
   */
  public addToRolePolicy(statement: iam.PolicyStatement): void {
    if (!this.policy) {
      throw new Error(
        `The fleet ${this.node.id} was given an existing role, so it does not own ` +
          'the role its workers run as. Add the statement to that role directly, or ' +
          'let the fleet create its own role by omitting the `role` property.',
      );
    }
    this.policy.addStatements(statement);
  }
}

/**
 * Create the IAM role a fleet's worker hosts run as.
 *
 * Every fleet gets its own, so a permission added for one fleet's workers does
 * not reach another's. The role starts with the service's managed policy for
 * fleet workers plus permission to write this farm's logs, and nothing else.
 */
function createWorkerRole(
  fleet: Construct,
  farm: Farm,
  policy: iam.PolicyDocument,
): iam.Role {
  policy.addStatements(
    new iam.PolicyStatement({
      // Lets Deadline Cloud create log streams for the farm.
      sid: 'CreateFarmLogStreams',
      actions: ['logs:CreateLogStream'],
      resources: [farm.logGroupArn],
      conditions: {
        'ForAnyValue:StringEquals': {
          'aws:CalledVia': `deadline.${cdk.Aws.URL_SUFFIX}`,
        },
      },
    }),
    new iam.PolicyStatement({
      // `PutLogEvents` lets a worker write its own log and the session logs of
      // the jobs it runs; `GetLogEvents` lets Deadline Cloud monitor users read
      // those worker logs.
      sid: 'WriteFarmLogs',
      actions: ['logs:PutLogEvents', 'logs:GetLogEvents'],
      resources: [farm.logGroupArn],
    }),
  );

  return new iam.Role(fleet, 'Role', {
    assumedBy: farm.deadlinePrincipal('credentials.deadline'),
    managedPolicies: [
      iam.ManagedPolicy.fromAwsManagedPolicyName('AWSDeadlineCloud-FleetWorker'),
    ],
    inlinePolicies: { FleetWorkerPolicy: policy },
  });
}

/**
 * The properties of a preset fleet such as {@link CpuLinuxFleet}.
 *
 * Everything except the farm is optional, because the preset supplies a default
 * for it. Pass a property to override that default -- for example a higher
 * `maxWorkerCount`, `instanceMarketType: 'on-demand'` for work that must not be
 * interrupted, or `instanceMarketType: 'wait-and-save'` for work that can wait
 * for cheaper capacity.
 */
export type PresetFleetProps = { readonly farm: Farm } & Partial<
  Omit<ServiceManagedFleetProps, 'farm'>
>;

/**
 * A fleet of Linux worker hosts for CPU work, such as simulation, encoding, and
 * CPU rendering.
 *
 * Defaults to up to 10 spot instances with 2-8 vCPUs and at least 16 GiB of RAM.
 * Pass `instanceMarketType` to trade that discount for jobs that start sooner
 * (`on-demand`) or cost less still (`wait-and-save`).
 */
export class CpuLinuxFleet extends ServiceManagedFleet {
  constructor(scope: Construct, id: string, props: PresetFleetProps) {
    super(scope, id, {
      ...preset(props, {
        displayName: 'CPU Linux Fleet',
        osFamily: 'LINUX',
        instanceMarketType: 'spot',
        maxWorkerCount: 10,
        vCpuCount: { min: 2, max: 8 },
        memoryMiB: { min: 16384 },
      }),
      farm: props.farm,
    });
  }
}

/**
 * A fleet of Windows worker hosts, for jobs that need applications or plugins
 * that only run on Windows.
 *
 * Defaults to the same hardware as {@link CpuLinuxFleet}.
 */
export class CpuWindowsFleet extends ServiceManagedFleet {
  constructor(scope: Construct, id: string, props: PresetFleetProps) {
    super(scope, id, {
      ...preset(props, {
        displayName: 'CPU Windows Fleet',
        osFamily: 'WINDOWS',
        instanceMarketType: 'spot',
        maxWorkerCount: 10,
        vCpuCount: { min: 2, max: 8 },
        memoryMiB: { min: 16384 },
      }),
      farm: props.farm,
    });
  }
}

/**
 * A fleet of Linux worker hosts with an NVIDIA GPU, for CUDA work such as GPU
 * rendering, machine learning, and 3D reconstruction.
 *
 * Defaults to a single on-demand instance with one A10G or L4 accelerator,
 * 4-16 vCPUs, and at least 32 GiB of RAM. On-demand rather than spot, because a
 * long GPU job loses more work to an interruption than it saves in instance
 * cost; pass `instanceMarketType: 'spot'` if your jobs are short or
 * checkpointed. GPU instances are expensive, so raise `maxWorkerCount` from one
 * deliberately.
 */
export class CudaLinuxFleet extends ServiceManagedFleet {
  constructor(scope: Construct, id: string, props: PresetFleetProps) {
    super(scope, id, {
      ...preset(props, {
        displayName: 'CUDA Linux Fleet',
        osFamily: 'LINUX',
        instanceMarketType: 'on-demand',
        maxWorkerCount: 1,
        vCpuCount: { min: 4, max: 16 },
        memoryMiB: { min: 32768 },
        accelerators: { names: ['a10g', 'l4'] },
      }),
      farm: props.farm,
    });
  }
}

/**
 * Apply a preset's defaults under the caller's overrides.
 *
 * A property the caller left out is `undefined` rather than absent, so the
 * overrides are filtered before being spread over the defaults; otherwise an
 * omitted property would erase the preset's value for it.
 */
function preset(
  overrides: PresetFleetProps,
  defaults: Omit<ServiceManagedFleetProps, 'farm'>,
): Omit<ServiceManagedFleetProps, 'farm'> {
  const provided = Object.fromEntries(
    Object.entries(overrides).filter(([, value]) => value !== undefined),
  );
  return { ...defaults, ...provided };
}

/** Translate a GPU requirement into the fleet's accelerator capabilities. */
function acceleratorCapabilities(
  accelerators?: AcceleratorRequirement,
): deadline.CfnFleet.AcceleratorCapabilitiesProperty | undefined {
  if (!accelerators) {
    return undefined;
  }
  if (accelerators.names.length === 0) {
    throw new Error(
      'A fleet with an accelerator requirement must name at least one accelerator. ' +
        'Omit `accelerators` for a fleet that does not need a GPU.',
    );
  }

  const runtime = accelerators.runtime ?? 'latest';
  return {
    count: accelerators.count ?? { min: 1, max: 1 },
    selections: accelerators.names.map((name) => ({ name, runtime })),
  };
}
