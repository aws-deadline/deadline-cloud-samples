# Job bundle: Copy S3 prefix to job attachments

## Use case for this job

With AWS Deadline Cloud job attachments, you can attach files and directories to the jobs you submit, and that
data gets uploaded to the job attachments S3 bucket that is configured on your queue. Any files that were already uploaded
do not need to be uploaded again. If you are adding a Deadline Cloud farm to a project that already has a large
volume of data, or are submitting a job that depends on a lot of new data like a fluid simulation output, there
can be a longer wait for the job attachments upload.

Because job attachments never re-uploads files that are already in job attachments, you can use alternative
upload tools like [AWS Snowball](https://aws.amazon.com/snowball/), [AWS DataSync](https://aws.amazon.com/datasync/),
or [Nimble Studio File Transfer](https://docs.aws.amazon.com/nimble-studio/latest/filetransfer-guide/what-is-file-transfer.html)
to first copy that data to S3, then use this job to copy it into the job attachments for your queue.

## How to submit this job

Use the [AWS Deadline Cloud client](https://github.com/aws-deadline/deadline-cloud) to submit this job, either
as a CLI command or with a GUI. Here's an example command to submit the job, if you want to process the copy across 20 workers.

```
$ deadline bundle submit copy_s3_prefix_to_job_attachments \
    -p S3CopySource=s3://SOURCE_BUCKET_NAME/prefix/to/copy \
    -p Parallelism=20
```

## Required IAM permissions

Here are the IAM permissions you will need to add to your queue IAM role. The role already has permissions
to read and write the job attachments bucket prefix, those do not need modification.

```json
{
    "Effect": "Allow",
    "Sid": "DeadlineQueueReadOnly",
    "Action": [
        "deadline:GetQueue"
    ],
    "Resource": [
        "arn:aws:deadline:REGION:ACCOUNT_ID:farm/FARM_ID/queue/QUEUE_ID"
    ]
},
{
    "Effect": "Allow",
    "Sid": "SourceBucketAccess",
    "Action": [
        "s3:ListBucket",
        "s3:GetObjectTagging",
        "s3:PutObjectTagging",
        "s3:GetObject"
    ],
    "Resource": [
        "arn:aws:s3:::SOURCE_BUCKET_NAME",
        "arn:aws:s3:::SOURCE_BUCKET_NAME/*"
    ]
}
```

## Estimating costs

This job calls Amazon S3 APIs, and makes copies of data into your queue's job attachments bucket,
that will incur additional costs on your AWS bill.

You can use information from the [Amazon S3 pricing](https://aws.amazon.com/s3/pricing/) page and the
[AWS Pricing Calculator](https://calculator.aws) to estimate the costs of this job. Here is
a summary of the API calls this job will make:

1. A paginated s3:ListObjectsV2 to get the full list of objects with the specified prefix.
2. For each object with the specified prefix:
    1. An s3:GetObjectTagging to get the tags and see if we already computed the job attachments hash.
    2. If the object does not have a tag with the job attachments hash:
        1. An s3:GetObject to read the full contents and compute the job attachments hash.
        2. An s3:PutObjectTagging to save the job attachments hash.
    3. If the object has a tag with the job attachments hash:
        1. An s3:HeadObject to read the POSIX mtime Metadata.
    4. An s3:HeadObject to determine whether the object is already in the Job Attachments bucket.
    5. If the object is not in the Job Attachments bucket:
        1. Various of s3:CopyObject, s3:HeadObject, s3:CreateMultipartUpload, s3:ListParts,
           s3:UploadPartCopy, etc. as necessary to transfer the object as a single or multiple part copy.
3. An s3:PutObject to write a manifest file for all the objects in the specified prefix.

## Implementation details

Objects in the input bucket are tagged with a key `"B64DeadlineJobAttachmentsXXH128"` with base64-encoded value
`"<etag>|<xxh128-hash>"`. When the etag matches, this tag is used instead of recomputing the hash.
