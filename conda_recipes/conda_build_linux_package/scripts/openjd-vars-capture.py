import json
import os
import sys

# Get the snapshot from `openjd-vars-start.py`, and the current environment state.
with open(sys.argv[1], "r", encoding="utf8") as f:
    before = json.load(f)
after = dict(os.environ)
# Exclude the env var "_" as it has special meaning to shells
if "_" in after:
    del after["_"]

# Identify the modified and deleted environment variables
vars_to_put = {k: v for k, v in after.items() if v != before.get(k)}
vars_to_delete = {k for k in before if k not in after}

# Print the env var changes following the Open Job Description specification
for k, v in vars_to_put.items():
    kv = json.dumps(f"{k}={v}", ensure_ascii=True)
    print(f"openjd_env: {kv}")
for k in vars_to_delete:
    print(f"openjd_unset_env: {k}")
