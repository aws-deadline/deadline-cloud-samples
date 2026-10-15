#!/bin/env bash
# Defaults --base-directory so that ComfyUI doesn't write into the shared conda env.
# Arguments passed to this command come last, so they override the defaults.
set -euo pipefail

PREFIX_DIR="$(cd "$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")/.." && pwd)"
export PYTHONUNBUFFERED=1

base_dir="${COMFYUI_BASE_DIRECTORY:-$PWD}"
args=(--base-directory "$base_dir")

# ComfyUI fails to start on a base directory without custom_nodes/. Create it in the
# base directory ComfyUI will use, which is the last --base-directory argument if any.
prev=""
for arg in "$@"; do
    case "$arg" in --base-directory=*) base_dir="${arg#*=}" ;; esac
    if [ "$prev" = "--base-directory" ]; then base_dir="$arg"; fi
    prev="$arg"
done
mkdir -p "$base_dir/custom_nodes"

if [ -n "${COMFYUI_USER_DIRECTORY:-}" ];   then args+=(--user-directory "$COMFYUI_USER_DIRECTORY"); fi
if [ -n "${COMFYUI_TEMP_DIRECTORY:-}" ];   then args+=(--temp-directory "$COMFYUI_TEMP_DIRECTORY"); fi
if [ -n "${COMFYUI_INPUT_DIRECTORY:-}" ];  then args+=(--input-directory "$COMFYUI_INPUT_DIRECTORY"); fi
if [ -n "${COMFYUI_OUTPUT_DIRECTORY:-}" ]; then args+=(--output-directory "$COMFYUI_OUTPUT_DIRECTORY"); fi

exec "$PREFIX_DIR/bin/python" "$PREFIX_DIR/opt/comfyui/main.py" "${args[@]}" "$@"
