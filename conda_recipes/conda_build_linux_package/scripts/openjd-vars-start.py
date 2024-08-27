"""
Saves a JSON snapshot of the environment variables to the filename
provided as the first parameter.
"""

import json
import os
import sys

# Exclude the env var "_" as it has special meaning to shells
before = dict(os.environ)
if "_" in before:
    del before["_"]

with open(sys.argv[1], "w", encoding="utf8") as f:
    json.dump(before, f)
