import argparse
import json
import sys
from pathlib import Path
from urllib.parse import urlparse

import boto3
from botocore.exceptions import ClientError

parser = argparse.ArgumentParser(prog="collect_object.py")
parser.add_argument("workspace_path", type=Path)
parser.add_argument("--index", type=int, required=True)
parser.add_argument("--copy-source", type=str, required=True)
args = parser.parse_args()

workspace_path = Path(sys.argv[1])

session = boto3.Session()
s3_client = session.client("s3")

url = urlparse(args.copy_source, allow_fragments=False)
s3_bucket_name = url.netloc

# Load the job attachments S3 settings
with open(workspace_path / "job_attachment_settings.json") as fh:
    ja_settings = json.load(fh)
ja_s3_bucket_name = ja_settings["s3BucketName"]
ja_root_prefix = ja_settings["rootPrefix"]

# Load the list of objects this task will process
with open(workspace_path / f"s3_objects_{args.index}.json") as fh:
    s3_objects = json.load(fh)

# Copy all the objects to the job attachments bucket
print(f"openjd_status: Processing {len(s3_objects)} objects...")
copied_object_count = 0
copied_bytes_count = 0
for i, s3_object in enumerate(s3_objects):
    print(f"openjd_progress: {100 * i / len(s3_objects):.1f}")
    print(f"Processing key {s3_object['key']} with hash {s3_object['xxh128_hash']}")
    ja_key = f"{ja_root_prefix}/Data/{s3_object['xxh128_hash']}.xxh128"
    # Check if the object exists, and skip the copy if it does
    try:
        s3_client.head_object(Bucket=ja_s3_bucket_name, Key=ja_key)
        print("Skipping copy, it is already there")
        continue
    except ClientError as exc:
        error_code = int(exc.response["ResponseMetadata"]["HTTPStatusCode"])
        if error_code != 404:
            raise
    copied_object_count += 1
    copied_bytes_count += s3_object["size"]
    print(f"Copying {s3_object['size']} bytes...")
    # Copy using the S3 managed copy operation that does a multi-threaded multi-part
    # copy when applicable.
    s3_client.copy(
        CopySource={"Bucket": s3_bucket_name, "Key": s3_object["key"]},
        Bucket=ja_s3_bucket_name,
        Key=ja_key,
        ExtraArgs={
            "CopySourceIfMatch": s3_object["etag"],
            "MetadataDirective": "REPLACE",
            "TaggingDirective": "REPLACE",
        },
    )
print(
    f"openjd_status: Processed {len(s3_objects)} objects (copied {copied_bytes_count} bytes in {copied_object_count} objects)"
)
print("openjd_progress: 100")
