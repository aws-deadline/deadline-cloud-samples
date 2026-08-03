# AWS Deadline Cloud utility scripts

These standalone command-line tools support common Deadline Cloud workflows outside a job bundle.

## Script index

This table covers every immediate user-selectable sample directory in `utility_scripts/`.

| Sample | What it demonstrates | Start here when |
|---|---|---|
| [Upload to job attachments](upload_to_job_attachments/) | Uploading files into content-addressable job attachment storage with deduplication | Large or reused datasets should be staged before job submission |
| [Virtual workstation](virtual_workstation/) | Provisioning a Linux or Windows workstation with a DCC, the Deadline Cloud submitter, and a pre-configured monitor profile | Artists should find a submission-ready machine and only need to sign in |

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

## Virtual workstation

Example scripts for Linux and Windows prepare a workstation for Deadline Cloud submission. Each one installs Blender, then installs the Deadline Cloud submitter and monitor through their silent installers. It finishes by creating a monitor profile non-interactively, so an artist only has to sign in.

```console
# Linux, as root. Add the artist's account when there is no SUDO_USER to infer,
# as under EC2 user data.
sudo virtual_workstation/setup_workstation_linux.sh https://mystudio.us-west-2.deadlinecloud.amazonaws.com/

# Windows, in an elevated PowerShell session as the artist's own account
.\virtual_workstation\setup_workstation_windows.ps1 https://mystudio.us-west-2.deadlinecloud.amazonaws.com/
```

Blender stands in for whichever DCC you run. See the [sample README](virtual_workstation/) for prerequisites, adapting the scripts to another DCC, and cleanup.

## Additional resources

* [AWS Deadline Cloud user guide](https://docs.aws.amazon.com/deadline-cloud/latest/userguide/index.html)
* [AWS Deadline Cloud developer guide](https://docs.aws.amazon.com/deadline-cloud/latest/developerguide/index.html)
* [AWS Deadline Cloud API reference](https://docs.aws.amazon.com/deadline-cloud/latest/APIReference/index.html)
* [Deadline Cloud CLI](https://github.com/aws-deadline/deadline-cloud)
