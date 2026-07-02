#!/usr/bin/env python3
"""Generate a sim pick-and-place dataset for the so100 in MuJoCo.

Records LeRobot-format episodes of a SCRIPTED joint-space pick of a cube, with
per-episode domain randomization (cube position/color). Each episode is VERIFIED
by checking that the cube actually rose off the floor (a height check on the
cube geom); episodes that fail are discarded and retried, and the saved/attempt
counts are reported, so a broken pick is dropped instead of silently producing a
garbage dataset.

Why: a policy finetuned on real-robot images can't drive this sim (real->sim
appearance gap). Training on images rendered FROM THIS SIM closes that gap.

Self-introspecting: joint names and home pose are read at runtime via
get_robot_state and logged, because exact names vary by robot model and the
grasp must be tuned against the actual so100.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--robot", default="so100")
    p.add_argument("--repo-id", default="local/so100_sim_pick")
    p.add_argument("--episodes", type=int, default=5)
    p.add_argument("--fps", type=int, default=30)
    p.add_argument("--width", type=int, default=640)
    p.add_argument("--height", type=int, default=480)
    p.add_argument("--cameras", default="top,wrist")
    p.add_argument("--camera-placements", default="")
    p.add_argument("--task", default="pick up the red cube")
    p.add_argument("--cube-size", type=float, default=0.025)
    p.add_argument("--randomize", action="store_true",
                   help="Jitter cube position/color per episode.")
    p.add_argument("--output-dir", default=os.environ.get("OUTPUT_DIR", "output"))
    p.add_argument("--introspect-only", action="store_true",
                   help="Print robot joints + gripper geoms and exit (no recording).")
    return p.parse_args()


def _xyz(s):
    return [float(x) for x in s.split(",")]


def main():
    args = parse_args()
    os.environ.setdefault("MUJOCO_GL", "egl")
    import numpy as np
    from strands_robots import Robot

    out = Path(args.output_dir)
    out.mkdir(parents=True, exist_ok=True)

    print(f"[datagen] MUJOCO_GL={os.environ['MUJOCO_GL']}", flush=True)
    print(f"[datagen] Loading robot '{args.robot}' ...", flush=True)
    sim = Robot(args.robot)

    # --- Introspect the robot: joints + home pose ---
    state = sim.get_robot_state(args.robot)
    joints = []
    for block in (state.get("content") or []):
        if isinstance(block, dict) and isinstance(block.get("json"), dict):
            joints = list(block["json"].get("state", {}).keys())
    print(f"[datagen] joints: {joints}", flush=True)

    cam_names = [c.strip() for c in args.cameras.split(",") if c.strip()]
    placements = {}
    if args.camera_placements.strip():
        try:
            placements = json.loads(args.camera_placements)
        except json.JSONDecodeError as exc:
            print(f"[datagen] bad camera-placements ({exc})", flush=True)

    def add_cameras():
        default_pos, default_tgt = [0.55, -0.45, 0.4], [0.25, 0.0, 0.05]
        for cn in cam_names:
            pl = placements.get(cn, {})
            sim.add_camera(name=cn, position=pl.get("position", default_pos),
                           target=pl.get("target", default_tgt),
                           width=args.width, height=args.height)

    # Introspection probe: add a cube + cameras, list contacts/geoms, exit.
    if args.introspect_only:
        sim.add_object(name="cube", shape="box",
                       size=[args.cube_size] * 3, position=[0.25, 0.0, 0.025],
                       color=[1, 0, 0, 1])
        add_cameras()
        sim.step(n_steps=10)
        # Dump ALL geom names from the MuJoCo model so we can identify the
        # gripper pad geoms and the cube geom -- home-pose contacts are empty,
        # so listing geoms is what actually tells us names.
        try:
            mj = sim._mj if hasattr(sim, "_mj") else __import__("mujoco")
            model = sim._world._model
            names = [mj.mj_id2name(model, mj.mjtObj.mjOBJ_GEOM, i)
                     for i in range(model.ngeom)]
            print(f"[datagen] geoms ({model.ngeom}): {names}", flush=True)
            bodies = [mj.mj_id2name(model, mj.mjtObj.mjOBJ_BODY, i)
                      for i in range(model.nbody)]
            print(f"[datagen] bodies ({model.nbody}): {bodies}", flush=True)
        except Exception as exc:
            print(f"[datagen] geom listing failed ({exc!r})", flush=True)
        contacts = sim.get_contacts()
        for block in (contacts.get("content") or []):
            if isinstance(block, dict) and block.get("json"):
                print(f"[datagen] contacts: {json.dumps(block['json'])[:1500]}", flush=True)
        print("[datagen] introspect-only done.", flush=True)
        return 0

    # --- LeRobot dataset recorder ---
    from strands_robots.dataset_recorder import DatasetRecorder

    joint_names = joints or ["Rotation", "Pitch", "Elbow", "Wrist_Pitch", "Wrist_Roll", "Jaw"]
    recorder = DatasetRecorder.create(
        repo_id=args.repo_id,
        fps=args.fps,
        robot_type=args.robot,
        joint_names=joint_names,
        camera_keys=cam_names,
        root=str(out / "dataset"),
    )

    import mujoco as mj

    # add_object / remove_object RECOMPILE the model, so _model/_data references go
    # stale every episode. Always read them live from sim._world, never cache.
    def md():
        return sim._world._model, sim._world._data

    def geom(n):
        # mj_name2id returns -1 for an unknown name; indexing geom_xpos with -1
        # does NOT raise (numpy wraps to the last geom) and would silently return
        # a wrong-but-plausible position, making the height-based grasp check
        # meaningless. Fail loudly instead so a renamed/missing geom is caught.
        m, data = md()
        gid = mj.mj_name2id(m, mj.mjtObj.mjOBJ_GEOM, n)
        if gid < 0:
            raise RuntimeError(f"geom {n!r} not found in the MuJoCo model")
        return np.array(data.geom_xpos[gid])

    # --- Reach-from-home grasp recipe (FORGIVING / error-tolerant) + verify-and-keep ---
    # Motion: start at HOME, sweep up to a HOVER directly above the cube, descend
    # straight down (jaw 0.4), close, then a GENTLE fine-grained lift. No weld -- a
    # genuine pinch. We record EVERY frame from HOME onward so the policy learns
    # the full reach (not just the lift). The grip is marginal and slips at some
    # randomized positions, so each episode is VERIFIED to actually raise the cube
    # and DISCARDED otherwise, retrying to the target count.
    # Joints [Rot,Pitch,Elbow,WPitch,WRoll]; Jaw 1.3=open, ~0=closed. To RAISE the
    # gripper DECREASE Pitch+Elbow; to pull reach IN toward the base INCREASE Pitch.
    #
    # GRASP-POSE CHOICE IS ABOUT POLICY TOLERANCE, NOT SCRIPTED LOOKS. A lower,
    # wider, perfectly-centered grasp LOOKS better in the scripted demo but is a
    # TIGHTER TARGET: the learned policy's descent has x,y error, and a low/wide
    # grip turns a near-miss into a KNOCK (fingers hit the cube side instead of
    # catching it). This higher, narrower grip (descend jaw 0.4, no lowering) is
    # uglier up close but CATCHES the cube despite policy error -- it's the version
    # that actually picked when rendered. (Sibling lesson to the tall-block-too-
    # tippy finding: optimize for the IMPERFECT policy, not the perfect script.)
    import math
    REF = [1.74, -1.1, 1.36, 1.21, 1.5]      # forgiving grasp pose for cube at (0.25,0)
    REF_XY = (0.25, 0.0)
    HOME = [0.0, -0.3, 0.5, 0.0, 1.5]        # neutral start the arm sweeps from
    APPROACH_JAW = 0.4                        # gripper open during descent (error-tolerant catch)
    ARM_FORCE = 12.0                          # boost arm joints 0-4 (NOT the jaw)
    LIFT_SEGS = 120                           # gentle, fine-grained lift
    # Confirmed object is a STABLE cube: footprint x footprint x footprint, resting
    # on the ground (center at half-height). add_object treats `size` as FULL
    # extents. Scale off --cube-size so the cube stays cubic at any footprint.
    FP = args.cube_size
    BLOCK_SIZE = [FP, FP, FP]
    BLOCK_Z = FP / 2.0
    BLOCK_MASS = 0.02

    def cube_z():
        return float(geom("cube_geom")[2])

    def kin(arm, jaw):
        m, data = md()
        sim.set_joint_positions(positions=dict(zip(joint_names, list(arm) + [jaw])),
                                robot_name=args.robot)
        # Teleport == reset: zero all velocities so residual motion from the prior
        # episode's lift/carry/release can't carry into the next grasp (else only
        # the first episode grips and the rest start mid-swing and slip).
        data.qvel[:] = 0.0
        mj.mj_forward(m, data)

    def boost_arm_force():
        # add_object/add_camera RECOMPILE the model, so re-apply every episode.
        m, _ = md()
        for i in range(min(5, m.nu)):    # joints 0-4 only; boosting the jaw ejects the block
            m.actuator_forcerange[i] = [-ARM_FORCE, ARM_FORCE]

    def solve_grasp(cx, cy):
        """Confirmed REF grasp pose, base-rotated to aim at the block's (cx,cy)."""
        base = REF[0] + (math.atan2(cy, cx) - math.atan2(REF_XY[1], REF_XY[0]))
        return [base, REF[1], REF[2], REF[3], REF[4]]

    def lerp(a, b, n):
        return [[a[i] + (b[i] - a[i]) * (k / n) for i in range(len(a))]
                for k in range(1, n + 1)]

    def drive(arm, jaw, n):
        for _ in range(n):
            sim.send_action({jn: float(v) for jn, v in zip(joint_names, list(arm) + [jaw])},
                            robot_name=args.robot)

    def record(arm, jaw):
        obs = sim.get_observation(args.robot)
        action = {jn: float(v) for jn, v in zip(joint_names, list(arm) + [jaw])}
        recorder.add_frame(observation=obs, action=action, task=args.task)

    def move(a, b, jaw, n):
        """Interpolate a->b over n segments, stepping physics and recording each frame."""
        for p in lerp(a, b, n):
            drive(p, jaw, 2); record(p, jaw)

    n_seg = max(3, args.fps // 3)
    rng = np.random.default_rng(0)
    saved = 0
    attempts = 0
    max_attempts = args.episodes * 4
    while saved < args.episodes and attempts < max_attempts:
        attempts += 1
        cx, cy = REF_XY
        color = [1, 0, 0, 1]
        if args.randomize:
            cx = 0.23 + 0.04 * float(rng.random())
            cy = -0.04 + 0.08 * float(rng.random())
            color = [0.7 + 0.3 * float(rng.random()), 0.0, 0.1 * float(rng.random()), 1]
        try:
            sim.remove_object("cube")
        except Exception:
            # Expected on the first attempt (no cube exists yet) and harmless on
            # later ones; we unconditionally re-add a fresh cube just below.
            pass
        sim.add_object(name="cube", shape="box", size=BLOCK_SIZE,
                       position=[cx, cy, BLOCK_Z], color=color, mass=BLOCK_MASS)
        add_cameras()
        boost_arm_force()

        grasp = solve_grasp(cx, cy)
        hover = [grasp[0], grasp[1] - 0.45, grasp[2] - 0.3, grasp[3], grasp[4]]
        lift = [grasp[0], -1.6, 0.4, grasp[3], grasp[4]]
        place = [grasp[0] - 0.4, -1.6, 0.4, grasp[3], grasp[4]]
        place_down = [grasp[0] - 0.4, grasp[1], grasp[2], grasp[3], grasp[4]]

        # Reach from HOME, recording the full trajectory into the episode buffer.
        kin(HOME, APPROACH_JAW)
        record(HOME, APPROACH_JAW)
        move(HOME, hover, APPROACH_JAW, 40)      # sweep up to directly above the block
        move(hover, grasp, APPROACH_JAW, 40)     # straight-down descent, gripper open
        drive(grasp, 0.0, 50); record(grasp, 0.0)  # close on the block
        move(grasp, lift, 0.0, LIFT_SEGS)        # gentle lift
        z_top = cube_z()
        move(lift, place, 0.0, max(30, n_seg * 2))       # carry
        move(place, place_down, 0.0, max(30, n_seg * 2))  # lower
        drive(place_down, 1.3, 10); record(place_down, 1.3)  # release

        # VERIFY: did the block actually leave the floor while grasped?
        held = z_top > BLOCK_Z + 0.04
        if held:
            recorder.save_episode()
            saved += 1
            print(f"[datagen] SAVED {saved}/{args.episodes} (attempt {attempts}) "
                  f"cube=({cx:.3f},{cy:.3f}) lift_z={z_top:.3f}", flush=True)
        else:
            # Discard the failed attempt's frames. This reset is the core
            # integrity guarantee -- without it the next attempt's frames append
            # to this one and save_episode() writes a corrupted, over-length
            # episode that starts with a failed grasp. Call the API directly (not
            # a best-effort hasattr guard) so a missing method fails loudly here
            # rather than silently corrupting the dataset.
            recorder.clear_episode_buffer()
            print(f"[datagen] discard attempt {attempts} cube=({cx:.3f},{cy:.3f}) "
                  f"lift_z={z_top:.3f} (no hold)", flush=True)

    print(f"[datagen] {saved}/{args.episodes} verified pick-and-lift episodes "
          f"({attempts} attempts)", flush=True)
    # Close parquet writers and flush dataset metadata. Call directly so a
    # missing method fails loudly rather than leaving a half-written dataset.
    recorder.finalize()
    print(f"[datagen] Done -> {out / 'dataset'}", flush=True)

    # Under-production must not look like success: if we couldn't verify enough
    # picks, the Train step would otherwise silently train on a short dataset.
    # Exit non-zero so the pipeline surfaces the degraded run.
    if saved < args.episodes:
        print(f"[datagen] ERROR: only {saved}/{args.episodes} episodes verified "
              f"after {attempts} attempts (grasp failed too often). Failing so a "
              f"partial dataset is not mistaken for a complete one.", flush=True)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
