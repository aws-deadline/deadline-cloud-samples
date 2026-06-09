"""Download output files from a source job and encode them into a video with FFmpeg."""
import json
import os
import subprocess
import sys
import tempfile
from collections import Counter
from pathlib import Path

from deadline.job_attachments.download import OutputDownloader
from deadline.job_attachments.models import (
    FileConflictResolution,
    JobAttachmentS3Settings,
)

IMAGE_EXTENSIONS = {"png", "exr", "jpg", "jpeg", "tga", "tiff", "tif", "dpx", "hdr", "bmp"}


def download_outputs(s3_settings_file, source_job_id, source_step_id, download_dir):
    """Download output files from the source job."""
    with open(s3_settings_file) as f:
        s3_cfg = json.load(f)

    s3_settings = JobAttachmentS3Settings(
        s3BucketName=s3_cfg["s3BucketName"],
        rootPrefix=s3_cfg["rootPrefix"],
    )

    downloader = OutputDownloader(
        s3_settings=s3_settings,
        farm_id=os.environ["DEADLINE_FARM_ID"],
        queue_id=os.environ["DEADLINE_QUEUE_ID"],
        job_id=source_job_id,
        step_id=source_step_id or None,
    )
    output_roots = list(downloader.get_output_paths_by_root().keys())
    for root in output_roots:
        downloader.set_root_path(root, download_dir)
    stats = downloader.download_job_output(
        file_conflict_resolution=FileConflictResolution.OVERWRITE,
    )
    print(f"Downloaded {stats.processed_files} files ({stats.processed_bytes} bytes)")


def detect_image_extension(download_dir):
    """Find the most common image extension in the download directory."""
    counts = Counter()
    for path in Path(download_dir).rglob("*"):
        if path.is_file() and path.suffix.lstrip(".").lower() in IMAGE_EXTENSIONS:
            counts[path.suffix.lstrip(".").lower()] += 1

    if not counts:
        files = list(Path(download_dir).rglob("*"))[:20]
        print("ERROR: No image files found. Available files:")
        for f in files:
            print(f"  {f}")
        sys.exit(1)

    ext, count = counts.most_common(1)[0]
    print(f"Detected {count} .{ext} files")
    return ext


def encode_video(download_dir, ext, frame_rate, pixel_format, preset, crf, resolution, output_path):
    """Build a concat file and encode with FFmpeg."""
    images = sorted(Path(download_dir).rglob(f"*.{ext}"))

    concat_file = tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False)
    for img in images:
        concat_file.write(f"file '{img}'\n")
    concat_file.close()

    print(f"First images: {[str(p) for p in images[:3]]}")
    print(f"Last images: {[str(p) for p in images[-3:]]}")

    scale_filter = "scale=in_color_matrix=bt709:out_color_matrix=bt709"
    if resolution:
        width, height = resolution.split("x")
        scale_filter = f"scale={width}:{height}:in_color_matrix=bt709:out_color_matrix=bt709"

    cmd = [
        "ffmpeg", "-y",
        "-f", "concat", "-safe", "0",
        "-r", str(frame_rate),
        "-i", concat_file.name,
        "-pix_fmt", pixel_format,
        "-vf", scale_filter,
        "-c:v", "libx264",
        "-preset", preset,
        "-crf", str(crf),
        "-color_range", "tv",
        "-colorspace", "bt709",
        "-color_primaries", "bt709",
        "-color_trc", "iec61966-2-1",
        "-movflags", "faststart",
        str(output_path),
    ]

    print("Encoding video...")
    subprocess.run(cmd, check=True)
    os.unlink(concat_file.name)
    print(f"Video saved to {output_path}")


def main():
    source_job_id = sys.argv[1]
    source_step_id = sys.argv[2]
    s3_settings_file = sys.argv[3]
    frame_rate = int(sys.argv[4])
    pixel_format = sys.argv[5]
    preset = sys.argv[6]
    crf = int(sys.argv[7])
    resolution = sys.argv[8]
    output_dir = sys.argv[9]
    output_filename = sys.argv[10]

    download_dir = tempfile.mkdtemp()
    output_path = Path(output_dir) / output_filename
    output_path.parent.mkdir(parents=True, exist_ok=True)

    print(f"Downloading outputs from source job {source_job_id}...")
    download_outputs(s3_settings_file, source_job_id, source_step_id, download_dir)

    ext = detect_image_extension(download_dir)
    encode_video(download_dir, ext, frame_rate, pixel_format, preset, crf, resolution, output_path)


if __name__ == "__main__":
    main()
