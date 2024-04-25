import argparse
import datetime
import json
import subprocess
import sys
from io import BytesIO
from pathlib import Path
from urllib.parse import urlparse

import boto3

subprocess.check_call([sys.executable, "-m", "pip", "install", "deadline"])
from deadline.job_attachments.asset_manifests.v2023_03_03 import (
    AssetManifest,
    ManifestPath,
)

parser = argparse.ArgumentParser(prog="collect_object.py")
parser.add_argument("workspace_path", type=Path)
parser.add_argument("--parallelism", type=int, required=True)
parser.add_argument("--copy-source", type=str, required=True)
args = parser.parse_args()

workspace_path = Path(sys.argv[1])

session = boto3.Session()
s3_client = session.client("s3")

url = urlparse(args.copy_source, allow_fragments=False)
s3_bucket_name = url.netloc
s3_prefix = url.path.strip("/")

# Load the job attachments S3 settings
with open(workspace_path / "job_attachment_settings.json") as fh:
    ja_settings = json.load(fh)
ja_s3_bucket_name = ja_settings["s3BucketName"]
ja_root_prefix = ja_settings["rootPrefix"]

total_size = 0
paths = []

for index in range(1, args.parallelism + 1):
    with open(workspace_path / f"s3_objects_{index}.json") as fh:
        for s3_object in json.load(fh):
            total_size += s3_object["size"]
            paths.append(
                ManifestPath(
                    path=s3_object["key"][len(s3_prefix) + 1 :],
                    hash=s3_object["xxh128_hash"],
                    mtime=s3_object["mtime"],
                    size=s3_object["size"],
                )
            )

paths.sort(key=lambda x: x.path, reverse=True)

manifest = AssetManifest(
    hash_alg="xxh128",
    paths=paths,
    total_size=total_size,
)

now_timestamp = (
    datetime.datetime.now(tz=datetime.timezone.utc)
    .isoformat(timespec="minutes")
    .replace("+00:00", "Z")
)
manifest_key = f"{ja_root_prefix}/Manifests/bucket-prefix-snapshot-{s3_bucket_name}/{s3_prefix}/{now_timestamp}-manifest.json"

print(f"Saving manifest with {len(paths)} paths, total {total_size} bytes")
s3_client.upload_fileobj(
    Fileobj=BytesIO(manifest.encode().encode("utf-8")),
    Bucket=ja_s3_bucket_name,
    Key=manifest_key,
)
print(f"openjd_status: Saved manifest url s3://{ja_s3_bucket_name}/{manifest_key}")
