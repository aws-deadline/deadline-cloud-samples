import sys
import argparse
import shutil
import subprocess
import yaml
import json
import boto3
import glob
import shlex
from pathlib import Path
from botocore.exceptions import ClientError
from urllib.parse import urlparse


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
    print(f"+ {shlex.join(command)}")
    package_search_result = subprocess.run(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    package_search_result_json = json.loads(package_search_result.stdout)
    print(json.dumps(package_search_result_json, indent=1))

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


def get_channel_options(s3_channel_bucket, s3_channel_prefix, conda_channels, s3_client):
    channel_options = []
    try:
        repodata_key = f"{s3_channel_prefix}/noarch/repodata.json.zst"
        print(f"Checking whether the S3 channel already has an index by looking for s3://{s3_channel_bucket}/{repodata_key}")
        s3_client.head_object(Bucket=s3_channel_bucket, Key=repodata_key)
        print(f"Found an index, adding s3://{s3_channel_bucket}/{s3_channel_prefix} to the input channel list")
        channel_options.extend(["-c", f"s3://{s3_channel_bucket}/{s3_channel_prefix}"])
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
    parser.add_argument("--override-prefix-length")
    parser.add_argument("--override-source-archive1")
    parser.add_argument("--override-source-archive2")
    parser.add_argument("--conda-build-config-file")
    args = parser.parse_args()

    session = boto3.Session()
    s3_client = session.client("s3")

    if args.conda_build_config_file:
        shutil.copy(args.conda_build_config_file, Path(args.recipe_dir) / "conda_build_config.yaml")

    s3_channel_bucket, s3_channel_prefix = parse_s3_channel_url(args.s3_conda_channel)

    # Make sure the package build starts with a clean conda-bld directory
    command = ["conda", "build", "purge"]
    print(f"+ {shlex.join(command)}")
    subprocess.check_call(command)

    channel_options = get_channel_options(s3_channel_bucket, s3_channel_prefix, args.conda_channels, s3_client)

    command = ["conda", "render", "--no-source", "-f", "rendered_meta.yaml", *channel_options, args.recipe_dir]
    print(f"+ {shlex.join(command)}")
    subprocess.check_call(command)

    rendered_meta_text = Path("rendered_meta.yaml").read_text()
    print(rendered_meta_text)
    rendered_meta = yaml.safe_load(rendered_meta_text)

    package_name = rendered_meta["package"]["name"]
    if args.override_package_name:
        package_name = args.override_package_name

    package_version = rendered_meta["package"]["version"]

    build_number = get_next_build_number(package_name, package_version, args.conda_platform, channel_options)
    print(f"openjd_status: Selected build number {build_number}")

    recipe_clobber = {"build": {"number": build_number}}
    if args.override_package_name:
        recipe_clobber["package"] = {}
        recipe_clobber["package"]["name"] = args.override_package_name
    if isinstance(rendered_meta["source"], dict):
        if args.override_source_archive1:
            recipe_clobber["source"] = {}
            recipe_clobber["source"]["url"] = args.override_source_archive1
    elif isinstance(rendered_meta["source"], list):
        rendered_source = rendered_meta["source"]
        if args.override_source_archive1 or args.override_source_archive2:
            if args.override_source_archive1:
                rendered_source[0]["url"] = args.override_source_archive1
            if args.override_source_archive2:
                rendered_source[1]["url"] = args.override_source_archive2
            recipe_clobber["source"] = rendered_source
    else:
        raise RuntimeError("The rendered meta.yaml's source field was not a string or a list.")

    Path("recipe_clobber.yaml").write_text(yaml.safe_dump(recipe_clobber))

    prefix_length_option = []
    if args.override_prefix_length:
        prefix_length_option = ["--prefix-length", f"{args.override_prefix_length}"]

    command = [
        "conda",
        "build",
        "--no-anaconda-upload",
        *prefix_length_option,
        *channel_options,
        "--clobber-file",
        "recipe_clobber.yaml",
        args.recipe_dir,
    ]
    print(f"+ {shlex.join(command)}")
    subprocess.check_call(command)

    for subdir in [args.conda_platform, "noarch"]:
        for package in glob.glob(str(Path(args.conda_bld_dir) / subdir / "*.conda")):
            package_name = Path(package).name
            package_key = f"{s3_channel_prefix}/{subdir}/{package_name}"
            print(f"Package {package_name} is {Path(package).stat().st_size} bytes")
            print(f"openjd_status: Uploading the package {package_name} to s3://{s3_channel_bucket}/{package_key}...")
            s3_client.upload_file(package, s3_channel_bucket, package_key)


if __name__ == "__main__":
    main()
