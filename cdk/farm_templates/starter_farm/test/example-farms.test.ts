// Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

// Tests for the example farm stacks other than the starter farm, which has a
// suite of its own. Each asserts the handful of things that make its farm the
// shape it claims to be, rather than restating what the construct tests in
// test/deadline-constructs.test.ts already cover.

import * as cdk from 'aws-cdk-lib';
import { Template } from 'aws-cdk-lib/assertions';

import { CudaFarmStack } from '../lib/cuda-farm-stack';
import { MultiPlatformFarmStack } from '../lib/multi-platform-farm-stack';
import { SimpleFarmStack } from '../lib/simple-farm-stack';
import { condaChannelsDefault, farmRoles, renderSynthesizedString } from './helpers';

const ENV = { account: '123456789012', region: 'us-west-2' };

/** The default value of `CondaChannels` in a stack's one queue environment. */
function condaChannels(template: Template): string {
  const environments = Object.values(
    template.findResources('AWS::Deadline::QueueEnvironment'),
  );
  expect(environments).toHaveLength(1);
  return condaChannelsDefault(renderSynthesizedString(environments[0].Properties.Template));
}

describe('SimpleFarmStack', () => {
  const template = Template.fromStack(
    new SimpleFarmStack(new cdk.App(), 'SimpleFarm', { env: ENV }),
  );

  test('is one farm, one queue, and one fleet', () => {
    template.resourceCountIs('AWS::Deadline::Farm', 1);
    template.resourceCountIs('AWS::Deadline::Queue', 1);
    template.resourceCountIs('AWS::Deadline::Fleet', 1);
    template.resourceCountIs('AWS::Deadline::QueueFleetAssociation', 1);
    // One queue role and one fleet worker role.
    expect(Object.keys(farmRoles(template))).toHaveLength(2);
  });

  test('runs jobs on Linux', () => {
    template.hasResourceProperties('AWS::Deadline::Fleet', {
      Configuration: {
        ServiceManagedEc2: {
          InstanceCapabilities: { OsFamily: 'LINUX' },
          InstanceMarketOptions: { Type: 'spot' },
        },
      },
    });
  });

  test('has no private Conda channel to initialize before jobs can run', () => {
    // The point of this farm is that it works immediately. A private channel
    // would have to be populated first, so the queue installs only from the
    // deadline-cloud channel and nothing grants access to an S3 channel.
    expect(condaChannels(template)).toBe('deadline-cloud');

    const statements = Object.values(template.findResources('AWS::IAM::Role')).flatMap(
      (role) =>
        (role.Properties?.Policies ?? []).flatMap(
          (policy: { PolicyDocument: { Statement: { Sid?: string }[] } }) =>
            policy.PolicyDocument.Statement,
        ),
    );
    expect(statements.map((s) => s.Sid).filter(Boolean)).not.toContain('CondaChannelReadOnly');
  });

  test('stores job attachments under the default prefix', () => {
    template.hasResourceProperties('AWS::Deadline::Queue', {
      JobAttachmentSettings: { RootPrefix: 'DeadlineCloud' },
    });
  });

  test('outputs what you need to submit a job and nothing about Conda channels', () => {
    expect(Object.keys(template.findOutputs('*')).sort()).toEqual([
      'FarmId',
      'FleetId',
      'JobAttachmentsBucketName',
      'QueueId',
    ]);
  });
});

describe('CudaFarmStack', () => {
  const template = Template.fromStack(
    new CudaFarmStack(new cdk.App(), 'CudaFarm', { env: ENV }),
  );

  test('requires a GPU on its one fleet', () => {
    template.resourceCountIs('AWS::Deadline::Fleet', 1);
    template.hasResourceProperties('AWS::Deadline::Fleet', {
      Configuration: {
        ServiceManagedEc2: {
          InstanceCapabilities: {
            AcceleratorCapabilities: {
              Count: { Min: 1, Max: 1 },
              Selections: [
                { Name: 'a10g', Runtime: 'latest' },
                { Name: 'l4', Runtime: 'latest' },
              ],
            },
            OsFamily: 'LINUX',
            CpuArchitectureType: 'x86_64',
            VCpuCount: { Min: 4, Max: 16 },
            MemoryMiB: { Min: 32768 },
            RootEbsVolume: { SizeGiB: 300, Iops: 3000, ThroughputMiB: 125 },
          },
          // On-demand: a long GPU job loses more to an interruption than spot
          // saves on the instance.
          InstanceMarketOptions: { Type: 'on-demand' },
        },
      },
    });
  });

  test('installs from conda-forge, where the CUDA toolchain lives', () => {
    expect(condaChannels(template)).toBe('deadline-cloud conda-forge');
  });

  test('defaults to a single GPU worker, since they are expensive', () => {
    template.hasResourceProperties('AWS::Deadline::Fleet', { MaxWorkerCount: 1 });
  });

  test('raising the worker count is a prop rather than an edit', () => {
    const scaled = Template.fromStack(
      new CudaFarmStack(new cdk.App(), 'CudaFarm', { env: ENV, maxWorkerCount: 8 }),
    );
    scaled.hasResourceProperties('AWS::Deadline::Fleet', { MaxWorkerCount: 8 });
  });
});

describe('MultiPlatformFarmStack', () => {
  const stack = new MultiPlatformFarmStack(new cdk.App(), 'MultiPlatformFarm', { env: ENV });
  const template = Template.fromStack(stack);

  test('attaches three fleets to one queue', () => {
    template.resourceCountIs('AWS::Deadline::Queue', 1);
    template.resourceCountIs('AWS::Deadline::Fleet', 3);
    template.resourceCountIs('AWS::Deadline::QueueFleetAssociation', 3);
    expect(stack.fleets).toHaveLength(3);
  });

  test('covers Linux, Windows, and GPU hardware', () => {
    const capabilities = Object.values(template.findResources('AWS::Deadline::Fleet')).map(
      (fleet) => fleet.Properties.Configuration.ServiceManagedEc2.InstanceCapabilities,
    );

    expect(capabilities.filter((c) => c.OsFamily === 'LINUX')).toHaveLength(2);
    expect(capabilities.filter((c) => c.OsFamily === 'WINDOWS')).toHaveLength(1);
    expect(capabilities.filter((c) => c.AcceleratorCapabilities)).toHaveLength(1);
  });

  test('gives each fleet its own worker role', () => {
    // Three fleet roles plus the queue's. A shared role would mean a permission
    // the Windows workers need also reaching the GPU workers.
    expect(Object.keys(farmRoles(template))).toHaveLength(4);
    expect(new Set(stack.fleets.map((fleet) => fleet.role.roleArn)).size).toBe(3);
  });

  test('outputs a fleet ID per fleet', () => {
    const outputs = Object.keys(template.findOutputs('*'));
    expect(outputs).toEqual(
      expect.arrayContaining([
        'CpuLinuxFleetId',
        'CpuWindowsFleetId',
        'CudaLinuxFleetId',
        'QueueId',
      ]),
    );
  });
});

describe('every example farm', () => {
  const stacks = () => {
    const app = new cdk.App();
    return [
      new SimpleFarmStack(app, 'SimpleFarm', { env: ENV }),
      new CudaFarmStack(app, 'CudaFarm', { env: ENV }),
      new MultiPlatformFarmStack(app, 'MultiPlatformFarm', { env: ENV }),
    ];
  };

  test('deletes its job attachments bucket with the stack', () => {
    // A sample someone deploys to try out should not leave storage behind. A
    // farm holding real work passes RemovalPolicy.RETAIN to the bucket instead.
    for (const stack of stacks()) {
      const template = Template.fromStack(stack);
      const buckets = Object.values(template.findResources('AWS::S3::Bucket'));
      expect(buckets.length).toBeGreaterThan(0);
      for (const bucket of buckets) {
        expect(bucket.DeletionPolicy).toBe('Delete');
      }
      // CloudFormation cannot delete a bucket that still holds objects, so the
      // deletion has to empty it first.
      template.resourceCountIs('Custom::S3AutoDeleteObjects', 1);
    }
  });

  test('scopes every role to its own farm', () => {
    for (const stack of stacks()) {
      const roles = Object.values(farmRoles(Template.fromStack(stack)));
      expect(roles.length).toBeGreaterThan(0);
      for (const role of roles) {
        for (const statement of role.Properties.AssumeRolePolicyDocument.Statement) {
          expect(statement.Condition.StringEquals['aws:SourceAccount']).toBe(ENV.account);
          expect(statement.Condition.ArnEquals['aws:SourceArn']).toBeDefined();
        }
      }
    }
  });
});
