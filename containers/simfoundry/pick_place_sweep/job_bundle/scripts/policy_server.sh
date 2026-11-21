#!/usr/bin/env bash
# Starts the OpenPI policy server in the session container, once per session, and waits until it
# has loaded the checkpoint and compiled its first inference.
# Usage: policy_server.sh <session-dir> <openpi-config> <checkpoint-dir> [port]
set -euo pipefail
session="$1"; config="$2"; checkpoint="$3"; port="${4:-8000}"
here="$(cd "$(dirname "$0")" && pwd)"
log="${session}/policy_server.log"

if curl -fsS "http://127.0.0.1:${port}/healthz" >/dev/null 2>&1; then
  echo "Policy server already up on port ${port}"
  exit 0
fi

# OpenPI downloads the checkpoint (about 12 GB) into OPENPI_DATA_HOME. JAX would otherwise take
# 75% of the GPU, and Isaac Sim and cuRobo share it.
export OPENPI_DATA_HOME="${session}/openpi-cache"
export XLA_PYTHON_CLIENT_MEM_FRACTION="${XLA_PYTHON_CLIENT_MEM_FRACTION:-0.45}"
mkdir -p "${OPENPI_DATA_HOME}"
cd /opt/openpi
echo "Starting OpenPI: ${config} from ${checkpoint} on port ${port}, log ${log}"
setsid nohup .venv/bin/python scripts/serve_policy.py --port "${port}" \
  policy:checkpoint --policy.config="${config}" --policy.dir="${checkpoint}" \
  > "${log}" 2>&1 < /dev/null &
pid=$!
echo "${pid}" > "${session}/policy_server.pid"

start=$(date +%s)
until curl -fsS "http://127.0.0.1:${port}/healthz" >/dev/null 2>&1; do
  if ! kill -0 "${pid}" 2>/dev/null; then
    echo "Policy server exited before it was ready:" >&2
    tail -n 60 "${log}" >&2
    exit 1
  fi
  if (( $(date +%s) - start > 2400 )); then
    echo "Policy server not ready after 40 minutes:" >&2
    tail -n 60 "${log}" >&2
    exit 1
  fi
  sleep 10
done
echo "Policy server up after $(( $(date +%s) - start )) s"

# The first inference compiles the model and blocks the server's event loop meanwhile, which
# can time out a client's keepalive pings. Compile it here, on a connection without pings.
.venv/bin/python "${here}/warmup_policy.py" "${port}"
echo "Policy server warm after $(( $(date +%s) - start )) s"
