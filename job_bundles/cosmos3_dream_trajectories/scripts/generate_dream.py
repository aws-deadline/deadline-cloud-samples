"""Step 1: generate one synthetic robot video from an image plus a language prompt.

One task handles one clip. The clip list comes from a JSON manifest delivered by
job attachments, and the task's ClipIndex selects its entry, so N tasks fill one
flat output directory with no filename collisions.

This is the "dream" half of the DreamGen workflow. It does not produce action
trajectories; extract_actions.py does that in a separate step, from the videos
this step writes.
"""

import argparse
import json
import os
import shutil
import subprocess
import sys

import cosmos3_client as c3


def load_manifest(path, expected_clips):
    with open(path, "r", encoding="utf-8") as handle:
        manifest = json.load(handle)
    if not isinstance(manifest, dict) or "clips" not in manifest:
        raise SystemExit("manifest %s has no top-level 'clips' array" % path)
    clips = manifest["clips"]
    if not isinstance(clips, list) or not clips:
        raise SystemExit("manifest %s 'clips' is empty or not an array" % path)
    # The parameter space size is fixed at submit time, so a manifest that has
    # since changed length would silently drop clips off the end or index past
    # it. Refuse rather than generate a partial dataset.
    if len(clips) != expected_clips:
        raise SystemExit(
            "manifest %s lists %d clips but the job was submitted with "
            "ClipCount=%d. Resubmit with ClipCount=%d."
            % (path, len(clips), expected_clips, len(clips))
        )
    # Output paths come from the sanitized name, so two entries that sanitize to
    # the same stem overwrite each other. "pick cube" and "pick_cube" both become
    # pick_cube.mp4. The later upload wins and step 2 then reports the wrong
    # cause: "expected N clip summaries ... found N-1". Fail here instead.
    seen = {}
    for index, clip in enumerate(clips, start=1):
        stem = clip_name(clip, index)
        if stem in seen:
            raise SystemExit(
                "manifest %s has two clips whose names both become %r after "
                "sanitizing: clip %d (%r) and clip %d (%r). Output filenames come "
                "from the sanitized name, so these would overwrite each other. "
                "Give them names that differ by more than punctuation."
                % (path, stem, seen[stem][0], seen[stem][1], index,
                   clip.get("name"))
            )
        seen[stem] = (index, clip.get("name"))
    return clips


def clip_name(clip, index):
    """Map a clip's name to a filename-safe stem.

    Names reach the filesystem, so every character outside [A-Za-z0-9-_] becomes
    an underscore. A name that keeps no alphanumeric character at all is
    rejected rather than silently turned into a row of underscores, because two
    such clips would collide on one output file.
    """
    name = str(clip.get("name") or "clip%03d" % index)
    safe = "".join(ch if (ch.isalnum() or ch in "-_") else "_" for ch in name)
    if not any(ch.isalnum() for ch in safe):
        raise SystemExit(
            "clip %d has the name %r, which keeps no alphanumeric character "
            "after sanitizing and so cannot be a unique filename" % (index, name)
        )
    return safe


def resolve_image(manifest_path, clip, index):
    raw = clip.get("image")
    if not raw:
        raise SystemExit("clip %d (%s) has no 'image'" % (index, clip_name(clip, index)))
    if os.path.isabs(raw):
        path = raw
    else:
        path = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(manifest_path)), raw))
    if not os.path.isfile(path):
        manifest_dir = os.path.dirname(os.path.abspath(manifest_path))
        try:
            siblings = sorted(os.listdir(manifest_dir))[:20]
        except OSError:
            siblings = []
        raise SystemExit(
            "clip %d (%s) image not found: %s\n"
            "Job attachments uploads exactly what the submitter declared. If the "
            "manifest arrived but its images did not, the job declared the "
            "manifest file instead of the directory holding both: submit with "
            "ClipDir pointing at that directory.\n"
            "Contents of %s: %s"
            % (index, clip_name(clip, index), path, manifest_dir, siblings or "<empty or unreadable>")
        )
    if os.path.getsize(path) == 0:
        raise SystemExit("clip %d image is zero bytes: %s" % (index, path))
    return path


def probe_frame_count(video_path):
    """Return the decoded frame count, or None when ffprobe is unavailable.

    The host image is not guaranteed to carry ffmpeg, so a missing ffprobe is
    not an error. A present ffprobe that reports too few frames is.
    """
    ffprobe = shutil.which("ffprobe")
    if not ffprobe:
        return None
    try:
        out = subprocess.run(
            [
                ffprobe,
                "-v",
                "error",
                "-select_streams",
                "v:0",
                "-count_frames",
                "-show_entries",
                "stream=nb_read_frames",
                "-of",
                "default=nokey=1:noprint_wrappers=1",
                video_path,
            ],
            capture_output=True,
            text=True,
            timeout=300,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    text = (out.stdout or "").strip()
    return int(text) if text.isdigit() else None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--clip-index", type=int, required=True, help="1-based")
    parser.add_argument("--expected-clips", type=int, required=True)
    parser.add_argument("--size", default="", help="WxH; empty means the server default")
    parser.add_argument("--num-frames", type=int, required=True)
    parser.add_argument("--fps", type=int, required=True)
    parser.add_argument("--num-inference-steps", type=int, required=True)
    parser.add_argument("--guidance-scale", type=float, required=True)
    parser.add_argument("--flow-shift", type=float, required=True)
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--guardrails", default="true", choices=["true", "false"])
    parser.add_argument("--request-timeout", type=int, default=3600)
    args = parser.parse_args()

    if args.clip_index < 1 or args.clip_index > args.expected_clips:
        raise SystemExit(
            "clip index %d is outside 1-%d" % (args.clip_index, args.expected_clips)
        )

    base_url = c3.base_url_from_env()
    clips = load_manifest(args.manifest, args.expected_clips)
    clip = clips[args.clip_index - 1]
    name = clip_name(clip, args.clip_index)
    image_path = resolve_image(args.manifest, clip, args.clip_index)

    prompt = clip.get("prompt")
    if not prompt:
        raise SystemExit("clip %d (%s) has no 'prompt'" % (args.clip_index, name))

    dreams_dir = os.path.join(args.output_dir, "dreams")
    os.makedirs(dreams_dir, exist_ok=True)
    video_path = os.path.join(dreams_dir, name + ".mp4")
    summary_path = os.path.join(dreams_dir, name + ".json")

    # The model card passes JSON-upsampled prompts as JSON strings. A plain
    # sentence is accepted too, so allow either: dump dicts and lists, pass
    # strings through.
    def as_field(value):
        return json.dumps(value) if isinstance(value, (dict, list)) else str(value)

    fields = {
        "prompt": as_field(prompt),
        "num_frames": str(args.num_frames),
        "fps": str(args.fps),
        "num_inference_steps": str(args.num_inference_steps),
        "guidance_scale": str(args.guidance_scale),
        "flow_shift": str(args.flow_shift),
        "seed": str(args.seed),
        "extra_params": json.dumps(
            {
                "use_resolution_template": False,
                "use_duration_template": False,
                "guardrails": args.guardrails == "true",
            }
        ),
    }
    if clip.get("negative_prompt"):
        fields["negative_prompt"] = as_field(clip["negative_prompt"])
    if args.size:
        fields["size"] = args.size

    with open(image_path, "rb") as handle:
        payload = handle.read()
    files = {
        "input_reference": (os.path.basename(image_path), payload, c3.guess_mime(image_path, "image/png"))
    }

    print("clip %d/%d name=%s image=%s" % (args.clip_index, args.expected_clips, name, image_path))
    print("prompt: %s" % str(prompt)[:300])
    video = c3.generate_sync(base_url, fields, files, timeout=args.request_timeout)

    with open(video_path, "wb") as handle:
        handle.write(video)

    # Assert on the artifact, not on the exit code. A server that returns a
    # tiny well-formed MP4 has still failed to generate anything useful.
    size = os.path.getsize(video_path)
    if size < 8192:
        raise SystemExit(
            "wrote only %d bytes to %s; that is not a usable clip" % (size, video_path)
        )
    frames = probe_frame_count(video_path)
    if frames is not None and frames < args.num_frames:
        raise SystemExit(
            "%s holds %d frames but %d were requested" % (video_path, frames, args.num_frames)
        )

    summary = {
        "clip": name,
        "clip_index": args.clip_index,
        "video": os.path.relpath(video_path, args.output_dir),
        "bytes": size,
        "frames_requested": args.num_frames,
        "frames_probed": frames,
        "fps": args.fps,
        "seed": args.seed,
        "image": os.path.basename(image_path),
        "prompt": prompt,
    }
    with open(summary_path, "w", encoding="utf-8") as handle:
        json.dump(summary, handle, indent=2)

    print(
        "clip %s complete: %d bytes, %s frames"
        % (name, size, frames if frames is not None else "unprobed")
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
