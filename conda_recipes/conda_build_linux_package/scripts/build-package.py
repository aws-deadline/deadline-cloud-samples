import argparse
import glob
import json
import os
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


def get_next_build_number(package_name, package_version, conda_platform, channel_options):
    command = [
        "conda",
        "search",
        *channel_options,
        "--platform",
        conda_platform,
        "--json",
        "--spec",
        f"{package_name}=={package_version}",
    ]
    print_command(command)
    package_search_result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    print(package_search_result.stdout.decode(errors="replace").replace("\r\n", "\n"))
    package_search_result_json = json.loads(package_search_result.stdout)

    if package_search_result.returncode == 0 and package_name in package_search_result_json:
        build_number = max(package["build_number"] for package in package_search_result_json[package_name]) + 1
    else:
        if package_search_result_json.get("error", "").startswith("PackagesNotFoundError") or package_search_result.returncode == 0:
            print("No matching conda packages found.")
            build_number = 0
        else:
            print(json.dumps(package_search_result_json, indent=1))
            sys.exit(1)

    return build_number


def get_channel_options(
    s3_channel_bucket,
    s3_channel_prefix,
    proxy_s3_conda_channel,
    conda_channels,
    s3_client,
):
    channel_options = []
    try:
        repodata_key = f"{s3_channel_prefix}/noarch/repodata.json.zst"
        print(f"Checking whether the S3 channel already has an index by looking for s3://{s3_channel_bucket}/{repodata_key}")
        s3_client.head_object(Bucket=s3_channel_bucket, Key=repodata_key)
        print(f"Found an index, adding {proxy_s3_conda_channel} to the input channel list")
        channel_options.extend(["-c", proxy_s3_conda_channel])
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
    parser.add_argument("--build-tool", required=True, choices=("conda-build", "rattler-build"))
    parser.add_argument("--conda-platform", required=True)
    parser.add_argument("--override-package-name")
    parser.add_argument("--conda-channels", default="")
    parser.add_argument("--conda-bld-dir", required=True)
    parser.add_argument("--s3-conda-channel", required=True)
    parser.add_argument("--proxy-s3-conda-channel", required=True)
    parser.add_argument("--override-prefix-length")
    parser.add_argument("--override-source-archive1")
    parser.add_argument("--override-source-archive2")
    parser.add_argument("--variant-config-file")
    args = parser.parse_args()

    session = boto3.Session()
    s3_client = session.client("s3")

    if args.variant_config_file:
        print("Using the following additional variant config:")
        print(Path(args.variant_config_file).read_text())
        print()

    s3_channel_bucket, s3_channel_prefix = parse_s3_channel_url(args.s3_conda_channel)

    # Make sure the package build starts with a clean conda-bld directory
    command = ["conda", "build", "purge"]
    print_command(command)
    subprocess.check_call(command)
    if os.path.isdir(args.conda_bld_dir):
        shutil.rmtree(args.conda_bld_dir)

    # Create the "-c CHANNEL_NAME" options
    channel_options = get_channel_options(
        s3_channel_bucket,
        s3_channel_prefix,
        args.proxy_s3_conda_channel,
        args.conda_channels,
        s3_client,
    )
    variant_config_option = []
    if args.variant_config_file:
        variant_config_option = ["-m", args.variant_config_file]

    # Render the recipe, to substitute any jinja templating. We can take and modify literal
    # values from the rendered recipe to apply the customizations specified by job parameters.
    if args.build_tool == "conda-build":
        recipe_file = f"{args.recipe_dir}/meta.yaml"
        command = [
            "conda",
            "render",
            *variant_config_option,
            "--no-source",
            "-f",
            "rendered_meta.yaml",
            *channel_options,
            "--override-channels",
            args.recipe_dir,
        ]
        print_command(command)
        subprocess.check_call(command)

        rendered_meta_text = Path("rendered_meta.yaml").read_text()
        print(rendered_meta_text)
        rendered_recipe = yaml.safe_load(rendered_meta_text)

        # When using conda-build, update the rendered recipe
        updated_recipe = rendered_recipe
    elif args.build_tool == "rattler-build":
        recipe_file = f"{args.recipe_dir}/recipe.yaml"
        updated_recipe_file = f"{args.recipe_dir}/updated_recipe.yaml"

        command = [
            "rattler-build",
            "build",
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

        # When using rattler-build, get values from the rendered recipe but update the original recipe
        recipe_text = Path(recipe_file).read_text()
        updated_recipe = yaml.safe_load(recipe_text)
    else:
        print(f"ERROR: Unsupported build tool {args.build_tool}")
        sys.exit(1)

    # Replace values in the rendered recipe
    if args.override_package_name:
        rendered_recipe["package"]["name"] = args.override_package_name
    package_name = rendered_recipe["package"]["name"]
    package_version = rendered_recipe["package"]["version"]

    build_number = get_next_build_number(package_name, package_version, args.conda_platform, channel_options)
    updated_recipe["build"]["number"] = build_number
    print(f"openjd_status: Selected build number {build_number}")

    # Validate that the provided input source archive files exist
    if args.override_source_archive1:
        if not os.path.isfile(args.override_source_archive1):
            print(f"ERROR: Override source archive 1 does not exist: {args.override_source_archive1}")
            sys.exit(1)
    if args.override_source_archive2:
        if not os.path.isfile(args.override_source_archive2):
            print(f"ERROR: Override source archive 2 does not exist: {args.override_source_archive2}")
            sys.exit(1)

    # Substitute the override archives into the recipe
    if "source" in rendered_recipe:
        updated_recipe["source"] = rendered_recipe["source"]
        if isinstance(rendered_recipe["source"], dict):
            if args.override_source_archive1:
                if args.build_tool == "conda-build":
                    updated_recipe["source"]["url"] = args.override_source_archive1
                else:
                    updated_recipe["source"].pop("url", None)
                    updated_recipe["source"]["path"] = args.override_source_archive1
        elif isinstance(rendered_recipe["source"], list):
            if args.override_source_archive1 or args.override_source_archive2:
                if args.override_source_archive1:
                    if args.build_tool == "conda-build":
                        updated_recipe["source"][0]["url"] = args.override_source_archive1
                    else:
                        updated_recipe["source"][0].pop("url", None)
                        updated_recipe["source"][0]["path"] = args.override_source_archive1
                if args.override_source_archive2:
                    if args.build_tool == "conda-build":
                        updated_recipe["source"][1]["url"] = args.override_source_archive2
                    else:
                        updated_recipe["source"][1].pop("url", None)
                        updated_recipe["source"][1]["path"] = args.override_source_archive2
        else:
            raise RuntimeError("The rendered recipe's source field was not a string or a list.")

    # Save the rendered recipe with modifications
    if args.build_tool == "conda-build":
        recipe_clobber = {
            "package": {"name": updated_recipe["package"]["name"]},
            "build": {"number": updated_recipe["build"]["number"]},
            "source": updated_recipe["source"],
        }
        print("Clobber file:")
        print(json.dumps(recipe_clobber, indent=1))
        Path("recipe_clobber.yaml").write_text(json.dumps(recipe_clobber))
    else:
        with open(updated_recipe_file, "w") as fh:
            json.dump(updated_recipe, fh)

    prefix_length_option = []
    if args.override_prefix_length and args.override_prefix_length != "0":
        if args.build_tool == "rattler-build":
            print("ERROR: The rattler-build package build tool does not support overriding the prefix length.")
            sys.exit(1)
        prefix_length_option = ["--prefix-length", f"{args.override_prefix_length}"]

    # Run the package build tool
    if args.build_tool == "conda-build":
        command = [
            "conda",
            "build",
            "--no-anaconda-upload",
            *prefix_length_option,
            *variant_config_option,
            *channel_options,
            "--clobber-file",
            "recipe_clobber.yaml",
            args.recipe_dir,
        ]
    else:
        command = [
            "rattler-build",
            "build",
            "--recipe",
            updated_recipe_file,
            *variant_config_option,
            "--output-dir",
            args.conda_bld_dir,
            "--verbose",
            *prefix_length_option,
            *channel_options,
        ]
    print_command(command)
    subprocess.check_call(command)

    if args.build_tool == "rattler-build":
        # Remove the recipe file created with modifications
        os.unlink(updated_recipe_file)

    # Upload all the built packages
    for subdir in [args.conda_platform, "noarch"]:
        for package in glob.glob(str(Path(args.conda_bld_dir) / subdir / "*.conda")):
            package_name = Path(package).name
            package_key = f"{s3_channel_prefix}/{subdir}/{package_name}"
            print(f"Package {package_name} is {Path(package).stat().st_size} bytes")
            print(f"openjd_status: Uploading the package {package_name} to s3://{s3_channel_bucket}/{package_key}...")
            s3_client.upload_file(package, s3_channel_bucket, package_key)


if __name__ == "__main__":
    main()
