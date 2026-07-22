# FFmpeg Encode Video job bundle

## Introduction

This job takes a directory of sequentially numbered image files and encodes them into an MP4 video using FFmpeg. It is useful as a standalone utility for converting render output to video, or as a reference for adding a video encoding step to a multi-step render pipeline.

## Features

* Encodes numbered image sequences (PNG, EXR, JPEG, etc.) into H.264 MP4 video
* Supports customizable frame rate, quality (CRF), and encoding speed presets
* Uses `####` hash-mark patterns for input file naming, automatically converted to FFmpeg's printf-style `%04d` format
* Works with job attachments or shared file systems
* Produces broadcast-safe output with BT.709 color space and `faststart` for web streaming

## Prerequisites

The job needs FFmpeg to run. On Deadline Cloud service-managed fleets, use `conda-forge` as the `CondaChannels` parameter for a [conda queue environment](https://docs.aws.amazon.com/deadline-cloud/latest/developerguide/provide-applications.html). FFmpeg is available from the [conda-forge](https://anaconda.org/conda-forge/ffmpeg) community channel.

> FFmpeg is not available from the `deadline-cloud` conda channel. You must use `conda-forge`.

## Example submission

### GUI submission

```
deadline bundle gui-submit ffmpeg_encode_video/
```

### CLI submission

```
deadline bundle submit ffmpeg_encode_video/ \
  -p InputDir=/path/to/frames \
  -p InputFilePattern="render.####.png" \
  -p StartFrame=1 \
  -p EndFrame=250 \
  -p OutputDir=/path/to/output \
  -p OutputFileName="my_video.mp4"
```

### Using output from another job

A common workflow is to render an image sequence with one job, then encode it to video with this job. If both jobs use job attachments, you can download the render output and include it as input to this job:

```bash
# Download rendered frames from a completed render job
deadline job download-output \
  --farm-id farm-XXXX --queue-id queue-XXXX --job-id job-XXXX

# Submit the encode job pointing to the downloaded frames
deadline bundle submit ffmpeg_encode_video/ \
  -p InputDir=/path/to/downloaded/frames \
  -p InputFilePattern="render.####.png" \
  -p StartFrame=1 \
  -p EndFrame=250
```

## Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| InputDir | *(required)* | Directory containing the numbered image sequence |
| InputFilePattern | `output_####.png` | Filename pattern using `####` for frame numbers |
| StartFrame | `1` | First frame number in the sequence |
| EndFrame | `100` | Last frame number in the sequence |
| OutputDir | `output` | Directory for the output video |
| OutputFileName | `output.mp4` | Name of the output video file |
| FrameRate | `24` | Playback frame rate in fps |
| EncodingPreset | `slower` | FFmpeg x264 preset (ultrafast to veryslow) |
| ConstantRateFactor | `18` | Quality setting: 0 = lossless, 51 = worst, 17-18 ≈ visually lossless |

## Adding video encoding to a multi-step job

This job bundle can serve as a reference for adding a video encoding step to an existing render job. The key elements to copy into your own job template are:

1. The `CondaChannels` parameter set to `conda-forge` (or add `conda-forge` alongside your existing channels)
2. The `EncodeVideo` step with its embedded bash script
3. A `dependencies` entry so the encode step waits for rendering to complete:

```yaml
steps:
  - name: Render
    # ... your render step ...

  - name: EncodeVideo
    dependencies:
      - dependsOn: Render
    # ... encode step from this template ...
```

See the [turntable_with_maya_arnold](../turntable_with_maya_arnold) sample for a complete example of a multi-step pipeline that includes video encoding.
