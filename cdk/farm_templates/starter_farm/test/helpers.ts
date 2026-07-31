// Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

// Helpers shared by the test suites for reading a synthesized template.

import * as cdk from 'aws-cdk-lib';
import { Template } from 'aws-cdk-lib/assertions';
import { IConstruct } from 'constructs';
import * as yaml from 'yaml';

/** A statement in a synthesized IAM policy document. */
export interface Statement {
  readonly Sid?: string;
  readonly Action: string[];
  readonly Resource: unknown;
  readonly Condition: Record<string, Record<string, unknown>>;
}

/**
 * The logical ID a construct's resource is synthesized under.
 *
 * Constructs are found by logical ID rather than by the `aws:cdk:path`
 * metadata, which only the CDK CLI adds and a bare `new cdk.App()` does not.
 */
export function logicalIdOf(construct: IConstruct): string {
  const resource = construct.node.defaultChild;
  if (!cdk.CfnElement.isCfnElement(resource)) {
    throw new Error(`${construct.node.path} has no default child resource.`);
  }
  return cdk.Stack.of(construct).getLogicalId(resource);
}

/** Every inline policy statement on the given role. */
export function inlineStatements(template: Template, role: IConstruct): Statement[] {
  const properties = template.findResources('AWS::IAM::Role')[logicalIdOf(role)]?.Properties;
  expect(properties).toBeDefined();
  return (properties.Policies ?? []).flatMap(
    (policy: { PolicyDocument: { Statement: Statement[] } }) => policy.PolicyDocument.Statement,
  );
}

/** The `Sid` of every inline policy statement on the given role. */
export function inlineStatementSids(template: Template, role: IConstruct): (string | undefined)[] {
  return inlineStatements(template, role).map((statement) => statement.Sid);
}

/** Every statement in the given role's trust policy. */
export function trustStatements(template: Template, role: IConstruct): Statement[] {
  const properties = template.findResources('AWS::IAM::Role')[logicalIdOf(role)]?.Properties;
  expect(properties).toBeDefined();
  return properties.AssumeRolePolicyDocument.Statement;
}

/**
 * The farm's own IAM roles, excluding any CDK created for its own bookkeeping.
 *
 * Emptying the job attachments bucket on stack deletion adds a custom resource
 * with a role of its own. Counting that alongside the queue and fleet roles would
 * make every role-count assertion depend on an implementation detail of CDK.
 */
export function farmRoles(template: Template): Record<string, any> {
  return Object.fromEntries(
    Object.entries(template.findResources('AWS::IAM::Role')).filter(
      ([logicalId]) => !logicalId.startsWith('CustomS3AutoDeleteObjects'),
    ),
  );
}

/** The default value of the `CondaChannels` parameter in a rendered OpenJD template. */
export function condaChannelsDefault(rendered: string): string {
  const doc = yaml.parse(rendered);
  return doc.parameterDefinitions.find((p: { name: string }) => p.name === 'CondaChannels')
    .default;
}

/**
 * Flatten a synthesized string, such as a policy resource or a queue
 * environment body, into plain text.
 *
 * Bucket names and ARNs are unresolved tokens at synth time, so every intrinsic
 * other than `Fn::Join` collapses to the placeholder `BUCKET`. An array yields
 * one string per element.
 */
export function renderSynthesized(value: unknown): string[] {
  if (Array.isArray(value)) {
    return value.flatMap(renderSynthesized);
  }
  if (typeof value === 'string') {
    return [value];
  }
  if (value && typeof value === 'object' && 'Fn::Join' in value) {
    const [delimiter, parts] = (value as { 'Fn::Join': [string, unknown[]] })['Fn::Join'];
    return [parts.flatMap(renderSynthesized).join(delimiter)];
  }
  return ['BUCKET'];
}

/** {@link renderSynthesized} for a value known to be a single string. */
export function renderSynthesizedString(value: unknown): string {
  const rendered = renderSynthesized(value);
  expect(rendered).toHaveLength(1);
  return rendered[0];
}
