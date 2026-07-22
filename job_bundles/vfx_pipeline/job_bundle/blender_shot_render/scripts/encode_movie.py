"""Encode a rendered PNG sequence into an H.264 review movie — using Blender.

The pipeline standardizes on a single DCC (Blender) and stages nothing else, so
we encode with Blender's bundled FFmpeg writer instead of a separate ffmpeg
binary. The frames are loaded as an image strip in the Video Sequence Editor and
rendered out as an MP4/H.264.

Run by the GenerateMovie step:

    blender --background --python encode_movie.py -- \\
        --frames-dir /path/frames --prefix shot_ \\
        --frame-range 1-48 --frame-rate 24 --output /path/shot.mp4
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
p.add_argument("--frame-rate", type=int, required=True)
p.add_argument("--output", required=True)
args = p.parse_args(argv)

start_s, end_s = args.frame_range.split("-")
start, end = int(start_s), int(end_s)
count = end - start + 1

first_file = f"{args.prefix}{start:04d}.png"
first_path = os.path.join(args.frames_dir, first_file)
if not os.path.isfile(first_path):
    print(f"ERROR: first frame not found: {first_path}", file=sys.stderr)
    sys.exit(1)

scene = bpy.context.scene
scene.render.fps = args.frame_rate
scene.frame_start = 1
scene.frame_end = count

# Match the output resolution to the source frames. Headless Blender starts with
# a 1920x1080 default scene, and the VSE renders the image strip at the scene
# resolution — so without this a shot rendered at any other size (e.g. Moonrise's
# 2048x1080) would be squeezed to 1920x1080. Read the first frame's real
# dimensions and set the render resolution from them.
_img = bpy.data.images.load(first_path)
scene.render.resolution_x, scene.render.resolution_y = _img.size
bpy.data.images.remove(_img)

# Build a sequence from the PNGs.
if not scene.sequence_editor:
    scene.sequence_editor_create()
seq = scene.sequence_editor

strip = seq.sequences.new_image(
    name="frames", filepath=first_path, channel=1, frame_start=1,
)
for n in range(start + 1, end + 1):
    strip.elements.append(f"{args.prefix}{n:04d}.png")

# FFmpeg / H.264 output settings (Blender's bundled encoder).
scene.render.image_settings.file_format = "FFMPEG"
scene.render.ffmpeg.format = "MPEG4"
scene.render.ffmpeg.codec = "H264"
scene.render.ffmpeg.constant_rate_factor = "HIGH"
scene.render.ffmpeg.ffmpeg_preset = "GOOD"
scene.render.ffmpeg.gopsize = 12
scene.render.resolution_percentage = 100
scene.render.filepath = args.output

os.makedirs(os.path.dirname(os.path.abspath(args.output)), exist_ok=True)
print(f"Encoding {count} frames @ {args.frame_rate}fps -> {args.output}")
bpy.ops.render.render(animation=True)

# Blender appends frame numbers for some containers; normalize to the exact name.
if not os.path.isfile(args.output):
    guess = f"{os.path.splitext(args.output)[0]}0001-{count:04d}.mp4"
    if os.path.isfile(guess):
        os.replace(guess, args.output)
print(f"Wrote {args.output}")
