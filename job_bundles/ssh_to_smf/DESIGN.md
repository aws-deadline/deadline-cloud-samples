# SSM Managed Node via Deadline Cloud Job — Design

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

### Step 1 — Install & Register SSM Agent

Following the [AWS docs for hybrid Linux nodes](https://docs.aws.amazon.com/systems-manager/latest/userguide/hybrid-multicloud-ssm-agent-install-linux.html):

```bash
# Download ssm-setup-cli from the correct region
mkdir -p /tmp/ssm
curl "https://amazon-ssm-${REGION}.s3.${REGION}.amazonaws.com/latest/linux_amd64/ssm-setup-cli" \
  -o /tmp/ssm/ssm-setup-cli
sudo chmod +x /tmp/ssm/ssm-setup-cli

# Register with SSM using the activation credentials
sudo /tmp/ssm/ssm-setup-cli \
  -register \
  -activation-code "${ACTIVATION_CODE}" \
  -activation-id "${ACTIVATION_ID}" \
  -region "${REGION}"
```

### Step 2 — Extract and Print Managed Node ID

After registration, the managed node ID (`mi-*`) is stored in `/var/lib/amazon/ssm/registration`. Write a small Python helper to a temp file, then use it to extract the ID:

```bash
# Write the extraction script to a temp file (never use python3 -c inline)
cat > /tmp/get_node_id.py << 'PYEOF'
import json, sys
data = json.load(sys.stdin)
print(data["ManagedInstanceID"])
PYEOF

MANAGED_NODE_ID=$(sudo cat /var/lib/amazon/ssm/registration | python3 /tmp/get_node_id.py)
echo "=============================================="
echo "SSM Managed Node ID: $MANAGED_NODE_ID"
echo "=============================================="
echo ""
echo "Connect with:  aws ssm start-session --target $MANAGED_NODE_ID"
```

### Step 3 — Keep Alive

Convert `SessionMinutes` to seconds and loop, printing status every 60s (same pattern as the VNC/DCV jobs in this project):

```bash
TOTAL_SECONDS=$((SESSION_MINUTES * 60))
ELAPSED=0
INTERVAL=60
while [ $ELAPSED -lt $TOTAL_SECONDS ]; do
  sleep $INTERVAL
  ELAPSED=$((ELAPSED + INTERVAL))
  REMAINING=$(( (TOTAL_SECONDS - ELAPSED) / 60 ))
  echo "[$(date)] SSM node $MANAGED_NODE_ID active. ${REMAINING}m remaining."
done
```

### Step 4 — Cleanup / Deregister

On exit (or when the timer expires), deregister the managed node and stop the agent:

```bash
echo "Session ended. Deregistering managed node..."
sudo amazon-ssm-agent -register -clear 2>/dev/null || true
sudo systemctl stop amazon-ssm-agent 2>/dev/null || true
echo "Cleanup complete."
```

## Submission Workflow

The submitter is responsible for creating the activation before submitting the job:

```bash
# 1. Create the hybrid activation (requires an IAM role for SSM)
ACTIVATION=$(aws ssm create-activation \
  --iam-role "SSMServiceRole" \
  --registration-limit 1 \
  --default-instance-name "deadline-worker-ssm" \
  --region us-west-2)

CODE=$(echo "$ACTIVATION" | jq -r '.ActivationCode')
ID=$(echo "$ACTIVATION" | jq -r '.ActivationId')

# 2. Submit the Deadline job with the activation credentials
deadline bundle submit ssh_ssm_managed_node/job \
  --parameter "ActivationCode=$CODE" \
  --parameter "ActivationId=$ID" \
  --parameter "SessionMinutes=120"
```

## Prerequisites

- The Deadline Cloud worker must have sudo access (stated in requirements)
- An IAM role for SSM hybrid nodes must exist (e.g. `SSMServiceRole` with `AmazonSSMManagedInstanceCore` policy)
  - **IMPORTANT**: This role must be created before first use. It requires:
    1. A trust policy allowing `ssm.amazonaws.com` to assume the role
    2. The `AmazonSSMManagedInstanceCore` managed policy attached
  - The submit script defaults to `SSMServiceRole` — if this role doesn't exist, `create-activation` will fail with `Nonexistent role or missing ssm service principal in trust policy`
  - Create it once per account:
    ```bash
    aws iam create-role --role-name SSMServiceRole \
      --assume-role-policy-document '{"Version":"2012-10-17","Statement":[{"Effect":"Allow","Principal":{"Service":"ssm.amazonaws.com"},"Action":"sts:AssumeRole"}]}'
    aws iam attach-role-policy --role-name SSMServiceRole \
      --policy-arn arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore
    ```
- The worker must have outbound internet access to reach `amazon-ssm-{region}.s3.{region}.amazonaws.com`
- The submitter needs `ssm:CreateActivation` permissions
- The SSM advanced-instances tier must be enabled in the account/region to use `aws ssm start-session` with hybrid `mi-*` nodes. This is a one-time setting per region:
  ```bash
  aws ssm update-service-setting \
    --setting-id "arn:aws:ssm:<region>:<account-id>:servicesetting/ssm/managed-instance/activation-tier" \
    --setting-value "advanced" \
    --region <region>
  ```
  Note: advanced tier costs ~$0.00695/hr per on-premises managed instance. For short-lived sessions this is negligible.

## File Structure

```
ssh_ssm_managed_node/
├── design.md          ← this file
└── job/
    └── template.yaml  ← Deadline Cloud job template
```

## Security Notes

- Activation codes are single-use (registration-limit=1) and short-lived (24h default expiry)
- The activation code/ID are passed as job parameters — they are not persisted or stored on disk beyond the job session
- The managed node is deregistered when the job ends
- No credentials are hardcoded; the activation is generated at submission time
