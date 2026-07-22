"""Generate the sample .blend assets referenced by the shot configs.

Run this with Blender (not plain Python) because it uses the `bpy` module:

    blender --background --python tools/make_sample_assets.py

It writes one .blend per shot into studio/assets, matching the `asset:` paths
in the shot configs:

    studio/assets/moonrise/seq010/sh010/hero_vehicle.blend   (a faceted "vehicle")
    studio/assets/moonrise/seq010/sh020/robot_droid.blend    (a stacked "droid")

Each scene is deliberately tiny — a primitive subject, a ground plane, a
three-point-ish light rig, a camera, and Cycles render settings — so the
repository stays small but the render job has a real, openable scene to work
with. The render step (scripts/render_shot.py) opens one of these, points the
camera, rotates the subject for the assigned frame, and renders a still.
"""
import math
import os

import bpy

# Resolve studio/assets relative to this file (tools/ is a sibling of studio/).
HERE = os.path.dirname(os.path.abspath(__file__))
ASSETS_ROOT = os.path.normpath(os.path.join(HERE, "..", "studio", "assets"))

# Each asset: the relative .blend path (matching the shot configs) and a
# builder that populates a fresh scene with the subject.
ASSETS = {
    "moonrise/seq010/sh010/hero_vehicle.blend": {
        "color": (0.15, 0.45, 0.85, 1.0),
        "build": "vehicle",
    },
    "moonrise/seq010/sh020/robot_droid.blend": {
        "color": (0.80, 0.30, 0.25, 1.0),
        "build": "droid",
    },
}


def _add_material(obj, color):
    mat = bpy.data.materials.new("AssetMat")
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    if bsdf:
        bsdf.inputs["Base Color"].default_value = color
        bsdf.inputs["Roughness"].default_value = 0.4
    obj.data.materials.append(mat)


def _build_vehicle():
    """A 'hero vehicle' with an asymmetric silhouette so its rotation reads
    clearly on a turntable: a stretched body, an offset raised cabin, and a
    pointed nose. Returns the joined body mesh (named "Subject" by the caller)."""
    bpy.ops.mesh.primitive_cube_add(size=2.0)
    body = bpy.context.active_object
    body.scale = (1.9, 1.0, 0.5)
    # Offset cabin toward the back — breaks front/back symmetry.
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=(-0.6, 0.0, 0.7))
    bpy.context.active_object.scale = (0.9, 0.8, 0.6)
    # Pointed nose at the front.
    bpy.ops.mesh.primitive_cone_add(radius1=0.9, depth=1.2,
                                    rotation=(0.0, math.radians(90.0), 0.0),
                                    location=(2.1, 0.0, 0.0))
    # Wheels, so orientation is unmistakable.
    for x in (-1.2, 1.2):
        for y in (-1.05, 1.05):
            bpy.ops.mesh.primitive_cylinder_add(
                radius=0.45, depth=0.3,
                rotation=(math.radians(90.0), 0.0, 0.0),
                location=(x, y, -0.5))
    return body


def _build_droid():
    """A 'robot droid' with a clearly-front face: a body sphere, a head, and a
    forward-facing 'eye' box so the turntable rotation is obvious."""
    bpy.ops.mesh.primitive_ico_sphere_add(radius=1.1, subdivisions=3)
    body = bpy.context.active_object
    bpy.ops.mesh.primitive_uv_sphere_add(radius=0.7, location=(0.0, 0.0, 1.5))
    # Forward-facing eye (toward -Y, the camera side) breaks symmetry.
    bpy.ops.mesh.primitive_cube_add(size=0.5, location=(0.0, -0.6, 1.6))
    bpy.context.active_object.scale = (0.7, 0.5, 0.3)
    return body


BUILDERS = {"vehicle": _build_vehicle, "droid": _build_droid}


def build_scene(spec):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene

    # Build the subject's parts, then join them into one mesh so the whole model
    # rotates together and the scatter add-on has faces across the entire
    # silhouette to work on.
    BUILDERS[spec["build"]]()
    parts = [o for o in bpy.context.scene.objects if o.type == "MESH"]
    bpy.ops.object.select_all(action="DESELECT")
    for o in parts:
        o.select_set(True)
    bpy.context.view_layer.objects.active = parts[0]
    if len(parts) > 1:
        bpy.ops.object.join()
    subject = bpy.context.active_object
    subject.name = "Subject"
    _add_material(subject, spec["color"])

    # Ground plane with a soft, slightly reflective material for a grounded look.
    bpy.ops.mesh.primitive_plane_add(size=40.0, location=(0.0, 0.0, -1.1))
    floor = bpy.context.active_object
    floor_mat = bpy.data.materials.new("Floor")
    floor_mat.use_nodes = True
    fb = floor_mat.node_tree.nodes.get("Principled BSDF")
    if fb:
        fb.inputs["Base Color"].default_value = (0.02, 0.02, 0.03, 1.0)
        fb.inputs["Roughness"].default_value = 0.35
    floor.data.materials.append(floor_mat)

    # A default camera so the .blend opens sensibly; the render step repositions
    # and aims it at the subject each shot (see scripts/render_shot.py).
    bpy.ops.object.camera_add(location=(3.6, -4.8, 3.0),
                              rotation=(math.radians(62.0), 0.0, math.radians(38.0)))
    scene.camera = bpy.context.active_object

    # Key + rim lights: the key shapes the subject, the rim separates it from the
    # dark background and catches the scattered greebles.
    bpy.ops.object.light_add(type="AREA", location=(5.0, -5.0, 7.0))
    key = bpy.context.active_object.data
    key.energy = 2000.0
    key.size = 5.0
    bpy.ops.object.light_add(type="AREA", location=(-6.0, 3.0, 4.0))
    rim = bpy.context.active_object.data
    rim.energy = 900.0
    rim.size = 3.0

    # Dark, faintly blue world so the emissive greebles from moonrise_scatter pop.
    world = bpy.data.worlds.new("World")
    world.use_nodes = True
    world.node_tree.nodes["Background"].inputs[0].default_value = (0.015, 0.02, 0.035, 1.0)
    scene.world = world

    scene.render.engine = "CYCLES"


def main():
    for rel_path, spec in ASSETS.items():
        build_scene(spec)
        out = os.path.join(ASSETS_ROOT, rel_path)
        os.makedirs(os.path.dirname(out), exist_ok=True)
        bpy.ops.wm.save_as_mainfile(filepath=out)
        print(f"Wrote {out}")


if __name__ == "__main__":
    main()
