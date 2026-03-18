#!/bin/bash
# Submit script for SSM Managed Node job
# Creates an SSM hybrid activation and submits the Deadline Cloud job with the credentials.
#
# Prerequisites:
#   - AWS CLI configured with ssm:CreateActivation permission
#   - An IAM role for SSM hybrid nodes (e.g. SSMServiceRole with AmazonSSMManagedInstanceCore)
#   - Deadline Cloud CLI installed
#
# Usage:
#   ./submit.sh <farm_id> <queue_id> [session_minutes] [iam_role_name] [region] [--show]
#
# Examples:
#   ./submit.sh farm-XXX queue-XXX                          # 60 min, SSMServiceRole, us-west-2
#   ./submit.sh farm-XXX queue-XXX 120                      # 120 min
#   ./submit.sh farm-XXX queue-XXX 60 MySSMRole             # custom IAM role
#   ./submit.sh farm-XXX queue-XXX 60 MySSMRole us-east-1
#   ./submit.sh farm-XXX queue-XXX 60 SSMServiceRole us-west-2 --show

set -e

# Parse --show flag from any position
SHOW_SECRET=false
ARGS=()
for arg in "$@"; do
  if [ "$arg" = "--show" ]; then
    SHOW_SECRET=true
  else
    ARGS+=("$arg")
  fi
done

FARM_ID="${ARGS[0]}"
QUEUE_ID="${ARGS[1]}"

if [ -z "$FARM_ID" ] || [ -z "$QUEUE_ID" ]; then
  echo "ERROR: farm_id and queue_id are required"
  echo "Usage: ./submit.sh <farm_id> <queue_id> [session_minutes] [iam_role_name] [region] [--show]"
  exit 1
fi

SESSION_MINUTES="${ARGS[2]:-60}"
IAM_ROLE="${ARGS[3]:-SSMServiceRole}"
REGION="${ARGS[4]:-us-west-2}"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "=============================================="
echo "SSM Managed Node — Job Submission"
echo "=============================================="
echo "Session:  ${SESSION_MINUTES} minutes"
echo "IAM Role: ${IAM_ROLE}"
echo "Region:   ${REGION}"
echo "Farm:     ${FARM_ID}"
echo "Queue:    ${QUEUE_ID}"
echo ""

# --- Create SSM hybrid activation ---
echo "Creating SSM hybrid activation..."
ACTIVATION=$(aws ssm create-activation \
  --iam-role "${IAM_ROLE}" \
  --registration-limit 1 \
  --default-instance-name "deadline-worker-ssm" \
  --region "${REGION}" \
  --output json)

# Write a temp script to parse the activation JSON (avoid inline python3 -c)
cat > /tmp/parse_activation.py << 'PYEOF'
import json, sys
data = json.load(sys.stdin)
print(data["ActivationCode"])
print(data["ActivationId"])
PYEOF

ACTIVATION_CODE=$(echo "$ACTIVATION" | python3 /tmp/parse_activation.py | sed -n '1p')
ACTIVATION_ID=$(echo "$ACTIVATION" | python3 /tmp/parse_activation.py | sed -n '2p')
rm -f /tmp/parse_activation.py

if [ -z "$ACTIVATION_CODE" ] || [ -z "$ACTIVATION_ID" ]; then
  echo "ERROR: Failed to create SSM activation"
  echo "Response: $ACTIVATION"
  exit 1
fi

echo "Activation created:"
if [ "$SHOW_SECRET" = true ]; then
  echo "  Code: ${ACTIVATION_CODE}"
else
  echo "  Code: ${ACTIVATION_CODE:0:4}****"
fi
echo "  ID:   ${ACTIVATION_ID}"
echo ""

# --- Submit the Deadline Cloud job ---
echo "Submitting Deadline Cloud job..."
deadline bundle submit "${SCRIPT_DIR}/job" \
  --farm-id "${FARM_ID}" \
  --queue-id "${QUEUE_ID}" \
  --parameter "ActivationCode=${ACTIVATION_CODE}" \
  --parameter "ActivationId=${ACTIVATION_ID}" \
  --parameter "AWS_REGION=${REGION}" \
  --parameter "SessionMinutes=${SESSION_MINUTES}"

echo ""
echo "Job submitted. Check the Deadline Cloud console for the managed node ID in the job log."
echo "=============================================="
