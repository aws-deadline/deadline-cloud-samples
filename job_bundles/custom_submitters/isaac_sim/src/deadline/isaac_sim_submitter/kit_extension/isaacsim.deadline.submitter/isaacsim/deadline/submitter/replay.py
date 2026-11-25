# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
"""Replay a robot trajectory from a job in the open stage, under PhysX.

A trajectory is a ``.npz`` file (NumPy ``savez``; ``*.trajectory.npz`` is the recommended
name) with:

* ``joint_positions``: float array ``(T, J)``, one row per frame, radians for revolute
  joints and meters for prismatic joints;
* ``joint_names``: string array ``(J,)``, matched to joint prim names under the robot prim;
* ``hz``: scalar, frames per second;
* ``object_T_reference`` (optional): float array ``(T, 4, 4)``, the tracked object's pose
  in the reference prim's frame, meters, column-vector convention (translation in the
  last column);
* ``robot_T_reference`` (optional): the robot root's pose in the reference prim's frame,
  same layout;
* ``success`` (optional): scalar bool, the episode's recorded outcome;
* ``label`` (optional): scalar string shown in the window.

Older evaluator output with ``roll_*`` names is read too: ``roll_q<N>`` (joint positions),
``roll_joint_names``, ``roll_hz``, ``roll_cube_T_base`` (object pose), ``roll_robot_T_base``
and ``roll_success``.

Replay is physics-driven: each frame sets the joints' drive targets
(``drive:angular:physics:targetPosition``, degrees, or ``drive:linear:...``, stage
units) and PhysX decides what happens to the objects, so a trajectory replayed under
different physics settings can end differently. The robot's start pose is written as
joint state and the object is placed where the trajectory started, so pressing Play
from frame 0 reproduces the recorded start.

Only ``pxr`` is used, which behaves the same on Isaac Sim 5.x and 6.x.
"""

from __future__ import annotations

import math
import os
import re
from dataclasses import dataclass, field
from typing import Any

import numpy as np

DEG = 180.0 / math.pi
SUFFIX = ".npz"

#: Older names accepted for each array, tried in order after the documented one.
ALIASES = {
    "joint_names": ("roll_joint_names",),
    "hz": ("roll_hz",),
    "object_T_reference": ("roll_cube_T_base",),
    "robot_T_reference": ("roll_robot_T_base",),
    "success": ("roll_success",),
}
_ROLL_Q = re.compile(r"^roll_q\d*$")


def _key(d: Any, name: str) -> str | None:
    """The archive key holding ``name``: the documented name, else an older alias."""
    if name in d.files:
        return name
    if name == "joint_positions":
        return next((k for k in d.files if _ROLL_Q.match(k)), None)
    return next((k for k in ALIASES.get(name, ()) if k in d.files), None)


@dataclass
class Trajectory:
    path: str
    joint_names: list
    q: np.ndarray  # (frames, joints), radians / meters
    hz: float
    object_T_reference: np.ndarray | None = None  # (frames, 4, 4)
    robot_T_reference: np.ndarray | None = None  # (frames, 4, 4)
    success: bool | None = None
    label: str = ""

    @property
    def frames(self) -> int:
        return int(self.q.shape[0])

    @property
    def seconds(self) -> float:
        return self.frames / self.hz if self.hz else 0.0

    def frame_at(self, t: float) -> int:
        return max(0, min(self.frames - 1, int(t * self.hz)))

    def object_start(self) -> np.ndarray | None:
        return None if self.object_T_reference is None else self.object_T_reference[0]

    def robot_start(self) -> np.ndarray | None:
        return None if self.robot_T_reference is None else self.robot_T_reference[0]


def _poses(d: Any, key: str, frames: int, name: str) -> np.ndarray | None:
    found = _key(d, key)
    if found is None:
        return None
    T = np.asarray(d[found], dtype=float)
    if T.ndim == 2:
        T = T[None]
    if T.ndim != 3 or T.shape[1:] != (4, 4) or T.shape[0] not in (1, frames):
        raise ValueError(
            f"{name}: {key} must have shape ({frames}, 4, 4), got {tuple(d[found].shape)}"
        )
    if not np.isfinite(T).all():
        raise ValueError(f"{name}: {key} has non-finite values")
    return T


def load(path: str) -> Trajectory:
    """Read and validate a trajectory file; ``ValueError`` names what is wrong."""
    name = os.path.basename(path)
    with np.load(path, allow_pickle=False) as d:
        keys = {k: _key(d, k) for k in ("joint_positions", "joint_names", "hz")}
        missing = [k for k, v in keys.items() if v is None]
        if missing:
            raise ValueError(f"{name} is not a trajectory: missing {', '.join(missing)}")
        q = np.asarray(d[keys["joint_positions"]], dtype=float)
        names = [str(n) for n in np.asarray(d[keys["joint_names"]]).reshape(-1)]
        if q.ndim != 2 or q.shape[0] < 1:
            raise ValueError(f"{name}: joint_positions must be a (frames, joints) array")
        if q.shape[1] != len(names):
            raise ValueError(
                f"{name}: joint_positions has {q.shape[1]} columns but joint_names has {len(names)}"
            )
        if not np.isfinite(q).all():
            raise ValueError(f"{name}: joint_positions has non-finite values")
        hz = float(np.asarray(d[keys["hz"]]).reshape(-1)[0])
        if not (math.isfinite(hz) and hz > 0):
            raise ValueError(f"{name}: hz must be a positive number, got {hz}")
        frames = int(q.shape[0])
        ok_key = _key(d, "success")
        success = bool(np.asarray(d[ok_key]).reshape(-1)[0]) if ok_key else None
        label = str(np.asarray(d["label"]).reshape(-1)[0]) if "label" in d.files else ""
        return Trajectory(
            path,
            names,
            q,
            hz,
            _poses(d, "object_T_reference", frames, name),
            _poses(d, "robot_T_reference", frames, name),
            success,
            label,
        )


# --------------------------------------------------------------- USD binding --


@dataclass
class Binding:
    """Which USD joint drives each trajectory column."""

    attrs: list = field(default_factory=list)  # (column, Usd.Attribute targetPosition, scale)
    states: list = field(default_factory=list)  # (column, Usd.Attribute state position, scale)
    missing: list = field(default_factory=list)  # trajectory joint names with no joint prim
    #: Joint names with a joint prim but no usable position drive: replay skips them.
    undriven: list = field(default_factory=list)
    #: Driven joint names with no joint state attribute: their start pose is not written.
    no_state: list = field(default_factory=list)

    @property
    def bound(self) -> int:
        return len(self.attrs)


def bind(stage: Any, robot_root: str, traj: Trajectory) -> Binding:
    """Match trajectory joints to joint prims under ``robot_root`` by prim name.

    Only joints that already have a position drive with nonzero stiffness are driven:
    applying a drive schema here would edit the user's stage permanently and still replay
    nothing (a new drive has zero stiffness, so targets do nothing). The rest are reported
    in :attr:`Binding.undriven`. Nothing is written outside an existing drive."""
    from pxr import Usd, UsdGeom, UsdPhysics

    root = stage.GetPrimAtPath(robot_root) if robot_root else None
    if not root or not root.IsValid():
        raise ValueError(f"no prim at {robot_root!r}")
    joints: dict = {}
    for prim in Usd.PrimRange(root, Usd.TraverseInstanceProxies()):
        if prim.IsA(UsdPhysics.RevoluteJoint):
            joints.setdefault(prim.GetName(), (prim, "angular", DEG))
        elif prim.IsA(UsdPhysics.PrismaticJoint):
            joints.setdefault(prim.GetName(), (prim, "linear", 1.0))
    out = Binding()
    for col, name in enumerate(traj.joint_names):
        hit = joints.get(name)
        if hit is None:
            out.missing.append(name)
            continue
        prim, kind, scale = hit
        drive = UsdPhysics.DriveAPI.Get(prim, kind)
        if not drive or not (drive.GetStiffnessAttr().Get() or 0.0):
            out.undriven.append(name)
            continue
        if kind == "linear":
            scale = 1.0 / (UsdGeom.GetStageMetersPerUnit(stage) or 1.0)
        out.attrs.append(
            (col, drive.GetTargetPositionAttr() or drive.CreateTargetPositionAttr(0.0), scale)
        )
        # The joint state attribute is PhysX's, and applying its schema would edit the
        # user's stage: write the start pose only where the attribute is already there.
        st = prim.GetAttribute(f"state:{kind}:physics:position")
        if st:
            out.states.append((col, st, scale))
        else:
            out.no_state.append(name)
    return out


def apply_frame(binding: Binding, traj: Trajectory, k: int) -> None:
    row = traj.q[max(0, min(traj.frames - 1, k))]
    for col, attr, scale in binding.attrs:
        attr.Set(float(row[col] * scale))


def set_start_pose(binding: Binding, traj: Trajectory) -> None:
    """Joint state + targets at frame 0, so Play starts from the recorded pose."""
    row = traj.q[0]
    for col, attr, scale in binding.states:
        attr.Set(float(row[col] * scale))
    apply_frame(binding, traj, 0)


def place_relative(stage: Any, prim_path: str, reference_path: str, T_reference_prim: Any) -> bool:
    """Put ``prim_path`` at ``T_reference_prim`` (4x4, meters, reference frame) relative to
    ``reference_path``, by rewriting its transform ops. Returns False if either is missing."""
    from pxr import Gf, Usd, UsdGeom

    prim, ref = stage.GetPrimAtPath(prim_path), stage.GetPrimAtPath(reference_path)
    if not (prim and prim.IsValid() and ref and ref.IsValid()):
        return False
    cache = UsdGeom.XformCache(Usd.TimeCode.Default())
    W_ref = cache.GetLocalToWorldTransform(ref)  # Gf row-vector convention
    W_parent = cache.GetLocalToWorldTransform(prim.GetParent())
    T_np = np.array(T_reference_prim, float)
    T_np[:3, 3] /= UsdGeom.GetStageMetersPerUnit(stage) or 1.0  # trajectories are in meters
    T = Gf.Matrix4d(*[float(v) for v in T_np.T.ravel()])  # column -> row convention
    local = T * W_ref * W_parent.GetInverse()
    xf = UsdGeom.Xformable(prim)
    xf.ClearXformOpOrder()
    xf.AddTransformOp().Set(local)
    return True


#: Load-message note when the object or reference prim setting is empty.
PLACEMENT_SKIPPED = (
    "object placement skipped: set objectPrim and referencePrim to place the object at the "
    "recorded start"
)


def _inside(path: str, root: str) -> bool:
    return path == root or path.startswith(root.rstrip("/") + "/")


def place_start(
    stage: Any,
    object_prim: str,
    reference_prim: str,
    traj: Trajectory,
    robot_prim: str = "",
) -> str:
    """Place the object (and, with ``robot_T_reference``, the robot) at the trajectory's
    recorded start; returns the load-message note ("" when nothing applies)."""
    notes = []
    T_obj, T_robot = traj.object_start(), traj.robot_start()
    if T_obj is not None:
        if not object_prim or not reference_prim:
            notes.append(PLACEMENT_SKIPPED)
        elif place_relative(stage, object_prim, reference_prim, T_obj):
            notes.append("object placed at the recorded start")
    # Moving the robot is skipped when the reference frame is part of the robot: the
    # reference would move with it.
    if (
        T_robot is not None
        and robot_prim
        and reference_prim
        and not _inside(reference_prim, robot_prim)
        and place_relative(stage, robot_prim, reference_prim, T_robot)
    ):
        notes.append("robot placed at the recorded start")
    return "; ".join(notes)
