import argparse
import json
import os
import sys
from pathlib import Path
from pprint import pprint
from urllib.parse import urlparse

import boto3

parser = argparse.ArgumentParser(prog="collect_object.py")
parser.add_argument("workspace_path", type=Path)
parser.add_argument("--parallelism", type=int, required=True)
parser.add_argument("--copy-source", type=str, required=True)
args = parser.parse_args()

# Initialize the workspace
os.makedirs(args.workspace_path, exist_ok=True)
os.chdir(args.workspace_path)

session = boto3.Session()
deadline_client = session.client("deadline")
s3_client = session.client("s3")

# Get the queue and save it into the workspace
response = deadline_client.get_queue(
    farmId=os.environ["DEADLINE_FARM_ID"], queueId=os.environ["DEADLINE_QUEUE_ID"]
)
with open(args.workspace_path / "job_attachment_settings.json", "w") as fh:
    json.dump(response["jobAttachmentSettings"], fh)

# Split the S3 copy source into bucket and prefix
url = urlparse(args.copy_source, allow_fragments=False)
if url.scheme != "s3":
    print(f"openjd_fail: Input S3 prefix {args.copy_source} is not an s3:// URL")
    sys.exit(1)
s3_bucket_name = url.netloc
s3_prefix = url.path.strip("/")

# Collect all the S3 objects under the prefix, skipping any
# that end with "/" as those are directory markers.
s3_objects = []
paginator = s3_client.get_paginator("list_objects_v2")
for page in paginator.paginate(Bucket=s3_bucket_name, Prefix=f"{s3_prefix}/"):
    s3_objects.extend(
        {
            "key": obj["Key"],
            "size": obj["Size"],
            "etag": obj["ETag"],
            "mtime": int(obj["LastModified"].timestamp() * 1e9),
        }
        for obj in page["Contents"]
        if not obj["Key"].endswith("/")
    )

total_size = sum(obj["size"] for obj in s3_objects)
print(
    f"openjd_status: Collected {len(s3_objects)} objects in {total_size / 1024 / 1024:.2f}MB containing the bucket prefix"
)
print("The first 20 objects:")
pprint(s3_objects[:20])

# Sort by size and then deal the S3 objects to the tasks.
# This will roughly distribute by both amount of data and file count.
s3_objects.sort(key=lambda v: v["size"])
for i in range(args.parallelism):
    with open(args.workspace_path / f"s3_objects_{i + 1}.json", "w") as fh:
        json.dump(s3_objects[i :: args.parallelism], fh)
