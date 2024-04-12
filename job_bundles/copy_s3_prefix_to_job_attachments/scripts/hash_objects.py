import argparse
import json
import os
import sys
from base64 import b64decode, b64encode
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from urllib.parse import urlparse

import boto3
from xxhash import xxh3_128

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

# Load the list of objects this task will process
with open(workspace_path / f"s3_objects_{args.index}.json") as fh:
    s3_objects = json.load(fh)


def update_mtime_from_metadata(s3_object, metadata):
    """Modifies the 'mtime' entry in s3_object from the S3 object metadata."""
    if posix_mtime_metadata := metadata.get("file-mtime"):
        # DataSync, FSx for Lustre, among others use x-amz-meta-file-mtime,
        # which is nanoseconds if it has an "ns" suffix, otherwise milliseconds.
        if posix_mtime_metadata[-2:] == "ns":
            s3_object["mtime"] = int(posix_mtime_metadata[:-2])
        else:
            s3_object["mtime"] = int(float(posix_mtime_metadata) * 1e6)
    elif posix_mtime_metadata := metadata.get("mtime"):
        # S3FS, RClone, among others use x-amz-meta-mtime, which is seconds
        # and may be floating point
        s3_object["mtime"] = int(float(posix_mtime_metadata) * 1e9)


# Check all the objects for the hash tag, and hash the data if it's missing or doesn't match the etag
hashed_object_count = 0
hashed_bytes_count = 0


def process_s3_object(i, s3_object):
    # NOTE: If we don't combine "\n" inside the main string of print(), it interleaves the "\n" with
    #       the bodies, and some lines get doubled up while others are empty.
    print(f"{i}: Processing key {s3_object['key']}\n", end="")
    response = s3_client.get_object_tagging(Bucket=s3_bucket_name, Key=s3_object["key"])
    tag_set = response["TagSet"]
    tag_set_dict = {obj["Key"]: obj["Value"] for obj in tag_set}
    etag_and_hash_encoded = tag_set_dict.get("B64DeadlineJobAttachmentsXXH128")
    if etag_and_hash_encoded:
        etag, ja_hash = (
            b64decode(etag_and_hash_encoded.encode("ascii")).decode("utf-8").split("|")
        )
        if etag == s3_object["etag"]:
            # If it's tagged, and the etag matches, use the JA hash from the tag
            s3_object["xxh128_hash"] = ja_hash
            print(f"{i}: Using the tagged hash {ja_hash}\n", end="")
            # Get the POSIX mtime if it's set
            response = s3_client.head_object(
                Bucket=s3_bucket_name, Key=s3_object["key"]
            )
            update_mtime_from_metadata(s3_object, response["Metadata"])
            return

    # We don't know the hash, so we need to compute it
    global hashed_object_count, hashed_bytes_count
    hashed_object_count += 1
    hashed_bytes_count += s3_object["size"]
    hasher = xxh3_128()
    if s3_object["size"] > 0:
        response = s3_client.get_object(
            Bucket=s3_bucket_name, Key=s3_object["key"], IfMatch=s3_object["etag"]
        )
        update_mtime_from_metadata(s3_object, response["Metadata"])
        for chunk in response["Body"].iter_chunks(2**20):
            hasher.update(chunk)
    else:
        # Get the POSIX mtime if it's set
        response = s3_client.head_object(Bucket=s3_bucket_name, Key=s3_object["key"])
        update_mtime_from_metadata(s3_object, response["Metadata"])
    ja_hash = hasher.hexdigest()
    s3_object["xxh128_hash"] = ja_hash
    print(f"{i}: Calculated hash {ja_hash}\n", end="")

    # Save the hash as an object tag
    etag_and_hash = b64encode(f"{s3_object['etag']}|{ja_hash}".encode("utf-8")).decode(
        "ascii"
    )
    tag_set = [
        obj for obj in tag_set if obj["Key"] != "B64DeadlineJobAttachmentsXXH128"
    ]
    tag_set.append({"Key": "B64DeadlineJobAttachmentsXXH128", "Value": etag_and_hash})
    s3_client.put_object_tagging(
        Bucket=s3_bucket_name,
        Key=s3_object["key"],
        Tagging={"TagSet": tag_set},
    )


# Get the available vcpus using the API recommended in Python documentation, then use 2 threads for each
available_vcpus = len(os.sched_getaffinity(0))
thread_count = 2 * available_vcpus
# Use multithreaded scheduling, as the xxhash function always releases the GIL
print(
    f"openjd_status: Processing {len(s3_objects)} objects using {thread_count} threads..."
)
with ThreadPoolExecutor(max_workers=thread_count) as executor:
    # Start the load operations and mark each future with its URL
    future_list = [
        executor.submit(process_s3_object, i, s3_object)
        for i, s3_object in enumerate(s3_objects)
    ]
    for i, future in enumerate(as_completed(future_list)):
        # Get the result so it re-raises any exceptions
        future.result()
        print(f"openjd_progress: {100 * i / len(s3_objects):.1f}\n", end="")
print(
    f"openjd_status: Processed {len(s3_objects)} objects (hashed {hashed_bytes_count} bytes in {hashed_object_count} objects)"
)
print("openjd_progress: 100")

# Update the metadata about these objects in the workspace
with open(workspace_path / f"s3_objects_{args.index}.json", "w") as fh:
    json.dump(s3_objects, fh)
