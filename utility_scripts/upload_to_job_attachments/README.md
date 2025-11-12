# AWS Deadline Cloud Job Attachments Uploader

Upload files and directories from your local workstation to AWS Deadline Cloud job attachments storage.

## Overview

This script uploads files to the job attachments S3 bucket in content-addressable storage format, allowing subsequent jobs to use the data without re-uploading. It's useful for pre-populating job attachments with large datasets.

## Features

- Upload individual files or entire directories recursively
- Multi-threaded uploads for better performance
- Automatic deduplication (skips files already in S3)
- Progress reporting and statistics
- Retry logic with exponential backoff
- Two configuration modes: direct S3 specification or queue lookup

## Requirements

- Python 3.7+
- boto3
- xxhash

Install dependencies:
```bash
pip install boto3 xxhash
```

## AWS Permissions

### For Direct S3 Configuration

Your AWS credentials need:

```json
{
    "Effect": "Allow",
    "Action": [
        "s3:PutObject",
        "s3:HeadObject"
    ],
    "Resource": "arn:aws:s3:::YOUR-BUCKET/*"
}
```

### For Queue Lookup Configuration

Your AWS credentials need:

```json
{
    "Effect": "Allow",
    "Action": [
        "deadline:GetQueue"
    ],
    "Resource": "arn:aws:deadline:*:*:farm/*/queue/*"
},
{
    "Effect": "Allow",
    "Action": [
        "s3:PutObject",
        "s3:HeadObject"
    ],
    "Resource": "arn:aws:s3:::YOUR-BUCKET/*"
}
```

## Usage

### Option 1: Direct S3 Specification

Specify the S3 bucket and prefix directly:

```bash
python upload_to_job_attachments.py \
    --s3-bucket my-bucket \
    --s3-prefix job-attachments \
    --paths /path/to/files /path/to/directory
```

### Option 2: Queue Lookup

Let the script retrieve S3 settings from a Deadline Cloud queue:

```bash
python upload_to_job_attachments.py \
    --farm-id farm-1234567890abcdef \
    --queue-id queue-1234567890abcdef \
    --paths /path/to/files /path/to/directory
```

### Additional Options

```bash
# Specify number of concurrent threads (default: 4)
python upload_to_job_attachments.py \
    --s3-bucket my-bucket \
    --s3-prefix job-attachments \
    --paths /data \
    --threads 8

# Use specific AWS profile and region
python upload_to_job_attachments.py \
    --s3-bucket my-bucket \
    --s3-prefix job-attachments \
    --paths /data \
    --profile my-aws-profile \
    --region us-west-2
```

### Transfer Configuration for Large Files

For very large files or bandwidth constraints, you can customize the S3 transfer behavior:

```bash
# Large files (>100MB) - use bigger chunks for efficiency
python upload_to_job_attachments.py \
    --s3-bucket my-bucket \
    --s3-prefix job-attachments \
    --paths /large-files \
    --multipart-threshold 50 \
    --multipart-chunksize 16 \
    --threads 4

# Throttle bandwidth to 10 MB/s
python upload_to_job_attachments.py \
    --s3-bucket my-bucket \
    --s3-prefix job-attachments \
    --paths /data \
    --max-bandwidth 10

# High concurrency for many small files
python upload_to_job_attachments.py \
    --s3-bucket my-bucket \
    --s3-prefix job-attachments \
    --paths /many-small-files \
    --threads 8 \
    --max-concurrency 5

# Conservative settings for slow/unstable networks
python upload_to_job_attachments.py \
    --s3-bucket my-bucket \
    --s3-prefix job-attachments \
    --paths /data \
    --threads 2 \
    --max-concurrency 5 \
    --max-bandwidth 5
```

### Transfer Configuration Options

- `--multipart-threshold N` - File size in MB to trigger multipart upload (default: 8 MB)
- `--multipart-chunksize N` - Chunk size in MB for multipart uploads (default: 8 MB)
- `--max-concurrency N` - Max concurrent requests per file for multipart uploads (default: 10)
- `--max-bandwidth N` - Maximum bandwidth in MB/s for uploads (optional throttling)

## How It Works

1. **File Collection**: Recursively collects all files from specified paths
2. **Hash Computation**: Computes xxh128 hash for each file using multiple threads
3. **Deduplication**: Checks if files already exist in S3 (by hash)
4. **Upload**: Uploads new files to S3 in content-addressable format: `{prefix}/Data/{hash}.xxh128`

## Output

The script provides:

- Real-time progress updates during hashing and uploading
- Summary statistics:
  - Total files collected
  - Files uploaded vs skipped (already in S3)
  - Total bytes uploaded
  - Any failed files with error messages

### Example Output

```
AWS Deadline Cloud Job Attachments Uploader
==================================================

[1/4] Getting S3 configuration...
  Using direct S3 configuration:
    Bucket: my-bucket
    Prefix: job-attachments

[2/4] Collecting files from 2 path(s)...
  Found 150 files (2.34 MB)

[3/4] Computing file hashes...
Computing hashes for 150 files using 4 threads...
  Hashing progress: 100.0% (150/150)
  Successfully hashed 150 files

[4/4] Uploading files to S3...
Uploading 150 files using 4 threads...
  Upload progress: 100.0% (150/150) - Uploaded: 45, Skipped: 105, Failed: 0

==================================================
Upload Summary
==================================================
Files collected:     150
Files processed:     150
Files uploaded:      45
Files skipped:       105 (already in S3)
Files failed:        0
Total bytes uploaded: 1.23 MB

Upload completed successfully!
```

## Error Handling

- **File read errors**: Logs warning and continues with remaining files
- **S3 upload failures**: Retries up to 3 times with exponential backoff
- **Network errors**: Retries with backoff, reports failures in summary
- **Configuration errors**: Provides clear error messages and exits

## Performance Tips

### Understanding Concurrency

The script has **two levels of concurrency**:

1. **File-level** (`--threads`): How many files upload simultaneously
2. **Part-level** (`--max-concurrency`): How many parts of a single multipart file upload simultaneously

**Total concurrent S3 requests = threads × max_concurrency**

### Recommendations by Use Case

#### Many Small Files (<10 MB each)
```bash
--threads 8              # Upload more files at once
--max-concurrency 5      # Fewer parts per file (most won't be multipart anyway)
# Total: 40 concurrent requests
```

**Why:** Small files don't use multipart, so increase file-level parallelism.

#### Few Large Files (>100 MB each)
```bash
--threads 2              # Fewer files at once
--multipart-threshold 50 # Start multipart at 50 MB
--multipart-chunksize 16 # Larger chunks for efficiency
--max-concurrency 10     # More parts per file (default)
# Total: 20 concurrent requests
```

**Why:** Large files benefit from multipart parallelism. Larger chunks reduce overhead.

#### Mixed File Sizes
```bash
--threads 4              # Balanced file parallelism (default)
--max-concurrency 8      # Moderate part parallelism
# Total: 32 concurrent requests
```

**Why:** Default settings work well for mixed workloads.

#### Bandwidth Constrained
```bash
--threads 2
--max-concurrency 5
--max-bandwidth 10       # Limit to 10 MB/s
# Total: 10 concurrent requests + bandwidth throttling
```

**Why:** Reduce concurrency and add throttling to avoid overwhelming the connection.

#### Fast Network / EC2 Upload
```bash
--threads 8
--max-concurrency 10
--multipart-chunksize 16
# Total: 80 concurrent requests
```

**Why:** Take advantage of high bandwidth and low latency to S3.

### General Guidelines

1. **Start with defaults** - The default settings (4 threads, 10 max_concurrency) work well for most cases

2. **Monitor your network** - If you see connection errors or timeouts, reduce concurrency

3. **Large datasets**:
   - Files are streamed during hashing (no memory issues)
   - Deduplication saves time on repeated uploads

## Troubleshooting

### "No files found to upload"
- Check that specified paths exist and are accessible
- Verify you have read permissions on the files/directories

### "Failed to get queue configuration"
- Verify farm-id and queue-id are correct
- Check AWS credentials have `deadline:GetQueue` permission
- Ensure queue has job attachments configured

### "Failed to upload" errors
- Check AWS credentials have S3 write permissions
- Verify S3 bucket exists and is accessible
- Check network connectivity

### Import errors
- Install required dependencies: `pip install boto3 xxhash`
