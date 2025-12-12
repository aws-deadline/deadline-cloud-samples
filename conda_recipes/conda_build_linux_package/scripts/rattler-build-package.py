import argparse
import os
import json
import shlex
import shutil
import subprocess
import sys
from pathlib import Path
from urllib.parse import urlparse

import boto3
import yaml
from botocore.exceptions import ClientError


def print_command(command):
    """Print a command with shlex, splitting each option to a separate line."""

    # Split the command, starting a new list for each option starting with "-"
    split_commands = [[command[0]]]
    for entry in command[1:]:
        if entry.startswith("-"):
            split_commands.append([])
        split_commands[-1].append(entry)

    # Print the command on multiple lines
    suffix = " \\" if len(split_commands) > 1 else ""
    print(f"+ {shlex.join(split_commands[0])}{suffix}")
    for index in range(1, len(split_commands)):
        if index == len(split_commands) - 1:
            suffix = ""
        print(f"+     {shlex.join(split_commands[index])}{suffix}")


def parse_s3_channel_url(s3_url):
    url = urlparse(s3_url, allow_fragments=False)
    if url.scheme != "s3":
        print(f"openjd_fail: Input S3 channel {s3_url} is not an s3:// URL")
        sys.exit(1)
    return (url.netloc, url.path.strip("/"))


def get_channel_options(
    s3_channel_bucket,
    s3_channel_prefix,
    conda_channels,
    s3_client,
):
    channel_options = []
    try:
        main_s3_channel = f"s3://{s3_channel_bucket}/{s3_channel_prefix}"
        repodata_key = f"{s3_channel_prefix}/noarch/repodata.json.zst"
        print(f"Checking whether the S3 channel already has an index by looking for s3://{s3_channel_bucket}/{repodata_key}")
        s3_client.head_object(Bucket=s3_channel_bucket, Key=repodata_key)
        print(f"Found an index, adding {main_s3_channel} to the input channel list")
        channel_options.extend(["-c", main_s3_channel])
    except ClientError as exc:
        print(exc)
        error_code = int(exc.response["ResponseMetadata"]["HTTPStatusCode"])
        if error_code != 404:
            raise
    channel_options.extend(v for channel in conda_channels.split() for v in ["-c", channel])

    return channel_options


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--recipe-dir", required=True)
    parser.add_argument("--conda-platform", required=True)
    parser.add_argument("--override-package-name")
    parser.add_argument("--conda-channels", default="")
    parser.add_argument("--conda-bld-dir", required=True)
    parser.add_argument("--s3-conda-channel", required=True)
    parser.add_argument("--override-source-archive1")
    parser.add_argument("--override-source-archive2")
    parser.add_argument("--override-source-dir")
    parser.add_argument("--variant-config-file")
    parser.add_argument("--extra-build-tool-args", default="")
    args = parser.parse_args()

    session = boto3.Session()
    s3_client = session.client("s3")

    if args.variant_config_file:
        print("Using the following additional variant config:")
        print(Path(args.variant_config_file).read_text())
        print()

    # Make sure the package build starts with a clean conda-bld directory
    if os.path.isdir(args.conda_bld_dir):
        shutil.rmtree(args.conda_bld_dir)

    recipe_file = f"{args.recipe_dir}/recipe.yaml"
    updated_recipe_file = f"{args.recipe_dir}/updated_recipe.yaml"

    # Create the "-c CHANNEL_NAME" options
    s3_channel_bucket, s3_channel_prefix = parse_s3_channel_url(args.s3_conda_channel)
    channel_options = get_channel_options(
        s3_channel_bucket,
        s3_channel_prefix,
        args.conda_channels,
        s3_client,
    )

    variant_config_option = []
    if args.variant_config_file:
        variant_config_option = ["--ignore-recipe-variants", "--variant-config", args.variant_config_file]

    command = [
        "rattler-build",
        "build",
        "--color",
        "never",
        "--render-only",
        "--recipe",
        recipe_file,
        *variant_config_option,
        "--output-dir",
        args.conda_bld_dir,
        "--verbose",
        *channel_options,
    ]
    print_command(command)
    recipe_render_result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    print(recipe_render_result.stdout.decode(errors="replace").replace("\r\n", "\n"))
    if recipe_render_result.returncode != 0:
        print("stderr:")
        print(recipe_render_result.stderr.decode(errors="replace").replace("\r\n", "\n"))
        print(f"ERROR: Process exited with return code {recipe_render_result.returncode}")
        sys.exit(1)
    recipe_list = json.loads(recipe_render_result.stdout)
    if len(recipe_list) != 1:
        print(f"ERROR: The options selected resulted in more than one rendered recipe, ensure only one variant is specified.")
        sys.exit(1)
    rendered_recipe = recipe_list[0]["recipe"]

    # Get values from the rendered recipe but update the original recipe
    updated_recipe = yaml.safe_load(Path(recipe_file).read_text(encoding="utf-8"))

    # Validate that the provided input source archive files exist
    if args.override_source_archive1:
        if not os.path.isfile(args.override_source_archive1):
            print(f"ERROR: Override source archive 1 does not exist: {args.override_source_archive1}")
            sys.exit(1)
    if args.override_source_archive2:
        if not os.path.isfile(args.override_source_archive2):
            print(f"ERROR: Override source archive 2 does not exist: {args.override_source_archive2}")
            sys.exit(1)
    if args.override_source_dir:
        if not os.path.isdir(args.override_source_dir):
            print(f"ERROR: Override source dir does not exist: {args.override_source_dir}")
            sys.exit(1)

    # Substitute the override archives into the recipe
    if "source" in rendered_recipe:
        updated_recipe["source"] = rendered_recipe["source"]
        # If the source is not in list form, turn it into a list
        if isinstance(updated_recipe["source"], dict):
            updated_recipe["source"] = [updated_recipe["source"]]

        if not isinstance(updated_recipe["source"], list):
            raise RuntimeError("The rendered recipe's source field was not a dict or a list.")

        # Put the source archives in a list to help process sequentially
        override_source_archives = []
        if args.override_source_archive1:
            override_source_archives.append(args.override_source_archive1)
        if args.override_source_archive2:
            override_source_archives.append(args.override_source_archive2)
        override_source_dir = args.override_source_dir

        # Iterate through the source entries and update either the directory path or URL
        # based on the input override parameters.
        for source_entry in updated_recipe["source"]:
            if "path" in source_entry:
                if override_source_dir:
                    source_entry["path"] = override_source_dir
            elif "url" in source_entry:
                if override_source_archives:
                    source_entry["url"] = f"file://{override_source_archives.pop(0)}"

        print("Recipe source updated to")
        print(yaml.dump(updated_recipe["source"]))
        print()

    # Save the updated recipe with modified source
    Path(updated_recipe_file).write_text(json.dumps(updated_recipe), encoding="utf-8")

    command = [
        "rattler-build",
        "publish",
        updated_recipe_file,
        "--to",
        args.s3_conda_channel,
        *variant_config_option,
        "--output-dir",
        args.conda_bld_dir,
        "--verbose",
        *shlex.split(args.extra_build_tool_args),
        *[v for channel in args.conda_channels.split() for v in ["-c", channel]],
        "--build-number",
        "+1",
    ]
    print_command(command)
    subprocess.check_call(command)

    os.unlink(updated_recipe_file)

if __name__ == "__main__":
    main()
