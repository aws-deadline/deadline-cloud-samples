#!/usr/bin/env bash
# Run a command with pip pointed at PyPI as it was at a cutoff time.
# Usage: with-pypi-cutoff <cutoff, e.g. 2026-08-27T02:13:06Z> <command> [args ...]
set -euo pipefail
cutoff="$1"; shift
port=8765
/opt/conda/bin/python "$(dirname "$(readlink -f "$0")")/pypi_cutoff_proxy.py" "${cutoff}" "${port}" &
proxy=$!
trap 'kill "${proxy}" 2>/dev/null || true' EXIT
for _ in $(seq 1 50); do
  curl -fsS -o /dev/null "http://127.0.0.1:${port}/simple/pip/" && break
  sleep 0.2
done
PIP_INDEX_URL="http://127.0.0.1:${port}/simple/" "$@"
