# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0
"""Build a procedural wedge scene in Blender and render one image.

Each wedge variant renders the same subject (a Suzanne monkey on a ground
plane, lit by a sun lamp) with the material roughness, sun rotation, and
Cycles sample count taken from one row of the wedge CSV. Building the scene
procedurally keeps every task fully independent — there is no shared .blend
file to pass between tasks.

Run by the RenderWedge step:

    blender --background --python render_wedge.py -- \\
        --wedge-name glossy --roughness 0.2 --sun-rotation 20 --samples 64 \\
        --resolution-x 960 --resolution-y 540 --output-dir /path/to/output
"""
import argparse
import math
import os
import sys

import bpy

argv = sys.argv[sys.argv.index("--") + 1:]
p = argparse.ArgumentParser()
p.add_argument("--wedge-name", required=True,
               help="Wedge variant name; the output image is <output-dir>/wedge_<name>.png.")
p.add_argument("--roughness", type=float, required=True)
p.add_argument("--sun-rotation", type=float, required=True,
               help="Sun lamp rotation around the vertical axis, in degrees.")
p.add_argument("--samples", type=int, required=True)
p.add_argument("--resolution-x", type=int, required=True)
p.add_argument("--resolution-y", type=int, required=True)
p.add_argument("--output-dir", required=True)
args = p.parse_args(argv)

# Fresh empty scene.
bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene

# Subject: Suzanne, angled toward the camera, with the wedged material.
bpy.ops.mesh.primitive_monkey_add(size=2.0, location=(0.0, 0.0, 1.1))
subject = bpy.context.active_object
subject.rotation_euler = (math.radians(8.0), 0.0, math.radians(30.0))
bpy.ops.object.shade_smooth()

material = bpy.data.materials.new("WedgeMaterial")
material.use_nodes = True
bsdf = material.node_tree.nodes["Principled BSDF"]
bsdf.inputs["Base Color"].default_value = (0.8, 0.33, 0.14, 1.0)
bsdf.inputs["Roughness"].default_value = args.roughness
bsdf.inputs["Metallic"].default_value = 1.0
subject.data.materials.append(material)

# Ground plane with a neutral diffuse material.
bpy.ops.mesh.primitive_plane_add(size=30.0, location=(0.0, 0.0, 0.0))
ground = bpy.context.active_object
ground_material = bpy.data.materials.new("GroundMaterial")
ground_material.use_nodes = True
ground_bsdf = ground_material.node_tree.nodes["Principled BSDF"]
ground_bsdf.inputs["Base Color"].default_value = (0.25, 0.25, 0.28, 1.0)
ground_bsdf.inputs["Roughness"].default_value = 0.9
ground.data.materials.append(ground_material)

# Sun lamp, tilted 50 degrees off vertical, swung around Z by the wedge value.
bpy.ops.object.light_add(type='SUN', location=(0.0, 0.0, 6.0))
sun = bpy.context.active_object
sun.data.energy = 4.0
sun.data.angle = math.radians(2.0)
sun.rotation_euler = (math.radians(50.0), 0.0, math.radians(args.sun_rotation))

# Uniform sky so reflections have something to pick up.
world = bpy.data.worlds.new("WedgeWorld")
world.use_nodes = True
background = world.node_tree.nodes["Background"]
background.inputs["Color"].default_value = (0.35, 0.42, 0.55, 1.0)
background.inputs["Strength"].default_value = 0.6
scene.world = world

# Camera, aimed at the subject.
bpy.ops.object.camera_add(location=(4.2, -4.2, 1.8))
camera = bpy.context.active_object
look_direction = subject.location - camera.location
camera.rotation_euler = look_direction.to_track_quat('-Z', 'Y').to_euler()
scene.camera = camera

# Render settings from the wedge row.
scene.render.engine = 'CYCLES'
scene.cycles.samples = args.samples
scene.cycles.use_denoising = False  # Keep sample-count wedges visible.
scene.render.resolution_x = args.resolution_x
scene.render.resolution_y = args.resolution_y
scene.render.resolution_percentage = 100
scene.render.image_settings.file_format = 'PNG'
scene.render.filepath = os.path.join(args.output_dir, f"wedge_{args.wedge_name}.png")

bpy.ops.render.render(write_still=True)
print(f"Wrote {scene.render.filepath}")
