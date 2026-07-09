#!/usr/bin/env python3
"""Render a Strands Robots MuJoCo policy rollout to an MP4 + final PNG.

Uses the blocking run_policy(video=...) path: run_policy executes the
policy's OWN control loop (stepping the sim and applying actions) and
records the MP4 itself. Do NOT also call sim.step() in a loop -- that
races the policy thread and captures a frozen pose (the bug that made
the arm look like it wasn't moving).
"""
from __future__ import annotations
import argparse, json, os, sys
from pathlib import Path

def _xyz(s):
    return [float(x) for x in s.split(",")]

def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--robot", default="so100")
    p.add_argument("--instruction", default="pick up the red cube")
    p.add_argument("--policy-provider", default="mock")
    p.add_argument("--policy-model", default="")
    p.add_argument("--policy-device", default="cuda")
    p.add_argument("--policy-type", default="")
    p.add_argument("--policy-embodiment", default="")
    # Comma-separated sim camera names to create. These must match
    # the model's camera feature short-names (e.g. 'top,wrist' ->
    # observation.images.top / .wrist) so the policy's observation
    # remap finds them. The first is used for the output video.
    p.add_argument("--cameras", default="webcam")
    p.add_argument("--camera-position", default="0.55,-0.45,0.4")
    p.add_argument("--camera-target", default="0.25,0.0,0.05")
    # Optional per-camera placement JSON: {"top": {"position": [...],
    # "target": [...]}, ...}. Cameras not listed fall back to
    # --camera-position/--camera-target. Lets 'top' sit overhead and
    # 'wrist' sit close/low to match the policy's training views.
    p.add_argument("--camera-placements", default="")
    p.add_argument("--cube-position", default="0.25,0.0,0.025")
    p.add_argument("--cube-size", type=float, default=0.025)
    p.add_argument("--duration", type=float, default=10.0)
    p.add_argument("--fps", type=int, default=30)
    p.add_argument("--width", type=int, default=640)
    p.add_argument("--height", type=int, default=480)
    p.add_argument("--output-dir", default=os.environ.get("OUTPUT_DIR", "output"))
    return p.parse_args()

def main():
    args = parse_args()
    # EGL = GPU-accelerated headless render (GPU fleet). Use osmesa for CPU.
    os.environ.setdefault("MUJOCO_GL", "egl")
    import imageio.v3 as iio
    import numpy as np
    from strands_robots import Robot

    out = Path(args.output_dir)
    out.mkdir(parents=True, exist_ok=True)

    print(f"[strands-render] MUJOCO_GL={os.environ['MUJOCO_GL']}", flush=True)
    print(f"[strands-render] Loading robot '{args.robot}' ...", flush=True)
    sim = Robot(args.robot)

    # Build the SAME object geometry datagen trained on: a STABLE cube,
    # footprint x footprint x footprint, resting on the ground (center at
    # half-height). The policy was trained to grasp this shape, so the
    # render scene must match it (else the policy sees an out-of-
    # distribution object). A tall block was tried first but was too tippy
    # for the imperfect policy -- it toppled rather than grasped it.
    FP = args.cube_size
    block_size = [FP, FP, FP]
    cx, cy, _cz = _xyz(args.cube_position)
    block_pos = [cx, cy, FP / 2.0]
    print(f"[strands-render] Adding red cube at ({cx},{cy}) "
          f"size {block_size} ...", flush=True)
    sim.add_object(name="cube", shape="box",
                   size=block_size, position=block_pos,
                   color=[1, 0, 0, 1], mass=0.02)

    # Provider config. lerobot_local loads a real pretrained VLA;
    # mock ignores model/device.
    policy_config = {}
    embodiment = None
    policy_object = None
    if args.policy_provider == "lerobot_local":
        policy_config["pretrained_name_or_path"] = args.policy_model
        policy_config["device"] = args.policy_device
        # Explicit type for older checkpoints whose config.json has
        # no 'type' field (auto-detection fails otherwise).
        if args.policy_type.strip():
            policy_config["policy_type"] = args.policy_type.strip()
        # Embodiment maps our sim obs keys -> the checkpoint's model
        # feature names (esp. our camera -> observation.images.*).
        emb = args.policy_embodiment.strip()
        if emb and emb != "{}":
            try:
                embodiment = json.loads(emb)
                policy_config["embodiment"] = embodiment
                print(f"[strands-render] embodiment: {embodiment}", flush=True)
            except json.JSONDecodeError as exc:
                print(f"[strands-render] bad --policy-embodiment JSON "
                      f"({exc}); using library default remap.", flush=True)

        # WORKAROUND (strands-robots bug): when a checkpoint has a
        # LeRobot preprocessor, strands feeds our sim's uint8 [0,255]
        # camera frames straight into LeRobot's normalizer, which
        # tries to cast its float stats to uint8 and raises
        # "value cannot be converted to type uint8 without overflow".
        # The sim renders uint8; LeRobot wants float32 [0,1]. We build
        # the policy ourselves and subclass get_actions to convert
        # image obs to float32 [0,1] before the parent preprocesses.
        from strands_robots.policies.lerobot_local.policy import (
            LerobotLocalPolicy,
        )

        class _Float01Policy(LerobotLocalPolicy):
            async def get_actions(self, observation_dict, instruction, **kw):
                # Sim emits HWC uint8 [0,255]; LeRobot's normalizer
                # wants CHW float32 [0,1] (its stats are (3,1,1), so
                # the channel axis must be first). Convert images;
                # leave non-image obs untouched.
                fixed = {}
                for k, v in observation_dict.items():
                    if (isinstance(v, np.ndarray) and v.ndim == 3
                            and v.shape[-1] == 3):
                        img = v.astype(np.float32)
                        if v.dtype == np.uint8:
                            img = img / 255.0
                        img = np.transpose(img, (2, 0, 1))  # HWC -> CHW
                        fixed[k] = img
                    else:
                        fixed[k] = v
                return await super().get_actions(fixed, instruction, **kw)

        policy_object = _Float01Policy(**policy_config)
        print("[strands-render] built _Float01Policy (uint8->float32 "
              "[0,1] image fix)", flush=True)

    # Create one sim camera per name in --cameras. Names must match
    # the model's camera feature short-names so the policy's obs
    # remap finds them. Per-camera placement (--camera-placements)
    # lets each view match its training semantics (e.g. 'top'
    # overhead, 'wrist' close/low); unlisted cameras fall back to
    # --camera-position/--camera-target. The first camera is the
    # video view.
    cam_names = [c.strip() for c in args.cameras.split(",") if c.strip()]
    default_pos, default_tgt = _xyz(args.camera_position), _xyz(args.camera_target)
    placements = {}
    if args.camera_placements.strip():
        try:
            placements = json.loads(args.camera_placements)
        except json.JSONDecodeError as exc:
            print(f"[strands-render] bad --camera-placements JSON ({exc}); "
                  "using uniform placement.", flush=True)
    for cn in cam_names:
        p = placements.get(cn, {})
        cpos = p.get("position", default_pos)
        ctgt = p.get("target", default_tgt)
        print(f"[strands-render] Adding policy camera '{cn}' at {cpos} -> {ctgt} ...",
              flush=True)
        cam_res = sim.add_camera(name=cn, position=cpos, target=ctgt,
                                 width=args.width, height=args.height)
        if isinstance(cam_res, dict) and cam_res.get("status") == "error":
            msg = cam_res.get("content", [{}])[0].get("text", "")
            print(f"[strands-render] add_camera '{cn}' failed ({msg})", flush=True)

    # Dedicated DEMO camera for the output video, separate from the policy's
    # cameras (top/wrist). Uses --camera-position/--camera-target (the
    # cinematic front_3q view) so the video isn't the unflattering top-down.
    camera = "demo_cam"
    print(f"[strands-render] Adding demo camera at {default_pos} -> {default_tgt} ...",
          flush=True)
    dcam = sim.add_camera(name=camera, position=default_pos, target=default_tgt,
                          width=args.width, height=args.height)
    if isinstance(dcam, dict) and dcam.get("status") == "error":
        msg = dcam.get("content", [{}])[0].get("text", "")
        print(f"[strands-render] demo_cam failed ({msg}); falling back to "
              f"'{cam_names[0]}'", flush=True)
        camera = cam_names[0]

    video_path = out / f"{args.robot}_render.mp4"
    video_cfg = {"path": str(video_path), "fps": args.fps,
                 "camera": camera, "width": args.width, "height": args.height}

    print(f"[strands-render] run_policy '{args.policy_provider}' "
          f"{policy_config or ''} for {args.duration}s : "
          f"{args.instruction!r}", flush=True)
    run_kwargs = dict(robot_name=args.robot,
                      instruction=args.instruction,
                      duration=args.duration,
                      video=video_cfg)
    if policy_object is not None:
        # Pre-built policy (uint8->float fix) takes precedence.
        run_kwargs["policy_object"] = policy_object
    else:
        run_kwargs["policy_provider"] = args.policy_provider
        run_kwargs["policy_config"] = policy_config
    result = sim.run_policy(**run_kwargs)
    status = result.get("status") if isinstance(result, dict) else "?"
    print(f"[strands-render] run_policy status={status}", flush=True)
    if isinstance(result, dict) and result.get("content"):
        for c in result["content"]:
            print(f"[strands-render]   {c.get('text','')}", flush=True)
    if status == "error":
        return 1

    # Save the final frame as a thumbnail from the same camera.
    try:
        frame = sim.get_observation(args.robot)[camera]
        iio.imwrite(out / f"{args.robot}_final_frame.png", np.asarray(frame))
    except Exception as exc:
        print(f"[strands-render] thumbnail skipped ({exc!r})", flush=True)

    print(f"[strands-render] Done -> {video_path}", flush=True)
    return 0

if __name__ == "__main__":
    sys.exit(main())
