#!/bin/env bash
# Starts ComfyUI with comfy launch, runs a model-free workflow with comfy run, and stops it.
set -euo pipefail
export COMFY_NO_TELEMETRY=1

WORK=$(mktemp -d)
BASE="$WORK/base"
OUT="$WORK/output"
# ComfyUI fails to start on a base directory without custom_nodes/.
mkdir -p "$BASE/custom_nodes" "$OUT"
PORT=$(python -c 'import socket; s = socket.socket(); s.bind(("127.0.0.1", 0)); print(s.getsockname()[1])')

stop_server() {
    comfy --skip-prompt stop --port "$PORT" || true
}
trap stop_server EXIT

echo "Starting ComfyUI with comfy-cli on port $PORT"
comfy --skip-prompt --workspace "$COMFYUI_LOCATION" launch --background -- \
    --cpu --listen 127.0.0.1 --port "$PORT" \
    --base-directory "$BASE" --output-directory "$OUT"

python - "$PORT" <<'EOF'
import sys, time, urllib.request
url = f"http://127.0.0.1:{sys.argv[1]}/system_stats"
for _ in range(300):
    try:
        urllib.request.urlopen(url, timeout=5)
        print("ComfyUI server is ready")
        break
    except Exception:
        time.sleep(1)
else:
    sys.exit("ComfyUI server didn't start within 300s")
EOF

echo "Running a workflow with comfy run"
comfy --skip-prompt run --workflow test_workflow_api.json --where local \
    --host 127.0.0.1 --port "$PORT" --wait
find "$OUT" -name 'comfy_cli_test*.png' | grep -q . || { echo "No output image in $OUT"; ls -lR "$OUT"; exit 1; }
echo "Output image written"

echo "Checking that comfy run fails for a broken workflow"
echo '{"1": {"class_type": "NodeThatDoesNotExist", "inputs": {} } }' > "$WORK/broken_api.json"
if comfy --skip-prompt run --workflow "$WORK/broken_api.json" --where local \
        --host 127.0.0.1 --port "$PORT" --wait; then
    echo "comfy run exited 0 for a broken workflow"
    exit 1
fi
echo "comfy run failed as expected"
