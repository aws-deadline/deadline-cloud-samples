// Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

// Tests for how this sample wires the reusable constructs together: which
// resources the farm has, and how its two queues differ. The constructs
// themselves are tested in test/deadline-constructs.test.ts.

import * as cdk from 'aws-cdk-lib';
import { Match, Template } from 'aws-cdk-lib/assertions';
import { IConstruct } from 'constructs';

import {
  condaChannelsDefault,
  farmRoles,
  inlineStatements,
  logicalIdOf,
  renderSynthesizedString,
} from './helpers';
import { ServiceManagedFleet } from '../lib/deadline';
import {
  ALL_FLEET_PRESETS,
  StarterFarmStack,
  StarterFarmStackProps,
} from '../lib/starter-farm-stack';

const ENV = { account: '123456789012', region: 'us-west-2' };

function build(props: StarterFarmStackProps = {}): StarterFarmStack {
  return new StarterFarmStack(new cdk.App(), 'TestFarm', { env: ENV, ...props });
}

function synth(props: StarterFarmStackProps = {}): Template {
  return Template.fromStack(build(props));
}

describe('default farm', () => {
  const template = synth();

  test('creates one farm', () => {
    template.resourceCountIs('AWS::Deadline::Farm', 1);
  });

  test('creates the production and package build queues', () => {
    template.resourceCountIs('AWS::Deadline::Queue', 2);
    template.hasResourceProperties('AWS::Deadline::Queue', {
      DisplayName: 'Production Job Queue',
      JobAttachmentSettings: { RootPrefix: 'DeadlineCloud' },
    });
    template.hasResourceProperties('AWS::Deadline::Queue', {
      DisplayName: 'Package Build Queue',
      JobAttachmentSettings: { RootPrefix: 'DeadlineCloudPkgBld' },
    });
  });

  test('stores both queues and the Conda channel on one bucket', () => {
    template.resourceCountIs('AWS::S3::Bucket', 1);
  });

  test('deploys only the CPU Linux fleet, associated with both queues', () => {
    template.resourceCountIs('AWS::Deadline::Fleet', 1);
    template.hasResourceProperties('AWS::Deadline::Fleet', {
      DisplayName: 'CPU Linux Fleet',
    });
    template.resourceCountIs('AWS::Deadline::QueueFleetAssociation', 2);
  });

  test('creates a role per queue and a role for the fleet', () => {
    expect(Object.keys(farmRoles(template))).toHaveLength(3);
  });

  test('outputs the IDs needed to submit a job', () => {
    const outputs = Object.keys(template.findOutputs('*'));
    expect(outputs).toEqual(
      expect.arrayContaining([
        'FarmId',
        'ProductionQueueId',
        'PackageBuildQueueId',
        'JobAttachmentsBucketName',
        'CondaChannelUrl',
        'CpuLinuxFleetId',
      ]),
    );
  });
});

describe('the two queues', () => {
  const template = synth();

  test('only the package build queue can write the Conda channel', () => {
    // A production job must not be able to modify the packages other jobs
    // depend on, so the split between these two grants is the security boundary
    // this farm's shape exists to create.
    const stack = build();
    const stackTemplate = Template.fromStack(stack);
    const condaSid = (role: IConstruct) =>
      inlineStatements(stackTemplate, role)
        .map((statement) => statement.Sid)
        .filter((sid) => sid?.startsWith('CondaChannel'));

    expect(condaSid(stack.productionQueue.role)).toEqual(['CondaChannelReadOnly']);
    expect(condaSid(stack.packageBuildQueue.role)).toEqual(['CondaChannelReadWrite']);
  });

  test('each owns a separate job attachments prefix', () => {
    const prefixes = Object.values(template.findResources('AWS::Deadline::Queue')).map(
      (queue) => queue.Properties.JobAttachmentSettings.RootPrefix,
    );
    expect(new Set(prefixes).size).toBe(prefixes.length);
  });

  test('only the production queue gets a Conda queue environment', () => {
    // The package build job bundles bring their own Conda environment and
    // define a CondaChannels parameter of their own, so a queue environment on
    // that queue would define the same parameter name twice over. This matches
    // the CloudFormation and Terraform starter farms.
    const stack = build();
    const stackTemplate = Template.fromStack(stack);
    const environments = Object.values(
      stackTemplate.findResources('AWS::Deadline::QueueEnvironment'),
    );
    expect(environments).toHaveLength(1);

    const environment = environments[0].Properties;
    expect(environment.QueueId).toEqual({
      'Fn::GetAtt': [logicalIdOf(stack.productionQueue), 'QueueId'],
    });
    expect(environment.Priority).toBe(1);
    expect(environment.TemplateType).toBe('YAML');
    expect(condaChannelsDefault(renderSynthesizedString(environment.Template))).toContain(
      's3://BUCKET/Conda/Default',
    );
  });

  test('are assumable only by this farm in this account', () => {
    const statements = Object.values(farmRoles(template)).flatMap(
      (role) => role.Properties.AssumeRolePolicyDocument.Statement,
    );
    expect(statements.length).toBeGreaterThan(0);
    for (const statement of statements) {
      expect(statement.Condition.StringEquals['aws:SourceAccount']).toBe(ENV.account);
      expect(statement.Condition.ArnEquals['aws:SourceArn']).toBeDefined();
    }
  });
});

describe('Conda channels', () => {
  test('the production queue installs from the private channel first', () => {
    const rendered = renderSynthesizedString(condaEnvironmentTemplate(build()));
    expect(condaChannelsDefault(rendered)).toBe('s3://BUCKET/Conda/Default deadline-cloud');
  });

  test('extra channels passed to the stack are appended', () => {
    const rendered = renderSynthesizedString(
      condaEnvironmentTemplate(build({ condaChannels: ['deadline-cloud', 'conda-forge'] })),
    );
    expect(condaChannelsDefault(rendered)).toBe(
      's3://BUCKET/Conda/Default deadline-cloud conda-forge',
    );
  });
});

describe('fleet selection', () => {
  test('every preset can be deployed at once', () => {
    const template = synth({ fleets: ALL_FLEET_PRESETS });
    template.resourceCountIs('AWS::Deadline::Fleet', 3);
    // Each fleet is associated with both queues.
    template.resourceCountIs('AWS::Deadline::QueueFleetAssociation', 6);
    // Two queue roles plus a worker role per fleet, so no fleet's permissions
    // reach another's workers.
    expect(Object.keys(farmRoles(template))).toHaveLength(5);
  });

  test('a preset each covers Linux, Windows, and GPU work', () => {
    const template = synth({ fleets: ALL_FLEET_PRESETS });
    const fleets = Object.values(template.findResources('AWS::Deadline::Fleet')).map(
      (fleet) => fleet.Properties,
    );
    const byName = new Map(fleets.map((fleet) => [fleet.DisplayName, fleet]));

    expect(byName.get('CPU Linux Fleet').Configuration.ServiceManagedEc2.InstanceCapabilities
      .OsFamily).toBe('LINUX');
    expect(byName.get('CPU Windows Fleet').Configuration.ServiceManagedEc2.InstanceCapabilities
      .OsFamily).toBe('WINDOWS');
    expect(byName.get('CUDA Linux Fleet').Configuration.ServiceManagedEc2.InstanceCapabilities
      .AcceleratorCapabilities).toBeDefined();
  });

  test('addFleet extends the farm with hardware the presets do not cover', () => {
    const stack = build();
    stack.addFleet(
      new ServiceManagedFleet(stack, 'ArmLinuxFleet', {
        farm: stack.farm,
        displayName: 'ARM Linux Fleet',
        osFamily: 'LINUX',
        cpuArchitecture: 'arm64',
        maxWorkerCount: 20,
        vCpuCount: { min: 4, max: 16 },
        memoryMiB: { min: 8192 },
      }),
    );
    const template = Template.fromStack(stack);

    expect(stack.fleets).toHaveLength(2);
    template.resourceCountIs('AWS::Deadline::Fleet', 2);
    // The added fleet is associated with both queues and gets an output, the
    // same as a preset one.
    template.resourceCountIs('AWS::Deadline::QueueFleetAssociation', 4);
    template.hasOutput('ArmLinuxFleetId', Match.anyValue());
  });

  test('a fleet ID that cannot name an output is rejected with a clear message', () => {
    // Two fleets whose IDs differ only in punctuation would collide on one
    // output name, which CDK reports without naming the constructs at fault.
    const stack = build();
    expect(() =>
      stack.addFleet(
        new ServiceManagedFleet(stack, 'arm-linux', {
          farm: stack.farm,
          displayName: 'ARM Linux Fleet',
          osFamily: 'LINUX',
          maxWorkerCount: 1,
          vCpuCount: { min: 4 },
          memoryMiB: { min: 8192 },
        }),
      ),
    ).toThrow(/only letters and digits/);
  });
});

describe('job attachments bucket', () => {
  test('is deleted with the stack, and emptied so the deletion succeeds', () => {
    const template = synth();
    for (const bucket of Object.values(template.findResources('AWS::S3::Bucket'))) {
      expect(bucket.DeletionPolicy).toBe('Delete');
    }
    template.resourceCountIs('Custom::S3AutoDeleteObjects', 1);
  });
});

/** The synthesized body of the production queue's Conda queue environment. */
function condaEnvironmentTemplate(stack: StarterFarmStack): unknown {
  const wanted = JSON.stringify({
    'Fn::GetAtt': [logicalIdOf(stack.productionQueue), 'QueueId'],
  });
  const environments = Object.values(
    Template.fromStack(stack).findResources('AWS::Deadline::QueueEnvironment'),
  ).filter((environment) => JSON.stringify(environment.Properties.QueueId) === wanted);
  expect(environments).toHaveLength(1);
  return environments[0].Properties.Template;
}
