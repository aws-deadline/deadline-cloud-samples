"""Pre-submission hook that writes job attachment S3 settings to a file in the bundle."""
import json
import os
import sys

from deadline.client import api

metadata = json.load(sys.stdin)
farm_id = metadata["farmId"]
queue_id = metadata["queueId"]
bundle_dir = metadata["jobBundleDir"]

print(f"Looking up job attachment settings for queue {queue_id}...", file=sys.stderr)
deadline = api.get_boto3_client("deadline")
queue = deadline.get_queue(farmId=farm_id, queueId=queue_id)
ja = queue.get("jobAttachmentSettings", {})

if not ja:
    print("ERROR: Queue has no job attachment settings configured.", file=sys.stderr)
    sys.exit(1)

bucket = ja["s3BucketName"]
prefix = ja["rootPrefix"]
print(f"S3 bucket: {bucket}, prefix: {prefix}", file=sys.stderr)

# Write settings file into the bundle so it gets uploaded as a job attachment
settings_path = os.path.join(bundle_dir, "s3_settings.json")
with open(settings_path, "w") as f:
    json.dump({"s3BucketName": bucket, "rootPrefix": prefix}, f)

# Output asset reference so the file gets uploaded
print(json.dumps({
    "attachments": {
        "assetReferences": {
            "inputFilenames": [settings_path]
        }
    }
}))
