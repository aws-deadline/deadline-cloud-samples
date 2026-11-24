# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
"""Synthetic ``quest-capture`` sessions, for trying the bundle without a headset (stdlib only).

    make_sample_sessions.py --out DIR [--sessions anchored,lost,unanchored,webxr] [--rate 60]

Writes ``DIR/<session>/session.jsonl`` and ``DIR/sessions.txt``. Each session is one right-hand
pick-and-place of a 46 mm cube on a table: rest, reach, pinch, lift, carry, place, open,
retreat, rest. The left hand rests on the table.

    anchored    openxr26 joints, touch-point calibration, a 50 ms right-hand dropout (bridged)
    lost        as anchored, but the right hand is untracked from 1.2 s to 4.4 s (flagged)
    unanchored  as anchored, without calibration (task frame unanchored)
    webxr       webxr25 joints, calibration as a T_xr_world header (as from a spatial anchor)
"""

from __future__ import annotations

import argparse
import json
import math
import os
import random
import sys

KINDS = ("anchored", "lost", "unanchored", "webxr")

DURATION = 6.0
CUBE_START = (0.05, 0.10)  # world xy (m); z = 0.023 (half the edge)
TARGET = (-0.10, 0.15, 0.05)  # seated cube center (m)
REST = (0.20, -0.05, 0.10)  # right pinch center at rest
LEFT_REST = (-0.25, -0.05, 0.03)  # left pinch center, resting on the table
HEAD = (0.05, -0.30, 0.55)  # head in world, looking at LOOK
LOOK = (0.0, 0.10, 0.0)
TABLE_XR = (0.0, 0.74, -0.35)  # world origin (table surface) in XR local-floor space
TOUCH_R = 0.008
GRASP_T = (2.0, 2.4)  # closing window
RELEASE_T = (4.0, 4.5)  # opening window (keeps opening while the hand departs)


# ---------------------------------------------------------------- 3D math --


def add(a, b):
    return tuple(x + y for x, y in zip(a, b))


def sub(a, b):
    return tuple(x - y for x, y in zip(a, b))


def mul(a, s):
    return tuple(x * s for x in a)


def lerp(a, b, w):
    return tuple(x + (y - x) * w for x, y in zip(a, b))


def cross(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def norm(a):
    n = math.sqrt(sum(x * x for x in a))
    return tuple(x / n for x in a)


def matvec(R, v):
    return tuple(sum(R[i][k] * v[k] for k in range(3)) for i in range(3))


def matmul(A, B):
    return [[sum(A[i][k] * B[k][j] for k in range(3)) for j in range(3)] for i in range(3)]


def cols(x, y, z):
    return [[x[i], y[i], z[i]] for i in range(3)]


def quat_xyzw(R):
    """Rotation matrix -> unit quaternion [x, y, z, w]."""
    t = R[0][0] + R[1][1] + R[2][2]
    if t > 0:
        s = math.sqrt(t + 1.0) * 2
        q = ((R[2][1] - R[1][2]) / s, (R[0][2] - R[2][0]) / s, (R[1][0] - R[0][1]) / s, 0.25 * s)
    elif R[0][0] > R[1][1] and R[0][0] > R[2][2]:
        s = math.sqrt(1.0 + R[0][0] - R[1][1] - R[2][2]) * 2
        q = (0.25 * s, (R[0][1] + R[1][0]) / s, (R[0][2] + R[2][0]) / s, (R[2][1] - R[1][2]) / s)
    elif R[1][1] > R[2][2]:
        s = math.sqrt(1.0 + R[1][1] - R[0][0] - R[2][2]) * 2
        q = ((R[0][1] + R[1][0]) / s, 0.25 * s, (R[1][2] + R[2][1]) / s, (R[0][2] - R[2][0]) / s)
    else:
        s = math.sqrt(1.0 + R[2][2] - R[0][0] - R[1][1]) * 2
        q = ((R[0][2] + R[2][0]) / s, (R[1][2] + R[2][1]) / s, 0.25 * s, (R[1][0] - R[0][1]) / s)
    return list(norm(q))


#: World (task) frame axes in XR space: +X right, +Y away (-Z_xr), +Z up (+Y_xr).
R_XR_WORLD = cols((1.0, 0.0, 0.0), (0.0, 0.0, -1.0), (0.0, 1.0, 0.0))


def xr_point(p_world):
    return add(matvec(R_XR_WORLD, p_world), TABLE_XR)


def T_xr_world():
    T = [row + [TABLE_XR[i]] for i, row in enumerate(R_XR_WORLD)]
    return T + [[0.0, 0.0, 0.0, 1.0]]


# ------------------------------------------------------------- the motion --


def smoothstep(x):
    x = min(1.0, max(0.0, x))
    return x * x * (3 - 2 * x)


def keyframes(t, keys):
    """Piecewise smooth interpolation of (time, value) keys."""
    if t <= keys[0][0]:
        return keys[0][1]
    for (t0, v0), (t1, v1) in zip(keys, keys[1:]):  # noqa: RUF007 - pairwise needs 3.10
        if t <= t1:
            return lerp(v0, v1, smoothstep((t - t0) / (t1 - t0)))
    return keys[-1][1]


CUBE_C = (CUBE_START[0], CUBE_START[1], 0.023)
PINCH_KEYS = [
    (0.0, REST),
    (1.0, REST),
    (1.6, (CUBE_C[0], CUBE_C[1], 0.08)),
    (2.0, CUBE_C),
    (2.4, CUBE_C),
    (2.8, (CUBE_C[0], CUBE_C[1], 0.15)),
    (3.3, (TARGET[0], TARGET[1], 0.15)),
    (3.6, TARGET),
    (4.2, TARGET),
    (4.6, (TARGET[0], TARGET[1], 0.15)),
    (5.2, REST),
    (6.0, REST),
]
APERTURE_KEYS = [
    (0.0, (0.080,)),
    (GRASP_T[0], (0.080,)),
    (GRASP_T[1], (0.046,)),
    (RELEASE_T[0], (0.046,)),
    (RELEASE_T[1], (0.080,)),
    (6.0, (0.080,)),
]


def hand_joints_world(c, ap, side):
    """25 joint positions (wrist, thumb 1-4, index..little metacarpal + 4) for a palm-down hand, fingers
    toward +Y, pinch center c with thumb-index aperture ap. Mirrored in x for the left hand."""
    m = 1.0 if side == "right" else -1.0

    def P(x, y, z):
        return add(c, (m * x, y, z))

    thumb_tip, index_tip = P(-ap / 2, 0, 0), P(ap / 2, 0, 0)
    wrist = P(0.02, -0.09, 0.04)
    out = [wrist]
    tm = P(-0.015, -0.065, 0.025)
    out += [tm, lerp(tm, thumb_tip, 0.4), lerp(tm, thumb_tip, 0.75), thumb_tip]
    for dx, tip in ((0.0, index_tip), (0.022, None), (0.04, None), (0.056, None)):
        knuckle = add(wrist, (m * (dx - 0.01), 0.085 - (0.01 if dx > 0.03 else 0), 0.0))
        tip = tip if tip is not None else add(knuckle, (0.0, 0.06, -0.03))
        meta = lerp(wrist, knuckle, 0.3)
        out += [meta, knuckle, lerp(knuckle, tip, 0.45), lerp(knuckle, tip, 0.75), tip]
    return out


def joint_rotation_world(side):
    """OpenXR joint axes for a palm-down hand pointing +Y: +Z toward the wrist, +Y out of the back."""
    z = (0.0, -1.0, 0.0)
    y = (0.0, 0.0, 1.0)
    return cols(cross(y, z), y, z)


def head_pose_xr(t):
    eye = add(
        HEAD, (0.01 * math.sin(1.3 * t), 0.005 * math.sin(0.7 * t), 0.004 * math.sin(1.1 * t))
    )
    look = add(LOOK, (0.03 * math.sin(0.5 * t), 0.0, 0.0))
    e, l_ = xr_point(eye), xr_point(look)
    f = norm(sub(l_, e))
    r = norm(cross(f, (0.0, 1.0, 0.0)))
    u = cross(r, f)
    R = cols(r, u, mul(f, -1.0))  # VIEW: +X right, +Y up, -Z forward
    return list(e) + quat_xyzw(R)


def make_session(name, rate=60.0, seed=0):
    rng = random.Random(f"{name}-{seed}")
    joint_set = "webxr25" if name == "webxr" else "openxr26"
    header = {
        "type": "header",
        "format": "quest-capture",
        "version": 1,
        "source": "synthetic",
        "device": "synthetic Quest 3",
        "reference_space": "local-floor",
        "joint_set": joint_set,
        "task": "place the cube on the target",
        "hand": "right",
        "recorder": "make_sample_sessions.py",
    }
    if name in ("anchored", "lost"):
        up = (0.0, 0.0, TOUCH_R)
        header["world"] = {
            "points": {
                "origin": list(xr_point(up)),
                "x": list(xr_point(add((0.2, 0, 0), up))),
                "y": list(xr_point(add((0, 0.2, 0), up))),
            },
            "touch_radius_m": TOUCH_R,
        }
    elif name == "webxr":
        header["world"] = {"T_xr_world": T_xr_world()}
    lines = [header]
    q_hand = {s: quat_xyzw(matmul(R_XR_WORLD, joint_rotation_world(s))) for s in ("right", "left")}
    t, k = 0.0, 0
    while t <= DURATION + 1e-9:
        c = keyframes(t, PINCH_KEYS)
        ap = keyframes(t, APERTURE_KEYS)[0]
        hands = {}
        for side, center in (("right", c), ("left", LEFT_REST)):
            js = hand_joints_world(center, ap if side == "right" else 0.07, side)
            if joint_set == "openxr26":
                palm = lerp(js[0], js[11], 0.5)  # wrist -> middle knuckle
                js = [palm] + js
            hands[side] = [
                [round(v, 6) for v in xr_point(p)] + [round(q, 6) for q in q_hand[side]] for p in js
            ]
        if name == "lost" and 1.2 <= t <= 4.4:
            hands["right"] = None
        if name != "lost" and 3.0 <= t < 3.05:
            hands["right"] = None  # a 50 ms dropout, bridged by the importer
        lines.append(
            {
                "type": "frame",
                "t": round(10.0 + t, 6),
                "head": [round(v, 6) for v in head_pose_xr(t)],
                "hands": hands,
            }
        )
        k += 1
        t = k / rate + rng.uniform(-0.002, 0.002)
    return lines


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--out", required=True)
    ap.add_argument("--sessions", default=",".join(KINDS))
    ap.add_argument("--rate", type=float, default=60.0)
    ap.add_argument("--seed", type=int, default=0)
    a = ap.parse_args(argv)
    names = [s.strip() for s in a.sessions.split(",") if s.strip()]
    bad = [n for n in names if n not in KINDS]
    if bad:
        print(f"ERROR: unknown session kind(s) {bad}; use {', '.join(KINDS)}", file=sys.stderr)
        return 2
    os.makedirs(a.out, exist_ok=True)
    for n in names:
        d = os.path.join(a.out, n)
        os.makedirs(d, exist_ok=True)
        with open(os.path.join(d, "session.jsonl"), "w", encoding="utf-8") as fh:
            fh.writelines(
                json.dumps(rec, separators=(",", ":")) + "\n"
                for rec in make_session(n, a.rate, a.seed)
            )
    with open(os.path.join(a.out, "sessions.txt"), "w", encoding="utf-8") as fh:
        fh.write("".join(n + "\n" for n in names))
    print(f"{len(names)} sample sessions in {a.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
