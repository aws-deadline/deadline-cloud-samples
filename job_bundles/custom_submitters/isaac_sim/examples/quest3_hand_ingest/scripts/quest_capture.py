# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
"""The ``quest-capture`` session format, its coordinate frames, and resampling.

Sessions folder
---------------

    sessions.txt      optional: session order, one name per line (default: sorted folder names)
    <session>/        one recorded demonstration, one dataset episode
      session.jsonl   required (below)

``session.jsonl`` (format ``quest-capture``, version 1) is UTF-8 JSON Lines. Line 1 is the header;
every other line is a frame or an event, in time order. Units are meters and seconds. Quaternions
are ``[x, y, z, w]`` (the OpenXR ``XrQuaternionf`` and WebXR ``DOMPointReadOnly`` order). A pose is
``[px, py, pz, qx, qy, qz, qw]`` in the XR reference space the header names::

    {"type": "header", "format": "quest-capture", "version": 1,
     "source": "webxr" | "openxr" | "unity",          # the recorder
     "device": "Meta Quest 3",                         # free text
     "reference_space": "local-floor",                 # XR space of every pose (y up, -z forward)
     "joint_set": "openxr26" | "webxr25",              # hand joint order, see JOINT_SETS
     "world": {"T_xr_world": 4x4 row-major}            # optional task frame, e.g. a spatial anchor,
           | {"points": {"origin": p, "x": p, "y": p},  #   or three points touched on the table
              "touch_radius_m": 0.008},
     "task": "...", "hand": "right"}                   # optional instruction text, grasping hand
    {"type": "frame", "t": 0.011,                      # seconds, increasing (any origin)
     "head": pose | null,                              # viewer pose; null = not tracked
     "hands": {"right": [pose x J] | null, "left": [pose x J] | null},
     "conf": {"right": 1.0, "left": 0.5}}              # optional per-hand confidence, 0 to 1
    {"type": "event", "t": 1.2, "name": "calib_origin" | "calib_x" | "calib_y", "p": [x, y, z]}

``J`` is 26 for ``openxr26`` (the XR_EXT_hand_tracking ``XrHandJointEXT`` order) and 25 for
``webxr25`` (the WebXR Hand Input order, OpenXR's without the palm). Unknown record types are
ignored, so recorders can add their own.

Frames
------

* XR space: +X right, +Y up, -Z forward.
* World (task) frame, used for every output: +X right, +Y away from the person, +Z up. From the
  header's ``world`` or the ``calib_*`` events when given (``origin``, a point along +X, and
  optionally one toward +Y, each touched with the index tip, so the frame sits ``touch_radius_m``
  below them). Otherwise the XR space turned Z-up with its origin on the floor under the first
  head pose, flagged ``world_frame_unanchored``.

numpy only.
"""

from __future__ import annotations

import json
import os
import re

import numpy as np

FORMAT = "quest-capture"
FORMAT_VERSION = 1
SESSION_FILE = "session.jsonl"
SIDES = ("right", "left")

#: The 25 joints every output uses, in OpenXR order without the palm.
JOINT_NAMES = [
    "wrist",
    "thumb_metacarpal", "thumb_proximal", "thumb_distal", "thumb_tip",
    "index_metacarpal", "index_proximal", "index_intermediate", "index_distal", "index_tip",
    "middle_metacarpal", "middle_proximal", "middle_intermediate", "middle_distal", "middle_tip",
    "ring_metacarpal", "ring_proximal", "ring_intermediate", "ring_distal", "ring_tip",
    "little_metacarpal", "little_proximal", "little_intermediate", "little_distal", "little_tip",
]  # fmt: skip
WRIST, THUMB_TIP, INDEX_TIP = 0, 4, 9
#: Joint count of each set, and the index of each output joint in it.
JOINT_SETS = {"openxr26": (26, list(range(1, 26))), "webxr25": (25, list(range(25)))}

#: World (Z up, +Y away) from XR (Y up, -Z forward): x_w = x_xr, y_w = -z_xr, z_w = y_xr.
R_WORLD_XR = np.array([[1.0, 0.0, 0.0], [0.0, 0.0, -1.0], [0.0, 1.0, 0.0]])
UP_XR = np.array([0.0, 1.0, 0.0])
TOUCH_RADIUS_M = 0.008
_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")


class InputError(Exception):
    """A session that cannot be used; the message says why."""


# ------------------------------------------------------------------ reading --


def list_sessions(sessions_dir: str) -> list:
    """``[(name, folder)]`` in episode order: ``sessions.txt`` when present, else sorted names."""
    if not os.path.isdir(sessions_dir):
        raise InputError(f"{sessions_dir!r} is not a folder")
    found = {
        d: os.path.join(sessions_dir, d)
        for d in os.listdir(sessions_dir)
        if not d.startswith(".") and os.path.isfile(os.path.join(sessions_dir, d, SESSION_FILE))
    }
    order = os.path.join(sessions_dir, "sessions.txt")
    if os.path.isfile(order):
        with open(order, encoding="utf-8") as fh:
            names = [n.strip() for n in fh.read().splitlines()]
        names = [n for n in names if n and not n.startswith("#")]
        missing = [n for n in names if n not in found]
        if missing:
            raise InputError(f"sessions.txt names folders without {SESSION_FILE}: {missing[:5]}")
    else:
        names = sorted(found)
    if not names:
        raise InputError(f"no <session>/{SESSION_FILE} in {sessions_dir}")
    for n in names:
        if not _NAME.match(n) or ".." in n:
            raise InputError(f"session name {n!r}: use letters, digits, '_', '-' and '.' only")
    return [(n, found[n]) for n in names]


def read_session(path: str) -> tuple:
    """``(header, frames, events)`` from one ``session.jsonl``, checked line by line."""
    header, frames, events = None, [], []
    with open(path, encoding="utf-8") as fh:
        for ln, line in enumerate(fh, 1):
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except ValueError as exc:
                raise InputError(f"{path}:{ln}: not JSON ({exc})") from None
            if not isinstance(rec, dict):
                raise InputError(f"{path}:{ln}: not a JSON object")
            kind = rec.get("type")
            if header is None:
                if kind != "header" or rec.get("format") != FORMAT:
                    raise InputError(f"{path}:{ln}: the first line must be the {FORMAT} header")
                if rec.get("version") != FORMAT_VERSION:
                    raise InputError(
                        f"{path}: version {rec.get('version')!r}; this reads {FORMAT_VERSION}"
                    )
                if rec.setdefault("joint_set", "openxr26") not in JOINT_SETS:
                    raise InputError(
                        f"{path}: joint_set {rec['joint_set']!r}; use {' or '.join(JOINT_SETS)}"
                    )
                header = rec
            elif kind == "frame":
                _check_frame(rec, JOINT_SETS[header["joint_set"]][0], f"{path}:{ln}")
                frames.append(rec)
            elif kind == "event":
                events.append(rec)
    if header is None:
        raise InputError(f"{path} is empty")
    if len(frames) < 2:
        raise InputError(f"{path} has {len(frames)} frame(s); need at least 2")
    t = [f["t"] for f in frames]
    if any(b <= a for a, b in zip(t, t[1:])):  # noqa: RUF007 - pairwise needs 3.10
        raise InputError(f"{path}: frame times must increase")
    return header, frames, events


def _check_frame(rec: dict, joints: int, where: str) -> None:
    if not isinstance(rec.get("t"), (int, float)) or isinstance(rec.get("t"), bool):
        raise InputError(f"{where}: a frame needs a numeric t")
    head = rec.get("head")
    if head is not None and (not isinstance(head, list) or len(head) != 7):
        raise InputError(f"{where}: head needs 7 numbers")
    for side, j in (rec.get("hands") or {}).items():
        if side not in SIDES:
            raise InputError(f"{where}: hand {side!r}; use right or left")
        if j is not None and (
            not isinstance(j, list) or len(j) != joints or any(len(p) != 7 for p in j)
        ):
            raise InputError(f"{where}: the {side} hand needs {joints} joints of 7 numbers")


def arrays(header: dict, frames: list) -> dict:
    """The session as arrays: ``t`` (m,), ``head`` (m,7), ``head_ok`` (m,), and per side
    ``<side>`` (m,25,7) joint poses, ``<side>_ok`` (m,), ``<side>_conf`` (m,)."""
    _n, pick = JOINT_SETS[header["joint_set"]]
    m = len(frames)
    out: dict = {"t": np.array([f["t"] for f in frames], float)}
    head = np.full((m, 7), np.nan)
    for i, f in enumerate(frames):
        if f.get("head") is not None:
            head[i] = f["head"]
    out["head"], out["head_ok"] = head, np.isfinite(head).all(1)
    for side in SIDES:
        poses = np.full((m, len(JOINT_NAMES), 7), np.nan)
        conf = np.ones(m)
        for i, f in enumerate(frames):
            j = (f.get("hands") or {}).get(side)
            if j is not None:
                poses[i] = np.asarray(j, float)[pick]
            c = (f.get("conf") or {}).get(side)
            if isinstance(c, (int, float)):
                conf[i] = float(c)
        ok = np.isfinite(poses).all((1, 2))
        out[side], out[side + "_ok"], out[side + "_conf"] = poses, ok, np.where(ok, conf, np.nan)
    return out


# ------------------------------------------------------------------- frames --


def _quat_to_R(q: np.ndarray) -> np.ndarray:
    """(n,4) [x, y, z, w] -> (n,3,3)."""
    q = q / np.linalg.norm(q, axis=1, keepdims=True)
    x, y, z, w = q.T
    return np.stack(
        [
            np.stack([1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)], -1),
            np.stack([2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)], -1),
            np.stack([2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)], -1),
        ],
        1,
    )


def _R_to_quat(R: np.ndarray) -> np.ndarray:
    """(n,3,3) -> (n,4) [x, y, z, w], w >= 0."""
    m = R
    w = np.sqrt(np.clip(1 + m[:, 0, 0] + m[:, 1, 1] + m[:, 2, 2], 0, None)) / 2
    x = np.sqrt(np.clip(1 + m[:, 0, 0] - m[:, 1, 1] - m[:, 2, 2], 0, None)) / 2
    y = np.sqrt(np.clip(1 - m[:, 0, 0] + m[:, 1, 1] - m[:, 2, 2], 0, None)) / 2
    z = np.sqrt(np.clip(1 - m[:, 0, 0] - m[:, 1, 1] + m[:, 2, 2], 0, None)) / 2
    x = np.copysign(x, m[:, 2, 1] - m[:, 1, 2])
    y = np.copysign(y, m[:, 0, 2] - m[:, 2, 0])
    z = np.copysign(z, m[:, 1, 0] - m[:, 0, 1])
    q = np.stack([x, y, z, w], 1)
    return q / np.linalg.norm(q, axis=1, keepdims=True)


def transform_poses(T: np.ndarray, poses: np.ndarray) -> np.ndarray:
    """Apply the rigid 4x4 ``T`` to poses (..., 7); NaN rows stay NaN."""
    flat = poses.reshape(-1, 7)
    out = np.full_like(flat, np.nan)
    good = np.isfinite(flat).all(1)
    if good.any():
        p, q = flat[good, :3], flat[good, 3:]
        # numpy 2.0 on macOS warns spuriously in matmul (the inputs are finite).
        with np.errstate(divide="ignore", over="ignore", invalid="ignore"):
            out[good, :3] = p @ T[:3, :3].T + T[:3, 3]
        out[good, 3:] = _R_to_quat(T[:3, :3] @ _quat_to_R(q))
    return out.reshape(poses.shape)


def world_frame(header: dict, events: list, head0) -> tuple:
    """``(T_world_xr, info, flags)``: how to turn XR-space poses into the task frame."""
    world = header.get("world") or {}
    points = dict(world.get("points") or {})
    for ev in events:
        name = str(ev.get("name", ""))
        if name.startswith("calib_") and ev.get("p") is not None:
            points[name[len("calib_") :]] = ev["p"]
    flags: list = []
    if "T_xr_world" in world:
        T_xr_world = np.array(world["T_xr_world"], float).reshape(4, 4)
        if abs(np.linalg.det(T_xr_world[:3, :3]) - 1) > 1e-3:
            raise InputError("world.T_xr_world is not a rigid transform")
        return np.linalg.inv(T_xr_world), {"method": "T_xr_world"}, flags
    if "origin" in points and "x" in points:
        o, px = np.array(points["origin"], float), np.array(points["x"], float)
        r = float(world.get("touch_radius_m", TOUCH_RADIUS_M))
        x = px - o
        x = x - (x @ UP_XR) * UP_XR  # level: XR spaces on the headset are gravity aligned
        if np.linalg.norm(x) < 0.03:
            raise InputError("calibration points origin and x are under 30 mm apart")
        x /= np.linalg.norm(x)
        T_xr_world = np.eye(4)
        T_xr_world[:3, :3] = np.stack([x, np.cross(UP_XR, x), UP_XR], 1)
        T_xr_world[:3, 3] = o - r * UP_XR
        tilt = float(
            np.degrees(np.arcsin(min(1.0, abs((px - o) @ UP_XR) / np.linalg.norm(px - o))))
        )
        if tilt > 5:
            flags.append("calibration_tilt_over_5_degrees")
        return (
            np.linalg.inv(T_xr_world),
            {"method": "touch_points", "tilt_deg": round(tilt, 2)},
            flags,
        )
    T = np.eye(4)
    T[:3, :3] = R_WORLD_XR
    origin = np.array([head0[0], 0.0, head0[2]]) if head0 is not None else np.zeros(3)
    T[:3, 3] = -R_WORLD_XR @ origin
    return T, {"method": "unanchored"}, ["world_frame_unanchored"]


# ---------------------------------------------------------------- resampling --


def _slerp(q0: np.ndarray, q1: np.ndarray, w: np.ndarray) -> np.ndarray:
    q0 = q0 / np.linalg.norm(q0, axis=-1, keepdims=True)
    q1 = q1 / np.linalg.norm(q1, axis=-1, keepdims=True)
    d = np.sum(q0 * q1, -1)
    q1 = np.where(d[..., None] < 0, -q1, q1)
    th = np.arccos(np.abs(d).clip(-1, 1))
    s = np.sin(th)
    small = s < 1e-6
    a = np.where(small, 1 - w, np.sin((1 - w) * th) / np.where(small, 1, s))
    b = np.where(small, w, np.sin(w * th) / np.where(small, 1, s))
    q = a[..., None] * q0 + b[..., None] * q1
    return q / np.linalg.norm(q, axis=-1, keepdims=True)


def resample(ts: np.ndarray, poses: np.ndarray, ok: np.ndarray, t: np.ndarray, max_gap: float):
    """Poses (m, ..., 7) sampled at ``ts`` -> (n, ..., 7) at ``t``: linear positions, slerped
    rotations, bridging tracking gaps up to ``max_gap`` seconds. Returns ``(poses, valid)``;
    frames outside the tracked span or inside a longer gap are NaN and not valid."""
    out = np.full((len(t),) + poses.shape[1:], np.nan)
    idx = np.flatnonzero(ok)
    if len(idx) == 0:
        return out, np.zeros(len(t), bool)
    vt = ts[idx]
    k = np.searchsorted(vt, t, side="right")
    lo, hi = np.clip(k - 1, 0, len(vt) - 1), np.clip(k, 0, len(vt) - 1)
    span = vt[hi] - vt[lo]
    w = np.where(span > 0, (t - vt[lo]) / np.where(span > 0, span, 1), 0.0).clip(0, 1)
    valid = (t >= vt[0] - 1e-9) & (t <= vt[-1] + 1e-9) & (span <= max_gap + 1e-9)
    if valid.any():
        a, b = poses[idx[lo[valid]]], poses[idx[hi[valid]]]
        ww = w[valid].reshape((-1,) + (1,) * (poses.ndim - 1))
        out[valid, ..., :3] = (1 - ww) * a[..., :3] + ww * b[..., :3]
        out[valid, ..., 3:] = _slerp(a[..., 3:], b[..., 3:], ww[..., 0])
    return out, valid
