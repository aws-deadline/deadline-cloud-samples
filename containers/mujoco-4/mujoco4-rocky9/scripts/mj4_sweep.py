#!/usr/bin/env python3
"""Run one point of a MuJoCo 4.0 parameter sweep, render it, and write metrics.json.

Two subcommands exercise the two headline features of MuJoCo 4.0:

  torsion  Elasto-plasticity. Sets the yield strain of the plastic bar in the
           model/plastic/torsion.xml scene and measures the permanent twist it keeps.
  cradle   Speculative contacts. Runs the model/speculative/newton.xml cradle at a
           chosen timestep with speculative contacts on or off and reports whether
           a plate tunnelled through its neighbour.

One invocation is one sweep point. The caller owns the sweep: here that caller is
an Open Job Description task parameter space. Parameters are applied to the
compiled mjModel, and every mutation checks that it touched something, so a
parameter that silently matched nothing fails the task instead of producing a run
at the model's defaults.
"""

import argparse
import json
import math
import pathlib
import shutil
import subprocess
import sys
import time

import mujoco
import numpy as np
from PIL import Image

MODELS = pathlib.Path("/models/mujoco/model")
SPECULATIVE_BIT = int(mujoco.mjtEnableBit.mjENBL_SPECULATIVE)
# flex_plasticmode bit for the stretching mode. 3D flexes only have this one.
PLASTIC_STRETCH = 2


def object_id(model, kind, name):
    found = mujoco.mj_name2id(model, kind, name)
    if found < 0:
        sys.exit(f"{name!r} not found in the model: wrong scene?")
    return found


def encode_mp4(frames_dir, label, out_path, fps, bitrate):
    """Encode the PNG sequence to an MP4, keeping the frames. Returns (bytes, codec, error).

    EPEL's ffmpeg-free has no libx264. H.264 comes from libopenh264, with MPEG-4 as
    the fallback when that encoder is missing.
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
            "-framerate", f"{fps:g}",
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


class Recorder:
    """Render a frame whenever simulated time reaches the next frame time."""

    def __init__(self, model, args, camera=None):
        self.renderer = mujoco.Renderer(model, args.height, args.width)
        self.camera = camera
        self.fps = args.fps
        self.label = args.label
        self.frames_dir = args.out_dir / "frames"
        self.frames_dir.mkdir(parents=True, exist_ok=True)
        self.count = 0
        self.next_time = 0.0
        self.brightest = 0.0

    def maybe_capture(self, data):
        if data.time + 1e-9 < self.next_time:
            return
        if self.camera is None:
            self.renderer.update_scene(data)
        else:
            self.renderer.update_scene(data, self.camera)
        pixels = self.renderer.render()
        self.brightest = max(self.brightest, float(pixels.mean()))
        Image.fromarray(pixels).save(self.frames_dir / f"{self.label}-{self.count:04d}.png")
        self.count += 1
        self.next_time = self.count / self.fps

    def close(self):
        if hasattr(self.renderer, "close"):
            self.renderer.close()


def finish(args, recorder, model, params, applied, results, wall_start):
    """Encode the clip, write metrics.json, print a one-line summary."""
    recorder.close()
    wall_seconds = time.time() - wall_start
    if recorder.count == 0:
        sys.exit("no frames rendered")
    # A broken GL stack renders black frames without raising.
    if recorder.brightest == 0.0:
        sys.exit("every rendered frame is black: offscreen rendering is broken")

    mp4_bytes, mp4_codec = None, None
    if args.video:
        mp4_bytes, mp4_codec, err = encode_mp4(recorder.frames_dir, args.label, args.out_dir / "clip.mp4",
                                               args.fps, args.video_bitrate)
        if err:
            sys.exit(f"MP4 encode failed: {err}")

    metrics = {
        "label": args.label,
        "sweep": args.command,
        "params": params,
        "model": {
            "path": str(args.model),
            "timestep": float(model.opt.timestep),
            "solver": mujoco.mjtSolver(model.opt.solver).name,
            "sparse": bool(mujoco.mj_isSparse(model)),
            "nv": int(model.nv),
            "nplastic": int(model.nplastic),
        },
        "applied": applied,
        "results": results,
        "frames": recorder.count,
        "mp4_bytes": mp4_bytes,
        "mp4_codec": mp4_codec,
        "wall_seconds": round(wall_seconds, 2),
        "mujoco": mujoco.__version__,
    }
    (args.out_dir / "metrics.json").write_text(json.dumps(metrics, indent=2) + "\n")
    shown = ", ".join(f"{k} {v}" for k, v in results.items())
    print(f"{args.label}: {shown}, {recorder.count} frames, mp4 {mp4_bytes or 'skipped'} bytes "
          f"({mp4_codec or 'none'}), {wall_seconds:.1f}s wall")


def check_stable(data, last_time):
    """Exit if the solver diverged. MuJoCo resets mjData on a bad acceleration and keeps going,
    so non-finite state is never visible; the warning counter is."""
    if data.warning[mujoco.mjtWarning.mjWARN_BADQACC].number:
        sys.exit(f"simulation diverged (bad acceleration) after t={last_time:.3f}s; try a smaller timestep")


def run_torsion(args):
    """Twist both bars past 180 degrees, release, and measure what the plastic bar keeps."""
    model = mujoco.MjModel.from_xml_path(str(args.model))
    plastic = object_id(model, mujoco.mjtObj.mjOBJ_FLEX, "plastic_bar")
    # The plastic state is allocated at compile time only for modes whose yield was
    # positive in the MJCF. Setting flex_yield on an elastic flex would do nothing.
    if not model.flex_plasticmode[plastic] & PLASTIC_STRETCH:
        sys.exit("plastic_bar has no plastic stretching state: its MJCF yield must be > 0")
    if args.yield_strain <= 0:
        sys.exit("--yield-strain must be > 0. Zero at run time means full plastic flow, not elastic")

    yield_before = float(model.flex_yield[plastic, 0])
    model.flex_yield[plastic, 0] = args.yield_strain
    if args.timestep is not None:
        model.opt.timestep = args.timestep
    applied = {
        "flex": "plastic_bar",
        "yield_strain_before": yield_before,
        "yield_strain_after": float(model.flex_yield[plastic, 0]),
        "plastic_state_slots": int(model.nplastic),
    }

    data = mujoco.MjData(model)
    twist = {name: model.jnt_qposadr[object_id(model, mujoco.mjtObj.mjOBJ_JOINT, f"twist_{i}")]
             for i, name in enumerate(("elastic", "plastic"))}
    # This flex's slice of mjData.plastic runs to the next allocated address, joints and
    # tendons included, or to the end.
    start = int(model.flex_plasticadr[plastic])
    later = [int(a) for adrs in (model.flex_plasticadr, model.jnt_plasticadr, model.tendon_plasticadr)
             for a in adrs if int(a) > start]
    end = min(later, default=int(model.nplastic))
    peak = {"elastic": 0.0, "plastic": 0.0}
    peak_plastic_l1 = 0.0

    recorder = Recorder(model, args)
    wall_start = time.time()
    for _ in range(int(round(args.duration / model.opt.timestep))):
        last_time = data.time
        mujoco.mj_step(model, data)
        check_stable(data, last_time)
        for name, adr in twist.items():
            peak[name] = max(peak[name], abs(math.degrees(data.qpos[adr])))
        peak_plastic_l1 = max(peak_plastic_l1, float(np.abs(data.plastic[start:end]).sum()))
        recorder.maybe_capture(data)

    results = {
        "peak_twist_deg": round(peak["plastic"], 1),
        "final_twist_deg": round(math.degrees(data.qpos[twist["plastic"]]), 1),
        "elastic_peak_twist_deg": round(peak["elastic"], 1),
        "elastic_final_twist_deg": round(math.degrees(data.qpos[twist["elastic"]]), 1),
        "peak_plastic_strain_l1": round(peak_plastic_l1, 3),
        "final_plastic_strain_l1": round(float(np.abs(data.plastic[start:end]).sum()), 3),
    }
    params = {"yield_strain": args.yield_strain, "duration_s": args.duration, "fps": args.fps}
    finish(args, recorder, model, params, applied, results, wall_start)


# newton.xml geometry: pivots 20 mm apart at z = 1.40 m, plate centres 1.0 m below.
CRADLE_PLATES = 5
CRADLE_PIVOT_Z = 1.40
CRADLE_ARM_M = 1.0
CRADLE_BUILT_ANGLE_DEG = 58.0
# The model tunes its plates for h * b = 1.996 with a direct solref of (0, -b), so the
# first impact reverses the normal velocity in one step. Keep that product at every
# timestep or the restitution changes with dt, and the solver diverges at large dt.
CRADLE_HB = 1.996


def run_cradle(args):
    """Release plate 1 and report whether any plate passes through its neighbour."""
    model = mujoco.MjModel.from_xml_path(str(args.model))
    plates = [object_id(model, mujoco.mjtObj.mjOBJ_GEOM, f"p{i}") for i in range(1, CRADLE_PLATES + 1)]
    joint1 = object_id(model, mujoco.mjtObj.mjOBJ_JOINT, "j1")
    pivots_x = [float(model.body_pos[model.geom_bodyid[g]][0]) for g in plates]

    timestep_before = float(model.opt.timestep)
    model.opt.timestep = args.timestep_ms / 1000.0
    if args.speculative == "enable":
        model.opt.enableflags |= SPECULATIVE_BIT
    else:
        model.opt.enableflags &= ~SPECULATIVE_BIT
    damping_before = float(-model.geom_solref[plates[0], 1])
    model.geom_solref[plates, 1] = -CRADLE_HB / model.opt.timestep
    applied = {
        "timestep_before_s": timestep_before,
        "timestep_after_s": float(model.opt.timestep),
        "speculative_flag": bool(model.opt.enableflags & SPECULATIVE_BIT),
        "plate_damping_before": damping_before,
        "plate_damping_after": float(-model.geom_solref[plates[0], 1]),
        "plates_rescaled": len(plates),
    }
    # Gap between neighbouring plate faces at rest, from the compiled geometry.
    gap_m = (pivots_x[1] - pivots_x[0]) - 2.0 * float(model.geom_size[plates[0], 0])

    data = mujoco.MjData(model)
    # pendulum1 is built swung out to 58 degrees. Its hinge angle adds to that.
    data.qpos[model.jnt_qposadr[joint1]] = math.radians(args.release_angle - CRADLE_BUILT_ANGLE_DEG)
    mujoco.mj_forward(model, data)

    def swing_deg(i):
        pos = data.geom_xpos[plates[i]]
        return math.degrees(math.atan2(pos[0] - pivots_x[i], CRADLE_PIVOT_Z - pos[2]))

    camera = mujoco.MjvCamera()
    mujoco.mjv_defaultFreeCamera(model, camera)
    camera.lookat[:] = (0.0, 0.0, 0.45)
    camera.distance = args.camera_distance
    camera.azimuth = 110.0
    camera.elevation = -12.0

    recorder = Recorder(model, args, camera)
    start_angle = swing_deg(0)
    peak_speed = 0.0
    first_pass = None
    worst_overlap = 0
    peak_last_swing = 0.0
    wall_start = time.time()
    for _ in range(int(round(args.duration / model.opt.timestep))):
        # Speculative sweeps use the pre-step velocity, so that is the travel that matters.
        peak_speed = max(peak_speed, abs(data.qvel[model.jnt_dofadr[joint1]]) * CRADLE_ARM_M)
        last_time = data.time
        mujoco.mj_step(model, data)
        check_stable(data, last_time)
        # Plates stay in order left to right unless one passed through another.
        out_of_order = int(np.sum(np.diff(data.geom_xpos[plates, 0]) < 0))
        if out_of_order and first_pass is None:
            first_pass = round(float(data.time), 3)
        worst_overlap = max(worst_overlap, out_of_order)
        peak_last_swing = max(peak_last_swing, swing_deg(CRADLE_PLATES - 1))
        recorder.maybe_capture(data)

    travel_mm = peak_speed * model.opt.timestep * 1000.0
    results = {
        "tunneled": first_pass is not None,
        "first_tunnel_s": first_pass,
        "max_plates_out_of_order": worst_overlap,
        "start_angle_deg": round(start_angle, 1),
        "peak_speed_m_s": round(peak_speed, 3),
        "travel_per_step_mm": round(travel_mm, 1),
        "plate_thickness_mm": round(2.0 * float(model.geom_size[plates[0], 0]) * 1000.0, 2),
        "gap_mm": round(gap_m * 1000.0, 1),
        "last_plate_peak_swing_deg": round(peak_last_swing, 1),
    }
    params = {
        "release_angle_deg": args.release_angle,
        "timestep_ms": args.timestep_ms,
        "speculative": args.speculative,
        "duration_s": args.duration,
        "fps": args.fps,
    }
    finish(args, recorder, model, params, applied, results, wall_start)


def main():
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--out-dir", required=True, type=pathlib.Path,
                        help="Directory for frames/, clip.mp4 and metrics.json.")
    common.add_argument("--label", default="run", help="Name for this sweep point, used in filenames.")
    common.add_argument("--fps", type=float, default=20.0, help="Rendered frames per simulated second.")
    common.add_argument("--width", type=int, default=480)
    common.add_argument("--height", type=int, default=360)
    common.add_argument("--no-video", dest="video", action="store_false",
                        help="Skip MP4 encoding and keep only the PNG frames.")
    common.add_argument("--video-bitrate", default="2M", help="Target bitrate for the MP4.")

    parser = argparse.ArgumentParser(description="One MuJoCo 4.0 sweep point: simulate, render, measure.")
    sub = parser.add_subparsers(dest="command", required=True)

    torsion = sub.add_parser("torsion", parents=[common], help="Elasto-plastic bar: permanent twist vs yield strain.")
    torsion.add_argument("--model", type=pathlib.Path, default=MODELS / "plastic" / "torsion.xml")
    torsion.add_argument("--yield-strain", type=float, required=True,
                         help="Stretching yield strain of the plastic bar. The model ships with 0.025.")
    torsion.add_argument("--timestep", type=float, help="Override the model timestep, in seconds.")
    # Each subcommand owns --duration. A shared parent argument would share one default.
    torsion.add_argument("--duration", type=float, default=3.0,
                         help="Simulated seconds, which is also the clip length.")
    torsion.set_defaults(func=run_torsion)

    cradle = sub.add_parser("cradle", parents=[common], help="Newton's cradle: tunnelling vs timestep.")
    cradle.add_argument("--model", type=pathlib.Path, default=MODELS / "speculative" / "newton.xml")
    cradle.add_argument("--timestep-ms", type=float, required=True, help="Simulation timestep in milliseconds.")
    cradle.add_argument("--speculative", choices=("enable", "disable"), required=True,
                        help="The speculative contacts flag, as in <flag speculative=.../>.")
    cradle.add_argument("--release-angle", type=float, default=58.0,
                        help="Degrees plate 1 is pulled back before release. The model ships with 58.")
    cradle.add_argument("--camera-distance", type=float, default=1.1)
    cradle.add_argument("--duration", type=float, default=2.0,
                        help="Simulated seconds, which is also the clip length.")
    cradle.set_defaults(func=run_cradle)

    args = parser.parse_args()
    positive = {"--duration": args.duration, "--fps": args.fps}
    if args.command == "torsion" and args.timestep is not None:
        positive["--timestep"] = args.timestep
    if args.command == "cradle":
        positive["--timestep-ms"] = args.timestep_ms
    for flag, value in positive.items():
        if value <= 0:
            sys.exit(f"{flag} must be > 0")
    if args.command == "cradle" and not 0 < args.release_angle < 90:
        sys.exit("--release-angle must be between 0 and 90 degrees")
    args.out_dir = args.out_dir.resolve()
    args.model = args.model.resolve()
    args.func(args)


if __name__ == "__main__":
    main()
