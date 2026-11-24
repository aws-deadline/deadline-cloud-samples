# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
"""Trajectory loading and USD replay binding, on a stage authored here (usd-core)."""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any

import numpy as np
import pytest
from isaacsim.deadline.submitter import replay as rp


def write_trajectory(tmp_path: Path, name: str = "ep_000.trajectory.npz", **arrays: Any) -> str:
    T = np.eye(4)
    T[:3, 3] = [0.1, 0.0, 0.05]
    data: dict = {
        "joint_positions": np.array([[0.0, math.pi / 2, 0.1], [0.1, math.pi / 4, 0.2]]),
        "joint_names": np.array(["left_elbow", "right_elbow", "lift"]),
        "hz": np.float32(20.0),
        "object_T_reference": np.stack([T, T]),
        "success": np.bool_(True),
        "label": np.array("episode 0"),
    }
    data.update(arrays)
    data = {k: v for k, v in data.items() if v is not None}
    p = tmp_path / name
    np.savez(p, **data)
    return str(p)


def test_load_full_and_minimal(tmp_path: Path) -> None:
    t = rp.load(write_trajectory(tmp_path))
    assert (t.frames, t.hz, t.success, t.label) == (2, 20.0, True, "episode 0")
    assert t.frame_at(99) == 1 and t.seconds == pytest.approx(0.1)
    start = t.object_start()
    assert start is not None and start[0, 3] == pytest.approx(0.1)
    m = rp.load(
        write_trajectory(
            tmp_path, "m.trajectory.npz", object_T_reference=None, success=None, label=None
        )
    )
    assert m.object_start() is None and m.success is None and m.label == ""


@pytest.mark.parametrize(
    "arrays,match",
    [
        ({"hz": None}, "missing hz"),
        ({"joint_names": np.array(["a", "b"])}, "3 columns but joint_names has 2"),
        ({"joint_positions": np.zeros(3)}, r"\(frames, joints\)"),
        ({"hz": np.float32(0.0)}, "positive"),
        ({"object_T_reference": np.zeros((5, 4, 4))}, r"shape \(2, 4, 4\)"),
        ({"joint_positions": np.array([[np.nan, 0, 0], [0, 0, 0]])}, "non-finite"),
    ],
)
def test_load_rejects_bad_files(tmp_path: Path, arrays: dict, match: str) -> None:
    with pytest.raises(ValueError, match=match):
        rp.load(write_trajectory(tmp_path, **arrays))


def _drive(s: Any, path: str, kind: str, *, stiffness: float = 1000.0, state: bool = True) -> Any:
    """What an articulation joint carries in a real stage: a position drive, and the PhysX
    joint state attribute the start pose is written to."""
    from pxr import Sdf, UsdPhysics

    prim = s.GetPrimAtPath(path)
    UsdPhysics.DriveAPI.Apply(prim, kind).CreateStiffnessAttr(stiffness)
    if state:
        prim.CreateAttribute(f"state:{kind}:physics:position", Sdf.ValueTypeNames.Float)
    return prim


def _stage(drives: bool = True) -> Any:
    # usd-core has no wheel for some platforms and versions; a broken install also skips.
    pytest.importorskip("pxr", exc_type=ImportError)
    from pxr import Gf, Usd, UsdGeom, UsdPhysics

    s = Usd.Stage.CreateInMemory()
    UsdGeom.SetStageMetersPerUnit(s, 1.0)
    UsdGeom.Xform.Define(s, "/World/Robot")
    for n in ("left_elbow", "right_elbow"):
        UsdPhysics.RevoluteJoint.Define(s, f"/World/Robot/joints/{n}")
    UsdPhysics.PrismaticJoint.Define(s, "/World/Robot/joints/lift")
    if drives:
        for n in ("left_elbow", "right_elbow"):
            _drive(s, f"/World/Robot/joints/{n}", "angular")
        _drive(s, "/World/Robot/joints/lift", "linear")
    ref = UsdGeom.Xform.Define(s, "/World/Table/Reference")
    ref.AddTranslateOp().Set(Gf.Vec3d(1.0, 2.0, 0.5))
    UsdGeom.Xform.Define(s, "/World/Table/Object")
    return s


def _world_translation(s: Any, path: str) -> tuple:
    from pxr import UsdGeom

    return tuple(
        UsdGeom.XformCache().GetLocalToWorldTransform(s.GetPrimAtPath(path)).ExtractTranslation()
    )


def test_bind_apply_and_place(tmp_path: Path) -> None:
    s, t = _stage(), rp.load(write_trajectory(tmp_path))
    b = rp.bind(s, "/World/Robot", t)
    assert b.bound == 3 and b.missing == []
    rp.set_start_pose(b, t)
    right = s.GetPrimAtPath("/World/Robot/joints/right_elbow")
    assert right.GetAttribute("drive:angular:physics:targetPosition").Get() == pytest.approx(90.0)
    assert right.GetAttribute("state:angular:physics:position").Get() == pytest.approx(90.0)
    rp.apply_frame(b, t, 1)
    assert right.GetAttribute("drive:angular:physics:targetPosition").Get() == pytest.approx(45.0)
    lift = s.GetPrimAtPath("/World/Robot/joints/lift")
    assert lift.GetAttribute("drive:linear:physics:targetPosition").Get() == pytest.approx(0.2)
    assert rp.place_relative(s, "/World/Table/Object", "/World/Table/Reference", t.object_start())
    assert _world_translation(s, "/World/Table/Object") == pytest.approx((1.1, 2.0, 0.55))


def test_unmatched_joints_are_reported(tmp_path: Path) -> None:
    s = _stage()
    t = rp.load(
        write_trajectory(
            tmp_path,
            joint_positions=np.zeros((2, 2)),
            joint_names=np.array(["lift", "wrist"]),
        )
    )
    b = rp.bind(s, "/World/Robot", t)
    assert b.bound == 1 and b.missing == ["wrist"]


def test_place_start(tmp_path: Path) -> None:
    s, t = _stage(), rp.load(write_trajectory(tmp_path))
    assert rp.place_start(s, "", "", t) == rp.PLACEMENT_SKIPPED
    assert "set objectPrim and referencePrim" in rp.place_start(s, "/World/Table/Object", "", t)
    assert rp.place_start(s, "/World/Nope", "/World/Table/Reference", t) == ""
    assert (
        rp.place_start(s, "/World/Table/Object", "/World/Table/Reference", t)
        == "object placed at the recorded start"
    )
    no_obj = rp.load(write_trajectory(tmp_path, "n.trajectory.npz", object_T_reference=None))
    assert rp.place_start(s, "/World/Table/Object", "/World/Table/Reference", no_obj) == ""


def test_robot_placement_needs_an_outside_reference(tmp_path: Path) -> None:
    s = _stage()
    T = np.eye(4)
    T[:3, 3] = [0.0, -0.5, 0.0]
    t = rp.load(write_trajectory(tmp_path, robot_T_reference=np.stack([T, T])))
    note = rp.place_start(s, "/World/Table/Object", "/World/Table/Reference", t, "/World/Robot")
    assert note == "object placed at the recorded start; robot placed at the recorded start"
    assert _world_translation(s, "/World/Robot") == pytest.approx((1.0, 1.5, 0.5))
    # A reference inside the robot would move with it: the robot is left alone.
    inside = rp.place_start(s, "", "/World/Robot/joints", t, "/World/Robot")
    assert "robot" not in inside


def test_bind_errors(tmp_path: Path) -> None:
    s, t = _stage(), rp.load(write_trajectory(tmp_path))
    with pytest.raises(ValueError, match="no prim"):
        rp.bind(s, "/World/Nope", t)
    with pytest.raises(ValueError, match="no prim"):
        rp.bind(s, "", t)


def test_joints_without_a_position_drive_are_not_bound(tmp_path: Path) -> None:
    """A joint with no drive, or one with zero stiffness, ignores targets. Applying a drive
    to it would edit the user's stage permanently and still replay nothing."""
    s, t = _stage(drives=False), rp.load(write_trajectory(tmp_path))
    _drive(s, "/World/Robot/joints/left_elbow", "angular")
    _drive(s, "/World/Robot/joints/lift", "linear", stiffness=0.0)
    b = rp.bind(s, "/World/Robot", t)
    assert b.bound == 1 and b.undriven == ["right_elbow", "lift"] and b.missing == []
    right = s.GetPrimAtPath("/World/Robot/joints/right_elbow")
    assert right.GetAppliedSchemas() == []
    assert not right.GetAttribute("drive:angular:physics:targetPosition")
    rp.set_start_pose(b, t)
    rp.apply_frame(b, t, 1)
    lift = s.GetPrimAtPath("/World/Robot/joints/lift")
    assert lift.GetAttribute("drive:linear:physics:targetPosition").Get() == pytest.approx(0.0)
    left = s.GetPrimAtPath("/World/Robot/joints/left_elbow")
    assert left.GetAttribute("drive:angular:physics:targetPosition").Get() == pytest.approx(
        math.degrees(0.1)
    )


def test_start_pose_is_written_only_where_a_joint_state_exists(tmp_path: Path) -> None:
    """No PhysxJointStateAPI is applied: the attribute is written only where it is already."""
    s, t = _stage(drives=False), rp.load(write_trajectory(tmp_path))
    _drive(s, "/World/Robot/joints/left_elbow", "angular")
    _drive(s, "/World/Robot/joints/right_elbow", "angular", state=False)
    _drive(s, "/World/Robot/joints/lift", "linear")
    b = rp.bind(s, "/World/Robot", t)
    assert b.bound == 3 and b.no_state == ["right_elbow"]
    rp.set_start_pose(b, t)
    right = s.GetPrimAtPath("/World/Robot/joints/right_elbow")
    assert not right.GetAttribute("state:angular:physics:position")
    assert not [x for x in right.GetAppliedSchemas() if "JointState" in x]
    assert right.GetAttribute("drive:angular:physics:targetPosition").Get() == pytest.approx(90.0)
    lift = s.GetPrimAtPath("/World/Robot/joints/lift")
    assert lift.GetAttribute("state:linear:physics:position").Get() == pytest.approx(0.1)


def test_load_reads_older_roll_names(tmp_path: Path) -> None:
    """Older evaluator rollouts (``roll_*`` arrays, any ``.npz`` name) replay as is."""
    T = np.eye(4, dtype=np.float32)
    p = tmp_path / "diag_ep_002.npz"
    np.savez(
        p,
        roll_q39=np.zeros((3, 2), dtype=np.float32),
        roll_joint_names=np.array(["a", "b"]),
        roll_hz=np.float32(20.0),
        roll_cube_T_base=np.stack([T, T, T]),
        roll_robot_T_base=np.stack([T, T, T]),
        roll_success=np.bool_(True),
        unrelated=np.zeros(4),
    )
    t = rp.load(str(p))
    assert (t.frames, t.hz, t.success, t.joint_names) == (3, 20.0, True, ["a", "b"])
    assert t.object_start() is not None and t.robot_T_reference is not None


def test_load_names_the_missing_arrays_for_other_npz_files(tmp_path: Path) -> None:
    p = tmp_path / "stats.npz"
    np.savez(p, mean=np.zeros(3))
    with pytest.raises(ValueError, match="stats.npz is not a trajectory: missing joint_positions"):
        rp.load(str(p))
