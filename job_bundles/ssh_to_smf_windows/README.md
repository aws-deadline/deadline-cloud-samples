# SSM Managed Node via Deadline Cloud Job (Windows)

Register a **Windows** Deadline Cloud worker as an SSM hybrid managed node, enabling RDP, SSH, or PowerShell access via Session Manager for the duration of the job.

This is the Windows sibling of [`ssh_to_smf`](../ssh_to_smf/README.md). The Linux version registers a Linux worker via bash + `ssm-setup-cli` (Linux amd64). This Windows version re-uses the **pre-installed** `amazon-ssm-agent.exe` shipped on the Deadline Cloud Windows AMI and re-registers it as a hybrid node.

> **Security note.** The RDP user is a local Administrator, and `job-user` is also made a local Administrator so the job can control the SSM service and the elevated task. Use this host config and job bundle for debugging purposes, not for production. Shut down all workers in this fleet once debugging is done — do not leave an RDP-capable instance running.

## How It Works

1. The submit script creates a one-time SSM hybrid activation (`aws ssm create-activation`).
2. The Deadline Cloud job runs on a Windows worker. It checks outbound reachability to the SSM endpoints, then asks a pre-installed SYSTEM-elevated scheduled task (`DeadlineSsmElevated`, set up by the fleet host config) to:
   1. Stop `AmazonSSMAgent`,
   2. Run `amazon-ssm-agent.exe -register -clear` to wipe the EC2 identity,
   3. Run `amazon-ssm-agent.exe -register -code <...> -id <...> -region <...>` with the hybrid activation,
   4. Reinstall the Windows service (the `-register` codepath on the Deadline AMI removes it),
   5. Start `AmazonSSMAgent` — it now comes up as a hybrid `mi-*` node.
3. The job prints the `mi-*` managed node ID to the log.
4. You connect with `aws ssm start-session --target mi-XXXXXXXXX` (shell, RDP port-forward, or SSH-over-SSM).
5. After the configured session duration, the job deregisters the node and cleans up.

### Why a SYSTEM-elevated scheduled task?

`amazon-ssm-agent.exe -register` requires an unfiltered admin token. On Windows, a process spawned by the Deadline worker runs as `job-user` with a **UAC-filtered** token, even if `job-user` is in `Administrators`. The SSM agent binary refuses to run in that context (`binary needs to be executed by administrator`). `NT AUTHORITY\SYSTEM` is not subject to UAC filtering, so the host-config script installs a scheduled task that runs as SYSTEM. `job-user` is granted `GenericRead + GenericExecute` on that task so the job template can trigger it via `schtasks.exe /Run` and read its captured output.

## One-Time Account Setup

Identical to the Linux bundle (`ssh_to_smf`) — do it once per account/region.

### 1. Create the SSM IAM Role

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

```bash
aws ssm update-service-setting \
  --setting-id "arn:aws:ssm:us-west-2:YOUR_ACCOUNT_ID:servicesetting/ssm/managed-instance/activation-tier" \
  --setting-value "advanced" \
  --region us-west-2
```

### 3. Worker Host Requirements

- Outbound HTTPS from the worker VPC to `ssm.<region>.amazonaws.com`, `ssmmessages.<region>.amazonaws.com`, `ec2messages.<region>.amazonaws.com`.
- The submitter needs `ssm:CreateActivation` IAM permissions.
- The fleet uses the pre-installed SSM Agent (`C:\Program Files\Amazon\SSM\amazon-ssm-agent.exe`), which ships on the Deadline Cloud service-managed Windows AMI.

## Deadline Fleet Host Configuration

Unlike a workstation-style "run this on each host" setup, this bundle relies on a **Deadline Cloud fleet host configuration script** (`setup/host_config.ps1`). That script is uploaded to the fleet once; Deadline then runs it **as Administrator on every fresh worker** before the worker takes any jobs.

### What `setup/host_config.ps1` does

- Creates a local user (default name `RDP`, password `ChangeMe2026!!@@##`) in the `Administrators` and `Remote Desktop Users` groups. Idempotent — rotates the password if the user already exists.
- Disables the UAC consent prompt (`ConsentPromptBehaviorAdmin = 0`) so scripted admin actions do not block on a prompt.
- Enables RDP (`fDenyTSConnections = 0`), enables the Remote Desktop firewall rule group, and sets `TermService` to Automatic + Running.
- Adds the Deadline worker service account `job-user` to `Administrators` (needed so the job can trigger the elevated scheduled task and own the eventual RDP/PowerShell session).
- Registers the `DeadlineSsmElevated` scheduled task (runs as `NT AUTHORITY\SYSTEM`, Highest run level). The task reads an `args.json` spec from `C:\ProgramData\Amazon\Deadline\SsmElevated\` and writes its stdout/stderr + exit code back to that directory. The DACL is rewritten to give `job-user` `GenericRead + GenericExecute`.

### Deploying the host config to a fleet

Pick one of the following — they are equivalent.

#### Option A: Deadline Cloud console

1. Open the fleet in the Deadline Cloud console.
2. Edit the fleet.
3. In **Host configuration**, paste the contents of `setup/host_config.ps1` into **Script body** and set **Timeout** to at least 300 seconds.
4. Save. The next worker that comes up runs it.

#### Option B: `aws deadline update-fleet`

```bash
# Build the --host-configuration payload from the local script.
python3 - <<'PY' > /tmp/hc_payload.json
import json, pathlib
body = pathlib.Path("setup/host_config.ps1").read_text()
print(json.dumps({"scriptBody": body, "scriptTimeoutSeconds": 300}))
PY

aws deadline update-fleet \
  --farm-id  farm-XXXXXXXX \
  --fleet-id fleet-XXXXXXXX \
  --region   us-west-2 \
  --host-configuration file:///tmp/hc_payload.json
```

The update takes effect for **new** workers only. Workers already running on the fleet keep their existing state. To roll the change out, cycle the fleet:

```bash
aws deadline update-fleet \
  --farm-id farm-XXXXXXXX --fleet-id fleet-XXXXXXXX --region us-west-2 \
  --min-worker-count 0 --max-worker-count 0

# Wait for workers to drain (a service-managed EC2 fleet typically takes 3-5 min
# to actually terminate the instance). Confirm with:
aws deadline list-workers --farm-id farm-XXXXXXXX --fleet-id fleet-XXXXXXXX \
  --region us-west-2 --query 'workers[].{id:workerId,status:status}' --output table

# Then scale back up:
aws deadline update-fleet \
  --farm-id farm-XXXXXXXX --fleet-id fleet-XXXXXXXX --region us-west-2 \
  --min-worker-count 1 --max-worker-count 1
```

The script is idempotent — re-running it rotates the RDP password and skips anything that is already configured.

## Usage

### Submit a Job

The bundle ships both a bash and a PowerShell submitter — use whichever matches your submitting OS.

**Linux / macOS:**

```bash
# Default: 60 min session, SSMServiceRole, us-west-2
./submit.sh farm-XXX queue-XXX

# Custom session duration
./submit.sh farm-XXX queue-XXX 120

# Custom IAM role and region
./submit.sh farm-XXX queue-XXX 60 MySSMRole us-east-1

# Debug mode (prints full activation code)
./submit.sh farm-XXX queue-XXX 60 SSMServiceRole us-west-2 --show
```

**Windows (PowerShell):**

```powershell
# Default: 60 min session, SSMServiceRole, us-west-2
.\submit.ps1 -FarmId farm-XXX -QueueId queue-XXX

# Custom session duration
.\submit.ps1 -FarmId farm-XXX -QueueId queue-XXX -SessionMinutes 120

# Custom IAM role and region
.\submit.ps1 -FarmId farm-XXX -QueueId queue-XXX -SessionMinutes 60 `
    -IamRole MySSMRole -Region us-east-1

# Debug mode
.\submit.ps1 -FarmId farm-XXX -QueueId queue-XXX -Show
```

> **Registration limit:** `submit.sh` and `submit.ps1` both create an activation with `--registration-limit 10`. Deadline retries a failed job up to 5 times by default, and each retry consumes one registration count. Dropping this back to 1 is fine in production once the job is stable.

### Connect to the Worker

Once the job is running, find the managed node ID in the Deadline Cloud job log — look for `SSM Managed Node ID: mi-XXXXXXXXX`.

Verify the node is reachable before attempting to connect:

```bash
aws ssm describe-instance-information --region us-west-2 \
  --filters "Key=InstanceIds,Values=mi-XXXXXXXXX" \
  --query 'InstanceInformationList[0].{id:InstanceId,ping:PingStatus,last:LastPingDateTime}' \
  --output json
```

`PingStatus` should be `Online` within ~30 seconds of the mi-* ID appearing in the job log.

#### Interactive PowerShell shell (via SSM Session Manager)

```bash
aws ssm start-session --target mi-XXXXXXXXX --region us-west-2
```

Session Manager drops you into a PowerShell prompt as the `ssm-user` account.

#### RDP via port-forward

```bash
aws ssm start-session \
  --target mi-XXXXXXXXX \
  --region us-west-2 \
  --document-name AWS-StartPortForwardingSession \
  --parameters '{"portNumber":["3389"],"localPortNumber":["13389"]}'
```

Then, from another terminal or Remote Desktop client:

```
mstsc /v:localhost:13389
```

Log in as the RDP user configured in `host_config.ps1` (default: username `RDP`, password `ChangeMe2026!!@@##`).

##### Logging in as `job-user` (optional)

`job-user` is the Deadline worker service account that actually runs the job. By default it does not support login with an exposed password, so you cannot RDP in as `job-user` directly. If you want to inspect the job environment as `job-user` (same token, same env vars, same filesystem view), first RDP in as the `RDP` admin, open an elevated PowerShell, and run:

```powershell
Set-LocalUser -Name job-user -Password (ConvertTo-SecureString -AsPlainText -Force 'ChangeMe2026!!@@##')
```

Pick your own password — the one above is a placeholder. You can now disconnect and reconnect via `mstsc /v:localhost:13389` as `job-user` with that password.

#### SSH over Session Manager

If the OpenSSH Server feature is installed on the worker (install with `Add-WindowsCapability -Online -Name OpenSSH.Server~~~~0.0.1.0`, Windows Server 2019+):

```
Host mi-*
  ProxyCommand aws ssm start-session --target %h --document-name AWS-StartSSHSession --parameters "portNumber=%p" --region us-west-2
  User RDP
  StrictHostKeyChecking no
```

```bash
ssh mi-XXXXXXXXX
```

## File Structure

```
ssh_to_smf_windows/
├── README.md              ← this file
├── submit.sh              ← bash submitter (Linux/macOS)
├── submit.ps1             ← PowerShell submitter (Windows)
├── setup/
│   └── host_config.ps1    ← Deadline fleet host configuration script
└── job/
    └── template.yaml      ← Deadline Cloud job template (Windows-only hostRequirements)
```

## Host Requirements

The job template restricts execution to Windows workers:

```yaml
hostRequirements:
  attributes:
  - name: attr.worker.os.family
    anyOf:
    - windows
```

Submitting against a queue that has no Windows workers will simply leave the job queued.

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `Nonexistent role or missing ssm service principal` | `SSMServiceRole` doesn't exist | Run the IAM role creation commands above |
| Host config log: `Finished running Host Configuration Script, exit code: 1` with all steps visibly succeeding | `Set-StrictMode` + `Format-Table` in PS 5.1 can leak a non-zero `$LASTEXITCODE` | `setup/host_config.ps1` already handles this with an explicit `exit 0` at the end — if you edit the script, keep that terminator |
| Job log: `flag provided but not defined: -y` | Older template was calling `ssm-setup-cli.exe -y` | This bundle no longer uses `ssm-setup-cli`. Make sure you submitted the current `job/template.yaml` |
| Job log: `Please run as root/admin. Err: binary needs to be executed by administrator` | Trying to run `amazon-ssm-agent.exe -register` directly as `job-user` (UAC-filtered admin token) | Make sure the `DeadlineSsmElevated` scheduled task is installed — re-run the fleet host config |
| Job log: `ERROR Registration failed ... RegistrationLimitExceeded` | Deadline retried the job and consumed all registration slots on the activation | Increase `--registration-limit` in `submit.sh` / `submit.ps1`, or reduce the job's retry count |
| Job log: `AmazonSSMAgent service not present` | `amazon-ssm-agent.exe -register` removed the Windows service on this AMI flavor | The template reinstalls it via `sc.exe create`; no action needed |
| Job log: `Could not extract mi-<hex> ID from elevated output or registration file` | PowerShell 5.1 captured `*>>` output is UTF-16 with null bytes that break regex | The template already strips null bytes before regex — re-submit with the current `job/template.yaml` |
| `aws ssm start-session` returns `TargetNotConnected` | Managed node hasn't finished registering, or the agent isn't running | Wait ~30s after `SSM Managed Node ID:` appears; verify with `aws ssm describe-instance-information --filters Key=InstanceIds,Values=mi-...` |
| Reachability check in job log: `FAIL ssm.<region>.amazonaws.com:443` | VPC has no outbound HTTPS to the SSM endpoints | Add a NAT gateway, or attach SSM VPC interface endpoints (`com.amazonaws.<region>.ssm`, `.ssmmessages`, `.ec2messages`) |
| `mstsc` connection refused on port 13389 | The port-forward isn't up, or RDP isn't listening on the worker | Confirm `setup/host_config.ps1` ran successfully on this worker; check CloudWatch `/aws/deadline/{farm}/{fleet}` stream `worker-*` for host-config errors |

### Iterating on the host-config script

Host-config failures are debugged via the per-worker CloudWatch log stream (not the per-session stream):

```bash
# Log group is /aws/deadline/{farm_id}/{fleet_id}
# Log stream is the worker ID.
aws logs tail "/aws/deadline/farm-XXXX/fleet-XXXX" \
  --log-stream-names "worker-XXXX" \
  --region us-west-2 --since 10m --follow
```

Push a new host-config via `aws deadline update-fleet --host-configuration file://...`, then cycle workers to 0 and back to pick up the change (see Option B above).

## See Also

- [`ssh_to_smf`](../ssh_to_smf/README.md) — the Linux version this bundle is cloned from
- [Linux sibling design reference](../ssh_to_smf/DESIGN.md) — background for the shared SSM activation pattern
