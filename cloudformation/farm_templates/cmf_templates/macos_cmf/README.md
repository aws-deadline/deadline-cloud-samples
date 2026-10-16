# A macOS customer-managed fleet with an EC2 Mac worker host

This CloudFormation template deploys an [AWS Deadline Cloud](https://aws.amazon.com/deadline-cloud/)
farm with a macOS [customer-managed fleet](https://docs.aws.amazon.com/deadline-cloud/latest/developerguide/manage-cmf.html),
allocates an Amazon EC2 Mac Dedicated Host, and launches one Apple silicon Mac instance that installs
and starts the Deadline Cloud worker agent from its user data. The agent registers the host as a
worker and the fleet shows it as `IDLE`. You never log in to the Mac to configure it.

> [!WARNING]
> **EC2 Mac Dedicated Hosts bill for a minimum of 24 hours from allocation.** Releasing the host
> sooner, including by deleting this stack, does not reduce that charge, and each redeployment that
> allocates a new host starts a new 24-hour period. Read
> [Amazon EC2 Mac instances](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/ec2-mac-instances.html)
> and [Amazon EC2 Dedicated Host pricing](https://aws.amazon.com/ec2/dedicated-hosts/pricing/)
> before you deploy. The `ExistingDedicatedHostId` parameter lets you reuse a host you have already
> paid for, which is the cheapest way to iterate on the template.

## Two macOS differences the installer leaves to you

macOS worker hosts differ from Linux hosts in two ways that make every job on the host fail if you
get them wrong, and the worker agent installer handles neither:

* **Every `jobRunAsUser` must belong to the shared job group.** macOS seals the root volume read only,
  so the agent cannot put the session root at `/sessions` the way it does on Linux. It nests the
  session root at `/var/lib/deadline/sessions` instead, under a parent directory that is mode `0750`
  and group owned by the job group. A job user outside that group gets a permission denied error on
  its own session directory.
* **The agent user needs a `sudoers` rule to run jobs as the job user.** The installer does not create
  that rule, on macOS or on Linux, and `--allow-shutdown` does not cover it. That option creates only
  the rule that lets the agent power the host off.

The user data script implements the macOS procedure from
[Worker host setup and configuration](https://docs.aws.amazon.com/deadline-cloud/latest/developerguide/worker-host.html)
in the AWS Deadline Cloud developer guide, in the same order, so you can read that chapter alongside
the template. Lift the script into your own image build, Auto Scaling group launch template, or
configuration management tool.

## Prerequisites

1. An AWS account where EC2 Mac Dedicated Hosts are available. Allocation of `mac2` hosts is
   restricted in some accounts and Regions, and the `Running Dedicated mac2 Hosts` service quota
   starts at 0 in many accounts. Check and raise it in the
   [Service Quotas console](https://console.aws.amazon.com/servicequotas/home/services/ec2/quotas)
   before you deploy, otherwise stack creation fails when it allocates the host.
2. An Availability Zone that offers the Mac instance type you want. Mac Dedicated Hosts are offered
   in a subset of the Availability Zones in each Region. List the offerings for your Region:

   ```console
   aws ec2 describe-instance-type-offerings \
       --location-type availability-zone \
       --filters Name=instance-type,Values=mac2.metal \
       --query 'InstanceTypeOfferings[].Location' \
       --output text
   ```

3. The ID of an Apple silicon macOS AMI in your Region. The newest Amazon-owned images are:

   ```console
   aws ec2 describe-images --owners amazon \
       --filters Name=name,Values='amzn-ec2-macos-*' Name=architecture,Values=arm64_mac \
       --query 'reverse(sort_by(Images,&CreationDate))[:5].[Name,ImageId]' \
       --output table
   ```

4. A Deadline Cloud monitor, so that you can watch the worker status and submit test jobs. From
   the [AWS Deadline Cloud management console](https://console.aws.amazon.com/deadlinecloud/home),
   select "Go to Monitor setup" and follow the steps.

## How it works

The template creates these resources:

* A VPC with one public subnet in the Availability Zone you choose, an internet gateway, and a
  security group that permits outbound traffic only. The template creates its own subnet rather than
  taking one as a parameter because EC2 rejects a targeted Dedicated Host launch when the subnet and
  the host are in different Availability Zones, and CloudFormation cannot read the Availability Zone
  of a subnet supplied as a parameter.
* A Deadline Cloud farm, a macOS customer-managed fleet, a queue, and the association between them.
  The fleet declares `OsFamily: MACOS` and `CpuArchitectureType: arm64`. The queue sets
  `JobRunAsUser.RunAs` to `QUEUE_CONFIGURED_USER` with a POSIX user and group, which is what makes
  the agent run each job through `sudo -u` and gives the `sudoers` rule something to do.
* An `AWS::EC2::Host` with `AutoPlacement: off`, and a Mac instance with `Tenancy: host` and
  `Affinity: host` targeting it.
* An instance profile with the `AWSDeadlineCloud-WorkerHost` managed policy attached, which grants
  `deadline:CreateWorker` and `deadline:AssumeFleetRoleForWorker` and nothing else. The agent calls
  `AssumeFleetRoleForWorker` to obtain the fleet role's credentials for everything it does after
  registration. The profile also has `AmazonSSMManagedInstanceCore` attached, so you can open a shell
  on the Mac through Session Manager instead of opening an SSH port.

`ec2-macos-init` runs the user data as root on first boot. The script, in order:

1. Creates a virtual environment from `/usr/bin/python3` and installs the worker agent into it.
   Homebrew's `pip3` is not used: it refuses a system-wide install under PEP 668 with
   `externally-managed-environment`.
2. Creates the shared job group, the queue's job group, and the job user. The job user is hidden from
   the login window, gets a home directory and a valid login shell, and joins both groups.
3. Writes the impersonation `sudoers` rule to a temporary file, validates it with `visudo -cf`, and
   only then moves it into `/etc/sudoers.d`. A malformed file in that directory breaks `sudo` for
   every user on the host. Validating first keeps a rejected file out of the real path entirely.
4. Runs `install-deadline-worker` with the farm ID, fleet ID, Region, agent user, and shared job
   group. The installer creates the agent user, the persistence and session directories,
   `/etc/amazon/deadline/worker.toml`, and the `launchd` daemon. It installs the daemon without
   loading it.
5. Adds the agent user to the queue's job group, then runs
   `sudo -u deadline-worker sudo -n -u <job user> -i /usr/bin/id -un` to prove the impersonation path
   works. The agent chowns each queue's credentials directory to the queue's configured group, and
   changing a file's group requires membership in the target group. The installer adds the agent user
   only to the group passed to `--group`. The check runs here rather than straight after the `sudoers`
   rule, because the installer is what creates the agent user.
6. Takes no action for credentials. The agent reads them from the instance profile.
7. Bootstraps the `launchd` daemon and polls for `state = running`. Both `launchctl kickstart` and the
   `pid` field of `launchctl print` report a process that exited immediately, so `state = running` is
   the only check that means the agent is up.

The script writes its own trace to `/var/log/deadline-worker-bootstrap.log`, mode `600`.

## Setup

### Using the CloudFormation console

1. Download the [deadline-cloud-macos-cmf-template.yaml](deadline-cloud-macos-cmf-template.yaml)
   CloudFormation template.
2. From the [CloudFormation console](https://console.aws.amazon.com/cloudformation/), choose
   **Create stack > With new resources (standard)**.
3. Choose **Upload a template file** and upload the template.
4. Enter a stack name, then the `AvailabilityZone` and `WorkerImageId` values from the prerequisites.
5. Follow the console steps to complete stack creation. Acknowledge the IAM capability prompt.
6. From the [AWS Deadline Cloud console](https://console.aws.amazon.com/deadlinecloud/home), open the
   new farm, select the **Access management** tab, and add your monitor user with the **Owner** access
   level.

### Using the CLI

```console
export AVAILABILITY_ZONE=us-west-2b
export WORKER_IMAGE_ID=ami-EXAMPLE1234567890

aws cloudformation deploy \
    --template-file deadline-cloud-macos-cmf-template.yaml \
    --stack-name macos-cmf \
    --capabilities CAPABILITY_IAM \
    --parameter-overrides \
        AvailabilityZone=$AVAILABILITY_ZONE \
        WorkerImageId=$WORKER_IMAGE_ID
```

To reuse a Dedicated Host you already pay for, add `ExistingDedicatedHostId=h-EXAMPLE1234567890`. The
host must be in `AvailabilityZone` and must support `WorkerInstanceType`.

### Confirm the worker joined the fleet

Allow 15 to 25 minutes after stack creation completes. An EC2 Mac instance takes 5 to 10 minutes to
boot far enough to run user data, and the agent install adds another 5.

1. In the Deadline Cloud monitor, open the fleet and confirm that one worker shows as `IDLE`.
2. If the fleet is still empty, open a shell on the host and read the bootstrap log:

   ```console
   aws ssm start-session --target i-EXAMPLE1234567890
   sudo tail -100 /var/log/deadline-worker-bootstrap.log
   sudo tail -f /var/log/amazon/deadline/worker-agent.log
   ```

3. Submit a job to the queue that prints `id -un` and fails when the name does not match the job
   user. One job verifies the group membership and the `sudoers` rule together. For more ways to
   validate a fleet, see
   [Test the configuration of your worker host](https://docs.aws.amazon.com/deadline-cloud/latest/developerguide/test-software.html).

## Parameters and outputs

| Parameter | Default | Description |
|---|---|---|
| `AvailabilityZone` | none | Availability Zone for the Dedicated Host and the worker subnet. |
| `WorkerImageId` | none | Apple silicon macOS AMI ID. |
| `WorkerInstanceType` | `mac2.metal` | Verified Apple silicon types: `mac2.metal`, `mac2-m2.metal`, `mac2-m2pro.metal`, `mac2-m1ultra.metal`. |
| `ExistingDedicatedHostId` | empty | Reuse an allocated Mac Dedicated Host instead of allocating one. |
| `MinVCpuCount` / `MinMemoryMiB` | `8` / `16384` | Capabilities the fleet advertises. Match them to your instance type. |
| `JobRunAsUserName` / `JobRunAsGroupName` | `deadline-job-user` | The queue's POSIX user and group. |
| `WorkerJobGroupName` | `deadline-job-users` | Shared job group passed to the installer's `--group`. |
| `WorkerAgentPackageSpecifier` | `deadline-cloud-worker-agent>=0.31.1` | pip requirement for the agent. macOS support arrived in 0.31.1. |
| `AllowWorkerShutdown` | `false` | Whether to pass `--allow-shutdown` to the installer. |
| `MaxWorkerCount` | `5` | Fleet worker limit. Terminal worker records still count against it. |
| `KeyName` | empty | Optional EC2 key pair for SSH as `ec2-user`. |
| `SshIngressCidr` | empty | Optional CIDR allowed to reach TCP port 22. Leave it empty to skip the inbound rule. |

Outputs give the farm, fleet, queue, instance, and Dedicated Host IDs, the two log paths on the host,
and a ready-to-run `aws ssm start-session` command.

### Why `AllowWorkerShutdown` defaults to false

`--allow-shutdown` creates the `sudoers` rule that lets the agent run `/sbin/shutdown -h now` when the
service stops the worker, and sets `shutdown_on_stop = true` in `worker.toml`. That is how EC2 Auto
Scaling reclaims idle capacity on Linux and Windows fleets, where stopping or terminating an instance
stops the charge for it.

On a Dedicated Host it saves nothing. You pay for the allocated host by the hour whether an instance
runs on it or not, and stopping the instance does not release the host or end its 24-hour minimum. The
only effect is a powered-off Mac that stops taking work until you start it again. Leave the parameter
at `false` for a Dedicated Host and for any physical Mac. Set it to `true` only if something outside
this template releases the host when the instance stops.

## Security, cost, and cleanup

**Cost.** The Dedicated Host bills a 24-hour minimum from allocation and dominates the cost of this
sample. Deleting the stack releases the host but does not refund the remainder of the 24 hours. The
template does not create a NAT gateway. The worker connects to PyPI and the Deadline Cloud endpoints
through a public IP in a public subnet.

**The impersonation `sudoers` rule.** The rule grants the agent user the ability to run any command as
the job user, which is what the queue-configured user model requires. It does not grant root. The
template writes one rule for one job user. Add a `Runas_Spec` entry for each additional
`jobRunAsUser` when you add queues, and keep the `visudo -cf` validation.

**Group separation.** `JobRunAsGroupName` defaults to a group of its own rather than reusing
`WorkerJobGroupName`. The agent chowns a queue's session credentials directory to the queue's
configured group, so pointing more than one queue at the shared job group would let each queue's job
users read the others' credentials. Give every queue its own group and add the agent user to each, as
Step 5 of the user data does.

**Inbound access.** The security group does not open an inbound port unless you set `SshIngressCidr`.
Session Manager doesn't need an inbound rule, so it is the preferred way in.

The instance profile includes `AmazonSSMManagedInstanceCore`, which is what Session Manager requires
of the role. Session Manager also needs the SSM Agent running on the host. If
`aws ssm start-session` reports that the target is not connected, set `KeyName` and `SshIngressCidr`
to a narrow range and use SSH instead. Prefer a prefix list over a wide CIDR, and never `0.0.0.0/0`.

**Platform considerations this template does not handle.** A headless `launchd` daemon can be blocked
by macOS Transparency, Consent, and Control from reading protected locations such as `Desktop`,
`Documents`, and removable volumes, and it cannot present the consent dialog. The default session root
under `/var/lib/deadline` is not a protected location, so the default configuration is unaffected. A
job that reads a protected location needs an MDM profile that grants Full Disk Access to the agent
binary.

**Cleanup.**

```console
aws cloudformation delete-stack --stack-name macos-cmf
```

Delete the stack's workers from the fleet first if you plan to redeploy. Worker records in a terminal
state continue to count against the fleet's `maxWorkerCount`, and a fleet at its limit rejects
`CreateWorker` with a `ConflictException` that says `reached its maxWorkerCount`.

## Troubleshooting

| Symptom | Cause | Resolution |
|---|---|---|
| Stack creation fails allocating the host | The Region, Availability Zone, or account does not offer the instance type, or the `Running Dedicated mac2 Hosts` quota is 0 | Check the offerings with `describe-instance-type-offerings` and raise the quota |
| The fleet is still empty after 25 minutes | The user data script failed. `ec2-macos-init` runs user data as a best-effort step, so a failed bootstrap does not fail the instance or the stack | Read `/var/log/deadline-worker-bootstrap.log` on the host. The script traces every command it runs into that file |
| `aws ssm start-session` reports the target is not connected | The SSM Agent is not running on the host | Set `KeyName` and a narrow `SshIngressCidr` and use SSH to read the bootstrap log instead |
| A job fails with a permission denied error on its session path | The `jobRunAsUser` is not in the job group | Add it with `dseditgroup -o edit -a <user> -t user deadline-job-users` and retry |
| A job fails to start as the queue's `jobRunAsUser` | The `sudoers` rule is missing, or the job user has no home directory or login shell | Run `sudo -u deadline-worker sudo -n -u <user> -i /usr/bin/id -un`. If it fails, the rule is the problem. If it succeeds, check the home directory ownership and the login shell |
| The agent logs a `ConflictException` saying `reached its maxWorkerCount` | Terminal worker records still count against the fleet limit | Delete the stale workers, or raise `MaxWorkerCount` |

For more symptoms, see
[Worker host setup and configuration](https://docs.aws.amazon.com/deadline-cloud/latest/developerguide/worker-host.html)
in the AWS Deadline Cloud developer guide.

## Related resources

* [Worker host setup and configuration](https://docs.aws.amazon.com/deadline-cloud/latest/developerguide/worker-host.html)
  in the AWS Deadline Cloud developer guide, the chapter with the procedure the user data implements.
* [Configuring AWS credentials](https://docs.aws.amazon.com/deadline-cloud/latest/developerguide/aws-credentials.html)
  in the AWS Deadline Cloud developer guide, for a worker host outside EC2 that has no instance
  profile.
* [Manage customer-managed fleets](https://docs.aws.amazon.com/deadline-cloud/latest/developerguide/manage-cmf.html)
  in the AWS Deadline Cloud developer guide.
* [CMF fleet health check](../) adds continuous monitoring to a customer-managed fleet that
  autoscales.
* [Passwordless sudo for the job user](../../../../host_configuration_scripts/sudo_for_job_user/)
  solves the related problem on Linux service-managed fleet workers.
* [Amazon EC2 Mac instances](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/ec2-mac-instances.html)
  in the Amazon EC2 User Guide.
