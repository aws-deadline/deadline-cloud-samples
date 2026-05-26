# Passwordless Sudo for Job User

Grant the Deadline Cloud `job-user` passwordless sudo access on Linux service managed fleet workers.

Some workloads require root privileges — for example, installing packages, mounting filesystems, or registering the worker as an SSM managed node. By default, `job-user` does not have sudo access.

## What It Does

The script adds a sudoers rule that allows `job-user` to run any command as root without a password prompt. If `job-user` does not exist yet (e.g. the worker agent hasn't created it), the script logs a warning and exits successfully so it doesn't block fleet provisioning.

## Security Considerations

Granting passwordless sudo to `job-user` means any job running on the worker can execute arbitrary commands as root. Only enable this on fleets where you trust the jobs being submitted, and consider scoping the sudoers rule to specific commands if your use case allows it.

## Usage

1. Open the AWS Deadline Cloud console
2. Navigate to your fleet
3. Go to the "Host configuration" section
4. Copy and paste the contents of `linux.sh` into the script field
5. Save the configuration

New fleet instances will automatically configure passwordless sudo for `job-user` on startup.
