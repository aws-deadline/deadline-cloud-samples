# Pick one fruit and place it on a plate in a SimFoundry OmniGibson scene, then score the
# attempt from object poses. Two methods:
#   scripted  OmniGibson's StarterSemanticActionPrimitives: GRASP, then PLACE_ON_TOP (cuRobo).
#   policy    A DROID joint-position policy served by OpenPI, driven the way SimFoundry's
#             eval stage (C_application/stages/1_eval_policy_og_scene.py) drives it.
# Writes <out-dir>/rollout.mp4 and <out-dir>/result.json. result.json is written before
# og.shutdown(), because Isaac Sim exits 0 at shutdown even after a Python error.
"""Pick-and-place attempt in a SimFoundry OmniGibson scene, scored from object poses."""

from __future__ import annotations

import argparse
import itertools
import json
import math
import os
import time
import traceback
from pathlib import Path

os.environ.setdefault("OMNIGIBSON_HEADLESS", "1")

import imageio
import numpy as np
import torch as th
from PIL import Image
from scipy.spatial.transform import Rotation

from simfoundry import CFG_DIR, configure_omnigibson_data_path, import_og_dependencies
from simfoundry.utils.processing_utils import resize_with_pad
from simfoundry.utils.scene_utils import load_json_with_absolute_usd_paths

configure_omnigibson_data_path(force=True)
import_og_dependencies()

import omnigibson as og
import omnigibson.lazy as lazy
import omnigibson.utils.transform_utils as T
from omnigibson import object_states
from omnigibson.macros import gm
from omnigibson.robots import BaseRobot
from omnigibson.sensors import VisionSensor
from omnigibson.utils.config_utils import parse_config

gm.ENABLE_CCD = True

# DROID's start pose, as authored in SimFoundry's published DROID scenes.
DROID_HOME = [0.0, -0.8232, 0.0, -2.3710, 0.0, 1.5097, 0.0]
LIFT_THRESHOLD_M = 0.05


def parse_args():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--method", choices=["scripted", "policy"], required=True)
    p.add_argument("--scene-json", required=True)
    p.add_argument("--target", required=True, help="Substring of the fruit's category, e.g. banana")
    p.add_argument("--place-on", required=True, help="Substring of the plate's category, e.g. teal")
    p.add_argument("--prompt", default=None, help="Language instruction for the policy")
    p.add_argument("--out-dir", required=True)
    p.add_argument("--robot-pos", default=None, help="x,y,z to move the robot base to, in the scene frame")
    p.add_argument("--policy-host", default="localhost")
    p.add_argument("--policy-port", type=int, default=8000)
    p.add_argument("--execute-horizon", type=int, default=8)
    p.add_argument("--timeout-s", type=float, default=60.0)
    p.add_argument("--action-freq", type=int, default=15)
    p.add_argument("--attempts", type=int, default=3, help="Retries per primitive (scripted)")
    p.add_argument("--image-height", type=int, default=360)
    p.add_argument("--image-width", type=int, default=640)
    p.add_argument("--seed", type=int, default=0)
    return p.parse_args()


def to_np(x):
    return x.detach().cpu().numpy() if isinstance(x, th.Tensor) else np.asarray(x)


def as_rgb(img):
    img = to_np(img)[..., :3]
    if img.dtype != np.uint8:
        img = (np.clip(img, 0, 1) * 255).astype(np.uint8) if img.max(initial=0) <= 1.0 else img.astype(np.uint8)
    return img


def look_at_quat(eye, target):
    """xyzw quaternion for a USD camera (looks down -Z, +Y up) at eye looking at target."""
    f = np.asarray(target, float) - np.asarray(eye, float)
    f /= np.linalg.norm(f)
    right = np.cross(f, [0.0, 0.0, 1.0])
    right /= np.linalg.norm(right)
    up = np.cross(right, f)
    return Rotation.from_matrix(np.stack([right, up, -f], axis=1)).as_quat().tolist()


def find_object_name(scene_json, needle):
    init = scene_json["objects_info"]["init_info"]
    hits = [n for n, info in init.items()
            if needle in str(info["args"].get("category", n)) or needle in n]
    hits = [n for n in hits if not n.startswith("robot")]
    if len(hits) != 1:
        raise ValueError(f"'{needle}' matches {hits} in the scene; need exactly one")
    return hits[0]


def scene_pose(scene_json, name):
    link = scene_json["state"]["registry"]["object_registry"][name]["root_link"]
    return np.asarray(link["pos"], float), np.asarray(link["ori"], float)


class Recorder:
    """Steps the env, keeps video frames, and tracks the fruit pose every step."""

    def __init__(self, env, robot, fruit, plate, view_name):
        self.env, self.robot, self.fruit, self.plate, self.view_name = env, robot, fruit, plate, view_name
        self.frames, self.steps = [], 0
        self.z0 = float(fruit.aabb_center[2])
        self.max_lift = 0.0
        self.ever_in_hand = False
        self.obs = None

    def wrist_key(self, obs):
        keys = list(obs[self.robot.name].keys())
        for k in keys:
            if "Camera" in k or "wrist" in k.lower():
                return k
        return keys[0]

    def frame(self, obs):
        ext = obs.get("external", {})
        view = as_rgb(ext[self.view_name]["rgb"])
        h = view.shape[0]
        tiles = [view]
        for name in ("external_cam0_left",):
            if name in ext:
                tiles.append(as_rgb(ext[name]["rgb"]))
        tiles.append(as_rgb(obs[self.robot.name][self.wrist_key(obs)]["rgb"]))
        out = []
        for t in tiles:
            w = max(1, round(t.shape[1] * h / t.shape[0]))
            out.append(t if t.shape[0] == h else np.asarray(Image.fromarray(t).resize((w, h))))
        return np.concatenate(out, axis=1)

    def observe(self, obs):
        self.obs = obs
        self.frames.append(self.frame(obs))
        lift = float(self.fruit.aabb_center[2]) - self.z0
        self.max_lift = max(self.max_lift, lift)
        if self.robot._ag_obj_in_hand[self.robot.default_arm] == self.fruit:
            self.ever_in_hand = True

    def step(self, action):
        obs, reward, terminated, truncated, info = self.env.step(action)
        self.steps += 1
        self.observe(obs)
        return obs


def placement(fruit, plate, robot):
    """Pose-based placement check: fruit centre over the plate's footprint, resting on or above it."""
    f_lo, f_hi = (to_np(v) for v in fruit.aabb)
    p_lo, p_hi = (to_np(v) for v in plate.aabb)
    c = (f_lo + f_hi) / 2
    over = bool(p_lo[0] <= c[0] <= p_hi[0] and p_lo[1] <= c[1] <= p_hi[1])
    above = bool(f_lo[2] >= p_lo[2] - 0.005)
    in_hand = robot._ag_obj_in_hand[robot.default_arm] == fruit
    try:
        ontop = bool(fruit.states[object_states.OnTop].get_value(plate))
    except Exception as e:  # report, don't fail the run on a predicate error
        ontop = f"error: {e}"
    return {
        "fruit_center": c.round(4).tolist(),
        "plate_aabb": [p_lo.round(4).tolist(), p_hi.round(4).tolist()],
        "xy_offset_from_plate_center_m": float(np.linalg.norm(c[:2] - (p_lo[:2] + p_hi[:2]) / 2)),
        "over_plate": over,
        "above_plate_bottom": above,
        "released": not in_hand,
        "on_target": over and above and not in_hand,
        "og_ontop_predicate": ontop,
    }


def run_scripted(env, robot, rec, fruit, plate, args):
    from omnigibson.action_primitives.curobo import CuRoboEmbodimentSelection, CuRoboMotionGenerator
    from omnigibson.action_primitives.starter_semantic_action_primitives import (
        ActionPrimitiveError,
        StarterSemanticActionPrimitives,
        StarterSemanticActionPrimitiveSet,
    )
    import omnigibson.action_primitives.starter_semantic_action_primitives as ssap

    arm = robot.default_arm
    arm_ctrl = f"arm_{arm}"
    grip_ctrl = f"gripper_{arm}"
    state = {"gripper_cmd": 1.0}  # MultiFingerGripperController smooth, 1 = open, 0 = closed

    def q_to_action(q):
        # The primitives call robot.q_to_action, which only holonomic-base robots define.
        action = th.zeros(robot.action_dim)
        c = robot.controllers[arm_ctrl]
        action[robot.controller_action_idx[arm_ctrl]] = c._reverse_preprocess_command(q[c.dof_idx])
        action[robot.controller_action_idx[grip_ctrl]] = state["gripper_cmd"]
        return action

    robot.q_to_action = q_to_action

    def finger_length():
        """EEF-to-fingertip distance along the EEF z axis (the approach direction)."""
        lengths = [float(v) for v in (robot.eef_to_fingertip_lengths or {}).get(arm, {}).values()]
        lengths = [v for v in lengths if math.isfinite(v) and v > 0]
        if lengths:
            return sum(lengths) / len(lengths)
        eef_pos = robot.get_eef_position(arm)
        z = T.quat2mat(robot.get_eef_orientation(arm))[:, 2]
        best = 0.0
        for link in robot.finger_links[arm]:
            lo, hi = link.aabb
            for c in itertools.product(*zip(lo.tolist(), hi.tolist())):
                best = max(best, float(th.dot(th.tensor(c) - eef_pos, z)))
        return best

    class FixedBasePrimitives(StarterSemanticActionPrimitives):
        """The starter primitives assume a mobile base and a trunk. A desk-mounted Franka has
        neither, so planning is arm-only and anything that would navigate fails instead."""

        def _manipulation_control_idx(self):
            return robot.arm_control_idx[arm]

        def _navigate_if_needed(self, obj, eef_pose=None):
            self._motion_generator.update_obstacles()
            if eef_pose is None:
                eef_pose, _ = self._sample_grasp_pose(obj)
            if not self._target_in_reach_of_robot(eef_pose, skip_obstacle_update=True):
                raise ActionPrimitiveError(ActionPrimitiveError.Reason.PLANNING_ERROR,
                                           "Target out of reach of the fixed-base arm", {"object": obj.name})
            return
            yield

        def _grasp(self, obj):
            # Upstream's assisted grasp, except the final approach ignores the target in the
            # planner: the fingers straddle the fruit, inside cuRobo's collision margin.
            self._tracking_object = obj
            if self._get_obj_in_hand() is not None:
                raise ActionPrimitiveError(ActionPrimitiveError.Reason.PRE_CONDITION_ERROR,
                                           "Hand already full", {"object": obj.name})
            yield from self._execute_release()
            pregrasp_pose, grasp_pose = self._sample_grasp_pose(obj)
            yield from self._navigate_if_needed(obj, eef_pose=pregrasp_pose)
            yield from self._move_hand(pregrasp_pose)
            yield from self._move_hand(grasp_pose, motion_constraint=[1, 1, 1, 1, 1, 0], ignore_objects=[obj])
            yield from self._execute_grasp()
            yield from self._settle_robot()
            if self._get_obj_in_hand() != obj:
                raise ActionPrimitiveError(ActionPrimitiveError.Reason.POST_CONDITION_ERROR,
                                           "Grasp completed, but the target is not in hand",
                                           {"target object": obj.name})

        def _sample_pose_near_object(self, *a, **k):
            return None

        def _sample_grasp_pose(self, obj):
            # Upstream puts the EEF at the top of the object's box, world-aligned, and takes the
            # finger length from the robot, which the Franka-Robotiq leaves empty (NaN pose).
            # Here: fingertips at a quarter of the object's height, fingers closing across the
            # object's short horizontal axis.
            lo, hi = obj.aabb
            h = float(hi[2] - lo[2])
            L = finger_length()
            tip_z = float(lo[2]) + max(0.25 * h, 0.012)
            center = (lo + hi) / 2
            grasp_pos = th.tensor([float(center[0]), float(center[1]), tip_z + L], dtype=th.float32)
            _, orn, ext, _ = obj.get_base_aligned_bbox(visual=False)
            yaw = float(T.quat2euler(orn)[2])
            if ext[1] > ext[0]:
                yaw += math.pi / 2  # close across the object's x extent instead
            cur_yaw = float(T.quat2euler(robot.get_eef_orientation(arm))[2])
            # The fingers are symmetric: take the yaw nearer the wrist's current one.
            alt = yaw + math.pi
            d = lambda a: abs(math.atan2(math.sin(a - cur_yaw), math.cos(a - cur_yaw)))
            yaw = yaw if d(yaw) <= d(alt) else alt
            down = th.tensor([1.0, 0.0, 0.0, 0.0])  # eef z down, x forward
            grasp_quat = T.quat_multiply(T.euler2quat(th.tensor([0.0, 0.0, yaw])), down)
            pregrasp_pos = grasp_pos + th.tensor([0.0, 0.0, max(L, 0.05) + 0.03])
            return (pregrasp_pos, grasp_quat), (grasp_pos, grasp_quat)

        def _get_joint_position_with_fingers_at_limit(self, limit_type):
            return robot.get_joint_positions()

        def _move_fingers_to_limit(self, limit_type):
            state["gripper_cmd"] = 0.0 if limit_type == "lower" else 1.0
            prev = None
            for i in range(ssap.m.MAX_STEPS_FOR_GRASP_OR_RELEASE):
                yield q_to_action(robot.get_joint_positions())
                fingers = robot.get_joint_positions()[robot.gripper_control_idx[arm]]
                if limit_type == "lower" and self._get_obj_in_hand() is not None and i > 10:
                    break
                if prev is not None and i > 10 and th.max(th.abs(fingers - prev)) < 1e-4:
                    break
                prev = fingers

        def _execute_motion_plan(self, q_traj, stop_on_contact=False, stop_on_ag=False,
                                 ignore_failure=False, low_precision=False, ignore_physics=False):
            idx = robot.arm_control_idx[arm]
            thr = ssap.m.LOW_PRECISION_JOINT_POS_DIFF_THRESHOLD if low_precision else ssap.m.JOINT_POS_DIFF_THRESHOLD
            for joint_pos in q_traj:
                reached = False
                for _ in range(ssap.m.MAX_STEPS_FOR_JOINT_MOTION):
                    yield q_to_action(joint_pos)
                    diff = th.max(th.abs(joint_pos[idx] - robot.get_joint_positions()[idx])).item()
                    if diff < thr:
                        reached = True
                        break
                    if stop_on_contact and ssap.detect_robot_collision_in_sim(robot):
                        return
                    if stop_on_ag and self._get_obj_in_hand() is not None:
                        return
                if not reached and not ignore_failure and diff > 10 * thr:
                    raise ActionPrimitiveError(ActionPrimitiveError.Reason.EXECUTION_ERROR,
                                               "Could not reach the target arm joint positions", {"diff": diff})

    prims = FixedBasePrimitives(env, robot, enable_head_tracking=False, curobo_batch_size=1,
                                skip_curobo_initilization=True)
    # Fixed-base robots publish one cuRobo config. The primitives plan with the ARM selection,
    # so register the same config under both names.
    path = robot.curobo_path
    prims._motion_generator = CuRoboMotionGenerator(
        robot=robot,
        robot_cfg_path={CuRoboEmbodimentSelection.DEFAULT: path, CuRoboEmbodimentSelection.ARM: path},
        batch_size=3,
        collision_activation_distance=ssap.m.DEFAULT_COLLISION_ACTIVATION_DISTANCE,
    )
    prims._curobo_batch_size = 3
    mg = prims._motion_generator

    # The DROID scenes' desk is one mesh with the robot mounted in it, so every arm pose
    # collides with it. The floor plane, at the desk's height, stands in for the desk top.
    background = [o for o in env.scene.objects if "background" in o.name or o.fixed_base and o != robot]
    full_update = mg.update_obstacles

    def update_obstacles(ignore_objects=None):
        return full_update(ignore_objects=list(ignore_objects or []) + background)

    mg.update_obstacles = update_obstacles

    # Reachability probes, logged so a planning failure can be told apart from a scene problem.
    probe = {"ignored_obstacles": [o.name for o in background]}
    try:
        eef = (robot.get_eef_position(arm), robot.get_eef_orientation(arm))
        pre, grasp = prims._sample_grasp_pose(fruit)
        mg.update_obstacles()
        probe["current_eef"] = prims._target_in_reach_of_robot(eef, skip_obstacle_update=True)
        probe["pregrasp"] = prims._target_in_reach_of_robot(pre, skip_obstacle_update=True)
        probe["pregrasp_pos"] = to_np(pre[0]).round(3).tolist()
        probe["eef_pos"] = to_np(eef[0]).round(3).tolist()
        probe["finger_length_m"] = round(finger_length(), 4)
        probe["fruit_aabb_extent_m"] = to_np(fruit.aabb_extent).round(4).tolist()
        probe["plate_aabb_extent_m"] = to_np(plate.aabb_extent).round(4).tolist()
        full_update(ignore_objects=list(env.scene.objects))
        probe["pregrasp_no_obstacles"] = prims._target_in_reach_of_robot(pre, skip_obstacle_update=True)
        mg.update_obstacles()
    except Exception as e:
        probe["error"] = f"{type(e).__name__}: {e}"
    print(f"[pick] reach probe {probe}", flush=True)

    log = []
    t_end = time.time() + args.timeout_s * 20
    for primitive, obj in ((StarterSemanticActionPrimitiveSet.GRASP, fruit),
                           (StarterSemanticActionPrimitiveSet.PLACE_ON_TOP, plate)):
        t0, s0 = time.time(), rec.steps
        entry = {"primitive": primitive.name, "object": obj.name}
        try:
            for action in prims.apply_ref(primitive, obj, attempts=args.attempts):
                rec.step(action)
                if time.time() > t_end:
                    raise TimeoutError("scripted run exceeded its wall-clock budget")
            entry["ok"] = True
        except Exception as e:  # ActionPrimitiveErrorGroup and friends: a failed attempt is a result
            entry["ok"] = False
            entry["error"] = f"{type(e).__name__}: {e}"[:2000]
        entry["steps"], entry["seconds"] = rec.steps - s0, round(time.time() - t0, 1)
        log.append(entry)
        print(f"[pick] {entry}", flush=True)
        if not entry["ok"]:
            break
    # Let the scene settle so the final pose is a resting pose.
    for _ in range(30):
        rec.step(q_to_action(robot.get_joint_positions()))
    return {"primitives": log, "reach_probe": probe}


def run_policy(env, robot, rec, fruit, plate, args):
    from simfoundry.policies.openpi import OpenPIClient

    policy = OpenPIClient(host=args.policy_host, port=args.policy_port, open_loop_horizon=args.execute_horizon)
    arm = robot.default_arm
    gidx = robot.gripper_control_idx[arm]
    lo, hi = robot.joint_lower_limits[gidx], robot.joint_upper_limits[gidx]
    closes_upper = robot._grasping_direction == "upper"

    def gripper_closedness():
        # DROID reports 0 for open and 1 for closed. The Robotiq's knuckle joints close towards
        # their upper limit; the Panda's fingers close towards their lower limit.
        q = robot.get_joint_positions()[gidx]
        frac = (q - lo) / (hi - lo)
        return float(th.clip(th.mean(frac if closes_upper else 1 - frac), 0, 1))

    n_steps = int(args.timeout_s * args.action_freq)
    held_steps, infer_s, n_infer, gripper_log = 0, 0.0, 0, []
    obs = rec.obs
    j = 0
    while j < n_steps:
        for obj in env.scene.objects:
            obj.wake()
        ext = obs.get("external", {})
        wrist = obs[robot.name][rec.wrist_key(obs)]["rgb"][:, :, :3]
        b1 = ext["external_cam0_left"]["rgb"][:, :, :3]
        b2 = ext["external_cam1_left"]["rgb"][:, :, :3]
        qpos = robot.get_joint_positions()
        curr = {
            "exterior_image_1_left": to_np(b1),
            "exterior_image_2_left": to_np(b2),
            "wrist_image_left": to_np(wrist),
            "joint_position": to_np(qpos[:7]).astype(np.float32),
            "gripper_position": np.array([gripper_closedness()], dtype=np.float32),
        }
        t0 = time.time()
        chunk = policy.infer(curr, args.prompt)["action"]
        infer_s += time.time() - t0
        n_infer += 1
        if n_infer == 1:
            print(f"[pick] first chunk shape {np.shape(chunk)}, action[0] {np.round(chunk[0], 3)}", flush=True)
        for i in range(min(args.execute_horizon, len(chunk))):
            if j >= n_steps:
                break
            a = th.from_numpy(np.asarray(chunk[i], dtype=np.float32))
            # DROID: 1 closes the gripper. The scenes' gripper controllers take 1 to open.
            g = 1.0 - float(th.clip(a[7], 0, 1))
            action = th.cat([a[:7], th.tensor([1.0 if g > 0.5 else 0.0])])
            obs = rec.step(action)
            j += 1
            if j % 15 == 0:
                gripper_log.append([j, round(float(a[7]), 3), round(gripper_closedness(), 3)])
            p = placement(fruit, plate, robot)
            held_steps = held_steps + 1 if (p["on_target"] and rec.max_lift >= LIFT_THRESHOLD_M) else 0
            if held_steps >= 15:
                break
        if held_steps >= 15:
            break
    return {
        "policy_steps": j,
        "inferences": n_infer,
        "mean_inference_s": round(infer_s / max(1, n_infer), 3),
        "gripper_action_vs_closedness": gripper_log,
        "early_stop_on_success": held_steps >= 15,
    }


def main():
    args = parse_args()
    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    result_path, video_path = out / "result.json", out / "rollout.mp4"
    result = {"method": args.method, "scene_json": args.scene_json, "target": args.target,
              "place_on": args.place_on, "prompt": args.prompt, "completed": False}
    t_start = time.time()
    np.random.seed(args.seed)
    th.manual_seed(args.seed)

    scene_json = load_json_with_absolute_usd_paths(args.scene_json)
    fruit_name = find_object_name(scene_json, args.target)
    plate_name = find_object_name(scene_json, args.place_on)
    reg = scene_json["state"]["registry"]["object_registry"]
    init = scene_json["objects_info"]["init_info"]
    robot_name = next(n for n in init if n.startswith("robot"))
    rargs = init[robot_name]["args"]
    rargs["grasping_mode"] = "assisted"
    rargs["sensor_config"] = {"VisionSensor": {"sensor_kwargs": {
        "image_height": args.image_height, "image_width": args.image_width}}}
    if args.robot_pos:
        reg[robot_name]["root_link"]["pos"] = [float(v) for v in args.robot_pos.split(",")]
    jp = reg[robot_name]["joint_pos"]
    jp[:7] = DROID_HOME
    gripper_cfg = dict(rargs["controller_config"][f"gripper_0"])
    for k in ("goal", "control_filter"):
        gripper_cfg.pop(k, None)

    fruit_pos, _ = scene_pose(scene_json, fruit_name)
    plate_pos, _ = scene_pose(scene_json, plate_name)
    robot_pos, robot_ori = scene_pose(scene_json, robot_name)
    result.update(fruit=fruit_name, plate=plate_name, robot_base=robot_pos.round(3).tolist())
    modified = out / "scene.json"
    modified.write_text(json.dumps(scene_json))

    # A camera that frames the grasp: to the robot's right and above it, looking at the
    # midpoint of the fruit and the plate.
    mid = (fruit_pos + plate_pos) / 2 + np.array([0.0, 0.0, 0.03])
    yaw = Rotation.from_quat(robot_ori).as_euler("xyz")[2]
    rot = Rotation.from_euler("z", yaw)
    eye = robot_pos + rot.apply([0.2, -0.65, 0.6])
    view_name = "pick_view"
    ext_cfg = parse_config(str(Path(CFG_DIR) / "external_sensors" / "nv_franka_droid.yaml"))["external_sensors"]
    for s in ext_cfg:
        s["sensor_kwargs"]["image_height"], s["sensor_kwargs"]["image_width"] = args.image_height, args.image_width
        s["modalities"] = ["rgb"]
        if robot_name != "robot0":
            s["relative_prim_path"] = s["relative_prim_path"].replace("robot0", robot_name)
    ext_cfg.append({
        "sensor_type": "VisionSensor", "name": view_name, "relative_prim_path": f"/{view_name}",
        "modalities": ["rgb"],
        "sensor_kwargs": {"image_height": 480, "image_width": 640, "focal_length": 17.0},
        "position": eye.tolist(), "orientation": look_at_quat(eye, mid), "pose_frame": "scene",
    })

    og_cfg = {
        "env": {"external_sensors": ext_cfg, "action_frequency": args.action_freq,
                "rendering_frequency": args.action_freq, "physics_frequency": 120},
        "scene": {"type": "Scene", "scene_file": str(modified), "use_floor_plane": True,
                  "floor_plane_visible": True, "use_skybox": True, "include_robots": True},
    }

    env = None
    try:
        env = og.Environment(configs=og_cfg)
        env.reset()
        robot = env.robots[0]
        fruit = env.scene.object_registry("name", fruit_name)
        plate = env.scene.object_registry("name", plate_name)
        arm = robot.default_arm
        if args.method == "policy":
            # The eval stage's arm controller: absolute joint positions, smoothed.
            arm_cfg = {"name": "JointController", "motor_type": "position", "command_input_limits": None,
                       "use_delta_commands": False, "smoothing_filter_size": 5}
        else:
            # The starter primitives need absolute joint-position control (see their docstring).
            arm_cfg = {"name": "JointController", "motor_type": "position", "command_input_limits": None,
                       "use_delta_commands": False, "use_impedances": False}
        robot.reload_controllers({f"arm_{arm}": arm_cfg, f"gripper_{arm}": gripper_cfg})
        env.scene.update_initial_file()

        # Physics settings the eval stage applies: CCD, grippy fingers, 0.5 friction elsewhere.
        with og.sim.stopped():
            for obj in env.scene.objects:
                for link in obj.links.values():
                    link.ccd_enabled = True
            finger_mat = lazy.isaacsim.core.api.materials.PhysicsMaterial(
                prim_path=f"{robot.prim_path}/Looks/finger_mat", name="finger_mat",
                static_friction=2.0, dynamic_friction=2.0, restitution=None)
            for link_name, link in robot.links.items():
                if "finger" in link_name.lower() or "gripper" in link_name.lower():
                    for mesh in link.collision_meshes.values():
                        mesh.apply_physics_material(finger_mat)
            default_mat = lazy.isaacsim.core.api.materials.PhysicsMaterial(
                prim_path="/World/Looks/default_friction_mat", name="default_friction_mat",
                static_friction=0.5, dynamic_friction=0.5, restitution=None)
            for obj in env.scene.objects:
                if obj.name == "gs_background" or isinstance(obj, BaseRobot):
                    continue
                for link in obj.links.values():
                    for mesh in link.collision_meshes.values():
                        mesh.apply_physics_material(default_mat)
        for sensor in robot.sensors.values():
            if isinstance(sensor, VisionSensor):
                sensor.focal_length = 2.8
                sensor.horizontal_aperture = 5.376

        obs, _ = env.reset()
        for _ in range(10):
            og.sim.step()
            og.sim.render()
        obs, _ = env.reset()

        rec = Recorder(env, robot, fruit, plate, view_name)
        rec.observe(obs)
        result["fruit_start_z"] = rec.z0
        t_roll = time.time()
        if args.method == "scripted":
            result.update(run_scripted(env, robot, rec, fruit, plate, args))
        else:
            result.update(run_policy(env, robot, rec, fruit, plate, args))
        result["rollout_seconds"] = round(time.time() - t_roll, 1)
        result["sim_steps"] = rec.steps

        p = placement(fruit, plate, robot)
        result["max_lift_m"] = round(rec.max_lift, 4)
        result["lifted"] = rec.max_lift >= LIFT_THRESHOLD_M
        result["ever_grasped_assisted"] = rec.ever_in_hand
        result["placement"] = p
        result["success"] = bool(result["lifted"] and p["on_target"])

        imageio.mimwrite(video_path, rec.frames, fps=args.action_freq)
        result["video"] = video_path.name
        result["video_frames"] = len(rec.frames)
        result["completed"] = True
    except Exception as e:
        result["error"] = f"{type(e).__name__}: {e}"
        result["traceback"] = traceback.format_exc()[-4000:]
        print(result["traceback"], flush=True)
    finally:
        result["wall_seconds"] = round(time.time() - t_start, 1)
        result_path.write_text(json.dumps(result, indent=2, default=str))
        print(f"[pick] result: success={result.get('success')} lifted={result.get('lifted')} "
              f"completed={result['completed']} -> {result_path}", flush=True)
        og.shutdown()


if __name__ == "__main__":
    main()
