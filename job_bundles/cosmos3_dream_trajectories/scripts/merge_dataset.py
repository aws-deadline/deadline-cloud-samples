"""Step 3: assemble the per-clip actions into one dataset and verify it.

Each per-clip task asserts on its own outputs, but only a merge sees whether the
dataset as a whole is complete. So a short run fails the job here, rather than
leaving a half-populated directory that looks like a success.

Output layout, which follows the LeRobot convention DreamGen's IDM dump also
writes:

    lerobot/
      meta/info.json        dataset-level metadata
      meta/tasks.jsonl      one row per distinct language instruction
      meta/episodes.jsonl   one row per clip
      data/chunk-000/episode_NNNNNN.{parquet,json}
      videos/observation.images.main/chunk-000/episode_NNNNNN.mp4

Task strings are prefixed `<DREAM>` so synthetic episodes stay distinguishable
from teleoperated ones after the two are mixed, which is what GR00T-Dreams does
for the same reason.

Standard library only, except for an optional pyarrow. LeRobot reads parquet; if
pyarrow is absent this step writes JSON instead and says so, rather than
pretending the dataset is loadable.
"""

import argparse
import json
import os
import shutil
import sys

try:
    import pyarrow  # noqa: F401
    import pyarrow.parquet as pq

    HAVE_PYARROW = True
except ImportError:
    HAVE_PYARROW = False


def rows_from_action(action, raw_action_dim):
    """Turn an action payload into a flat list of per-step action vectors."""
    data = action["data"]
    shape = action.get("shape")
    if isinstance(shape, list) and len(shape) >= 2 and int(shape[-1]) == raw_action_dim:
        # Walk down to the innermost lists of length raw_action_dim.
        steps = []

        def descend(node):
            if (
                isinstance(node, list)
                and node
                and all(isinstance(v, (int, float)) and not isinstance(v, bool) for v in node)
            ):
                if len(node) == raw_action_dim:
                    steps.append([float(v) for v in node])
                return
            if isinstance(node, list):
                for item in node:
                    descend(item)

        descend(data)
        if steps:
            return steps

    # Fall back to chunking a flat stream.
    flat = []

    def collect(node):
        if isinstance(node, list):
            for item in node:
                collect(item)
        elif isinstance(node, (int, float)) and not isinstance(node, bool):
            flat.append(float(node))

    collect(data)
    if not flat:
        return []
    if len(flat) % raw_action_dim != 0:
        raise SystemExit(
            "action stream holds %d values, which is not a multiple of "
            "raw_action_dim=%d; cannot reshape into steps"
            % (len(flat), raw_action_dim)
        )
    return [flat[i : i + raw_action_dim] for i in range(0, len(flat), raw_action_dim)]


def merge_videos_only(args, out, dreams_dir):
    """Assemble the dataset when step 2 was skipped: videos and metadata only.

    This is DreamGen's stage 2 output, which an inverse-dynamics model consumes,
    so it gets the same layout and completeness check as the action path. It has
    no `action` feature. info.json records that rather than shipping a column of
    zeros that would look trainable.
    """
    summaries = sorted(f for f in os.listdir(dreams_dir) if f.endswith(".json"))
    if len(summaries) != args.expected_clips:
        raise SystemExit(
            "found %d of %d expected clip summaries under %s. Every clip that "
            "reported success writes one, so a gap means a task failed silently."
            % (len(summaries), args.expected_clips, dreams_dir)
        )

    root = os.path.join(out, "lerobot")
    video_dir = os.path.join(root, "videos", args.video_key, "chunk-000")
    meta_dir = os.path.join(root, "meta")
    for path in (video_dir, meta_dir):
        os.makedirs(path, exist_ok=True)

    task_index = {}
    episodes = []
    for episode_index, summary_name in enumerate(summaries):
        with open(os.path.join(dreams_dir, summary_name), "r", encoding="utf-8") as handle:
            summary = json.load(handle)
        clip = summary["clip"]
        source_video = os.path.join(out, summary["video"])
        if not os.path.isfile(source_video):
            raise SystemExit("clip %s: video missing at %s" % (clip, source_video))
        size = os.path.getsize(source_video)
        if size < 8192:
            raise SystemExit("clip %s: video is only %d bytes" % (clip, size))

        task = "<DREAM> " + str(summary.get("prompt", "")).strip()
        if task not in task_index:
            task_index[task] = len(task_index)

        stem = "episode_%06d" % episode_index
        shutil.copy2(source_video, os.path.join(video_dir, stem + ".mp4"))
        episodes.append(
            {
                "episode_index": episode_index,
                "clip": clip,
                "tasks": [task],
                "length": None,
                "frames_requested": summary.get("frames_requested"),
                "frames_probed": summary.get("frames_probed"),
            }
        )
        print("episode %d <- %s: video only (%d bytes)" % (episode_index, clip, size))

    with open(os.path.join(meta_dir, "episodes.jsonl"), "w", encoding="utf-8") as handle:
        for row in episodes:
            handle.write(json.dumps(row) + "\n")
    with open(os.path.join(meta_dir, "tasks.jsonl"), "w", encoding="utf-8") as handle:
        for task, index in sorted(task_index.items(), key=lambda kv: kv[1]):
            handle.write(json.dumps({"task_index": index, "task": task}) + "\n")

    info = {
        "codebase_version": "v2.1",
        "robot_type": "unlabelled-synthetic-video",
        "total_episodes": len(episodes),
        "total_frames": None,
        "total_tasks": len(task_index),
        "total_videos": len(episodes),
        "chunks_size": 1000,
        "fps": args.fps,
        "video_path": "videos/{video_key}/chunk-{episode_chunk:03d}/episode_{episode_index:06d}.mp4",
        "features": {args.video_key: {"dtype": "video", "shape": None}},
        "has_actions": False,
        "next_step": (
            "Actions were not extracted. Run an inverse-dynamics model trained on "
            "your embodiment over videos/, for example GR00T-Dreams' "
            "seonghyeonye/IDM_so100 for SO-100 and SO-101 class arms."
        ),
    }
    with open(os.path.join(meta_dir, "info.json"), "w", encoding="utf-8") as handle:
        json.dump(info, handle, indent=2)

    summary = {
        "episodes": len(episodes),
        "total_steps": 0,
        "tasks": len(task_index),
        "action_mode": "none",
        "has_actions": False,
        "fps": args.fps,
        "dataset_root": os.path.relpath(root, out),
    }
    with open(os.path.join(out, "dream_summary.json"), "w", encoding="utf-8") as handle:
        json.dump(summary, handle, indent=2)

    print("")
    print("merged %d episodes, videos only, %d task(s)" % (len(episodes), len(task_index)))
    print("dataset: %s" % root)
    print("NOTE: no action trajectories. ActionMode was none, so this is the")
    print("stage-2 artifact: feed videos/ to an IDM for your embodiment.")
    return 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--expected-clips", type=int, required=True)
    parser.add_argument("--raw-action-dim", type=int, required=True)
    parser.add_argument("--fps", type=int, required=True)
    parser.add_argument("--video-key", default="observation.images.main")
    parser.add_argument(
        "--action-mode",
        default="inverse_dynamics",
        choices=["none", "inverse_dynamics"],
        help="none merges a video-only dataset, because step 2 was skipped.",
    )
    parser.add_argument(
        "--min-steps-per-episode",
        type=int,
        default=1,
        help="Fail the job when any episode carries fewer steps than this.",
    )
    args = parser.parse_args()

    out = args.output_dir
    dreams_dir = os.path.join(out, "dreams")
    actions_dir = os.path.join(out, "actions")

    if not os.path.isdir(dreams_dir):
        raise SystemExit(
            "no dreams directory at %s. Step 1 produced nothing, or its outputs "
            "did not sync to this worker." % dreams_dir
        )

    if args.action_mode == "none":
        return merge_videos_only(args, out, dreams_dir)

    if not os.path.isdir(actions_dir):
        raise SystemExit(
            "no actions directory at %s. The upstream step produced nothing, or "
            "its outputs did not sync to this worker." % actions_dir
        )

    metas = sorted(f for f in os.listdir(actions_dir) if f.endswith(".meta.json"))
    if len(metas) != args.expected_clips:
        missing = args.expected_clips - len(metas)
        raise SystemExit(
            "found %d of %d expected clips under %s (%d missing). Every clip "
            "that reported success writes a .meta.json, so a gap here means a "
            "task failed silently." % (len(metas), args.expected_clips, actions_dir, missing)
        )

    root = os.path.join(out, "lerobot")
    data_dir = os.path.join(root, "data", "chunk-000")
    video_dir = os.path.join(root, "videos", args.video_key, "chunk-000")
    meta_dir = os.path.join(root, "meta")
    for path in (data_dir, video_dir, meta_dir):
        os.makedirs(path, exist_ok=True)

    task_index = {}
    episodes = []
    total_steps = 0

    for episode_index, meta_name in enumerate(metas):
        with open(os.path.join(actions_dir, meta_name), "r", encoding="utf-8") as handle:
            meta = json.load(handle)
        clip = meta["clip"]
        with open(os.path.join(out, meta["action"]), "r", encoding="utf-8") as handle:
            action = json.load(handle)

        steps = rows_from_action(action, args.raw_action_dim)
        if len(steps) < args.min_steps_per_episode:
            raise SystemExit(
                "clip %s yielded %d action steps, below the floor of %d"
                % (clip, len(steps), args.min_steps_per_episode)
            )

        # The clip's instruction, not the inverse-dynamics system prompt. Falls
        # back to the dream summary for metas written before clip_prompt existed.
        clip_prompt = meta.get("clip_prompt")
        if not clip_prompt:
            summary_path = os.path.join(dreams_dir, "%s.json" % clip)
            if os.path.isfile(summary_path):
                with open(summary_path, "r", encoding="utf-8") as handle:
                    clip_prompt = json.load(handle).get("prompt")
        if not clip_prompt:
            clip_prompt = meta.get("action_prompt") or meta.get("prompt", "")
        task = "<DREAM> " + str(clip_prompt).strip()
        if task not in task_index:
            task_index[task] = len(task_index)

        stem = "episode_%06d" % episode_index
        rows = {
            "action": steps,
            "timestamp": [i / float(args.fps) for i in range(len(steps))],
            "frame_index": list(range(len(steps))),
            "episode_index": [episode_index] * len(steps),
            "index": [total_steps + i for i in range(len(steps))],
            "task_index": [task_index[task]] * len(steps),
        }
        if HAVE_PYARROW:
            pq.write_table(pyarrow.table(rows), os.path.join(data_dir, stem + ".parquet"))
        else:
            with open(os.path.join(data_dir, stem + ".json"), "w", encoding="utf-8") as handle:
                json.dump(rows, handle)

        source_video = os.path.join(out, meta["video"])
        if not os.path.isfile(source_video):
            raise SystemExit("clip %s: video missing at %s" % (clip, source_video))
        shutil.copy2(source_video, os.path.join(video_dir, stem + ".mp4"))

        episodes.append(
            {
                "episode_index": episode_index,
                "clip": clip,
                "tasks": [task],
                "length": len(steps),
            }
        )
        total_steps += len(steps)
        print("episode %d <- %s: %d steps" % (episode_index, clip, len(steps)))

    if total_steps == 0:
        raise SystemExit(
            "merged 0 action steps across %d clips. Every clip reported success "
            "and the dataset is still empty." % len(metas)
        )

    with open(os.path.join(meta_dir, "episodes.jsonl"), "w", encoding="utf-8") as handle:
        for row in episodes:
            handle.write(json.dumps(row) + "\n")
    with open(os.path.join(meta_dir, "tasks.jsonl"), "w", encoding="utf-8") as handle:
        for task, index in sorted(task_index.items(), key=lambda kv: kv[1]):
            handle.write(json.dumps({"task_index": index, "task": task}) + "\n")

    info = {
        "codebase_version": "v2.1",
        "robot_type": "cosmos3-inverse-dynamics",
        "total_episodes": len(episodes),
        "total_frames": total_steps,
        "total_tasks": len(task_index),
        "total_videos": len(episodes),
        "chunks_size": 1000,
        "fps": args.fps,
        "data_path": "data/chunk-{episode_chunk:03d}/episode_{episode_index:06d}."
        + ("parquet" if HAVE_PYARROW else "json"),
        "video_path": "videos/{video_key}/chunk-{episode_chunk:03d}/episode_{episode_index:06d}.mp4",
        "features": {
            "action": {"dtype": "float32", "shape": [args.raw_action_dim]},
            args.video_key: {"dtype": "video", "shape": None},
        },
        "data_format": "parquet" if HAVE_PYARROW else "json",
    }
    with open(os.path.join(meta_dir, "info.json"), "w", encoding="utf-8") as handle:
        json.dump(info, handle, indent=2)

    summary = {
        "episodes": len(episodes),
        "total_steps": total_steps,
        "tasks": len(task_index),
        "raw_action_dim": args.raw_action_dim,
        "fps": args.fps,
        "data_format": "parquet" if HAVE_PYARROW else "json",
        "dataset_root": os.path.relpath(root, out),
    }
    with open(os.path.join(out, "dream_summary.json"), "w", encoding="utf-8") as handle:
        json.dump(summary, handle, indent=2)

    print("")
    print("merged %d episodes, %d action steps, %d task(s)" % (len(episodes), total_steps, len(task_index)))
    print("dataset: %s" % root)
    if not HAVE_PYARROW:
        print(
            "NOTE: pyarrow was not importable, so per-episode action tables were "
            "written as JSON. LeRobot reads parquet; convert before training."
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
