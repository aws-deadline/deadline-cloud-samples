"""Generate a runnable clip directory: a manifest plus its conditioning images.

The sample ships no photograph and no third-party asset, because NVIDIA's model
and asset licenses do not permit redistributing their example media through this
repository. The conditioning frames are drawn procedurally here instead, so the
sample runs without a hand-supplied image.

Three scenes. Which one you pick decides whether step 2 can recover actions,
because Cosmos 3's inverse dynamics covers a fixed set of embodiments:

  agibot (default) A dual-arm manipulator's own camera view over a tabletop.
         Agibot is one of the embodiments Cosmos 3 covers, so all three steps
         run and the job produces a trainable 29-D action dataset.
  av     An ego-view road, for the autonomous-vehicle embodiment (9-D). Also
         runs all three steps.
  so101  An SO-101 arm over a tabletop. Cosmos 3's inverse dynamics does NOT
         cover SO-101, so pair this with ActionMode=none and feed the generated
         videos to an SO-100/SO-101 IDM afterwards, as GR00T-Dreams does.

Standard library only. The PNG is assembled by hand because Pillow is not a
dependency of this repository.

    python3 scripts/make_example_clips.py --output-dir example_clips --clips 2

Then submit with -p ClipDir=example_clips -p ClipCount=2.
"""

import argparse
import json
import os
import struct
import sys
import zlib


# --------------------------------------------------------------------- png ---

def write_png(path, width, height, pixel_fn):
    """Write an 8-bit RGB PNG. pixel_fn(x, y) returns an (r, g, b) tuple."""
    raw = bytearray()
    for y in range(height):
        raw.append(0)  # filter type 0 (None) for this scanline
        for x in range(width):
            r, g, b = pixel_fn(x, y)
            raw.append(max(0, min(255, int(r))))
            raw.append(max(0, min(255, int(g))))
            raw.append(max(0, min(255, int(b))))

    def chunk(tag, payload):
        return (
            struct.pack(">I", len(payload))
            + tag
            + payload
            + struct.pack(">I", zlib.crc32(tag + payload) & 0xFFFFFFFF)
        )

    header = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    with open(path, "wb") as handle:
        handle.write(b"\x89PNG\r\n\x1a\n")
        handle.write(chunk(b"IHDR", header))
        handle.write(chunk(b"IDAT", zlib.compress(bytes(raw), 9)))
        handle.write(chunk(b"IEND", b""))


# ------------------------------------------------------------------ raster ---

def quad(x, y, w, h, angle=0.0):
    """Corners of a w x h bar whose left edge is centred on (x, y), rotated."""
    import math

    ca, sa = math.cos(angle), math.sin(angle)
    half = h / 2.0
    pts = [(0.0, -half), (w, -half), (w, half), (0.0, half)]
    return [(x + px * ca - py * sa, y + px * sa + py * ca) for px, py in pts]


def inside(poly, x, y):
    """Even-odd point-in-polygon test."""
    hit = False
    count = len(poly)
    for i in range(count):
        x0, y0 = poly[i]
        x1, y1 = poly[(i + 1) % count]
        if (y0 > y) != (y1 > y):
            if x < x0 + (y - y0) * (x1 - x0) / (y1 - y0):
                hit = not hit
    return hit


def painter(width, height, background, shapes):
    """Return a pixel_fn that paints `shapes` back to front over `background`.

    `shapes` is a list of (polygon, colour). Later entries win, so the list reads
    like paint order rather than like a z-buffer.
    """

    def pixel(x, y):
        colour = background(x, y)
        px, py = x + 0.5, y + 0.5
        for poly, shade in shapes:
            if inside(poly, px, py):
                colour = shade
        return colour

    return pixel


# ------------------------------------------------------------------ scenes ---

def so101_scene(width, height, pose, cube_colour):
    """An SO-101 arm over a tabletop, posed by shoulder/elbow angles.

    Deliberately schematic. Its job is to put a plausible arm, table and target
    object in frame so the world model has something to continue, not to be a
    rendering of the real robot. For a real one, render a frame from the
    strands_robots MuJoCo model that job_bundles/mujoco_sim_to_policy uses.
    """
    import math

    shoulder_deg, elbow_deg = pose
    horizon = int(height * 0.42)
    table_top = int(height * 0.58)

    wall = (188, 192, 198)
    table = (142, 110, 78)
    table_edge = (118, 90, 62)
    metal = (206, 210, 214)
    joint = (64, 68, 74)
    base = (48, 52, 58)

    def background(x, y):
        if y < horizon:
            t = y / float(max(1, horizon))
            return (wall[0] - 18 * t, wall[1] - 18 * t, wall[2] - 16 * t)
        if y < table_top:
            return (158, 162, 168)
        t = (y - table_top) / float(max(1, height - table_top))
        return (table[0] + 26 * t, table[1] + 20 * t, table[2] + 14 * t)

    # Arm geometry, rooted on the table behind the work area.
    root_x, root_y = width * 0.30, table_top + (height - table_top) * 0.22
    upper_len = width * 0.20
    fore_len = width * 0.16

    sh = math.radians(shoulder_deg)
    el = sh + math.radians(elbow_deg)
    elbow_x = root_x + upper_len * math.cos(sh)
    elbow_y = root_y + upper_len * math.sin(sh)
    wrist_x = elbow_x + fore_len * math.cos(el)
    wrist_y = elbow_y + fore_len * math.sin(el)

    cube = width * 0.055
    cube_x = width * 0.63
    cube_y = table_top + (height - table_top) * 0.50

    shapes = [
        # Table edge, so the surface reads as a surface.
        ([(0, table_top), (width, table_top), (width, table_top + 9), (0, table_top + 9)], table_edge),
        # Target object.
        ([(cube_x - cube, cube_y - cube), (cube_x + cube, cube_y - cube),
          (cube_x + cube, cube_y + cube), (cube_x - cube, cube_y + cube)], cube_colour),
        # Base, then the two links, then the gripper.
        ([(root_x - width * 0.055, root_y - height * 0.012),
          (root_x + width * 0.055, root_y - height * 0.012),
          (root_x + width * 0.045, root_y + height * 0.075),
          (root_x - width * 0.045, root_y + height * 0.075)], base),
        (quad(root_x, root_y, upper_len, height * 0.055, sh), metal),
        (quad(elbow_x, elbow_y, fore_len, height * 0.042, el), metal),
        # Joints last so they sit on top of both links.
        (quad(root_x - width * 0.012, root_y, width * 0.024, height * 0.06, 0.0), joint),
        (quad(elbow_x - width * 0.011, elbow_y, width * 0.022, height * 0.05, 0.0), joint),
        # Two gripper fingers straddling the forearm axis.
        (quad(wrist_x, wrist_y - height * 0.028, width * 0.045, height * 0.016, el), joint),
        (quad(wrist_x, wrist_y + height * 0.028, width * 0.045, height * 0.016, el), joint),
    ]
    return painter(width, height, background, shapes)


def av_scene(width, height, curve, daylight):
    """An ego-view road, bent by `curve` in [-1, 1]."""
    horizon = int(height * 0.45)
    sky_top = (108, 156, 206) if daylight else (28, 32, 54)
    sky_bottom = (198, 216, 234) if daylight else (62, 60, 88)
    ground = (96, 104, 86) if daylight else (36, 40, 38)
    asphalt = (74, 74, 78) if daylight else (38, 38, 42)
    paint = (236, 230, 190)

    def pixel(x, y):
        if y < horizon:
            t = y / float(max(1, horizon))
            return tuple(sky_top[i] + (sky_bottom[i] - sky_top[i]) * t for i in range(3))
        depth = (y - horizon) / float(max(1, height - horizon))
        center = width * 0.5 + curve * width * 0.32 * (1.0 - depth) ** 2
        half = width * (0.03 + 0.46 * depth)
        offset = x - center
        if abs(offset) > half:
            shade = 1.0 - 0.35 * (1.0 - depth)
            return tuple(c * shade for c in ground)
        across = offset / max(1.0, half)
        band = int(depth * 14.0)
        if abs(across) < 0.045 and band % 2 == 0:
            return paint
        if abs(across) > 0.9:
            return paint
        shade = 0.72 + 0.28 * depth
        return tuple(c * shade for c in asphalt)

    return pixel


def agibot_scene(width, height, reach, object_colour):
    """A dual-arm manipulator's own camera view over a tabletop.

    Both grippers enter frame from the lower corners, as they do in a chest or
    head camera view, with one target object on the table between them. `reach`
    moves the grippers inward and down from 0.0 to 1.0.

    Deliberately schematic, like the other scenes here. Its job is to put the
    embodiment's own arms and a target object in frame so the world model
    continues an Agibot-shaped scene, which is what makes the 29-D inverse
    dynamics request coherent.
    """
    import math

    horizon = int(height * 0.30)
    table_near = height
    table_far = int(height * 0.44)

    def background(x, y):
        if y < horizon:
            t = y / max(1, horizon)
            return (74 + 26 * t, 78 + 26 * t, 86 + 24 * t)
        return (108, 96, 84)

    shapes = []
    # Table surface, wider at the bottom so it reads as perspective.
    inset = width * 0.26
    shapes.append(
        ([(inset, table_far), (width - inset, table_far), (width, table_near), (0, table_near)],
         (156, 130, 102))
    )
    # Target object, sitting on the table just past the midpoint.
    obj = height * 0.11
    cx = width * 0.5
    cy = table_far + (table_near - table_far) * 0.34
    shapes.append(([(cx - obj, cy), (cx + obj, cy), (cx + obj, cy + obj * 1.1),
                    (cx - obj, cy + obj * 1.1)], object_colour))
    shapes.append(([(cx - obj, cy), (cx + obj, cy), (cx + obj * 0.72, cy - obj * 0.42),
                    (cx - obj * 1.28, cy - obj * 0.42)],
                   tuple(min(255, c + 34) for c in object_colour)))

    # Two arms, mirrored, entering from the lower corners. The elbow sits along
    # the base-to-gripper line and is pushed sideways, so the gripper lands on
    # the object at any frame size. Fixed link lengths overshoot as width grows.
    thickness = height * 0.085
    for side in (-1, 1):
        base_x = width * (0.5 + side * 0.46)
        base_y = height * 1.04
        grip_x = cx + side * obj * 1.25
        grip_y = cy + obj * (0.30 + 0.45 * reach)
        along = math.atan2(grip_y - base_y, grip_x - base_x)
        span = math.hypot(grip_x - base_x, grip_y - base_y)
        bend = span * (0.26 - 0.10 * reach)
        mid_x = base_x + (grip_x - base_x) * 0.56 - side * bend * math.sin(along)
        mid_y = base_y + (grip_y - base_y) * 0.56 + side * bend * math.cos(along)

        upper_ang = math.atan2(mid_y - base_y, mid_x - base_x)
        fore_ang = math.atan2(grip_y - mid_y, grip_x - mid_x)
        upper_len = math.hypot(mid_x - base_x, mid_y - base_y)
        fore_len = math.hypot(grip_x - mid_x, grip_y - mid_y)

        shapes.append((quad(base_x, base_y, upper_len, thickness, upper_ang), (226, 228, 232)))
        shapes.append((quad(mid_x, mid_y, fore_len, thickness * 0.82, fore_ang), (238, 240, 244)))
        shapes.append((quad(mid_x, mid_y, thickness * 0.55, thickness * 1.1, fore_ang), (52, 56, 64)))
        # Two gripper fingers, closing as `reach` grows.
        spread = math.radians(15 - 9 * reach)
        for finger in (-1, 1):
            shapes.append((quad(grip_x, grip_y, thickness * 0.95, thickness * 0.24,
                                fore_ang + finger * spread), (44, 48, 56)))

    return painter(width, height, background, shapes)


# ----------------------------------------------------------------- prompts ---

NEGATIVE = "blurry, distorted, low quality, warped geometry, flickering, jump cut"

SO101_CLIPS = [
    ("so101_reach_cube",
     "A low-cost SO-101 robot arm on a wooden tabletop reaches toward a blue "
     "cube and closes its gripper around it. Smooth continuous motion, fixed "
     "camera, even indoor lighting.",
     (-32.0, 46.0), (62, 104, 196)),
    ("so101_lift_cube",
     "A low-cost SO-101 robot arm grasps a blue cube on a wooden tabletop and "
     "lifts it straight up, holding it steady. Smooth continuous motion, fixed "
     "camera, even indoor lighting.",
     (-20.0, 38.0), (62, 104, 196)),
    ("so101_place_right",
     "A low-cost SO-101 robot arm carries a red cube across a wooden tabletop "
     "and places it down to the right, then releases its gripper. Smooth "
     "continuous motion, fixed camera.",
     (-44.0, 58.0), (186, 72, 64)),
    ("so101_push_cube",
     "A low-cost SO-101 robot arm pushes a green cube along a wooden tabletop "
     "with its closed gripper. Smooth continuous motion, fixed camera, even "
     "indoor lighting.",
     (-12.0, 30.0), (74, 150, 86)),
]

AV_CLIPS = [
    ("av_ego_01",
     "Ego-view dashcam footage from a car driving forward along a two-lane road "
     "in daylight. The vehicle holds its lane and continues straight at a "
     "steady speed. Stable camera, consistent lighting.",
     0.0, True),
    ("av_ego_02",
     "Ego-view dashcam footage from a car following a two-lane road as it bends "
     "gently to the right. The vehicle tracks the curve smoothly without "
     "braking. Stable camera, overcast daylight.",
     0.55, True),
    ("av_ego_03",
     "Ego-view dashcam footage from a car following a two-lane road as it bends "
     "to the left. The vehicle steers through the curve at a constant speed. "
     "Stable camera, late afternoon light.",
     -0.55, True),
    ("av_ego_04",
     "Ego-view dashcam footage from a car driving forward along an unlit "
     "two-lane road at night, headlights on. The vehicle holds its lane. "
     "Stable camera.",
     0.0, False),
]

AGIBOT_CLIPS = [
    ("agibot_grasp_box",
     "Ego-view camera on a dual-arm mobile manipulator working at a tabletop. "
     "Both grippers move inward and close around a cardboard box in front of "
     "the robot. Smooth continuous motion, fixed camera, even indoor lighting.",
     0.25, (168, 132, 92)),
    ("agibot_lift_box",
     "Ego-view camera on a dual-arm mobile manipulator lifting a cardboard box "
     "off a tabletop with both grippers and holding it steady. Smooth "
     "continuous motion, fixed camera, warehouse lighting.",
     0.70, (168, 132, 92)),
    ("agibot_place_bin",
     "Ego-view camera on a dual-arm mobile manipulator lowering a blue plastic "
     "bin onto a tabletop and opening both grippers to release it. Smooth "
     "continuous motion, fixed camera.",
     0.45, (68, 104, 176)),
    ("agibot_push_tray",
     "Ego-view camera on a dual-arm mobile manipulator pushing a grey tray "
     "across a tabletop with both closed grippers. Smooth continuous motion, "
     "fixed camera, even indoor lighting.",
     0.10, (142, 146, 152)),
]

# name -> (clip specs, builder, submit hint). Data-driven so adding a scene does
# not mean editing main()'s dispatch.
SCENES = {
    "agibot": (AGIBOT_CLIPS, agibot_scene,
               "  -p DomainName=agibotworld -p RawActionDim=29"),
    "av": (AV_CLIPS, av_scene,
           "  -p DomainName=av -p RawActionDim=9"),
    "so101": (SO101_CLIPS, so101_scene, "  -p ActionMode=none"),
}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--scene", default="agibot", choices=sorted(SCENES))
    parser.add_argument("--clips", type=int, default=2)
    parser.add_argument("--width", type=int, default=848)
    parser.add_argument("--height", type=int, default=480)
    args = parser.parse_args()

    specs, builder, submit_hint = SCENES[args.scene]
    if not 1 <= args.clips <= len(specs):
        raise SystemExit(
            "--clips must be between 1 and %d for scene '%s'" % (len(specs), args.scene)
        )

    frames_dir = os.path.join(args.output_dir, "frames")
    os.makedirs(frames_dir, exist_ok=True)

    clips = []
    for index in range(args.clips):
        name, prompt, first, second = specs[index]
        pixel_fn = builder(args.width, args.height, first, second)

        image_rel = os.path.join("frames", name + ".png")
        write_png(os.path.join(args.output_dir, image_rel), args.width, args.height, pixel_fn)
        clips.append(
            {"name": name, "image": image_rel, "prompt": prompt, "negative_prompt": NEGATIVE}
        )
        print("wrote %s" % os.path.join(args.output_dir, image_rel))

    manifest_path = os.path.join(args.output_dir, "clips.json")
    with open(manifest_path, "w", encoding="utf-8") as handle:
        json.dump({"scene": args.scene, "clips": clips}, handle, indent=2)
    print("wrote %s with %d clip(s)" % (manifest_path, len(clips)))

    print("")
    print("submit with:")
    print("  -p ClipDir=%s -p ClipCount=%d" % (os.path.abspath(args.output_dir), len(clips)))
    print(submit_hint)
    if args.scene == "so101":
        print("")
        print("ActionMode=none because Cosmos 3's inverse dynamics does not cover")
        print("SO-101. Step 1 generates the videos; recover actions afterwards with an")
        print("SO-100/SO-101 IDM such as GR00T-Dreams' seonghyeonye/IDM_so100.")
    print("")
    print("ClipDir is the directory, not the manifest file: job attachments uploads")
    print("what was declared, and declaring only clips.json leaves the images behind.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
