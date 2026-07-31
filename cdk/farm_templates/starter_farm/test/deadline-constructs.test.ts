// Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

// Tests for the reusable constructs in lib/deadline/, exercised on their own
// rather than through the starter farm stack. They cover what a construct
// promises to any farm that composes it; test/starter-farm-stack.test.ts covers
// how this sample wires them together.

import * as cdk from 'aws-cdk-lib';
import { Match, Template } from 'aws-cdk-lib/assertions';
import * as yaml from 'yaml';

import {
  condaChannelsDefault,
  farmRoles,
  inlineStatements,
  inlineStatementSids,
  renderSynthesized,
  renderSynthesizedString,
  trustStatements,
} from './helpers';
import {
  CondaChannel,
  CondaQueueEnvironment,
  CpuLinuxFleet,
  CudaLinuxFleet,
  Farm,
  JobAttachmentsBucket,
  Queue,
  QueueEnvironmentFile,
  ServiceManagedFleet,
} from '../lib/deadline';

const ENV = { account: '123456789012', region: 'us-west-2' };

/** A stack with a farm and a bucket in it, the starting point of most tests. */
function scaffold() {
  const stack = new cdk.Stack(new cdk.App(), 'TestStack', { env: ENV });
  const farm = new Farm(stack, 'Farm', { displayName: 'Test Farm' });
  const bucket = new JobAttachmentsBucket(stack, 'Bucket');
  return { stack, farm, bucket, template: () => Template.fromStack(stack) };
}

describe('Farm', () => {
  test('creates a farm and no roles of its own', () => {
    const { template } = scaffold();
    template().resourceCountIs('AWS::Deadline::Farm', 1);
    template().hasResourceProperties('AWS::Deadline::Farm', { DisplayName: 'Test Farm' });
    // Roles belong to the queues and fleets that use them, not to the farm.
    expect(Object.keys(farmRoles(template()))).toHaveLength(0);
  });

  test('deadlinePrincipal guards against the confused deputy problem', () => {
    const { stack, farm } = scaffold();
    const grantee = new cdk.aws_iam.Role(stack, 'Grantee', {
      assumedBy: farm.deadlinePrincipal('deadline', 'credentials.deadline'),
    });

    const statements = trustStatements(Template.fromStack(stack), grantee);
    expect(statements).toHaveLength(2);
    for (const statement of statements) {
      expect(statement.Condition.StringEquals['aws:SourceAccount']).toBe(ENV.account);
      expect(statement.Condition.ArnEquals['aws:SourceArn']).toBeDefined();
    }
  });
});

describe('JobAttachmentsBucket', () => {
  test('blocks public access, encrypts, and requires TLS', () => {
    const { template } = scaffold();
    template().hasResourceProperties('AWS::S3::Bucket', {
      PublicAccessBlockConfiguration: {
        BlockPublicAcls: true,
        BlockPublicPolicy: true,
        IgnorePublicAcls: true,
        RestrictPublicBuckets: true,
      },
      BucketEncryption: Match.objectLike({
        ServerSideEncryptionConfiguration: Match.anyValue(),
      }),
    });
    template().hasResourceProperties('AWS::S3::BucketPolicy', {
      PolicyDocument: Match.objectLike({
        Statement: Match.arrayWith([
          Match.objectLike({
            Effect: 'Deny',
            Condition: { Bool: { 'aws:SecureTransport': 'false' } },
          }),
        ]),
      }),
    });
  });

  test('is deleted with the stack by default, and emptied so that succeeds', () => {
    // S3 cannot delete a bucket that still holds objects, and a farm that has run
    // jobs always does, so opting into deletion has to opt into emptying too.
    const { template } = scaffold();
    for (const bucket of Object.values(template().findResources('AWS::S3::Bucket'))) {
      expect(bucket.DeletionPolicy).toBe('Delete');
    }
    template().resourceCountIs('Custom::S3AutoDeleteObjects', 1);
  });

  test('RETAIN keeps it, and then nothing empties it', () => {
    const stack = new cdk.Stack(new cdk.App(), 'TestStack', { env: ENV });
    new JobAttachmentsBucket(stack, 'Bucket', {
      removalPolicy: cdk.RemovalPolicy.RETAIN,
    });
    const template = Template.fromStack(stack);

    for (const bucket of Object.values(template.findResources('AWS::S3::Bucket'))) {
      expect(bucket.DeletionPolicy).toBe('Retain');
    }
    template.resourceCountIs('Custom::S3AutoDeleteObjects', 0);
  });
});

describe('Queue', () => {
  test('creates a queue with job attachments under the prefix it was given', () => {
    const { farm, bucket, template } = scaffold();
    new Queue(farm, 'RenderQueue', {
      farm,
      displayName: 'Render Queue',
      jobAttachmentsBucket: bucket,
      jobAttachmentsPrefix: 'Renders',
    });

    template().hasResourceProperties('AWS::Deadline::Queue', {
      DisplayName: 'Render Queue',
      JobAttachmentSettings: { RootPrefix: 'Renders' },
    });
  });

  test('omitting the bucket leaves job attachments unconfigured', () => {
    const { farm, template } = scaffold();
    const queue = new Queue(farm, 'NoAttachmentsQueue', {
      farm,
      displayName: 'No Attachments Queue',
    });

    const resources = template().findResources('AWS::Deadline::Queue');
    expect(Object.values(resources)[0].Properties.JobAttachmentSettings).toBeUndefined();
    // ...and the role gets no S3 permissions it would never use.
    expect(inlineStatementSids(template(), queue.role)).not.toContain('JobAttachmentsReadWrite');
  });

  test('the role reaches only its own job attachments prefix', () => {
    const { farm, bucket, template } = scaffold();
    const queue = new Queue(farm, 'RenderQueue', {
      farm,
      displayName: 'Render Queue',
      jobAttachmentsBucket: bucket,
      jobAttachmentsPrefix: 'Renders',
    });

    const statement = inlineStatements(template(), queue.role).find(
      (s) => s.Sid === 'JobAttachmentsReadWrite',
    );
    expect(statement).toBeDefined();
    const objectResources = renderSynthesized(statement!.Resource).filter((r) =>
      r.includes('/'),
    );
    expect(objectResources).toEqual(['BUCKET/Renders/*']);
  });

  test('every queue can read its session logs and the Deadline provided software', () => {
    const { farm, template } = scaffold();
    const queue = new Queue(farm, 'RenderQueue', { farm, displayName: 'Render Queue' });

    const sids = inlineStatementSids(template(), queue.role);
    expect(sids).toContain('JobLogsReadOnly');
    expect(sids).toContain('DeadlineServiceManagedFleetSoftwareAccess');
  });

  test('addToRolePolicy grants a queue something the construct does not know about', () => {
    const { farm, template } = scaffold();
    const queue = new Queue(farm, 'RenderQueue', { farm, displayName: 'Render Queue' });
    queue.addToRolePolicy(
      new cdk.aws_iam.PolicyStatement({
        sid: 'ReadAssetDatabase',
        actions: ['dynamodb:GetItem'],
        resources: ['arn:aws:dynamodb:us-west-2:123456789012:table/Assets'],
      }),
    );

    expect(inlineStatementSids(template(), queue.role)).toContain('ReadAssetDatabase');
  });

  test('environments are numbered in the order they are added', () => {
    const { farm, template } = scaffold();
    const queue = new Queue(farm, 'RenderQueue', {
      farm,
      displayName: 'Render Queue',
      // Off, so the numbering under test is not offset by the default one.
      addDefaultCondaQueueEnvironment: false,
    });
    queue.addEnvironment({ templateYaml: 'first: true' });
    queue.addEnvironment({ templateYaml: 'second: true' });

    const environments = Object.values(template().findResources('AWS::Deadline::QueueEnvironment'));
    expect(environments).toHaveLength(2);
    expect(
      environments.map((e) => [e.Properties.Priority, e.Properties.Template]).sort(),
    ).toEqual([
      [1, 'first: true'],
      [2, 'second: true'],
    ]);
  });

  test('comes with a Conda queue environment by default', () => {
    const { farm, template } = scaffold();
    new Queue(farm, 'RenderQueue', { farm, displayName: 'Render Queue' });

    template().resourceCountIs('AWS::Deadline::QueueEnvironment', 1);
    const environment = Object.values(
      template().findResources('AWS::Deadline::QueueEnvironment'),
    )[0].Properties;
    expect(environment.Priority).toBe(1);
    expect(condaChannelsDefault(renderSynthesizedString(environment.Template))).toBe(
      'deadline-cloud',
    );
  });

  test('opting out of the default environment leaves the queue with none', () => {
    const { farm, template } = scaffold();
    new Queue(farm, 'ScriptOnlyQueue', {
      farm,
      displayName: 'Script Only Queue',
      addDefaultCondaQueueEnvironment: false,
    });

    template().resourceCountIs('AWS::Deadline::QueueEnvironment', 0);
  });

  test('passing a private channel puts it first and grants the queue read access', () => {
    const { farm, bucket, template } = scaffold();
    const channel = new CondaChannel({ bucket });
    const queue = new Queue(farm, 'RenderQueue', {
      farm,
      displayName: 'Render Queue',
      condaChannels: [channel, 'deadline-cloud'],
    });

    const environment = Object.values(
      template().findResources('AWS::Deadline::QueueEnvironment'),
    )[0].Properties;
    expect(condaChannelsDefault(renderSynthesizedString(environment.Template))).toBe(
      's3://BUCKET/Conda/Default deadline-cloud',
    );
    // Without the grant the queue's jobs would fail at Conda install time, so
    // the construct does it rather than leaving it to the caller.
    expect(inlineStatementSids(template(), queue.role)).toContain('CondaChannelReadOnly');
  });

  test('channels without an environment to apply them to is rejected', () => {
    const { farm } = scaffold();
    expect(
      () =>
        new Queue(farm, 'RenderQueue', {
          farm,
          displayName: 'Render Queue',
          addDefaultCondaQueueEnvironment: false,
          condaChannels: ['conda-forge'],
        }),
    ).toThrow(/would have no effect/);
  });

  test('associateFleet lets the queue run jobs on the fleet', () => {
    const { farm, template } = scaffold();
    const queue = new Queue(farm, 'RenderQueue', { farm, displayName: 'Render Queue' });
    queue.associateFleet(new CpuLinuxFleet(farm, 'CpuLinuxFleet', { farm }));

    template().resourceCountIs('AWS::Deadline::QueueFleetAssociation', 1);
  });
});

describe('CondaChannel', () => {
  test('its URL points at a directory in the bucket', () => {
    const { bucket } = scaffold();
    const channel = new CondaChannel({ bucket, name: 'Studio' });
    expect(channel.url).toBe(`s3://${bucket.bucketName}/Conda/Studio`);
  });

  test('grantRead lets a queue install packages but not change them', () => {
    const { farm, bucket, template } = scaffold();
    const queue = new Queue(farm, 'RenderQueue', { farm, displayName: 'Render Queue' });
    new CondaChannel({ bucket }).grantRead(queue);

    const statement = inlineStatements(template(), queue.role).find(
      (s) => s.Sid === 'CondaChannelReadOnly',
    );
    expect(statement).toBeDefined();
    expect(statement!.Action).toContain('s3:GetObject');
    expect(statement!.Action).not.toContain('s3:PutObject');
    expect(statement!.Action).not.toContain('s3:DeleteObject');
  });

  test('two channels on one queue get distinct policy Sids', () => {
    // IAM requires Sids to be unique within a policy document, so a queue
    // granted access to two channels would fail to deploy if both grants used
    // the same Sid. Synth does not catch that, so this test does.
    const { farm, bucket, template } = scaffold();
    const queue = new Queue(farm, 'RenderQueue', {
      farm,
      displayName: 'Render Queue',
      condaChannels: [
        new CondaChannel({ bucket }),
        new CondaChannel({ bucket, prefix: 'Vendor-Pkgs' }),
        // Shares the default prefix and differs only by name, so the Sid has to
        // distinguish channels by their full location rather than by prefix.
        new CondaChannel({ bucket, name: 'Studio' }),
      ],
    });

    const sids = inlineStatementSids(template(), queue.role);
    expect(new Set(sids).size).toBe(sids.length);
    // The conventional location keeps the unqualified Sid, so the common case
    // stays readable.
    expect(sids).toContain('CondaChannelReadOnly');
    expect(sids).toContain('CondaChannelReadOnlyVendorPkgsDefault');
    expect(sids).toContain('CondaChannelReadOnlyCondaStudio');
  });

  test('a grant reaches only its own channel, not a sibling sharing the prefix', () => {
    const { farm, bucket, template } = scaffold();
    const queue = new Queue(farm, 'RenderQueue', {
      farm,
      displayName: 'Render Queue',
      condaChannels: [new CondaChannel({ bucket, name: 'Default' })],
    });

    const statement = inlineStatements(template(), queue.role).find(
      (s) => s.Sid === 'CondaChannelReadOnly',
    );
    expect(statement).toBeDefined();
    const objectResources = renderSynthesized(statement!.Resource).filter((r) =>
      r.includes('/'),
    );
    expect(objectResources).toEqual(['BUCKET/Conda/Default/*']);
  });

  test('grantReadWrite lets a package build queue publish to the channel', () => {
    const { farm, bucket, template } = scaffold();
    const queue = new Queue(farm, 'BuildQueue', { farm, displayName: 'Build Queue' });
    new CondaChannel({ bucket }).grantReadWrite(queue);

    const statement = inlineStatements(template(), queue.role).find(
      (s) => s.Sid === 'CondaChannelReadWrite',
    );
    expect(statement).toBeDefined();
    expect(statement!.Action).toContain('s3:PutObject');
    expect(statement!.Action).toContain('s3:DeleteObject');
  });
});

describe('CondaQueueEnvironment', () => {
  test('is a valid OpenJD environment template within the service length limit', () => {
    const { bucket } = scaffold();
    const rendered = new CondaQueueEnvironment({
      channels: [new CondaChannel({ bucket }), 'deadline-cloud'],
    }).templateYaml;

    expect(rendered.length).toBeLessThanOrEqual(15000);
    const doc = yaml.parse(rendered);
    expect(doc.specificationVersion).toBe('environment-2023-09');
    expect(doc.environment.name).toBe('Conda');
    expect(doc.environment.script.actions.onEnter).toBeDefined();
  });

  test('defaults CondaChannels to the channels it was given, in order', () => {
    const { bucket } = scaffold();
    const rendered = new CondaQueueEnvironment({
      channels: [new CondaChannel({ bucket }), 'deadline-cloud', 'conda-forge'],
    }).templateYaml;

    expect(condaChannelsDefault(rendered)).toBe(
      `s3://${bucket.bucketName}/Conda/Default deadline-cloud conda-forge`,
    );
  });

  test('a channel name containing $ is substituted verbatim', () => {
    // `String.replace` with a string replacement expands `$&` into the matched
    // text, which would corrupt the rendered template. S3 keys allow `$`.
    const { bucket } = scaffold();
    const rendered = new CondaQueueEnvironment({
      channels: [new CondaChannel({ bucket, name: 'foo$&bar' }), 'deadline-cloud'],
    }).templateYaml;

    expect(condaChannelsDefault(rendered)).toBe(
      `s3://${bucket.bucketName}/Conda/foo$&bar deadline-cloud`,
    );
  });

  test('a channel list is required, since jobs could install nothing without one', () => {
    expect(() => new CondaQueueEnvironment({ channels: [] })).toThrow(/at least one channel/);
  });

  test('a template missing the channels placeholder is rejected', () => {
    expect(
      () =>
        new CondaQueueEnvironment({
          channels: ['deadline-cloud'],
          templatePath: `${__dirname}/../jest.config.js`,
        }),
    ).toThrow(/does not contain/);
  });
});

describe('QueueEnvironmentFile', () => {
  test('reads an environment template from disk', () => {
    const environment = new QueueEnvironmentFile(
      `${__dirname}/../conda_queue_env_inline_improved_caching.yaml`,
    );
    expect(yaml.parse(environment.templateYaml).specificationVersion).toBe(
      'environment-2023-09',
    );
  });
});

describe('ServiceManagedFleet', () => {
  test('describes hardware rather than naming instance types', () => {
    const { farm, template } = scaffold();
    new ServiceManagedFleet(farm, 'ArmLinuxFleet', {
      farm,
      displayName: 'ARM Linux Fleet',
      osFamily: 'LINUX',
      cpuArchitecture: 'arm64',
      maxWorkerCount: 20,
      vCpuCount: { min: 4, max: 16 },
      memoryMiB: { min: 8192 },
    });

    template().hasResourceProperties('AWS::Deadline::Fleet', {
      DisplayName: 'ARM Linux Fleet',
      MinWorkerCount: 0,
      MaxWorkerCount: 20,
      Configuration: {
        ServiceManagedEc2: {
          InstanceCapabilities: Match.objectLike({
            OsFamily: 'LINUX',
            CpuArchitectureType: 'arm64',
            VCpuCount: { Min: 4, Max: 16 },
            MemoryMiB: { Min: 8192 },
            RootEbsVolume: { SizeGiB: 300, Iops: 3000, ThroughputMiB: 125 },
          }),
          InstanceMarketOptions: { Type: 'spot' },
        },
      },
    });
  });

  test('each fleet gets its own worker role', () => {
    // Fleets must not share a role: a permission added for one fleet's workers
    // would otherwise reach every other fleet's too.
    const { farm, template } = scaffold();
    const first = new CpuLinuxFleet(farm, 'FirstFleet', { farm });
    const second = new CpuLinuxFleet(farm, 'SecondFleet', { farm });

    expect(first.role).not.toBe(second.role);
    template().resourceCountIs('AWS::Deadline::Fleet', 2);
    expect(Object.keys(farmRoles(template()))).toHaveLength(2);
  });

  test('the worker role carries the fleet worker managed policy', () => {
    const { farm, template } = scaffold();
    new CpuLinuxFleet(farm, 'CpuLinuxFleet', { farm });

    template().hasResourceProperties('AWS::IAM::Role', {
      ManagedPolicyArns: Match.arrayWith([
        Match.objectLike({
          'Fn::Join': Match.arrayWith([
            Match.arrayWith([':iam::aws:policy/AWSDeadlineCloud-FleetWorker']),
          ]),
        }),
      ]),
    });
  });

  test('the worker role can only write logs belonging to its farm', () => {
    const { farm, template } = scaffold();
    const fleet = new CpuLinuxFleet(farm, 'CpuLinuxFleet', { farm });
    const resources = inlineStatements(template(), fleet.role).flatMap((statement) =>
      renderSynthesized(statement.Resource),
    );

    expect(resources.length).toBeGreaterThan(0);
    for (const resource of resources) {
      expect(resource).toContain(':log-group:/aws/deadline/');
      expect(resource).not.toBe('*');
    }
  });

  test('addToRolePolicy grants only the fleet it is called on', () => {
    const { farm, template } = scaffold();
    const granted = new CpuLinuxFleet(farm, 'GrantedFleet', { farm });
    const other = new CpuLinuxFleet(farm, 'OtherFleet', { farm });
    granted.addToRolePolicy(
      new cdk.aws_iam.PolicyStatement({
        sid: 'ReadSharedAssets',
        actions: ['s3:GetObject'],
        resources: ['arn:aws:s3:::shared-assets/*'],
      }),
    );

    expect(inlineStatementSids(template(), granted.role)).toContain('ReadSharedAssets');
    expect(inlineStatementSids(template(), other.role)).not.toContain('ReadSharedAssets');
  });

  test('an existing role can be shared deliberately', () => {
    const { stack, farm, template } = scaffold();
    const shared = new cdk.aws_iam.Role(stack, 'SharedRole', {
      assumedBy: farm.deadlinePrincipal('credentials.deadline'),
    });
    const first = new CpuLinuxFleet(farm, 'FirstFleet', { farm, role: shared });
    const second = new CpuLinuxFleet(farm, 'SecondFleet', { farm, role: shared });

    expect(first.role).toBe(shared);
    expect(second.role).toBe(shared);
    // Two fleets, one role between them.
    template().resourceCountIs('AWS::Deadline::Fleet', 2);
    expect(Object.keys(farmRoles(template()))).toHaveLength(1);
  });

  test('addToRolePolicy on a fleet that does not own its role is refused', () => {
    // Silently editing a role the fleet was handed would affect whatever else
    // uses it.
    const { stack, farm } = scaffold();
    const shared = new cdk.aws_iam.Role(stack, 'SharedRole', {
      assumedBy: farm.deadlinePrincipal('credentials.deadline'),
    });
    const fleet = new CpuLinuxFleet(farm, 'CpuLinuxFleet', { farm, role: shared });

    expect(() =>
      fleet.addToRolePolicy(
        new cdk.aws_iam.PolicyStatement({ actions: ['s3:GetObject'], resources: ['*'] }),
      ),
    ).toThrow(/given an existing role/);
  });

  test('a GPU requirement asks for one accelerator by default', () => {
    const { farm, template } = scaffold();
    new ServiceManagedFleet(farm, 'GpuFleet', {
      farm,
      displayName: 'GPU Fleet',
      osFamily: 'LINUX',
      maxWorkerCount: 1,
      vCpuCount: { min: 4 },
      memoryMiB: { min: 16384 },
      accelerators: { names: ['l40s'] },
    });

    template().hasResourceProperties('AWS::Deadline::Fleet', {
      Configuration: {
        ServiceManagedEc2: {
          InstanceCapabilities: Match.objectLike({
            AcceleratorCapabilities: {
              Count: { Min: 1, Max: 1 },
              Selections: [{ Name: 'l40s', Runtime: 'latest' }],
            },
          }),
        },
      },
    });
  });

  test('a fleet with no GPU requirement has no accelerator capabilities', () => {
    const { farm, template } = scaffold();
    new CpuLinuxFleet(farm, 'CpuLinuxFleet', { farm });

    const fleet = Object.values(template().findResources('AWS::Deadline::Fleet'))[0];
    expect(
      fleet.Properties.Configuration.ServiceManagedEc2.InstanceCapabilities
        .AcceleratorCapabilities,
    ).toBeUndefined();
  });

  test('an empty accelerator list is rejected rather than silently ignored', () => {
    const { farm } = scaffold();
    expect(
      () =>
        new ServiceManagedFleet(farm, 'GpuFleet', {
          farm,
          displayName: 'GPU Fleet',
          osFamily: 'LINUX',
          maxWorkerCount: 1,
          vCpuCount: { min: 4 },
          memoryMiB: { min: 16384 },
          accelerators: { names: [] },
        }),
    ).toThrow(/at least one accelerator/);
  });

  test('a fleet can wait for cheaper capacity', () => {
    const { farm, template } = scaffold();
    new ServiceManagedFleet(farm, 'BatchFleet', {
      farm,
      displayName: 'Batch Fleet',
      osFamily: 'LINUX',
      instanceMarketType: 'wait-and-save',
      maxWorkerCount: 10,
      vCpuCount: { min: 2, max: 8 },
      memoryMiB: { min: 16384 },
    });

    template().hasResourceProperties('AWS::Deadline::Fleet', {
      Configuration: {
        ServiceManagedEc2: Match.objectLike({
          InstanceMarketOptions: { Type: 'wait-and-save' },
        }),
      },
    });
  });

  test('a GPU fleet cannot wait for cheaper capacity', () => {
    // The service rejects accelerators on a wait-and-save fleet, and synth would
    // otherwise render a template that only fails partway through deployment.
    const { farm } = scaffold();
    expect(
      () =>
        new ServiceManagedFleet(farm, 'GpuFleet', {
          farm,
          displayName: 'GPU Fleet',
          osFamily: 'LINUX',
          instanceMarketType: 'wait-and-save',
          maxWorkerCount: 1,
          vCpuCount: { min: 4 },
          memoryMiB: { min: 16384 },
          accelerators: { names: ['l4'] },
        }),
    ).toThrow(/wait-and-save/);
  });
});

describe('fleet presets', () => {
  test('CpuLinuxFleet is spot Linux hardware sized for CPU work', () => {
    const { farm, template } = scaffold();
    new CpuLinuxFleet(farm, 'CpuLinuxFleet', { farm });

    template().hasResourceProperties('AWS::Deadline::Fleet', {
      DisplayName: 'CPU Linux Fleet',
      MaxWorkerCount: 10,
      Configuration: {
        ServiceManagedEc2: {
          InstanceCapabilities: Match.objectLike({
            OsFamily: 'LINUX',
            VCpuCount: { Min: 2, Max: 8 },
            MemoryMiB: { Min: 16384 },
          }),
          InstanceMarketOptions: { Type: 'spot' },
        },
      },
    });
  });

  test('CudaLinuxFleet requires an A10G or L4 GPU on an on-demand instance', () => {
    const { farm, template } = scaffold();
    new CudaLinuxFleet(farm, 'CudaLinuxFleet', { farm });

    template().hasResourceProperties('AWS::Deadline::Fleet', {
      DisplayName: 'CUDA Linux Fleet',
      MaxWorkerCount: 1,
      Configuration: {
        ServiceManagedEc2: {
          InstanceCapabilities: Match.objectLike({
            AcceleratorCapabilities: {
              Count: { Min: 1, Max: 1 },
              Selections: [
                { Name: 'a10g', Runtime: 'latest' },
                { Name: 'l4', Runtime: 'latest' },
              ],
            },
          }),
          InstanceMarketOptions: { Type: 'on-demand' },
        },
      },
    });
  });

  test('an override replaces one preset value and keeps the rest', () => {
    const { farm, template } = scaffold();
    new CudaLinuxFleet(farm, 'CudaLinuxFleet', {
      farm,
      maxWorkerCount: 8,
      rootEbsVolume: { sizeGiB: 500, iops: 4000, throughputMiB: 250 },
    });

    template().hasResourceProperties('AWS::Deadline::Fleet', {
      MaxWorkerCount: 8,
      Configuration: {
        ServiceManagedEc2: {
          InstanceCapabilities: Match.objectLike({
            // Overridden.
            RootEbsVolume: { SizeGiB: 500, Iops: 4000, ThroughputMiB: 250 },
            // Still the preset's.
            VCpuCount: { Min: 4, Max: 16 },
            AcceleratorCapabilities: Match.anyValue(),
          }),
          InstanceMarketOptions: { Type: 'on-demand' },
        },
      },
    });
  });
});
