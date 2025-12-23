# AWS Deadline Cloud utility scripts

This directory contains sample utility scripts to help you work with AWS Deadline Cloud. These scripts provide
command-line tools for common tasks like managing job attachments, working with queues, and automating workflows.

## Script index

### Upload to Job Attachments

The [upload_to_job_attachments](upload_to_job_attachments) script uploads files and directories from your local
workstation or server to AWS Deadline Cloud job attachments storage. It uploads files to the job attachments S3 bucket in
content-addressable storage format, allowing subsequent Deadline Cloud jobs to use the data without re-uploading. This is useful
for pre-populating job attachments with large datasets that multiple jobs will use.

Key features:
- Upload individual files or entire directories recursively
- Multi-threaded uploads for better performance
- Automatic deduplication (skips files already in S3)
- Generates JSON manifest of uploaded files
- Two configuration modes: direct S3 specification or queue lookup

Example usage:
```bash
# Upload using direct S3 specification
python upload_to_job_attachments.py \
    --s3-bucket my-bucket \
    --s3-prefix job-attachments \
    --paths /path/to/files /path/to/directory

# Upload using queue lookup
python upload_to_job_attachments.py \
    --farm-id farm-1234567890abcdef \
    --queue-id queue-1234567890abcdef \
    --paths /path/to/files /path/to/directory
```

## Additional Resources

* [AWS Deadline Cloud user guide](https://docs.aws.amazon.com/deadline-cloud/latest/userguide/index.html)
* [AWS Deadline Cloud developer guide](https://docs.aws.amazon.com/deadline-cloud/latest/developerguide/index.html)
* [AWS Deadline Cloud API reference](https://docs.aws.amazon.com/deadline-cloud/latest/APIReference/index.html)
* [Deadline Cloud CLI](https://github.com/aws-deadline/deadline-cloud)
