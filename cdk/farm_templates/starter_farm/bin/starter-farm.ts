#!/usr/bin/env node
// Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

import * as cdk from 'aws-cdk-lib';

import { CudaFarmStack } from '../lib/cuda-farm-stack';
import { MultiPlatformFarmStack } from '../lib/multi-platform-farm-stack';
import { SimpleFarmStack } from '../lib/simple-farm-stack';
import { StarterFarmStack } from '../lib/starter-farm-stack';

/**
 * Every example farm is defined as its own stack, and deploying one names it:
 *
 *   cdk deploy SimpleFarm
 *
 * They are alternatives rather than layers, so deploy one. `cdk list` shows the
 * names, and `cdk deploy --all` would create four separate farms.
 *
 * Each stack is a short, readable composition of the constructs in
 * `lib/deadline/`. Read the one closest to what you need, then change it here or
 * copy it into an app of your own.
 */
const app = new cdk.App();

// Resolve the account and region from the ambient AWS credentials, so each
// farm's IAM policies and log group ARNs are built for the environment you
// deploy into rather than being region-agnostic.
const env = {
  account: process.env.CDK_DEFAULT_ACCOUNT,
  region: process.env.CDK_DEFAULT_REGION,
};

// Start here: one queue and one Linux fleet. Jobs can install applications from
// the deadline-cloud Conda channel with no further setup.
new SimpleFarmStack(app, 'SimpleFarm', {
  env,
  description:
    'A minimal AWS Deadline Cloud farm: one queue and one Linux fleet. ' +
    'See the README.md alongside this CDK app to learn more.',
});

// Adds a private Conda channel and a queue that builds packages for it, for
// software the deadline-cloud channel does not provide.
new StarterFarmStack(app, 'StarterFarm', {
  env,
  description:
    'An AWS Deadline Cloud starter farm: a production queue, a Conda package build queue, ' +
    'and service-managed fleets. See the README.md alongside this CDK app to learn more.',
  // Add 'cpu-windows' or 'cuda-linux' for a farm that also runs Windows or GPU
  // jobs. The hardware of each preset is defined in lib/deadline/fleet.ts.
  fleets: ['cpu-linux'],
  // Add 'conda-forge' to also install packages from https://conda-forge.org/.
  condaChannels: ['deadline-cloud'],
});

// The simple farm specialized for GPU work.
new CudaFarmStack(app, 'CudaFarm', {
  env,
  description:
    'An AWS Deadline Cloud farm for CUDA jobs: a GPU fleet and a queue configured for ' +
    'the conda-forge channel. See the README.md alongside this CDK app to learn more.',
});

// One queue reaching Linux, Windows, and GPU fleets, selected per job step.
new MultiPlatformFarmStack(app, 'MultiPlatformFarm', {
  env,
  description:
    'An AWS Deadline Cloud farm whose queue reaches Linux, Windows, and GPU fleets. ' +
    'See the README.md alongside this CDK app to learn more.',
});

app.synth();
