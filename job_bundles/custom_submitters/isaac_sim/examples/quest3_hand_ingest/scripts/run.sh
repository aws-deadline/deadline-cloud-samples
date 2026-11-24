#!/usr/bin/env bash
# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
#
# run.sh SESSION_DIR SCRIPT [ARGS...]: run one of this bundle's scripts with a Python that has
# numpy, pyarrow and pandas.
#
# 1. A Python on PATH that already has all three is used as is.
# 2. A Python that has numpy but not the other two, such as the one the isaaclab or isaacsim
#    conda package provides (CondaPackages), gets a venv layered on it with
#    --system-site-packages: pip installs only pyarrow and pandas there, so numpy and everything
#    else stay the conda environment's.
# 3. Otherwise python3 gets a plain venv with requirements.txt.
#
# The venv is built in SESSION_DIR by the session's first task and reused by later ones. Cases 2
# and 3 need network access to PyPI.
set -euo pipefail
session_dir="$1"; script="$2"; shift 2
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
all='import numpy, pyarrow, pandas'
venv="$session_dir/quest3-venv"

has() { "$1" -c "$2" >/dev/null 2>&1; }

python=""
base=""
for candidate in python python3; do
  command -v "$candidate" >/dev/null 2>&1 || continue
  if has "$candidate" "$all"; then python="$candidate"; break; fi
  if [ -z "$base" ] && has "$candidate" 'import numpy'; then base="$candidate"; fi
done
if [ -z "$python" ]; then
  if [ -x "$venv/bin/python" ] && has "$venv/bin/python" "$all"; then
    python="$venv/bin/python"
  elif [ -n "$base" ]; then
    echo "Adding pyarrow and pandas to $(command -v "$base") in $venv"
    "$base" -m venv --system-site-packages "$venv"
    "$venv/bin/python" -m pip install --quiet pyarrow pandas
    python="$venv/bin/python"
  else
    echo "No Python with numpy on PATH: building $venv from requirements.txt"
    python3 -m venv "$venv"
    "$venv/bin/python" -m pip install --quiet --requirement "$here/requirements.txt"
    python="$venv/bin/python"
  fi
fi
echo "Python: $(command -v "$python") ($("$python" --version 2>&1), numpy $("$python" -c 'import numpy; print(numpy.__version__)'))"
exec "$python" -I "$here/$script" "$@"
