# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
"""What the app asks of the open stage: its file, trajectory replay, USD references, the
replay's prims and the selection.
Only this module and :mod:`.extension` touch ``omni.usd`` and ``omni.timeline``."""

from __future__ import annotations

import os

import omni.usd

from . import replay as rp
from . import settings as st

#: Where loaded USD files are added as references.
REFERENCE_ROOT = "/World/DeadlineCloud"


def _stage():
    return omni.usd.get_context().get_stage()


def stage_file_path() -> str:
    """The open stage's file, or "" for an unsaved stage."""
    stage = _stage()
    if stage is None:
        return ""
    layer = stage.GetRootLayer()
    path = layer.realPath if layer else ""
    return path if path and not layer.anonymous else ""


def add_reference(path: str) -> str:
    """Add ``path`` as a reference on a new prim under :data:`REFERENCE_ROOT`; the prim path."""
    from pxr import Tf, UsdGeom

    stage = _stage()
    if stage is None:
        raise ValueError("no stage is open")
    UsdGeom.Xform.Define(stage, REFERENCE_ROOT)
    name = Tf.MakeValidIdentifier(os.path.splitext(os.path.basename(path))[0])
    prim_path, n = f"{REFERENCE_ROOT}/{name}", 1
    while stage.GetPrimAtPath(prim_path):
        n += 1
        prim_path = f"{REFERENCE_ROOT}/{name}_{n}"
    prim = UsdGeom.Xform.Define(stage, prim_path).GetPrim()
    prim.GetReferences().AddReference(path)
    return prim_path


#: Replay role (protocol) -> setting key.
ROLE_SETTINGS = {"robot": st.ROBOT_PRIM, "object": st.OBJECT_PRIM, "reference": st.REFERENCE_PRIM}


def replay_prims() -> dict:
    """``{"prims": {role: path}, "exists": {role: bool}}`` for the open stage. An empty path
    counts as not existing (the object and reference are optional)."""
    stage = _stage()
    prims = {role: st.get_str(key) for role, key in ROLE_SETTINGS.items()}

    def exists(path: str) -> bool:
        if not path or stage is None:
            return False
        prim = stage.GetPrimAtPath(path)
        return bool(prim and prim.IsValid())

    return {"prims": prims, "exists": {role: exists(p) for role, p in prims.items()}}


def set_replay_prims(prims: dict) -> dict:
    """Save the given roles' prim paths in the persistent settings (the next replay uses
    them), then report all of them as :func:`replay_prims` does."""
    for role, path in prims.items():
        st.set_str(ROLE_SETTINGS[role], path)
    return replay_prims()


def selected_prims(limit: int) -> list:
    """The prim paths selected in the stage, at most ``limit``."""
    try:
        paths = omni.usd.get_context().get_selection().get_selected_prim_paths()
    except Exception:  # noqa: BLE001 - no selection API: nothing selected
        return []
    return [str(p) for p in list(paths or [])[:limit]]


class ReplaySession:
    """Drives one trajectory's joint targets from the timeline, frame by frame."""

    def __init__(self):
        self.traj = None
        self.binding = None
        self.message = ""

    def load(self, path: str) -> str:
        import omni.timeline

        stage = _stage()
        traj = rp.load(path)
        binding = rp.bind(stage, st.get_str(st.ROBOT_PRIM), traj)
        if not binding.bound:
            why = (
                f"{len(binding.undriven)} joints have no position drive"
                if binding.undriven
                else f"no joints of this trajectory under {st.get_str(st.ROBOT_PRIM)}"
            )
            raise ValueError(
                f"{why} (set the robot prim with the setting {st.ROOT}{st.ROBOT_PRIM})"
            )
        omni.timeline.get_timeline_interface().stop()
        rp.set_start_pose(binding, traj)
        placed = rp.place_start(
            stage,
            st.get_str(st.OBJECT_PRIM),
            st.get_str(st.REFERENCE_PRIM),
            traj,
            st.get_str(st.ROBOT_PRIM),
        )
        self.traj, self.binding = traj, binding
        notes = [
            f"{traj.label or os.path.basename(path)}: {traj.frames} frames, {traj.seconds:.1f} s, "
            f"{binding.bound} joints bound"
            + (f", {len(binding.missing)} not in the stage" if binding.missing else "")
        ]
        if binding.undriven:
            notes.append(
                f"{len(binding.undriven)} joints have no position drive; replay skips them"
            )
        if binding.no_state:
            notes.append(
                f"{len(binding.no_state)} joints have no joint state, so their start pose is "
                "not written"
            )
        if placed:
            notes.append(placed)
        self.message = "; ".join(notes)
        return self.message

    def play(self) -> None:
        import omni.timeline

        if self.traj is None:
            return
        tl = omni.timeline.get_timeline_interface()
        tl.stop()
        # The stage's timeline may end before the episode does (it would loop back to 0
        # every few seconds); run it to the episode's end plus a short hold.
        if tl.get_end_time() < self.traj.seconds + 2.0:
            tl.set_end_time(self.traj.seconds + 2.0)
        tl.set_current_time(tl.get_start_time())
        rp.set_start_pose(self.binding, self.traj)
        tl.play()

    def stop(self) -> None:
        import omni.timeline

        omni.timeline.get_timeline_interface().stop()

    def on_update(self) -> None:
        if self.traj is None:
            return
        import omni.timeline

        tl = omni.timeline.get_timeline_interface()
        if tl.is_playing():
            rp.apply_frame(
                self.binding,
                self.traj,
                self.traj.frame_at(tl.get_current_time() - tl.get_start_time()),
            )
