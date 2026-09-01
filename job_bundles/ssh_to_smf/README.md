# SSM Managed Node via Deadline Cloud Job

Register a Deadline Cloud worker as an SSM hybrid managed node, enabling SSH access via Session Manager for the duration of the job.

## Why Shell Access to a Worker?

A service-managed fleet worker has no public address and accepts no inbound connections, so a failing job normally has to be diagnosed from its log alone. That works until the question turns environmental: whether the license server answers from the worker's subnet, or why a plugin that loads on your workstation fails on the worker.

The job in this bundle registers the worker as an SSM managed node, which gets you an interactive shell on the machine that ran your job. Session Manager brokers the connection, so access is IAM-gated and audited in CloudTrail. Reaching the node depends on the SSM agent, which the job stops on its way out, so the shell dies with the job.

Session Manager logs you in as `ssm-user` rather than the `job-user` account the job itself runs under. Switch accounts once you are connected:

```bash
sudo -u job-user -i
```

That opens a clean login shell as `job-user`, with that account's own profile and the same view of the filesystem the job has, which is what you want for running a step by hand. The job's live environment is a separate thing: variables that queue environments set exist only inside the session's process tree, so read those from the job log rather than from this shell.

Some ways customers use it:

- **Diagnose a failing job in place.** Inspect the job attachment mounts and whatever a failing step left on disk, as `job-user` sees them, rather than inferring from log output.
- **Prototype a host configuration script.** Install and test packages by hand until the steps work, then paste the finished commands into your fleet's host configuration. Pairs well with [`sudo_for_job_user`](../../host_configuration_scripts/sudo_for_job_user/README.md).
- **Reach interactive tools through a port forward.** A Jupyter notebook or a GPU profiler running on the worker becomes available on `localhost`. See [Port forwarding](#port-forwarding) below.
- **Confirm what the AMI includes.** Check driver versions and conda environments on the instance type your fleet uses, before you commit a long render to it.
- **Verify network reachability.** Test license servers and package repositories from inside the worker's subnet, where a job's real failure often lives.
- **Validate a container setup.** Run images by hand and check GPU passthrough before wiring them into a job template, alongside [`docker_nvidia_container_toolkit`](../../host_configuration_scripts/docker_nvidia_container_toolkit/README.md).

Treat the bundle as a debugging tool. The job holds the worker for the full `SessionMinutes` whether or not anyone is connected, and disconnecting your session does not release it, so worker time bills until the timer expires. Keep `SessionMinutes` short and cancel the job when you finish.

Cancelling stops the billing, but the `mi-` entry remains in your account's SSM inventory either way. Deregister it afterwards:

```bash
aws ssm deregister-managed-instance --instance-id mi-XXXXXXXXX --region us-west-2
```

## How It Works

1. The submit script creates a one-time SSM hybrid activation (`aws ssm create-activation`)
2. The Deadline Cloud job runs on a worker, downloads `ssm-setup-cli`, then registers the worker as a managed node
3. The job prints the `mi-*` managed node ID to the log
4. You connect with `aws ssm start-session --target mi-XXXXXXXXX`
5. After the configured session duration, the job deregisters the node and cleans up

## One-Time Account Setup

### 1. Create the SSM IAM Role

The hybrid activation requires an IAM role with the SSM service principal trust and the managed instance core policy.

```bash
aws iam create-role --role-name SSMServiceRole \
  --assume-role-policy-document '{
    "Version": "2012-10-17",
    "Statement": [{
      "Effect": "Allow",
      "Principal": {"Service": "ssm.amazonaws.com"},
      "Action": "sts:AssumeRole"
    }]
  }'

aws iam attach-role-policy --role-name SSMServiceRole \
  --policy-arn arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore
```

### 2. Enable Advanced-Instances Tier

Session Manager requires the advanced-instances tier for hybrid `mi-*` nodes. This tier is a one-time setting per region.

```bash
aws ssm update-service-setting \
  --setting-id "arn:aws:ssm:us-west-2:YOUR_ACCOUNT_ID:servicesetting/ssm/managed-instance/activation-tier" \
  --setting-value "advanced" \
  --region us-west-2
```

Cost: ~$0.00695/hr per on-premises managed instance. Negligible for short-lived sessions.

### 3. Worker Host Requirements

- The Deadline Cloud worker must have passwordless sudo for `job-user` (see `setup/host_config.sh`)
- Outbound internet access to `amazon-ssm-{region}.s3.{region}.amazonaws.com`
- The submitter needs `ssm:CreateActivation` IAM permissions

## Usage

### Submit a Job

The submit script creates an SSM hybrid activation and submits the Deadline Cloud job in one step:

```bash
# Default: 60 min session, SSMServiceRole, us-west-2
./submit.sh

# Custom session duration (120 minutes)
./submit.sh 120

# Custom IAM role and region
./submit.sh 60 MySSMRole us-east-1

# Debug mode (prints full activation code)
./submit.sh 60 SSMServiceRole us-west-2 --show
```

Or submit manually with the Deadline CLI:

```bash
# Create activation first
ACTIVATION=$(aws ssm create-activation \
  --iam-role SSMServiceRole \
  --registration-limit 1 \
  --region us-west-2 \
  --output json)

CODE=$(echo "$ACTIVATION" | jq -r '.ActivationCode')
ID=$(echo "$ACTIVATION" | jq -r '.ActivationId')

# Submit the job bundle
deadline bundle submit job/ \
  --farm-id farm-XXXXXXXX \
  --queue-id queue-XXXXXXXX \
  --parameter "ActivationCode=$CODE" \
  --parameter "ActivationId=$ID" \
  --parameter "SessionMinutes=120"
```

### Connect to the Worker

Once the job is running, find the managed node ID in the Deadline Cloud job log (it prints `SSM Managed Node ID: mi-XXXXXXXXX`).

#### Interactive shell

```bash
aws ssm start-session --target mi-XXXXXXXXX --region us-west-2
```

#### Port forwarding

Forward a remote port on the worker to your local machine, so you can reach services running on the worker such as web UIs and Jupyter notebooks:

```bash
# Forward worker port 8888 to localhost:8888
aws ssm start-session \
  --target mi-XXXXXXXXX \
  --region us-west-2 \
  --document-name AWS-StartPortForwardingSession \
  --parameters '{"portNumber":["8888"],"localPortNumber":["8888"]}'
```

#### SSH over Session Manager

You can also use SSH through the SSM tunnel. Add this to your `~/.ssh/config`:

```
Host mi-*
  ProxyCommand aws ssm start-session --target %h --document-name AWS-StartSSHSession --parameters "portNumber=%p" --region us-west-2
  User ssm-user
  StrictHostKeyChecking no
```

Then connect directly:

```bash
ssh mi-XXXXXXXXX
```

Or use SSH port forwarding for multiple ports at once:

```bash
ssh -L 8888:localhost:8888 -L 6006:localhost:6006 mi-XXXXXXXXX
```

## File Structure

```
ssh_ssm_managed_node/
├── README.md              ← this file
├── design.md              ← design document
├── submit.sh              ← creates activation + submits job
├── setup/
│   └── host_config.sh     ← worker host setup (placeholder)
└── job/
    └── template.yaml      ← Deadline Cloud job template
```

## Troubleshooting

| Error | Cause | Fix |
|-------|-------|-----|
| `Nonexistent role or missing ssm service principal` | SSMServiceRole doesn't exist | Run the IAM role creation commands above |
| `Enable advanced-instances tier` | Standard tier can't use Session Manager with `mi-*` nodes | Run the `update-service-setting` command above |
| `gpg: failed to create temporary file '/root/.gnupg/...'` | Root's gnupg dir missing on worker | The template handles this automatically with `mkdir -p /root/.gnupg` |
| Job keeps failing with signature verification | GPG still broken on worker | The template falls back to `-skip-signature-validation` automatically |
