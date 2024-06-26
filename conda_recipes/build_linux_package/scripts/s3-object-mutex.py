"""
Provides enter/exit actions for an OpenJobDescription environment that
holds a mutex for a specific S3 object provided as an s3://<bucket-name>/prefix/object
URL.

The lock on the mutex times out after 15 minutes (900 seconds), so all tasks within
its scope must complete faster than this. If a session is not stopped in an orderly
fashion, for example due to the worker host being terminated, this timeout ensures
that package build jobs will resume without intervention.

To enter the mutex:
    $ python s3-object-mutex.py enter s3://<bucket-name>/prefix/object

To exit the mutex:
    $ python s3-object-mutex.py exit s3://<bucket-name>/prefix/object

Required permissions on the S3 bucket prefix:
* s3:ListBucket
* s3:PutObject
* s3:GetObject
* s3:DeleteObject
"""

import argparse
import datetime
import json
import os
import sys
import time
from pprint import pprint
from urllib.parse import urlparse

import boto3
from botocore.exceptions import ClientError

MUTEX_OBJECT_SUFFIX = ".s3-object-mutex-lock.json"
MUTEX_TIMEOUT_SECONDS = 900
MUTEX_ACQUISITION_TIMEOUT_SECONDS = 120
MUTEX_WAIT_POLLING_SECONDS = 20

parser = argparse.ArgumentParser()
parser.add_argument("action", type=str, choices=["enter", "exit"])
parser.add_argument("s3_object_url", type=str)
args = parser.parse_args()

# Split the S3 URL into bucket and prefix
url = urlparse(args.s3_object_url, allow_fragments=False)
if url.scheme != "s3":
    print(f"openjd_fail: Input S3 object {args.s3_object_url} is not an s3:// URL")
    sys.exit(1)
s3_bucket_name = url.netloc
s3_prefix = url.path.lstrip("/")
s3_lock_object = s3_prefix + MUTEX_OBJECT_SUFFIX

s3_client = boto3.client("s3")


def _get_data_for_lock():
    return {
        "farmId": os.environ["DEADLINE_FARM_ID"],
        "queueId": os.environ["DEADLINE_QUEUE_ID"],
        "fleetId": os.environ["DEADLINE_FLEET_ID"],
        "jobId": os.environ["DEADLINE_JOB_ID"],
        "sessionId": os.environ["DEADLINE_SESSION_ID"],
        "workerId": os.environ["DEADLINE_WORKER_ID"],
    }


def _mutex_get_lock_data(mutex_timeout_seconds=MUTEX_TIMEOUT_SECONDS):
    """
    If the mutex is locked, this function returns (lock_data, time_until_expiry),
    otherwise returns (None, None).

    The mutex is locked if:
        1. The object key + MUTEX_OBJECT_SUFFIX exists.
        2. The last-modified date of the object is newer than MUTEX_TIMEOUT_MINUTES ago.
    """
    try:
        response = s3_client.get_object(Bucket=s3_bucket_name, Key=s3_lock_object)
    except ClientError as exc:
        error_code = int(exc.response["ResponseMetadata"]["HTTPStatusCode"])
        if error_code != 404:
            raise
        # It's not locked if the lock object is missing
        return (None, None)

    time_until_expiry = response["LastModified"] + datetime.timedelta(seconds=mutex_timeout_seconds) - datetime.datetime.now(tz=datetime.timezone.utc)
    if time_until_expiry <= datetime.timedelta(seconds=0):
        # If the object hasn't been refreshed within the timeout, it's not locked. This
        # way the mutex can recover from hosts disappearing such as via spot instance interruptions.
        return (None, None)

    try:
        return (json.loads(response["Body"].read()), time_until_expiry)
    except json.JSONDecodeError:
        # If the object does not contain valid JSON, it's not locked.
        return (None, None)


def _mutex_wait_while_locked():
    """
    Wait while the mutex is locked.
    """
    lock_data, time_until_expiry = _mutex_get_lock_data()
    while lock_data is not None:
        print(f"Waiting, the lock for mutex s3://{s3_bucket_name}/{s3_lock_object} expires in {time_until_expiry}, info:")
        pprint(lock_data)
        time.sleep(MUTEX_WAIT_POLLING_SECONDS)
        lock_data, time_until_expiry = _mutex_get_lock_data()
    return


def enter():
    """
    Lock the mutex, waiting as necessary.
    """
    # Write the lock acquisition object to get in line for the mutex
    s3_lock_acquisition_object = f"{s3_lock_object}.{os.environ['DEADLINE_SESSION_ID']}"
    print(f"Creating object s3://{s3_bucket_name}/{s3_lock_acquisition_object}")
    s3_client.put_object(
        Bucket=s3_bucket_name, Key=s3_lock_acquisition_object, Body=b""
    )

    paginator = s3_client.get_paginator("list_objects_v2")
    while True:
        # Wait until the mutex is available
        _mutex_wait_while_locked()

        # Get all the lock acquisition objects
        all_s3_objects = []
        for page in paginator.paginate(
            Bucket=s3_bucket_name, Prefix=f"{s3_lock_object}."
        ):
            all_s3_objects.extend(page.get("Contents", []))

        # Check our object for expiry or deletion
        our_expiry = datetime.datetime.now(
            tz=datetime.timezone.utc
        ) - datetime.timedelta(
            seconds=MUTEX_ACQUISITION_TIMEOUT_SECONDS - MUTEX_WAIT_POLLING_SECONDS
        )
        our_s3_object = [
            obj for obj in all_s3_objects if obj["Key"] == s3_lock_acquisition_object
        ]
        if len(our_s3_object) == 0 or our_s3_object[0]["LastModified"] < our_expiry:
            # Re-write the lock acquisition object, and restart the loop
            if len(our_s3_object) == 0:
                print("The lock acquisition object was deleted.")
            else:
                print("The lock acquisition object expired.")
            print(
                f"Re-creating object s3://{s3_bucket_name}/{s3_lock_acquisition_object}"
            )
            s3_client.put_object(
                Bucket=s3_bucket_name, Key=s3_lock_acquisition_object, Body=b""
            )
            continue

        # Filter out expired objects
        expiry = datetime.datetime.now(tz=datetime.timezone.utc) - datetime.timedelta(
            seconds=MUTEX_ACQUISITION_TIMEOUT_SECONDS
        )
        s3_objects = [obj for obj in all_s3_objects if obj["LastModified"] > expiry]

        # Sort the objects oldest first, then by key
        s3_objects.sort(key=lambda obj: (obj["LastModified"], obj["Key"]))
        if s3_objects[0]["Key"] == s3_lock_acquisition_object:
            break

        # Print the list of sessions ahead of us
        our_index = next(i for i, obj in enumerate(s3_objects) if obj["Key"] == s3_lock_acquisition_object)
        ahead_s3_objects = s3_objects[:our_index]
        print("These Deadline Cloud job sessions are waiting for the mutex ahead of us:")
        for obj in ahead_s3_objects:
            print(f"    {obj['Key'].rsplit('.', 1)[-1]}")
        time.sleep(MUTEX_WAIT_POLLING_SECONDS)

    # We're at the front of the line, so take the lock
    lock_data = _get_data_for_lock()
    body = json.dumps(lock_data).encode("utf8")
    print(f"Creating object s3://{s3_bucket_name}/{s3_lock_object}")
    s3_client.put_object(Bucket=s3_bucket_name, Key=s3_lock_object, Body=body)

    # Delete our lock acquisition object and any expired ones
    delete_s3_objects = [
        obj
        for obj in all_s3_objects
        if obj["LastModified"] <= expiry or obj["Key"] == s3_lock_acquisition_object
    ]
    for obj in delete_s3_objects:
        print(f"Deleting object s3://{s3_bucket_name}/{obj['Key']}")
        s3_client.delete_object(Bucket=s3_bucket_name, Key=obj["Key"])


def exit():
    """
    Unlocks the mutex if it's being held by this session.
    """
    # Get the lock data with a 10 seconds faster timeout. If there's less time than that
    # remaining just let it time out instead of deleting the object.
    lock_data, _ = _mutex_get_lock_data(mutex_timeout_seconds=MUTEX_TIMEOUT_SECONDS - 10)
    if lock_data == _get_data_for_lock():
        print(f"Deleting object s3://{s3_bucket_name}/{s3_lock_object}")
        s3_client.delete_object(Bucket=s3_bucket_name, Key=s3_lock_object)


if args.action == "enter":
    enter()
else:
    exit()
