#!/usr/bin/env python3
"""preSubmission hook: set the Flow job parameters from the environment.

Studios usually already have environment or project-tracking tooling that sets
environment variables when an artist opens a shell or launches an application
(via Rez, a launcher, a "set project" script, and so on). This hook reads those
variables and writes them into the job template's Flow parameter defaults, so
the submitting artist does not re-enter the project id, asset name, secret ARN,
etc. by hand.

How it works: the Deadline Cloud client runs this as a preSubmission hook
(configured in hooks.yaml). It passes the submission metadata as JSON on stdin,
including ``jobBundleDir``. The hook loads the job template from that bundle,
overwrites the ``default`` of each Flow parameter from the matching environment
variable, and prints the modified template on stdout under the ``template`` key.
The client uses that template for the CreateJob call. Because the Flow
parameters are HIDDEN with no value supplied at submission, this hook is the
single source of their values.

If a required environment variable is missing the hook prints an explanation to
stderr and exits non-zero, which aborts the submission.

Environment variables:

    Required (unless FLOW_PUBLISH=FALSE):
        FLOW_PROJECT_ID        -> FlowProjectId
        FLOW_ASSET_NAME        -> FlowAssetName
        FLOW_SECRET_ARN        -> FlowSecretArn

    Optional (fall back to the template placeholder default):
        FLOW_ASSET_TYPE        -> FlowAssetType
        FLOW_STEP_SHORT_NAME   -> FlowStepShortName
        FLOW_TASK_NAME         -> FlowTaskName
        FLOW_TASK_STATUS       -> FlowTaskStatus
        FLOW_PUBLISH           -> EnableFlowPublish ("TRUE"/"FALSE")
"""
import json
import os
import sys

import yaml

# Maps an environment variable name to (job parameter name, required?).
ENV_TO_PARAMETER = {
    "FLOW_PROJECT_ID": ("FlowProjectId", True),
    "FLOW_ASSET_NAME": ("FlowAssetName", True),
    "FLOW_SECRET_ARN": ("FlowSecretArn", True),
    "FLOW_ASSET_TYPE": ("FlowAssetType", False),
    "FLOW_STEP_SHORT_NAME": ("FlowStepShortName", False),
    "FLOW_TASK_NAME": ("FlowTaskName", False),
    "FLOW_TASK_STATUS": ("FlowTaskStatus", False),
    "FLOW_PUBLISH": ("EnableFlowPublish", False),
}

# Parameters the template defines as INT; coerce these to numbers.
INT_PARAMETERS = {"FlowProjectId"}


def fail(message):
    print(f"flow_params_from_env: {message}", file=sys.stderr)
    sys.exit(1)


def main():
    metadata = json.load(sys.stdin)
    bundle_dir = metadata["jobBundleDir"]

    template_path = os.path.join(bundle_dir, "template.yaml")
    with open(template_path, "r", encoding="utf-8") as f:
        template = yaml.safe_load(f)

    definitions = {p["name"]: p for p in template.get("parameterDefinitions", [])}

    # Is publishing turned off for this submission? Then the Flow values are not required.
    publish = os.environ.get("FLOW_PUBLISH", "TRUE").upper() != "FALSE"

    missing = []
    for env_name, (param_name, required) in ENV_TO_PARAMETER.items():
        value = os.environ.get(env_name)
        if value is None or value == "":
            if required and publish:
                missing.append(env_name)
            continue

        if param_name not in definitions:
            continue  # Template doesn't define this parameter; skip.

        if param_name in INT_PARAMETERS:
            try:
                value = int(value)
            except ValueError:
                fail(f"{env_name}={value!r} is not a valid integer for {param_name}.")

        definitions[param_name]["default"] = value

    if missing:
        fail(
            "missing required Flow environment variable(s): "
            + ", ".join(sorted(missing))
            + ".\nSet them (your studio's project setup normally does this), or set "
            "FLOW_PUBLISH=FALSE to submit without publishing to Flow."
        )

    # Emit the modified template. Match the on-disk format so the client parses it cleanly.
    print(json.dumps({"template": yaml.safe_dump(template, sort_keys=False)}))


if __name__ == "__main__":
    main()
