"""Make a poster-frame thumbnail from the rendered sequence — using Blender.

Takes the middle frame of the range (a representative still, not an extra
render, so it costs no render time) and writes a downscaled JPG via Blender's
image API. Like the movie encode, this avoids needing any tool other than the
one staged DCC.

Run by the GenerateThumbnail step:

    blender --background --python make_thumbnail.py -- \\
        --frames-dir /path/frames --prefix shot_ \\
        --frame-range 1-48 --max-width 640 --output /path/thumbnail.jpg
"""
import argparse
import os
import sys

import bpy

argv = sys.argv[sys.argv.index("--") + 1:]
p = argparse.ArgumentParser()
p.add_argument("--frames-dir", required=True)
p.add_argument("--prefix", required=True)
p.add_argument("--frame-range", required=True)
p.add_argument("--max-width", type=int, default=640)
p.add_argument("--output", required=True)
args = p.parse_args(argv)

# Contiguous "start-end", or a single frame like "5".
if "-" in args.frame_range:
    start_s, end_s = args.frame_range.split("-")
    start, end = int(start_s), int(end_s)
else:
    start = end = int(args.frame_range)
mid = (start + end) // 2
src = os.path.join(args.frames_dir, f"{args.prefix}{mid:04d}.png")
if not os.path.isfile(src):
    print(f"ERROR: mid frame not found: {src}", file=sys.stderr)
    sys.exit(1)
print(f"Using mid frame {mid} as thumbnail source: {src}")

img = bpy.data.images.load(src)
width, height = img.size
if width > args.max_width:
    new_w = args.max_width
    new_h = max(1, int(height * args.max_width / width))
    img.scale(new_w, new_h)

img.file_format = "JPEG"
os.makedirs(os.path.dirname(os.path.abspath(args.output)), exist_ok=True)
img.filepath_raw = args.output
img.save()
print(f"Wrote {args.output}")
