# AWS Deadline Cloud farms (AWS CDK)

## Overview

This [AWS CDK](https://aws.amazon.com/cdk/) app deploys an [AWS Deadline Cloud](https://aws.amazon.com/deadline-cloud/) farm you can use to run jobs such as rendering images and reconstructing 3D scenes, or transforming your data in custom ways. It is the CDK counterpart of the [CloudFormation farm templates](../../../cloudformation/farm_templates/) and the [Terraform starter farm configuration](../../../terraform/farm_templates/starter_farm/).

The app contains four example farms, each a separate CDK stack built from the same reusable constructs. Deploy whichever one is closest to what you need. Its source is then the starting point for a farm of your own.

| Stack | What you get | Deploy it when |
|---|---|---|
| **`SimpleFarm`** | A single Linux fleet on one queue | **You are getting started.** Jobs can install Blender, Maya, Nuke, or Houdini right away, and there is nothing to set up first |
| `StarterFarm` | Adds a private Conda channel and a queue that builds packages for it | You need software the `deadline-cloud` channel does not provide, such as your own tools and plugins |
| `CudaFarm` | A GPU fleet, with `conda-forge` for the CUDA toolchain | Your jobs need a GPU, for GPU rendering or machine learning |
| `MultiPlatformFarm` | One queue reaching Linux, Windows, and GPU fleets | Different steps of one job need different hardware or operating systems |

**New to Deadline Cloud? Deploy `SimpleFarm`.** It is the shortest path to a working farm, and the [Deployment](#deployment) steps below use it. The private Conda channel that `StarterFarm` adds has to be populated before jobs can install from it, which is worth doing when you need it and worth skipping until then.

Sample jobs to submit are available in the [deadline-cloud-samples on GitHub](https://github.com/aws-deadline/deadline-cloud-samples/tree/mainline/job_bundles#readme). Deadline Cloud provides many [integrated submitter plugins for applications](https://github.com/aws-deadline/#integrations), and you can [build your own jobs](https://docs.aws.amazon.com/deadline-cloud/latest/developerguide/building-jobs.html).

Every farm here uses [service-managed fleets](https://docs.aws.amazon.com/deadline-cloud/latest/userguide/smf-manage.html), so Deadline Cloud launches worker hosts when there is work queued and shuts them down when there is not. Every queue comes with a Conda queue environment, so a job names the applications it needs in the `CondaPackages` parameter and they are installed before its steps run.

When supported applications need licenses to run, they will use Deadline Cloud's usage-based licensing. See [Deadline Cloud pricing](https://aws.amazon.com/deadline-cloud/pricing/) to learn which applications are supported and the associated costs.

## Prerequisites

1. [Node.js](https://nodejs.org/) 18 or later installed.
2. AWS credentials configured (via `aws configure`, environment variables, or IAM role) for the account and region you will deploy into.
3. Your account and region [bootstrapped for CDK](https://docs.aws.amazon.com/cdk/v2/guide/bootstrapping.html), if it is not already:
   ```bash
   npx cdk bootstrap
   ```
4. A Deadline Cloud monitor to view and manage the jobs you will submit to your queues. From the [AWS Deadline Cloud management console](https://console.aws.amazon.com/deadlinecloud/home), select the "Go to Monitor setup" option and follow the steps to enter a name for your monitor URL, enable IAM Identity Center, and then create a user login account to access the monitor. Your monitor URL will look similar to `https://<name>.<region>.deadlinecloud.amazonaws.com/`. You will need this URL to log in with the Deadline Cloud monitor desktop application.

## Resources created

Every stack creates a farm, an S3 bucket for job attachments, at least one queue with a Conda queue environment, at least one fleet, and one IAM role per queue and per fleet. What differs is the count:

| Resource | `SimpleFarm` | `StarterFarm` | `CudaFarm` | `MultiPlatformFarm` |
|---|---|---|---|---|
| `AWS::Deadline::Farm` | 1 | 1 | 1 | 1 |
| `AWS::Deadline::Queue` | 1 | 2 | 1 | 1 |
| `AWS::Deadline::QueueEnvironment` | 1 | 1 | 1 | 1 |
| `AWS::Deadline::Fleet` | 1 | 1 to 3 | 1 | 3 |
| `AWS::Deadline::QueueFleetAssociation` | 1 | 2 to 6 | 1 | 3 |
| `AWS::IAM::Role` | 2 | 3 to 5 | 2 | 4 |
| `AWS::S3::Bucket` | 1 | 1 | 1 | 1 |

Each fleet gets its own IAM role, so a permission granted for one fleet's workers does not reach another's. Only `StarterFarm` puts a private Conda channel on its bucket, and its second queue is the package build queue, which carries no queue environment because the package build job bundles bring their own.

## How the app is organized

Each example farm is a short composition of reusable constructs, so a stack reads as a description of its shape rather than a list of resources and policies.

| File | Contents |
|------|----------|
| [`bin/starter-farm.ts`](./bin/starter-farm.ts) | The entry point: instantiates each stack |
| [`lib/simple-farm-stack.ts`](./lib/simple-farm-stack.ts) | `SimpleFarm`: one queue, one Linux fleet |
| [`lib/starter-farm-stack.ts`](./lib/starter-farm-stack.ts) | `StarterFarm`: adds a private Conda channel and a package build queue |
| [`lib/cuda-farm-stack.ts`](./lib/cuda-farm-stack.ts) | `CudaFarm`: a GPU fleet and the `conda-forge` channel |
| [`lib/multi-platform-farm-stack.ts`](./lib/multi-platform-farm-stack.ts) | `MultiPlatformFarm`: one queue, three fleets |
| [`lib/deadline/`](./lib/deadline/) | The reusable constructs every stack is built from |

The constructs in `lib/deadline/` wrap the `CfnFarm`, `CfnQueue`, and `CfnFleet` L1 resources from `aws-cdk-lib/aws-deadline`, each creating the IAM role and permissions its resource needs:

| Construct | What it is |
|-----------|-----------|
| `Farm` | A farm. Creates no role of its own, and supplies the log group ARN and trust policy that the queue and fleet roles below are built from |
| `Queue` | A queue, the IAM role its jobs run as, and a Conda queue environment, with `addEnvironment()` and `associateFleet()` |
| `ServiceManagedFleet` | A fleet of worker hosts described by hardware requirements rather than instance types, with its own IAM role |
| `CpuLinuxFleet`, `CpuWindowsFleet`, `CudaLinuxFleet` | Presets of `ServiceManagedFleet` for the common hardware shapes |
| `JobAttachmentsBucket` | An S3 bucket with the settings a farm's storage should have |
| `CondaChannel` | A private Conda channel on that bucket, with `grantRead()` and `grantReadWrite()` |
| `CondaQueueEnvironment` | A queue environment that installs the Conda packages a job asks for |

A whole working farm is four constructs. The following is the entire body of `SimpleFarm`:

```ts
const farm = new Farm(this, 'Farm', { displayName: 'My Farm' });
const bucket = new JobAttachmentsBucket(this, 'Bucket');

const queue = new Queue(this, 'Queue', {
  farm,
  displayName: 'Job Queue',
  jobAttachmentsBucket: bucket,
});
queue.associateFleet(new CpuLinuxFleet(this, 'Fleet', { farm }));
```

The queue's Conda environment and both IAM roles come with those constructs, so nothing above has to mention a policy. Specializing the farm is a matter of what you pass:

```ts
// A GPU fleet instead of a CPU one, and a channel with the CUDA toolchain.
const queue = new Queue(this, 'Queue', {
  farm,
  displayName: 'CUDA Job Queue',
  jobAttachmentsBucket: bucket,
  condaChannels: ['deadline-cloud', 'conda-forge'],
});
queue.associateFleet(new CudaLinuxFleet(this, 'Fleet', { farm }));

// Or a private channel, which also grants the queue read access to it.
const channel = new CondaChannel({ bucket });
const queue = new Queue(this, 'Queue', {
  farm,
  displayName: 'Production Job Queue',
  jobAttachmentsBucket: bucket,
  condaChannels: [channel, 'deadline-cloud'],
});
```

Anything a construct does not expose is reachable on the L1 resource it wraps (`farm.cfnFarm`, `queue.cfnQueue`, and `fleet.cfnFleet`), so you never have to stop using them to reach a property they left out.

## Deployment

### 1. Install dependencies

```bash
cd cdk/farm_templates/starter_farm
npm ci
```

### 2. Choose a farm

```bash
npx cdk list
```

```
SimpleFarm
StarterFarm
CudaFarm
MultiPlatformFarm
```

The steps below deploy `SimpleFarm`. Substitute another name to deploy a different farm; each is independent, so deploying two creates two farms.

### 3. Review the changes

```bash
npx cdk diff SimpleFarm
```

### 4. Deploy

```bash
npx cdk deploy SimpleFarm
```

When the deployment finishes, the IDs you need for the next steps are printed as stack outputs:

```
Outputs:
SimpleFarm.FarmId = farm-<...>
SimpleFarm.FleetId = fleet-<...>
SimpleFarm.JobAttachmentsBucketName = <bucket>
SimpleFarm.QueueId = queue-<...>
```

`StarterFarm` prints `ProductionQueueId` and `PackageBuildQueueId` instead of a single `QueueId`, plus a `CondaChannelUrl` for its private channel.

### 5. Add user access

From the [AWS Deadline Cloud management console](https://console.aws.amazon.com/deadlinecloud/home), navigate to the farm that you created, and select the "Access management" tab. Select "Users", then "Add user", and then add the user you created for yourself from the prerequisites. Use the "Owner" access level to give yourself full access.

## Outputs

Every farm outputs these:

| Output | Description |
|--------|-------------|
| `FarmId` | The Deadline Cloud farm ID |
| `JobAttachmentsBucketName` | The S3 bucket holding job attachments |

`SimpleFarm` and `CudaFarm` add `QueueId` and `FleetId`. `MultiPlatformFarm` adds `QueueId` plus a fleet ID per fleet (`CpuLinuxFleetId`, `CpuWindowsFleetId`, `CudaLinuxFleetId`). `StarterFarm` adds:

| Output | Description |
|--------|-------------|
| `ProductionQueueId` | The production queue ID |
| `PackageBuildQueueId` | The package build queue ID |
| `CondaChannelUrl` | The farm's private S3 Conda channel URL |
| `<Name>FleetId` | The fleet ID of each deployed fleet, such as `CpuLinuxFleetId` |

## Next steps: submit a job

Submitting jobs is outside this sample's scope, and the Deadline Cloud documentation covers it in full. In short:

1. **Install the client tools.** Download the Deadline Cloud monitor and submitter from the "Downloads" page of the [AWS Deadline Cloud management console](https://console.aws.amazon.com/deadlinecloud/home), or `pip install "deadline[gui]"`. See [Set up the Deadline Cloud CLI](https://docs.aws.amazon.com/deadline-cloud/latest/userguide/set-up-cli.html).
2. **Point the CLI at the farm you deployed** with `deadline config gui`, using the `FarmId` and queue ID from the stack outputs above.
3. **Submit something.** The [job bundle samples](../../../job_bundles/README.md) are ready to run; [Bash CLI job](../../../job_bundles/cli_job/) is the smallest way to confirm the farm works end to end. See [Submit jobs](https://docs.aws.amazon.com/deadline-cloud/latest/userguide/submit-jobs.html) and [building jobs](https://docs.aws.amazon.com/deadline-cloud/latest/developerguide/building-jobs.html) to write your own.

To install applications, name them in a job's `CondaPackages` parameter and the queue environment installs them before the job's steps run. `SimpleFarm`, `CudaFarm`, and `MultiPlatformFarm` install from the `deadline-cloud` channel, which provides Blender, Houdini, Maya, and Nuke, so a Conda job works right after deployment.

**`StarterFarm` needs one setup step first.** Its queue installs from the private S3 channel, which fails during the "Launch Conda" action until the channel is initialized. See [Publish packages to an Amazon S3 conda channel](https://docs.aws.amazon.com/deadline-cloud/latest/developerguide/publish-packages-s3-channel.html), then the [Conda recipe samples](../../../conda_recipes/README.md) for building your own packages.

## Development

```bash
npm run build    # type check with tsc
npm test         # jest tests against the synthesized templates
npm run synth    # synthesize every stack into cdk.out/
```

The jest tests in [`test/`](./test/) assert on the synthesized templates. They run in CI along with `cdk synth` and `cfn-lint` over every stack, configured in [`.github/workflows/cdk_checks.yml`](../../../.github/workflows/cdk_checks.yml).

## Use the farm for production

Give more people access with the [AWS IAM Identity Center management console](https://aws.amazon.com/iam/identity-center/), then grant them farm permissions from the [AWS Deadline Cloud management console](https://console.aws.amazon.com/deadlinecloud/home). To submit from applications rather than the CLI, install a [DCC integrated submitter](https://github.com/aws-deadline/#integrations).

## Customize the farm

### Select fleets to deploy

By deploying fleets with multiple different hardware configurations, you can create a farm that supports a wide variety of jobs. The app comes with three fleet presets in [`lib/deadline/fleet.ts`](./lib/deadline/fleet.ts):

- `CpuLinuxFleet`, for simulation, encoding, and CPU rendering
- `CpuWindowsFleet`, for applications and plugins that only run on Windows
- `CudaLinuxFleet`, for GPU rendering, machine learning, and 3D reconstruction

`MultiPlatformFarm` deploys all three on one queue, and `StarterFarm` takes a `fleets` list naming the ones it should deploy. Attaching more than one fleet to a queue means Deadline Cloud picks a fleet per job step, based on that step's [`hostRequirements`](https://github.com/OpenJobDescription/openjd-specifications/wiki/2023-09-Template-Schemas#33-hostrequirements). Those control the operating system and memory a step needs, along with whether it needs a GPU.

### Customize the fleet hardware

A preset takes the same properties as `ServiceManagedFleet`, so you can override any part of its hardware while keeping the rest. This raises the CUDA fleet's worker count and gives it a larger disk:

```ts
new CudaLinuxFleet(this, 'CudaLinuxFleet', {
  farm,
  maxWorkerCount: 8,
  rootEbsVolume: { sizeGiB: 500, iops: 4000, throughputMiB: 250 },
});
```

If you use spot instances, you generally want to include wider ranges of these properties when possible to increase the available instance types you can get.

`instanceMarketType` trades cost against how soon a job starts:

| Market type | Cost | Behavior |
|---|---|---|
| `on-demand` | Highest | Runs without interruption, for work with a deadline and for long tasks |
| `spot` (default) | Discounted | Unreserved capacity, interrupted by on-demand requests |
| `wait-and-save` | Lowest | Waits for cheap capacity rather than starting right away, and is interrupted by on-demand and spot requests. Suits work with no deadline, such as an overnight batch |

An interruption is not a save. The task is retried from the beginning on another worker, so a long task loses its progress. The service does not allow `wait-and-save` on a fleet with GPU accelerators, and the constructs reject that at synth rather than mid-deployment.

For hardware no preset covers, build a `ServiceManagedFleet` directly:

```ts
const fleet = new ServiceManagedFleet(this, 'ArmLinuxFleet', {
  farm,
  displayName: 'ARM Linux Fleet',
  osFamily: 'LINUX',
  cpuArchitecture: 'arm64',
  maxWorkerCount: 20,
  vCpuCount: { min: 4, max: 16 },
  memoryMiB: { min: 8192 },
});
queue.associateFleet(fleet);
```

On `StarterFarm`, pass it to `addFleet()` instead, which associates it with both queues and adds an output for its ID the same way a preset fleet gets one.

Each fleet has its own IAM role, so grant a fleet's workers what only they need with `fleet.addToRolePolicy(...)` and no other fleet is affected.

### Choose the Conda channels a queue installs from

A queue's `condaChannels` prop sets where its jobs get packages, in order of preference. Pass a `CondaChannel` for a private channel and a string for a named public one:

```ts
new Queue(this, 'Queue', {
  farm,
  displayName: 'Job Queue',
  jobAttachmentsBucket: bucket,
  condaChannels: [privateChannel, 'deadline-cloud', 'conda-forge'],
});
```

Passing a `CondaChannel` also grants the queue's role read access to it, so a job cannot fail at Conda install time because a grant was forgotten. Add [conda-forge](https://conda-forge.org/) for community-built packages, or a channel such as [bioconda](https://bioconda.github.io/). A job can override the list per submission with the `CondaChannels` parameter.

For a queue whose jobs bring their own software, pass `addDefaultCondaQueueEnvironment: false` and it gets no queue environment at all. `StarterFarm`'s package build queue does that, because the job bundles in [`conda_recipes/`](../../../conda_recipes/) carry their own Conda job environment and define a `CondaChannels` parameter of their own.

### Modify the Conda queue environment

The Conda queue environment comes from [`conda_queue_env_inline_improved_caching.yaml`](./conda_queue_env_inline_improved_caching.yaml), a copy of the [shared queue environment sample](../../../queue_environments/conda_queue_env_inline_improved_caching.yaml) of the same name. `CondaQueueEnvironment` reads that file at synth time and rewrites the default `CondaChannels` value to point at the queue's channels.

The copy is kept byte-identical to the shared original, and CI enforces that, so a fix to one is a fix to both. To customize the Conda behavior for your own farm, such as adjusting the caching behavior or the environment creation logic, edit your copy and remove it from `_SHARED_QUEUE_ENVIRONMENT_COPIES` in [`tests/test_cdk.py`](../../../tests/test_cdk.py).

To supply an environment template of your own, pass its path as `templatePath`, or add any object with a `templateYaml` property to a queue with `addEnvironment()`.

See the [queue environment samples](../../../queue_environments/README.md) for more ideas on how to configure queue environments.

### Create a CDK app for your own farm

Each example stack is a plain `cdk.Stack` subclass with typed props, so you can import one into a larger CDK application as it is.

When you want a farm none of them matches, copy [`lib/deadline/`](./lib/deadline/) into your own app and write a stack of your own. Prefer that over adding props to these stacks. A stack here is a few dozen lines of composition, and yours can be too, so start from whichever example is closest and change how the constructs are composed.

We recommend you follow Infrastructure as Code best practices, such as keeping your app in version control and strictly making changes by editing the app and deploying it instead of mixing CDK together with manual infrastructure updates from the AWS console. See the [AWS Well-Architected guidance on Infrastructure as Code](https://docs.aws.amazon.com/wellarchitected/latest/devops-guidance/dl.eac.1-organize-infrastructure-as-code-for-scale.html) to dive deeper into this topic.

## Cleanup

To destroy a farm and its queues and fleets, name the stack you deployed:

```bash
npx cdk destroy SimpleFarm
```

**That deletes the job attachments bucket too**, along with everything in it. Job input and output files go, as do any Conda packages published to its S3 channel. Nothing is left behind to keep paying for, which is what you want for a farm you deployed to try out.

For a farm holding work you care about, pass `removalPolicy: cdk.RemovalPolicy.RETAIN` to its `JobAttachmentsBucket` before you deploy it. The bucket then outlives the stack, and you delete it from the [Amazon S3 console](https://s3.console.aws.amazon.com/s3/home) once you are certain you no longer need its contents.

## Comparison with CloudFormation and Terraform

`StarterFarm` creates the same Deadline Cloud resources as the [CloudFormation starter_farm template](../../../cloudformation/farm_templates/starter_farm/) and the [Terraform starter farm](../../../terraform/farm_templates/starter_farm/), plus the job attachments bucket. `CudaFarm` corresponds to the [CloudFormation cuda_farm template](../../../cloudformation/farm_templates/cuda_farm/). See the [parent README](../../README.md) for a comparison table.
