"""Open a shot's .blend asset and render one turntable frame.

Unlike a procedural build, this opens the *attached shot asset* (delivered by
Deadline Cloud job attachments) and renders the assigned frame. The subject in
each sample asset is named "Subject"; we spin it a full 360 degrees across the
frame range so each frame is deterministic and independent — the property that
lets every frame be its own farm task.

Run by the RenderShot step:

    blender --background <shot.blend> --python render_shot.py -- \\
        --frame 12 --frame-range 1-48 \\
        --resolution-x 1920 --resolution-y 1080 --samples 96 \\
        --output-prefix /path/to/frames/shot_ \\
        --addon-module moonrise_scatter

Each --addon-module names a studio Blender add-on to enable. The add-ons ship as
Conda packages (see conda_recipes/) and are made importable by the Conda queue
environment before this script runs, so we only need the module name — no
directory to register. This shot uses the in-house moonrise_scatter add-on, whose
operator scatters greeble geometry over the subject, proving the plugin package
loaded as part of the render.
"""
import argparse
import math
import sys

import bpy

argv = sys.argv[sys.argv.index("--") + 1:]
p = argparse.ArgumentParser()
p.add_argument("--frame", type=int, required=True)
p.add_argument("--frame-range", required=True)
p.add_argument("--resolution-x", type=int, required=True)
p.add_argument("--resolution-y", type=int, required=True)
p.add_argument("--samples", type=int, required=True)
p.add_argument("--output-prefix", required=True,
               help="Path prefix; the 4-digit frame number and .png are appended.")
p.add_argument("--addon-module", action="append", default=[],
               help="Studio Blender add-on module to enable. Its Conda package "
                    "makes it importable. Repeatable.")
args = p.parse_args(argv)


def enable_addons(addon_modules):
    """Enable studio add-ons by module name.

    The add-ons' Conda packages put them on Blender's add-on search path
    (BLENDER_USER_SCRIPTS, set when the Conda environment activates), so enabling
    one is just the headless equivalent of ticking its checkbox in Preferences.
    """
    for module in addon_modules:
        print(f"Enabling studio add-on: {module}")
        bpy.ops.preferences.addon_enable(module=module)

start_s, end_s = args.frame_range.split("-")
start, end = int(start_s), int(end_s)
span = max(end - start + 1, 1)
rotation = 2.0 * math.pi * (args.frame - start) / span

scene = bpy.context.scene

# Enable any studio add-ons (delivered as Conda packages) before we touch the scene.
enable_addons(args.addon_module)

# Spin the shot's subject. The sample assets name it "Subject"; fall back to the
# first mesh object so the script still does something sensible on other scenes.
subject = bpy.data.objects.get("Subject")
if subject is None:
    subject = next((o for o in bpy.data.objects if o.type == "MESH"), None)
if subject is not None:
    subject.rotation_euler = (subject.rotation_euler[0],
                              subject.rotation_euler[1],
                              rotation)
    # Force the dependency graph to recompute matrix_world now. Assigning
    # rotation_euler does not refresh matrix_world until the next view-layer
    # update, and the scatter operator below reads target.matrix_world to place
    # each greeble — without this it would place them on the unrotated surface
    # while the mesh renders rotated.
    bpy.context.view_layer.update()

# If the moonrise_scatter add-on is enabled, scatter greeble geometry over the
# subject. The scatter uses a fixed seed, so the greeble pattern is identical on
# every frame and worker; because it runs after the rotation is applied, the
# greebles sit on the rotated surface and turn with the subject.
if "moonrise_scatter" in args.addon_module and subject is not None:
    bpy.ops.moonrise.scatter(target=subject.name, count=120, size=0.15, seed=7)

# Ensure there is a camera, then frame the subject: place it at a fixed
# three-quarter vantage and aim it at the subject so the turntable fills the
# frame the same way every shot. The camera is fixed while the subject rotates
# underneath it — that keeps each frame a pure function of its frame number,
# which is what lets every frame render as an independent farm task.
cam = scene.camera or next((o for o in bpy.data.objects if o.type == "CAMERA"), None)
if cam is None:
    cam_data = bpy.data.cameras.new("Camera")
    cam = bpy.data.objects.new("Camera", cam_data)
    scene.collection.objects.link(cam)
scene.camera = cam

from mathutils import Vector

# The subject sits at the world origin; aim the camera there.
target_point = subject.matrix_world.translation if subject is not None else Vector((0.0, 0.0, 0.0))
cam.location = Vector((3.6, -4.8, 3.0))
cam.rotation_euler = (target_point - cam.location).to_track_quat("-Z", "Y").to_euler()
cam.data.lens = 50.0

# Render settings come from the resolved shot context (passed as args).
scene.render.engine = "CYCLES"
# Use a GPU if the fleet provides one, otherwise fall back to CPU.
try:
    prefs = bpy.context.preferences.addons["cycles"].preferences
    prefs.get_devices()
    for compute_type in ("OPTIX", "CUDA", "HIP", "METAL", "ONEAPI"):
        try:
            prefs.compute_device_type = compute_type
            if any(d.type == compute_type for d in prefs.devices):
                scene.cycles.device = "GPU"
                for d in prefs.devices:
                    d.use = True
                break
        except TypeError:
            continue
except Exception as exc:  # noqa: BLE001
    print(f"GPU detection skipped, rendering on CPU: {exc}")

scene.cycles.samples = args.samples
scene.render.resolution_x = args.resolution_x
scene.render.resolution_y = args.resolution_y
scene.render.resolution_percentage = 100
scene.render.image_settings.file_format = "PNG"
output_path = f"{args.output_prefix}{args.frame:04d}"
scene.render.filepath = output_path
scene.render.use_file_extension = True
scene.frame_set(args.frame)

print(f"Rendering frame {args.frame} (rotation {math.degrees(rotation):.1f} deg) -> {output_path}.png")
bpy.ops.render.render(write_still=True)
