"""Build a procedural turntable scene in Blender and render one frame.

The object spins a full 360 degrees across the frame range, so the rendered
frame for a given frame number is deterministic and does not depend on any
other frame or a shared scene file.

Run by the RenderTurntable step:

    blender --background --python build_turntable.py -- \\
        --shape monkey --frame 12 --frame-range 1-48 \\
        --resolution-x 960 --resolution-y 540 --samples 48 \\
        --output-prefix /path/to/frames/turntable_
"""
import argparse
import math
import sys

import bpy

argv = sys.argv[sys.argv.index("--") + 1:]
p = argparse.ArgumentParser()
p.add_argument("--shape", required=True)
p.add_argument("--frame", type=int, required=True)
p.add_argument("--frame-range", required=True)
p.add_argument("--resolution-x", type=int, required=True)
p.add_argument("--resolution-y", type=int, required=True)
p.add_argument("--samples", type=int, required=True)
p.add_argument("--output-prefix", required=True,
               help="Path prefix; the 4-digit frame number and .png are appended.")
args = p.parse_args(argv)

start_s, end_s = args.frame_range.split("-")
start, end = int(start_s), int(end_s)
span = max(end - start + 1, 1)
# Fraction of a full rotation for this frame (end+1 == 360 so the loop is seamless).
rotation = 2.0 * math.pi * (args.frame - start) / span

# Fresh empty scene.
bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene

# Subject.
builders = {
    "monkey": lambda: bpy.ops.mesh.primitive_monkey_add(size=2.0),
    "cube": lambda: bpy.ops.mesh.primitive_cube_add(size=2.0),
    "torus": lambda: bpy.ops.mesh.primitive_torus_add(major_radius=1.0, minor_radius=0.4),
    "ico_sphere": lambda: bpy.ops.mesh.primitive_ico_sphere_add(radius=1.2, subdivisions=3),
    "cylinder": lambda: bpy.ops.mesh.primitive_cylinder_add(radius=1.0, depth=2.0),
    "cone": lambda: bpy.ops.mesh.primitive_cone_add(radius1=1.2, depth=2.4),
}
builders.get(args.shape, builders["monkey"])()
subject = bpy.context.active_object
subject.rotation_euler = (0.0, 0.0, rotation)

# A simple colored material so the rotation is legible in the movie.
mat = bpy.data.materials.new("TurntableMat")
mat.use_nodes = True
bsdf = mat.node_tree.nodes.get("Principled BSDF")
if bsdf:
    bsdf.inputs["Base Color"].default_value = (0.15, 0.45, 0.85, 1.0)
    bsdf.inputs["Roughness"].default_value = 0.35
subject.data.materials.append(mat)

# Ground plane for a soft contact shadow.
bpy.ops.mesh.primitive_plane_add(size=20.0, location=(0.0, 0.0, -1.4))

# Camera looking slightly down at the subject.
bpy.ops.object.camera_add(location=(0.0, -6.0, 2.4), rotation=(math.radians(75.0), 0.0, 0.0))
scene.camera = bpy.context.active_object

# Three-point-ish lighting.
bpy.ops.object.light_add(type="AREA", location=(4.0, -4.0, 6.0))
bpy.context.active_object.data.energy = 1200.0
bpy.ops.object.light_add(type="AREA", location=(-5.0, -2.0, 3.0))
bpy.context.active_object.data.energy = 500.0

# World background.
world = bpy.data.worlds.new("TurntableWorld")
world.use_nodes = True
world.node_tree.nodes["Background"].inputs[0].default_value = (0.05, 0.05, 0.06, 1.0)
scene.world = world

# Render settings.
scene.render.engine = "CYCLES"
# Use GPU if the fleet provides one, otherwise fall back to CPU.
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
# Build the explicit, zero-padded output path. Using render.filepath with
# '#' placeholders only works for animation renders, not write_still, so
# construct the final name here to guarantee one distinct file per frame.
output_path = f"{args.output_prefix}{args.frame:04d}"
scene.render.filepath = output_path
scene.render.use_file_extension = True
scene.frame_set(args.frame)

print(f"Rendering frame {args.frame} (rotation {math.degrees(rotation):.1f} deg) -> {output_path}.png")
bpy.ops.render.render(write_still=True)
