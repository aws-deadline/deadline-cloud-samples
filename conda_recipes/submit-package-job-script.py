#!/usr/bin/env python
"""
Submits a Conda package build job to the configured AWS Deadline Cloud queue.

Installation Requirements:
* Python 3.9+
* The `deadline` library installed into Python.
"""
import argparse
import fnmatch
import json
import os
import re
import shutil
import sys
from copy import deepcopy
from pathlib import Path
from urllib.parse import urlparse

import yaml
from deadline.client.api import create_job_from_job_bundle, get_boto3_client, list_queues
from deadline.client.config import get_setting, set_setting
from deadline.client.config.config_file import read_config
from deadline.client.job_bundle import create_job_history_bundle_dir


def validate_recipe(recipe_dir):
    """Validate the conda build recipe directory with some basic sanity checks."""
    if not os.path.isdir(recipe_dir):
        raise RuntimeError(f"The recipe directory does not exist: {recipe_dir}.")

    meta_yaml_file = recipe_dir / "recipe" / "meta.yaml"
    recipe_yaml_file = recipe_dir / "recipe" / "recipe.yaml"
    if not meta_yaml_file.is_file() and not recipe_yaml_file.is_file():
        raise RuntimeError(f"No meta.yaml or recipe.yaml exists in {recipe_dir}.")

    submit_yaml_file = recipe_dir / "deadline-cloud.yaml"
    if not submit_yaml_file.is_file():
        raise RuntimeError(f"The submit metadata file does not exist: {submit_yaml_file}.")


def determine_s3_channel(s3_channel_url, config):
    """
    Get the S3 channel as a (bucket, prefix) tuple. The input s3_channel_url can either
    be the full channel URL, just a channel name, or empty. The default queue's job attachments
    bucket is used when not provided.
    """
    if s3_channel_url and s3_channel_url.startswith("s3://"):
        # Split the S3 copy source into bucket and prefix
        url = urlparse(s3_channel_url, allow_fragments=False)
        s3_channel_bucket = url.netloc
        s3_channel_prefix = url.path.strip("/")
        print("The full S3 channel URL was provided")
    else:
        deadline_client = get_boto3_client("deadline", config=config)
        queue_id = get_setting("defaults.queue_id", config=config)
        farm_id = get_setting("defaults.farm_id", config=config)
        queue = deadline_client.get_queue(
            farmId=farm_id,
            queueId=queue_id,
        )
        s3_channel_bucket = queue["jobAttachmentSettings"]["s3BucketName"]
        if s3_channel_url:
            print("A channel name provided, attaching it to the queue's job attachments bucket")
            s3_channel_prefix = f"Conda/{s3_channel_url.strip('/')}"
        else:
            print("No channel URL was provided, using a default prefix on the queue's job attachments bucket")
            s3_channel_prefix = "Conda/Default"
    return (s3_channel_bucket, s3_channel_prefix)


param_ref_regex = re.compile(r"\{\{\s*Param.([A-Za-z_][A-Za-z0-9_]*)\s*\}\}")


def find_referenced_parameters(obj):
    """Find all the job parameters that are referenced in the provided object."""
    result = set()
    if isinstance(obj, str):
        result.update(param_ref_regex.findall(obj))
    elif isinstance(obj, list):
        for item in obj:
            result.update(find_referenced_parameters(item))
    elif isinstance(obj, dict):
        for item in obj.values():
            result.update(find_referenced_parameters(item))
    return result


def update_host_requirements(obj, input):
    """Like dict.update, but recursively updates inside of each dict, and concatenates lists instead of replacing."""
    for key, value in input.items():
        if key in obj:
            if isinstance(value, dict) and isinstance(obj[key], dict):
                update_host_requirements(obj[key], value)
            elif isinstance(value, list) and isinstance(obj[key], list):
                obj[key].extend(value)
            else:
                obj[key] = value
        else:
            obj[key] = value


def apply_regex_substitutions_to_object(obj, regex_substitutions):
    """
    Creates a copy of the provided object, with the provided regex substitutions applied to each string.
    The provided regex_substitutions are a list of (pattern, replacement_string) tuples.
    """
    if isinstance(obj, str):
        for pattern, repl in regex_substitutions:
            obj = re.sub(pattern, repl, obj)
        return obj
    elif isinstance(obj, list):
        return [apply_regex_substitutions_to_object(item, regex_substitutions) for item in obj]
    elif isinstance(obj, dict):
        return {key: apply_regex_substitutions_to_object(value, regex_substitutions) for key, value in obj.items()}
    else:
        return obj


def extract_job_entity(job_template, entity_type, entity_name):
    """Extract a job environment or a step from the provided job template."""
    entities = job_template.get(entity_type + "s", [])
    for entity in entities:
        if entity["name"] == entity_name:
            # Filter the job's parameters to just the ones referenced by the environment
            parameter_names = find_referenced_parameters(entity)
            parameter_defs = [param for param in job_template["parameterDefinitions"] if param["name"] in parameter_names]
            result = {
                "parameterDefinitions": deepcopy(parameter_defs),
                "entity": deepcopy(entity),
            }

            # Get the entity's metadata, which is YAML in the description starting from a line
            # containing only the content "meta:"
            description_lines = entity.get("description", "").splitlines()
            meta_index = None
            try:
                meta_index = description_lines.index("meta:")
            except ValueError:
                pass
            if meta_index is not None:
                meta = yaml.safe_load("\n".join(description_lines[meta_index:]))
                result["meta"] = meta["meta"]

            return result

    raise RuntimeError(f"Job template does not have an entity named {entity_name!r} to extract from the {entity_type} list")


def get_recipe_conda_platforms(*, conda_platforms_meta, conda_platform_patterns):
    if not conda_platforms_meta:
        raise RuntimeError("The recipe's deadline-cloud.yaml doesn't have a condaPlatforms item")
    all_platform_names = set()
    for conda_platform in conda_platforms_meta:
        if "variant" in conda_platform:
            conda_platform["name"] = f"{conda_platform['platform']}-{conda_platform['variant']}"
        else:
            conda_platform["name"] = conda_platform["platform"]

        # Add the name into the list of all names, checking for errors in the input yaml.
        if conda_platform["name"] in all_platform_names:
            raise RuntimeError(f"The recipe's deadline-cloud.yaml has platform/variant {conda_platform['name']} listed multiple times")
        all_platform_names.add(conda_platform["name"])

    # Get the conda platforms to submit. If provided at the CLI, they must select from the ones specified
    # in deadline-cloud.yaml, otherwise it's all the default ones from there.
    if conda_platform_patterns:
        requested_conda_platform_names = set()
        for pattern in conda_platform_patterns:
            matched_names = [name for name in all_platform_names if fnmatch.fnmatchcase(name, pattern)]
            # Validate that each pattern matched at least one name
            if len(matched_names) == 0:
                raise RuntimeError(
                    f"The requested conda platform[-variant] glob pattern {pattern!r} did not match any of {sorted(all_platform_names)}"
                )
            requested_conda_platform_names.update(matched_names)
        # Filter to the names that matched
        conda_platforms_meta = [p for p in conda_platforms_meta if p["name"] in requested_conda_platform_names]
    else:
        # Filter to the conda platforms with field "defaultSubmit" set to True
        conda_platforms_meta = [p for p in conda_platforms_meta if p.get("defaultSubmit")]

    return conda_platforms_meta


def set_queue_in_config(queue_name_prefix, config):
    queues = list_queues(farmId=get_setting("defaults.farm_id", config))["queues"]
    # Get the shortest-named queue that has the requested name as a prefix
    candidate_queues = [queue for queue in queues if queue["displayName"].startswith(queue_name_prefix)]
    candidate_queues.sort(key=lambda queue: len(queue["displayName"]), reverse=True)
    if candidate_queues:
        set_setting("defaults.queue_id", candidate_queues[0]["queueId"], config)
    else:
        print(f"No queue matched the prefix {queue_name_prefix!r}")
        print(f"Available queues: {', '.join(repr(queue['displayName']) for queue in queues)}")
        sys.exit(1)


def create_job_bundle(
    *,
    default_build_tool,
    job_bundle_dir,
    recipe_dir,
    archive_file_dir,
    job_parameters_meta,
    job_name,
    s3_channel_bucket,
    s3_channel_prefix,
    conda_platforms,
):
    # Read the conda_build_linux_package template, and then decompose it into pieces
    build_linux_package_bundle_dir = Path(__file__).parent / "conda_build_linux_package"
    build_linux_package_template = yaml.safe_load((build_linux_package_bundle_dir / "template.yaml").read_text())
    parameter_values = {
        item["name"]: item["value"]
        for item in yaml.safe_load((build_linux_package_bundle_dir / "parameter_values.yaml").read_text())["parameterValues"]
    }
    package_build_env = extract_job_entity(build_linux_package_template, "jobEnvironment", "Package Build Env")
    build_package_template = extract_job_entity(build_linux_package_template, "step", "PackageBuild")
    reindex_channel_template = extract_job_entity(build_linux_package_template, "step", "ReindexCondaChannel")

    conda_platform_host_requirements = yaml.safe_load((Path(__file__).parent / "conda_platform_host_requirements.yaml").read_text())

    # Copy the scripts from the build_linux_package job bundle
    shutil.copytree(
        build_linux_package_bundle_dir / "scripts",
        job_bundle_dir / "scripts",
        dirs_exist_ok=True,
    )

    collected_parameters = {}
    build_package_steps = []

    # Populate job-level parameter values
    parameter_values["RecipeDir"] = str(recipe_dir / "recipe")
    parameter_values["S3CondaChannel"] = f"s3://{s3_channel_bucket}/{s3_channel_prefix}"
    if job_parameters_meta:
        for param in job_parameters_meta:
            print(f"Applying job parameter {param['name']}={param['value']}")
            parameter_values[param["name"]] = param["value"]

    # For each platform, create an OpenJobDescription step to build the package as it
    for platform_meta in conda_platforms:
        platform = platform_meta["platform"]
        platform_template = deepcopy(build_package_template)
        step_name_suffix = "".join(s.capitalize() for s in platform.split("-")) + "".join(
            s.capitalize() for s in platform_meta.get("variant", "").split("-")
        )
        build_tool = platform_meta.get("buildTool", default_build_tool)

        if build_tool not in ["conda-build", "rattler-build"]:
            raise RuntimeError(f"Recipe provided an unsupported build tool {build_tool}")

        parameter_values[f"CondaPlatform_{step_name_suffix}"] = platform
        parameter_values[f"BuildTool_{step_name_suffix}"] = build_tool

        # The platform_meta.yaml file can specify the local filename for the source archive.
        # If it's specified, provide it as one or more parameter values.
        source_archive_filename = platform_meta.get("sourceArchiveFilename")
        if source_archive_filename:
            missing_source_archives = []
            if isinstance(source_archive_filename, str):
                if not (archive_file_dir / source_archive_filename).is_file():
                    missing_source_archives.append(source_archive_filename)
                parameter_values[f"OverrideSourceArchive1_{step_name_suffix}"] = str(archive_file_dir / source_archive_filename)
            elif isinstance(source_archive_filename, list):
                if not 1 <= len(source_archive_filename) <= 2:
                    raise RuntimeError(
                        f"The deadline-cloud.yaml property sourceArchiveFilename is a list of length {len(source_archive_filename)}, it must be between 1 and 2."
                    )
                for i, filename in enumerate(source_archive_filename, start=1):
                    if not (archive_file_dir / filename).is_file():
                        missing_source_archives.append(filename)
                    parameter_values[f"OverrideSourceArchive{i}_{step_name_suffix}"] = str(archive_file_dir / filename)
            else:
                raise RuntimeError("The deadline-cloud.yaml property sourceArchiveFilename must be a string or a list.")

            if missing_source_archives:
                print(f"ERROR: File(s) {', '.join(missing_source_archives)} not found in {archive_file_dir}.")
                print(f"To submit the {recipe_dir.name} package build, you need these files.")
                print(f"To acquire this archive, follow these instructions and place it in the {archive_file_dir} directory:")
                print(f"    {platform_meta['sourceDownloadInstructions']}")
                sys.exit(1)

        # Rename the platform-specific parameter values
        per_step_parameters = set(platform_template["meta"]["perStepParameters"])

        # Process the parameters, using an annotation to share them or make them unique (based on platform)
        params = platform_template["parameterDefinitions"]
        renames = []
        for param in params:
            original_param_name = param["name"]
            if original_param_name in per_step_parameters:
                param["name"] = f"{original_param_name}_{step_name_suffix}"
                param["userInterface"]["groupLabel"] += f": {step_name_suffix}"
                renames.append(
                    (
                        re.compile(r"\{\{\s*" + re.escape(f"Param.{original_param_name}") + r"\s*\}\}"),
                        "{{Param." + param["name"] + "}}",
                    )
                )
            collected_parameters[param["name"]] = param

        step = platform_template["entity"]
        step["name"] += step_name_suffix

        # Get the conda platform-specific host requirements
        step.update(deepcopy(conda_platform_host_requirements[platform]))
        # If the platform-specific metadata has additional host requirements, add them too
        update_host_requirements(
            step["hostRequirements"],
            platform_meta.get("additionalHostRequirements", {}),
        )

        # If provided, write the conda_build_config.yaml file
        if "condaBuildConfig" in platform_meta or "variantConfig" in platform_meta:
            variant_config_path = job_bundle_dir / "data" / f"variant_config_{step_name_suffix}.yaml"
            variant_config_path.parent.mkdir(exist_ok=True)
            variant_config_path.write_text(
                json.dumps(
                    platform_meta.get("condaBuildConfig", platform_meta.get("variantConfig")),
                    indent=1,
                    sort_keys=False,
                )
            )
            parameter_values[f"VariantConfigFile_{step_name_suffix}"] = str(variant_config_path)

        build_package_steps.append(apply_regex_substitutions_to_object(step, renames))

    print(f"Creating steps for conda platforms: {', '.join(sorted(p['name'] for p in conda_platforms))}")

    # Process the channel reindex step
    reindex_step = reindex_channel_template["entity"]
    reindex_step["dependencies"] = [{"dependsOn": step["name"]} for step in build_package_steps]
    for param in reindex_channel_template["parameterDefinitions"]:
        collected_parameters[param["name"]] = param
    for param in package_build_env["parameterDefinitions"]:
        collected_parameters[param["name"]] = param

    job_description = f"""
    This job uses conda-build to build a Conda package for
    the package {recipe_dir.name}, uploading the result to
    the S3 Conda channel s3::{s3_channel_bucket}/{s3_channel_prefix}.
    It then reindexes the channel.
    """

    # Assemble the job template
    job_template = {
        "specificationVersion": "jobtemplate-2023-09",
        "name": job_name,
        "description": job_description,
        "parameterDefinitions": list(collected_parameters.values()),
        "jobEnvironments": [
            package_build_env["entity"],
        ],
        "steps": [*build_package_steps, reindex_step],
    }

    (job_bundle_dir / "template.yaml").write_text(json.dumps(job_template, indent=1, sort_keys=False))
    (job_bundle_dir / "parameter_values.yaml").write_text(
        json.dumps(
            {"parameterValues": [{"name": name, "value": value} for name, value in parameter_values.items()]},
            indent=1,
            sort_keys=False,
        )
    )


def progress_callback(op_name):
    previous_progress = None

    def callback(progress_metadata):
        nonlocal previous_progress
        if progress_metadata.progress != previous_progress and previous_progress != 100:
            end = "\r"
            if progress_metadata.progress == 100:
                end = "\n"
            print(f"{op_name}: {progress_metadata.progress:.1f}%      ", end=end)
            previous_progress = progress_metadata.progress
        return True

    return callback


def main():
    parser = argparse.ArgumentParser(prog="submit-package-job")
    parser.add_argument("recipe_dir", type=Path, help="The package build recipe to build on Deadline Cloud.")
    parser.add_argument("-q", "--queue", default="Package", help="A prefix of the queue name to submit to.")
    parser.add_argument("--s3-channel", help="The S3 conda channel to build the package to, in s3://S3_BUCKET/prefix_path format.")
    parser.add_argument(
        "-p",
        "--conda-platform",
        action="append",
        help="The conda platform, as specified by the recipe's deadline-cloud.yaml. Can be wildcard * like filename globs.",
    )
    parser.add_argument(
        "--all-platforms", action="store_true", help="Submit all the platforms specified by the recipe's deadline-cloud.yaml."
    )
    args = parser.parse_args()

    if args.conda_platform and args.all_platforms:
        parser.error("-p/--conda-platform cannot be used together with --all-platforms")

    recipe_dir = args.recipe_dir.absolute()
    validate_recipe(recipe_dir)

    config = read_config()
    set_queue_in_config(args.queue, config)

    s3_channel_bucket, s3_channel_prefix = determine_s3_channel(args.s3_channel, config)
    print(f"Building packages into channel s3://{s3_channel_bucket}/{s3_channel_prefix}")

    # Read the recipe's submit metadata
    submit_meta = yaml.safe_load((recipe_dir / "deadline-cloud.yaml").read_text())
    conda_platforms = get_recipe_conda_platforms(
        conda_platforms_meta=submit_meta.get("condaPlatforms"),
        conda_platform_patterns=["**"] if args.all_platforms else args.conda_platform,
    )

    job_name = f"CondaBuild: {recipe_dir.name} ({', '.join(conda_platform['name'] for conda_platform in conda_platforms)})"
    # TODO: The job name is shortened to 10 characters for this directory until the job attachments
    #       implementation on Windows improves support for long filename paths. Restore it to just `job_name`
    #       when that is fixed.
    job_bundle_dir = Path(create_job_history_bundle_dir("CondaBuild", job_name[:10]))

    default_build_tool = submit_meta.get("buildTool", "conda-build")

    if default_build_tool not in ["conda-build", "rattler-build"]:
        raise RuntimeError(f"Recipe provided an unsupported build tool {default_build_tool}")

    create_job_bundle(
        default_build_tool=default_build_tool,
        job_bundle_dir=job_bundle_dir,
        recipe_dir=recipe_dir,
        archive_file_dir=Path(__file__).parent / "archive_files",
        job_parameters_meta=submit_meta.get("jobParameters"),
        job_name=job_name,
        s3_channel_bucket=s3_channel_bucket,
        s3_channel_prefix=s3_channel_prefix,
        conda_platforms=conda_platforms,
    )
    print(f"Wrote job bundle:\n  '{job_bundle_dir}'")

    create_job_from_job_bundle(
        job_bundle_dir,
        print_function_callback=print,
        hashing_progress_callback=progress_callback("Hashing"),
        upload_progress_callback=progress_callback("Uploading"),
        config=config,
    )


if __name__ == "__main__":
    try:
        main()
    except RuntimeError as e:
        print(f"{type(e).__name__}: {e}")
        sys.exit(1)
