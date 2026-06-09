# FFmpeg Movie from Job Output

## Introduction

This job bundle downloads the rendered output of another completed job in the same queue
and uses FFmpeg to encode the image sequence into an MP4 video file. It is useful as a
post-processing utility — for example, after a Blender or Maya render job completes, you
can submit this job to automatically assemble the frames into a movie.

See also [ffmpeg_encode_video](../ffmpeg_encode_video) for a simpler sample that encodes
a local image sequence without downloading from another job.

## How it works

A [pre-submission hook](https://github.com/aws-deadline/deadline-cloud/blob/mainline/docs/submission-hooks.md)
(`inject_s3_settings.py`) runs at submission time on your workstation and looks up the
queue's job attachment S3 bucket configuration. It writes the settings to a JSON file that
gets uploaded as a job attachment, so the worker can access S3 without needing any
Deadline Cloud API permissions.

On the worker, the job installs the `deadline` Python library via pip in a job environment,
then runs a single step that:

1. Uses the `deadline.job_attachments` Python API to download the output files from the
   source job's job attachments in S3.
2. Auto-detects the image format from the downloaded files, sorts them alphabetically, and
   encodes them into an H.264 MP4 video using FFmpeg with BT.709 color space metadata.

## Prerequisites

### Software

The job requires FFmpeg (from conda-forge) and the Deadline Cloud Python library (installed
via pip at runtime). On service-managed fleets, set the conda queue environment channel to
`conda-forge`. The job's `CondaPackages` parameter defaults to `ffmpeg`.

### Submission hooks

This job bundle uses a pre-submission hook to inject S3 settings. Enable bundle hooks
before submitting (one-time setup):

```bash
deadline config set settings.allow_bundle_hooks true
```

The hook runs on your local machine at submission time using your existing AWS credentials.
No additional IAM permissions are needed on the queue role.

### Source job requirements

- The source job must have completed and produced output files via job attachments.
- Both jobs must be in the same queue (they share the same job attachments S3 bucket).

## Parameters

| Parameter | Description | Default |
|-----------|-------------|---------|
| Source Job ID | The Job ID of the completed source job | (required) |
| Source Step ID | Restrict download to a specific step's output | (empty = all) |
| Frame Rate | Video frame rate in fps | 24 |
| Pixel Format | Output pixel format (`yuv420p` or `yuv444p`) | yuv420p |
| Encoding Preset | FFmpeg speed/compression tradeoff | medium |
| Constant Rate Factor | H.264 quality (0 = lossless, 51 = worst, 17-18 ≈ visually lossless) | 18 |
| Output Resolution | Optional WIDTHxHEIGHT override (e.g. `1920x1080`) | (empty = source) |
| Output Filename | Name of the output video file | output.mp4 |
| Output Directory | Where to save the video | output |

## Example submission

```bash
# Enable bundle hooks (one-time setup)
deadline config set settings.allow_bundle_hooks true

# Submit via GUI
deadline bundle gui-submit ffmpeg_movie_from_job_output/

# Submit via CLI
deadline bundle submit ffmpeg_movie_from_job_output/ \
    -p SourceJobId=job-0123456789abcdef0123456789abcdef \
    -p FrameRate=30 \
    -p OutputFilename=my_render.mp4

# Download only a specific step's output
deadline bundle submit ffmpeg_movie_from_job_output/ \
    -p SourceJobId=job-0123456789abcdef0123456789abcdef \
    -p SourceStepId=step-0123456789abcdef0123456789abcdef
```

## Typical workflow

1. Submit a render job (e.g. Blender, Maya) to your queue.
2. Wait for the render job to complete.
3. Copy the Job ID from Deadline Cloud Monitor.
4. Submit this job bundle with the source Job ID.
5. Download the output video from Deadline Cloud Monitor.

You can also automate this by scripting the submission after the render job completes
using `deadline job wait` followed by `deadline bundle submit`.
