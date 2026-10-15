"""Step 2: extract an action trajectory from one generated video.

This is the half that DreamGen does with a separately trained IDM model. Cosmos 3
carries inverse dynamics in the same checkpoint, so the video to action step is a
second request to the same server rather than a second model.

One task handles one clip, reading the MP4 that step 1 wrote and writing an
action JSON beside it.

Nothing in the request assumes the video was synthetic, so the same call labels
real footage. Running this over a directory of real video still needs work
though: the input is located through the dreams/NAME.json summaries step 1
writes, so that lookup has to be replaced or those summaries synthesized.
"""

import argparse
import json
import math
import os
import sys

import cosmos3_client as c3


def flatten(value, out, limit):
    """Collect leaf numbers from an arbitrarily nested array, up to `limit`."""
    if len(out) >= limit:
        return
    if isinstance(value, list):
        for item in value:
            flatten(item, out, limit)
            if len(out) >= limit:
                return
    elif isinstance(value, (int, float)) and not isinstance(value, bool):
        out.append(float(value))


def check_action(action, expected_chunk, expected_dim, clip):
    """Fail on an action payload that is shaped wrong or carries no signal."""
    if not isinstance(action, dict) or "data" not in action:
        raise SystemExit(
            "clip %s: response carried no action.data:\n%s"
            % (clip, json.dumps(action, indent=2)[:4000])
        )

    shape = action.get("shape")
    if isinstance(shape, list) and len(shape) >= 2:
        chunk, dim = int(shape[-2]), int(shape[-1])
        if dim != expected_dim:
            raise SystemExit(
                "clip %s: server returned action dim %d but RawActionDim=%d was "
                "requested. Fix RawActionDim to match the embodiment: the "
                "dimensionality is a property of the embodiment, not a free "
                "choice." % (clip, dim, expected_dim)
            )
        if chunk != expected_chunk:
            raise SystemExit(
                "clip %s: server returned %d action steps but ActionChunkSize=%d "
                "was requested" % (clip, chunk, expected_chunk)
            )
    else:
        print("warning: action payload reported no usable shape: %r" % (shape,))

    # An all-zero or non-finite trajectory passes every other check: the request
    # succeeds and the file is written, but no policy can learn from it.
    sample = []
    flatten(action["data"], sample, 20000)
    if not sample:
        raise SystemExit("clip %s: action.data holds no numbers" % clip)
    if not all(math.isfinite(v) for v in sample):
        raise SystemExit("clip %s: action.data contains NaN or inf" % clip)
    if all(v == 0.0 for v in sample):
        raise SystemExit(
            "clip %s: every one of %d sampled action values is zero. The server "
            "reported success but predicted no motion." % (clip, len(sample))
        )
    return sample


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--clip-index", type=int, required=True, help="1-based")
    parser.add_argument("--expected-clips", type=int, required=True)
    parser.add_argument("--prompt", required=True)
    parser.add_argument("--domain-name", required=True)
    parser.add_argument("--view-point", required=True)
    parser.add_argument("--action-chunk-size", type=int, required=True)
    parser.add_argument("--raw-action-dim", type=int, required=True)
    parser.add_argument("--image-size", type=int, required=True)
    parser.add_argument("--num-frames", type=int, required=True)
    parser.add_argument("--fps", type=int, required=True)
    parser.add_argument("--num-inference-steps", type=int, required=True)
    parser.add_argument("--guidance-scale", type=float, required=True)
    parser.add_argument("--flow-shift", type=float, required=True)
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--guardrails", default="true", choices=["true", "false"])
    parser.add_argument("--request-timeout", type=int, default=3600)
    args = parser.parse_args()

    base_url = c3.base_url_from_env()
    dreams_dir = os.path.join(args.output_dir, "dreams")

    # Find this task's clip through the summary step 1 wrote, so the two steps
    # agree without re-reading the manifest.
    #
    # Match on the recorded clip_index rather than on sorted position. Both give
    # every clip exactly one task, but only the index keeps step 2's ClipIndex
    # paired with step 1's, which is what makes --seed reproducible per clip and
    # makes logs/actions_NNNN.log describe the clip its name implies.
    summaries = sorted(
        f for f in os.listdir(dreams_dir) if f.endswith(".json")
    ) if os.path.isdir(dreams_dir) else []
    if len(summaries) != args.expected_clips:
        raise SystemExit(
            "expected %d clip summaries under %s but found %d. Step 1 did not "
            "complete, or its outputs did not sync to this worker."
            % (args.expected_clips, dreams_dir, len(summaries))
        )
    summary = None
    for name in summaries:
        with open(os.path.join(dreams_dir, name), "r", encoding="utf-8") as handle:
            candidate = json.load(handle)
        if candidate.get("clip_index") == args.clip_index:
            summary = candidate
            break
    if summary is None:
        raise SystemExit(
            "no summary under %s records clip_index=%d, though %d summaries are "
            "present. Step 1 wrote a set that does not cover this task's index."
            % (dreams_dir, args.clip_index, len(summaries))
        )
    clip = summary["clip"]
    video_path = os.path.join(args.output_dir, summary["video"])

    if not os.path.isfile(video_path):
        raise SystemExit("clip %s: video missing at %s" % (clip, video_path))
    size = os.path.getsize(video_path)
    if size < 8192:
        raise SystemExit("clip %s: video is only %d bytes" % (clip, size))

    actions_dir = os.path.join(args.output_dir, "actions")
    os.makedirs(actions_dir, exist_ok=True)

    extra_params = {
        "action_mode": "inverse_dynamics",
        "domain_name": args.domain_name,
        "action_chunk_size": args.action_chunk_size,
        "image_size": args.image_size,
        "view_point": args.view_point,
        "raw_action_dim": args.raw_action_dim,
        "guardrails": args.guardrails == "true",
    }
    fields = {
        "prompt": args.prompt,
        "num_frames": str(args.num_frames),
        "fps": str(args.fps),
        "num_inference_steps": str(args.num_inference_steps),
        "guidance_scale": str(args.guidance_scale),
        "flow_shift": str(args.flow_shift),
        "seed": str(args.seed),
        "extra_params": json.dumps(extra_params),
    }
    with open(video_path, "rb") as handle:
        payload = handle.read()
    files = {"input_reference": (os.path.basename(video_path), payload, "video/mp4")}

    print("clip %d/%d name=%s video=%s (%d bytes)" % (
        args.clip_index, args.expected_clips, clip, video_path, size))
    print("extra_params: %s" % json.dumps(extra_params))

    job_id = c3.submit_async(base_url, fields, files)
    final = c3.poll_async(base_url, job_id, timeout_seconds=args.request_timeout)

    action = final.get("action")
    sample = check_action(action, args.action_chunk_size, args.raw_action_dim, clip)

    action_path = os.path.join(actions_dir, clip + ".json")
    with open(action_path, "w", encoding="utf-8") as handle:
        json.dump(action, handle, indent=2)

    meta = {
        "clip": clip,
        "clip_index": args.clip_index,
        "action": os.path.relpath(action_path, args.output_dir),
        "video": summary["video"],
        "shape": action.get("shape"),
        "dtype": action.get("dtype"),
        "sampled_values": len(sample),
        "domain_name": args.domain_name,
        "view_point": args.view_point,
        "raw_action_dim": args.raw_action_dim,
        "action_chunk_size": args.action_chunk_size,
        "fps": args.fps,
        # Two different prompts, and the merge step needs the first one.
        # clip_prompt is the clip's language instruction, which step 1 recorded.
        # action_prompt is the job-wide system prompt sent with the inverse-dynamics
        # request. Building the LeRobot task from the system prompt collapses
        # tasks.jsonl to a single row and loses the per-clip instruction.
        "clip_prompt": summary.get("prompt"),
        "action_prompt": args.prompt,
    }
    with open(os.path.join(actions_dir, clip + ".meta.json"), "w", encoding="utf-8") as handle:
        json.dump(meta, handle, indent=2)

    print("clip %s actions: shape=%s dtype=%s" % (clip, action.get("shape"), action.get("dtype")))
    return 0


if __name__ == "__main__":
    sys.exit(main())
