#!/usr/bin/env python3
"""Run one Shadow Hand simulation and render frames, for one point in a parameter sweep.

One invocation is one sweep point. The caller varies the parameters and owns the
sweep itself -- here that caller is an Open Job Description task parameter space.

Parameters are applied to the compiled mjModel rather than by rewriting the MJCF.
Editing the XML by element name looks convenient but fails silently on this model:
the compiled Shadow Hand has exactly one *named* geom, and its per-class joint
damping lives in <default> blocks, so name-matching edits hit nothing and the
simulation runs at its defaults. Every mutation below therefore counts what it
touched and fails if that count is zero.
"""

import argparse
import json
import os
import pathlib
import shutil
import subprocess
import sys
import time

import mujoco
import numpy as np
from PIL import Image

# Menagerie's own scene suggests this viewing angle via <global azimuth/>.
DEFAULT_AZIMUTH = 220.0
DEFAULT_ELEVATION = -30.0


def hand_camera(model, data, azimuth, elevation, zoom):
    """Aim a free camera at the hand, derived from where the hand actually is.

    The Shadow Hand lies along +X and is nearly flat in Z, so a hardcoded lookat
    is easy to get wrong -- and a wrong one silently renders a picture of the
    floor. Frame the bounding box of the hand's own geoms instead, ignoring the
    scene's free-floating object so it cannot drag the view off the hand.
    """
    body_names = [mujoco.mj_id2name(model, mujoco.mjtObj.mjOBJ_BODY, i) for i in range(model.nbody)]
    hand_bodies = {i for i, n in enumerate(body_names) if n and n.startswith("rh_")}
    hand_geoms = [g for g in range(model.ngeom) if model.geom_bodyid[g] in hand_bodies]
    if not hand_geoms:
        # Not the Shadow Hand; fall back to MuJoCo's whole-model framing.
        hand_geoms = list(range(model.ngeom))

    lo = data.geom_xpos[hand_geoms].min(axis=0)
    hi = data.geom_xpos[hand_geoms].max(axis=0)

    camera = mujoco.MjvCamera()
    mujoco.mjv_defaultFreeCamera(model, camera)
    camera.lookat[:] = (lo + hi) / 2.0
    camera.distance = float(np.linalg.norm(hi - lo)) * zoom
    camera.azimuth = azimuth
    camera.elevation = elevation
    return camera


def build_model(model_path, damping_scale, stiffness_scale, friction_scale):
    """Compile the model and apply the sweep parameters to it.

    Returns (model, applied) where `applied` records what each mutation changed,
    so a parameter that silently matched nothing is a hard error rather than a
    run that quietly used defaults.
    """
    # meshdir and <include> in the MJCF resolve against the process working
    # directory, so compile from the model's own directory.
    model_path = pathlib.Path(model_path).resolve()
    os.chdir(model_path.parent)
    model = mujoco.MjModel.from_xml_path(str(model_path))

    # Hinge DOFs are the hand's finger and wrist joints. The scene also carries a
    # free-floating object whose 6 DOFs must keep their own damping, so select on
    # joint type instead of touching dof_damping wholesale.
    hinge_dofs = [
        d
        for d in range(model.nv)
        if model.jnt_type[model.dof_jntid[d]] == mujoco.mjtJoint.mjJNT_HINGE
    ]
    if not hinge_dofs:
        sys.exit("no hinge DOFs found: wrong model?")

    damping_before = float(np.mean(model.dof_damping[hinge_dofs]))
    model.dof_damping[hinge_dofs] *= damping_scale
    damping_after = float(np.mean(model.dof_damping[hinge_dofs]))

    # The hand is driven by position actuators; their gainprm/biasprm carry the
    # position gain kp. Scaling it changes how hard the fingers are driven toward
    # the target, which is visible as reach and overshoot.
    position_acts = [
        a
        for a in range(model.nu)
        if model.actuator_gaintype[a] == mujoco.mjtGain.mjGAIN_FIXED
    ]
    if not position_acts:
        sys.exit("no fixed-gain actuators found: wrong model?")

    kp_before = float(np.mean(model.actuator_gainprm[position_acts, 0]))
    for a in position_acts:
        model.actuator_gainprm[a, 0] *= stiffness_scale
        # biasprm[1] is -kp for a position actuator; keep it consistent or the
        # actuator no longer behaves as position control.
        model.actuator_biasprm[a, 1] *= stiffness_scale
    kp_after = float(np.mean(model.actuator_gainprm[position_acts, 0]))

    # Friction on the manipulated object. Only meaningful because the scene puts
    # a free-floating body in the palm; scale all three components (sliding,
    # torsional, rolling) so their ratio is preserved. The object carries
    # priority="1", so its friction wins over the hand's in every contact pair --
    # scaling it here is what actually changes grip.
    body_names = [mujoco.mj_id2name(model, mujoco.mjtObj.mjOBJ_BODY, i) for i in range(model.nbody)]
    object_bodies = {i for i, n in enumerate(body_names) if n == "object"}
    object_geoms = [g for g in range(model.ngeom) if model.geom_bodyid[g] in object_bodies]
    if not object_geoms:
        sys.exit("no geoms on a body named 'object': scene has nothing to grip?")

    friction_before = float(np.mean(model.geom_friction[object_geoms, 0]))
    model.geom_friction[object_geoms] *= friction_scale
    friction_after = float(np.mean(model.geom_friction[object_geoms, 0]))

    applied = {
        "hinge_dofs_scaled": len(hinge_dofs),
        "mean_damping_before": damping_before,
        "mean_damping_after": damping_after,
        "position_actuators_scaled": len(position_acts),
        "mean_kp_before": kp_before,
        "mean_kp_after": kp_after,
        "object_geoms_scaled": len(object_geoms),
        "mean_slide_friction_before": friction_before,
        "mean_slide_friction_after": friction_after,
    }
    return model, applied


def encode_mp4(frames_dir, label, out_path, fps, bitrate):
    """Encode the rendered PNG sequence to an MP4, keeping the frames in place.

    Returns (size_bytes, codec, error). H.264 via libopenh264 is tried first for
    playback compatibility; EPEL's ffmpeg-free has no libx264, and its
    libopenh264 needs a library from a separate repo, so mpeg4 is the fallback
    when that is absent. yuv420p is explicit because players reject the formats
    these encoders otherwise pick.
    """
    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg is None:
        return None, None, "ffmpeg not found on PATH"

    attempts = (
        ("libopenh264", ["-c:v", "libopenh264", "-b:v", bitrate]),
        ("mpeg4", ["-c:v", "mpeg4", "-q:v", "3"]),
    )

    last = "no encoder attempted"
    for codec, codec_args in attempts:
        cmd = [
            ffmpeg, "-hide_banner", "-loglevel", "error", "-y",
            "-framerate", str(fps),
            "-i", str(frames_dir / f"{label}-%04d.png"),
            *codec_args,
            "-pix_fmt", "yuv420p",
            str(out_path),
        ]
        done = subprocess.run(cmd, capture_output=True, text=True)
        if done.returncode == 0 and out_path.exists() and out_path.stat().st_size > 0:
            return out_path.stat().st_size, codec, None
        tail = (done.stderr or "").strip().splitlines()[-1:]
        last = f"{codec} failed ({done.returncode}): {' '.join(tail)[:120]}"

    return None, None, last


def grasp_targets(model, phase):
    """Control targets for an open/close cycle, as a fraction `phase` of full flexion.

    Each actuator is driven between its ctrlrange midpoint (open) and its upper
    limit (flexed), so the motion stays inside every joint's declared range.
    """
    low = model.actuator_ctrlrange[:, 0]
    high = model.actuator_ctrlrange[:, 1]
    open_pose = np.where(low < 0.0, np.zeros_like(low), low)
    return open_pose + phase * (high - open_pose)


def main():
    p = argparse.ArgumentParser(description="Shadow Hand sweep point: simulate and render.")
    p.add_argument("--model", default="/models/mujoco_menagerie/shadow_hand/scene_right.xml")
    p.add_argument("--damping-scale", type=float, default=1.0,
                   help="Multiplier on hinge-joint damping.")
    p.add_argument("--stiffness-scale", type=float, default=1.0,
                   help="Multiplier on position-actuator kp.")
    p.add_argument("--friction-scale", type=float, default=1.0,
                   help="Multiplier on the manipulated object's friction (slide, torsion, roll).")
    p.add_argument("--duration", type=float, default=2.0,
                   help="Simulated seconds, which is also the clip length.")
    p.add_argument("--cycle", type=float, default=2.0,
                   help="Seconds per open/close cycle.")
    p.add_argument("--fps", type=float, default=20.0,
                   help="Rendered frames per simulated second.")
    p.add_argument("--width", type=int, default=480)
    p.add_argument("--height", type=int, default=360)
    p.add_argument("--out-dir", required=True,
                   help="Directory for frames/, preview.gif and metrics.json.")
    p.add_argument("--label", default="run",
                   help="Name for this sweep point, used in filenames.")
    p.add_argument("--azimuth", type=float, default=DEFAULT_AZIMUTH)
    p.add_argument("--elevation", type=float, default=DEFAULT_ELEVATION)
    p.add_argument("--zoom", type=float, default=1.15,
                   help="Camera distance as a multiple of the hand's bounding diagonal.")
    p.add_argument("--no-video", dest="video", action="store_false",
                   help="Skip MP4 encoding and keep only the PNG frames.")
    p.add_argument("--video-bitrate", default="2M",
                   help="Target bitrate for the MP4 (libopenh264 is bitrate-driven).")
    p.add_argument("--gif", action="store_true",
                   help="Also write preview.gif. Off by default; the MP4 supersedes it.")
    args = p.parse_args()

    model, applied = build_model(args.model, args.damping_scale, args.stiffness_scale,
                                 args.friction_scale)
    data = mujoco.MjData(model)

    steps = int(round(args.duration / model.opt.timestep))
    frame_every = max(1, int(round(1.0 / (args.fps * model.opt.timestep))))

    out_dir = pathlib.Path(args.out_dir)
    frames_dir = out_dir / "frames"
    frames_dir.mkdir(parents=True, exist_ok=True)

    mujoco.mj_forward(model, data)
    camera = hand_camera(model, data, args.azimuth, args.elevation, args.zoom)

    # Track the manipulated object so the friction axis is measurable: a low
    # friction ball squirts out of the fingers, which shows up as displacement
    # and a drop in height rather than in the force numbers.
    object_bid = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_BODY, "object")
    object_start = np.array(data.xpos[object_bid]) if object_bid >= 0 else None
    object_min_z = float("inf")

    renderer = mujoco.Renderer(model, args.height, args.width)
    frames = []
    peak_flexion = 0.0
    peak_actuator_force = 0.0
    wall_start = time.time()

    for step in range(steps):
        # Triangle wave in [0, 1]: closes, opens, repeats.
        cycle_pos = (data.time % args.cycle) / args.cycle
        phase = 2.0 * cycle_pos if cycle_pos < 0.5 else 2.0 * (1.0 - cycle_pos)
        data.ctrl[:] = grasp_targets(model, phase)

        mujoco.mj_step(model, data)

        peak_flexion = max(peak_flexion, float(np.abs(data.qpos[: model.nu]).max()))
        peak_actuator_force = max(peak_actuator_force, float(np.abs(data.actuator_force).max()))
        if object_bid >= 0:
            object_min_z = min(object_min_z, float(data.xpos[object_bid][2]))

        if step % frame_every == 0:
            renderer.update_scene(data, camera)
            px = renderer.render()
            frames.append(Image.fromarray(px))
            frames[-1].save(frames_dir / f"{args.label}-{len(frames) - 1:04d}.png")

    if hasattr(renderer, "close"):
        renderer.close()

    wall_seconds = time.time() - wall_start

    if frames and args.gif:
        frames[0].save(out_dir / "preview.gif", format="GIF", save_all=True,
                       append_images=frames[1:], duration=int(1000 / args.fps), loop=0)

    # The frames stay on disk either way; the MP4 is an addition, not a
    # replacement. Encoding is a hard failure when asked for, so a sweep cannot
    # report success while quietly producing no clips.
    mp4_bytes = None
    mp4_codec = None
    if frames and args.video:
        mp4_bytes, mp4_codec, err = encode_mp4(frames_dir, args.label, out_dir / "clip.mp4",
                                               args.fps, args.video_bitrate)
        if err:
            sys.exit(f"MP4 encode failed: {err}")

    metrics = {
        "label": args.label,
        "params": {
            "damping_scale": args.damping_scale,
            "stiffness_scale": args.stiffness_scale,
            "friction_scale": args.friction_scale,
            "duration_s": args.duration,
            "cycle_s": args.cycle,
            "fps": args.fps,
        },
        "model": {
            "path": str(args.model),
            "timestep": float(model.opt.timestep),
            "nq": int(model.nq),
            "nv": int(model.nv),
            "nu": int(model.nu),
        },
        "applied": applied,
        "steps": steps,
        "frames": len(frames),
        "clip_seconds": round(len(frames) / args.fps, 3) if frames else 0,
        "mp4_bytes": mp4_bytes,
        "mp4_codec": mp4_codec,
        "peak_flexion_rad": peak_flexion,
        "peak_actuator_force": peak_actuator_force,
        "object_displacement_m": (
            round(float(np.linalg.norm(np.array(data.xpos[object_bid]) - object_start)), 5)
            if object_start is not None else None
        ),
        "object_min_z_m": round(object_min_z, 5) if object_min_z != float("inf") else None,
        "object_final_z_m": (
            round(float(data.xpos[object_bid][2]), 5) if object_bid >= 0 else None
        ),
        "wall_seconds": round(wall_seconds, 2),
        "mujoco": mujoco.__version__,
    }
    (out_dir / "metrics.json").write_text(json.dumps(metrics, indent=2) + "\n")

    print(
        f"{args.label}: {steps} steps = {args.duration}s sim, {len(frames)} frames, "
        f"damping x{args.damping_scale} ({applied['mean_damping_before']:.4f} -> "
        f"{applied['mean_damping_after']:.4f} over {applied['hinge_dofs_scaled']} dofs), "
        f"kp x{args.stiffness_scale} ({applied['mean_kp_before']:.2f} -> "
        f"{applied['mean_kp_after']:.2f} over {applied['position_actuators_scaled']} actuators), "
        f"friction x{args.friction_scale} ({applied['mean_slide_friction_before']:.3f} -> "
        f"{applied['mean_slide_friction_after']:.3f} over {applied['object_geoms_scaled']} geoms), "
        f"peak_flexion {peak_flexion:.3f} rad, peak_force {peak_actuator_force:.3f}, "
        f"mp4 {mp4_bytes if mp4_bytes is not None else 'skipped'} bytes "
        f"({mp4_codec or 'none'}), "
        f"{wall_seconds:.1f}s wall"
    )

    if len(frames) == 0:
        sys.exit("no frames rendered")


if __name__ == "__main__":
    main()
