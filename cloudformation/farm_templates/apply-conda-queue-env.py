#!/usr/bin/env python
"""
python apply-conda-queue-env.py CFN_YAML_TEMPLATE_FILE CONDA_QUEUE_ENVIRONMENT_FILE CONDA_CHANNELS_DEFAULT

Modifies a farm YAML CloudFormation template to insert a provided conda queue environment.
It modifies the default CondaChannels parameter default to prepend a provided S3 conda channel URL.

For example, here's the command that was used for the starter_farm template:

python apply-conda-queue-env.py starter_farm/deadline-cloud-starter-farm-template.yaml \
       ../../queue_environments/conda_queue_env_improved_caching.yaml \
       's3://${JobAttachmentsBucketName}/Conda/Default ${ProdCondaChannels}'

Requirements:
  1. The CloudFormation template must have delimiters around the queue environment content to substitute,
     indented as desired. The delimiters are "### START_QUEUE_ENV" and "### END_QUEUE_ENV".
  2. The conda queue environment template must have 'default: "deadline-cloud"' as the text that defines
     the default value for its CondaChannels directory.
"""
import argparse
import json
from pathlib import Path
import sys

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("cfn_yaml_template_file", type=Path, help="The YAML CloudFormation template to modify.")
    parser.add_argument("conda_queue_environment_file", type=Path, help="The YAML conda queue environment to insert.")
    parser.add_argument("conda_channels_default", help="Content to replace as the CondaChannels parameter default.")
    args = parser.parse_args()

    # Load the conda queue environment, and substitute the CondaChannels parameter default
    queue_env = args.conda_queue_environment_file.read_text(encoding="utf-8")
    conda_channels_default = 'default: "deadline-cloud"'
    if conda_channels_default not in queue_env:
        print(f"The provided conda queue environment does not contain {conda_channels_default!r}.")
        sys.exit(1)
    queue_env = queue_env.replace(conda_channels_default, f"default: {json.dumps(args.conda_channels_default)}").splitlines()

    # Load the CFN template, and substitute the conda queue environment
    cfn_template = args.cfn_yaml_template_file.read_text(encoding="utf-8")
    start_delim = "### START_QUEUE_ENV"
    end_delim = "### END_QUEUE_ENV"
    if cfn_template.count(start_delim) != 1 or cfn_template.count(end_delim) != 1:
        print(f"The provided CloudFormation contains {cfn_template.count(start_delim)} copies of {start_delim!r} and {cfn_template.count(end_delim)} copies of {end_delim!r}. It must contain one of each.")
        sys.exit(1)
    cfn_template = cfn_template.splitlines()

    result_cfn_template = []
    skipping_content = False
    for line in cfn_template:
        if skipping_content:
            if end_delim in line:
                skipping_content = False
            else:
                continue

        result_cfn_template.append(line)
        if start_delim in line:
            prefix = line.split(start_delim, 1)[0]
            result_cfn_template.extend(prefix + qe_line for qe_line in queue_env)
            skipping_content = True
    result_cfn_template.append("")

    # Write the resulting CFN template
    args.cfn_yaml_template_file.write_text("\n".join(result_cfn_template), encoding="utf-8")
    print("The provided queue environment has been written into the CloudFormation template. \nPlease check your template and deploy it.")
if __name__ == "__main__":
    main()
