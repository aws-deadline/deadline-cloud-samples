#!/usr/bin/env bash
# Verify the tools every step needs are on PATH before any of them runs.
# Runs as the job environment's onEnter action.
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/common.sh"

REQUIRED_TOOLS_CSV=""
CONDA_PACKAGES=""
CONDA_CHANNELS=""
for arg in "$@"; do
  case "$arg" in
    --required-tools=*) REQUIRED_TOOLS_CSV="${arg#*=}" ;;
    --conda-packages=*) CONDA_PACKAGES="${arg#*=}" ;;
    --conda-channels=*) CONDA_CHANNELS="${arg#*=}" ;;
    *) unknown_arg "$arg" ;;
  esac
done
require_arg "$REQUIRED_TOOLS_CSV" --required-tools

# Checking here means a queue environment missing a tool fails once, up front,
# with the packages and channels to fix it, rather than partway into a step.
parse_list REQUIRED_TOOLS "$REQUIRED_TOOLS_CSV"
echo "Verifying toolchain: ${REQUIRED_TOOLS[*]}"
missing=0
for tool in "${REQUIRED_TOOLS[@]}"; do
  if ! command -v "$tool" >/dev/null 2>&1; then
    echo "ERROR: required tool '$tool' is not on PATH." >&2
    missing=1
  fi
done
if [[ "$missing" -ne 0 ]]; then
  echo "" >&2
  echo "Attach a conda queue environment that provides:" >&2
  echo "  packages: $CONDA_PACKAGES" >&2
  echo "  channels: $CONDA_CHANNELS" >&2
  exit 1
fi

# Log the htslib tool versions, since those are the ones whose behavior differs
# enough between releases to matter when reproducing a callset. Not every tool in
# the list, because they do not agree on a version flag.
#
# Read the first line without a pipe: 'set -o pipefail' plus 'head' closing the
# pipe early makes "tool | head" exit 141 (SIGPIPE) even though the tool
# succeeded.
for tool in samtools bcftools; do
  read -r line < <("$tool" --version) && echo "$line"
done
echo "Toolchain ready."
