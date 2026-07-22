# SSM Managed Node via Deadline Cloud Job: Design

## Overview

A Deadline Cloud job bundle that registers the worker as an SSM hybrid managed node, enabling SSH access via Session Manager. The job:

1. Receives an SSM hybrid activation code + ID as parameters (generated externally via `aws ssm create-activation`)
2. Downloads and runs `ssm-setup-cli` to register the worker as a managed node
3. Prints the resulting `mi-*` managed node ID to the job log
4. Keeps the job alive for a configurable duration (minutes), then deregisters and cleans up

## Architecture

```
┌──────────────────────┐       ┌──────────────────────────┐
│  Submitter (you)     │       │  Deadline Cloud Worker    │
│                      │       │  (Linux, sudo access)     │
│  1. aws ssm          │       │                           │
│     create-activation│       │  3. curl ssm-setup-cli    │
│     --iam-role ...   │──────▶│  4. ssm-setup-cli         │
│                      │ params│     -register              │
│  2. deadline submit  │       │     -activation-code ...   │
│     --parameters     │       │     -activation-id ...     │
│     ActivationCode=X │       │  5. Print mi-XXXXXXX      │
│     ActivationId=Y   │       │  6. Sleep SESSION_MINUTES │
│     SessionMinutes=60│       │  7. Deregister + cleanup  │
└──────────────────────┘       └──────────────────────────┘
```

## Job Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `Message` | STRING | "Starting SSM Managed Node registration" | Log banner |
| `ActivationCode` | STRING | *(required)* | SSM hybrid activation code from `create-activation` |
| `ActivationId` | STRING | *(required)* | SSM hybrid activation ID from `create-activation` |
| `AWS_REGION` | STRING | us-west-2 | Region where the activation was created and where to download ssm-setup-cli |
| `SessionMinutes` | INT | 60 | How many minutes to keep the managed node registered and the job alive |

## Job Script Flow

The job template (`job/template.yaml`) implements four phases:

1. **Install & Register**: Downloads `ssm-setup-cli` and registers the worker as a managed node using the activation credentials
2. **Extract Node ID**: Reads the `mi-*` managed node ID from `/var/lib/amazon/ssm/registration` and prints it to the job log
3. **Keep Alive**: Loops for `SessionMinutes`, printing status every 60s (same pattern as the VNC/DCV jobs in this project)
4. **Cleanup / Deregister**: Deregisters the managed node and stops the SSM agent

See `job/template.yaml` for the full implementation.

## Prerequisites

- The Deadline Cloud worker must have sudo access (stated in requirements)
- An IAM role for SSM hybrid nodes must exist (e.g. `SSMServiceRole` with `AmazonSSMManagedInstanceCore` policy)
  - **IMPORTANT**: This role must be created before first use. It requires:
    1. A trust policy allowing `ssm.amazonaws.com` to assume the role
    2. The `AmazonSSMManagedInstanceCore` managed policy attached
  - The submit script defaults to `SSMServiceRole`. If this role doesn't exist, `create-activation` will fail with `Nonexistent role or missing ssm service principal in trust policy`
  - Create it once per account:
    ```bash
    aws iam create-role --role-name SSMServiceRole \
      --assume-role-policy-document '{"Version":"2012-10-17","Statement":[{"Effect":"Allow","Principal":{"Service":"ssm.amazonaws.com"},"Action":"sts:AssumeRole"}]}'
    aws iam attach-role-policy --role-name SSMServiceRole \
      --policy-arn arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore
    ```
- The worker must have outbound internet access to reach `amazon-ssm-{region}.s3.{region}.amazonaws.com`
- The submitter needs `ssm:CreateActivation` permissions
- The SSM advanced-instances tier must be enabled in the account/region to use `aws ssm start-session` with hybrid `mi-*` nodes. Set this once per region:
  ```bash
  aws ssm update-service-setting \
    --setting-id "arn:aws:ssm:<region>:<account-id>:servicesetting/ssm/managed-instance/activation-tier" \
    --setting-value "advanced" \
    --region <region>
  ```
  Note: advanced tier costs ~$0.00695/hr per on-premises managed instance.

## File Structure

```
ssh_ssm_managed_node/
├── design.md          ← this file
└── job/
    └── template.yaml  ← Deadline Cloud job template
```

## Security Notes

- The activation code is a secret, so treat it like a password. The activation ID is not secret and can be shared safely.
- Activation codes are single-use (registration-limit=1) and short-lived (24h default expiry)
- The activation code/ID are passed as job parameters. They are not persisted or stored on disk beyond the job session
- The managed node is deregistered when the job ends
- No credentials are hardcoded; the activation is generated at submission time
