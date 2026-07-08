#!/usr/bin/env python3
# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0
"""
Pre-submission hook: Inject license limit host requirements into job steps.

This hook reads the job bundle's template and adds hostRequirements amounts
for each configured license limit. This ensures Deadline Cloud's scheduler
enforces license concurrency limits without artists needing to manually
configure host requirements.

Configure limits in license_limits.json alongside this script.
"""

import json
import sys
from pathlib import Path

try:
    import yaml

    HAS_YAML = True
except ImportError:
    HAS_YAML = False


def load_limits_config():
    """Load license limits configuration from the file next to this script."""
    config_path = Path(__file__).parent / "license_limits.json"
    with open(config_path) as f:
        return json.load(f)["limits"]


def main():
    metadata = json.load(sys.stdin)
    bundle_dir = Path(metadata["jobBundleDir"])

    # Find the template
    template_path = bundle_dir / "template.yaml"
    is_yaml = True
    if not template_path.exists():
        template_path = bundle_dir / "template.json"
        is_yaml = False
    if not template_path.exists():
        print("No template found in bundle dir, skipping.", file=sys.stderr)
        sys.exit(0)

    # Load template
    with open(template_path) as f:
        if is_yaml:
            if not HAS_YAML:
                print(
                    "ERROR: PyYAML is required to process YAML templates. "
                    "Install with: pip install pyyaml",
                    file=sys.stderr,
                )
                sys.exit(1)
            template = yaml.safe_load(f)
        else:
            template = json.load(f)

    # Load limits config
    limits = load_limits_config()

    # Inject hostRequirements into each step
    modified = False
    for step in template.get("steps", []):
        host_req = step.setdefault("hostRequirements", {})
        amounts = host_req.setdefault("amounts", [])

        for limit_name, limit_config in limits.items():
            req_name = limit_config["amount_requirement_name"]
            already_set = any(a.get("name") == req_name for a in amounts)
            if not already_set:
                amounts.append({"name": req_name, "min": limit_config["min"]})
                modified = True

    if modified:
        with open(template_path, "w") as f:
            if is_yaml:
                yaml.dump(template, f, default_flow_style=False, sort_keys=False)
            else:
                json.dump(template, f, indent=2)
        injected = ", ".join(
            cfg["amount_requirement_name"] for cfg in limits.values()
        )
        print(f"Injected license limits ({injected}) into job steps.", file=sys.stderr)
    else:
        print("All license limits already present in job steps.", file=sys.stderr)

    sys.exit(0)


if __name__ == "__main__":
    main()
