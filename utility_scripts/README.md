# AWS Deadline Cloud utility scripts

These standalone command-line tools support common Deadline Cloud workflows outside a job bundle.

## Script index

This table covers every immediate user-selectable sample directory in `utility_scripts/`.

| Sample | What it demonstrates | Start here when |
|---|---|---|
| [Upload to job attachments](upload_to_job_attachments/) | Uploading files into content-addressable job attachment storage with deduplication | Large or reused datasets should be staged before job submission |

## Upload to job attachments

The uploader accepts files and directories from a workstation or server and places them in a queue's job attachments S3 bucket. Subsequent jobs can use the data without uploading unchanged content again.

Key features:

* Upload individual files or directories recursively.
* Use multiple upload threads.
* Skip content that is already present in S3.
* Generate a JSON manifest.
* Configure storage directly or discover it from a farm and queue.

```console
# Upload using an explicit S3 location
python upload_to_job_attachments/upload_to_job_attachments.py \
    --s3-bucket my-bucket \
    --s3-prefix job-attachments \
    --paths /path/to/files /path/to/directory

# Discover storage from a queue
python upload_to_job_attachments/upload_to_job_attachments.py \
    --farm-id farm-1234567890abcdef \
    --queue-id queue-1234567890abcdef \
    --paths /path/to/files /path/to/directory
```

See the [sample README](upload_to_job_attachments/) for installation, permissions, options, and manifest details.

## Additional resources

* [AWS Deadline Cloud user guide](https://docs.aws.amazon.com/deadline-cloud/latest/userguide/index.html)
* [AWS Deadline Cloud developer guide](https://docs.aws.amazon.com/deadline-cloud/latest/developerguide/index.html)
* [AWS Deadline Cloud API reference](https://docs.aws.amazon.com/deadline-cloud/latest/APIReference/index.html)
* [Deadline Cloud CLI](https://github.com/aws-deadline/deadline-cloud)
