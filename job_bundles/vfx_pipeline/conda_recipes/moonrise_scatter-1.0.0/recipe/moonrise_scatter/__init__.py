"""moonrise_scatter — a tiny in-house Blender add-on used by the sample pipeline.

This stands in for the kind of studio-authored Blender add-on a real pipeline
ships to its render nodes: a small tool that pipeline code calls to produce
render-visible geometry. Here it scatters instanced "greeble" cubes across the
faces of a target mesh, so the effect is clearly visible in the rendered frame
and proves the plugin was staged and enabled on the worker.

The pipeline does not click a button in the UI; the render script enables this
add-on and calls its operator (bpy.ops.moonrise.scatter) headlessly. That is the
realistic path: studio tools expose operators that automation drives.

Real third-party Blender add-ons are almost always GPL (importing `bpy` makes a
work a derivative of Blender). This sample repository is MIT-0, so it ships this
purpose-built in-house add-on rather than vendoring a GPL one. To use an actual
third-party add-on instead, write a Conda recipe that installs its files into
`share/blender/scripts/addons/` (as this package's recipe does), publish it to
your channel, and call its operator from render_shot.py. The delivery path is
identical.
"""

bl_info = {
    "name": "Moonrise Scatter",
    "author": "Moonrise Studios",
    "version": (1, 0, 0),
    "blender": (4, 2, 0),
    "description": "Scatter instanced greeble geometry over a target mesh.",
    "category": "Object",
}

import bpy
from mathutils import Vector


class MOONRISE_OT_scatter(bpy.types.Operator):
    """Scatter small cubes across the faces of the target object."""

    bl_idname = "moonrise.scatter"
    bl_label = "Moonrise Scatter"
    bl_options = {"REGISTER", "UNDO"}

    target: bpy.props.StringProperty(
        name="Target",
        description="Name of the mesh object to scatter over",
        default="Subject",
    )
    count: bpy.props.IntProperty(
        name="Count", description="Number of scattered instances", default=120, min=1
    )
    size: bpy.props.FloatProperty(
        name="Size", description="Base edge length of each greeble", default=0.15, min=0.001
    )
    seed: bpy.props.IntProperty(name="Seed", default=0)

    def execute(self, context):
        import math
        import random

        target = bpy.data.objects.get(self.target)
        if target is None or target.type != "MESH":
            self.report({"ERROR"}, f"Target mesh {self.target!r} not found")
            return {"CANCELLED"}

        mesh = target.data
        if not mesh.polygons:
            self.report({"ERROR"}, "Target mesh has no faces to scatter on")
            return {"CANCELLED"}

        rng = random.Random(self.seed)

        # A single emissive material shared by every greeble, so the scatter reads
        # as glowing "tech" detail in the render — visible proof the plugin ran.
        mat = bpy.data.materials.new("greeble_glow")
        mat.use_nodes = True
        bsdf = mat.node_tree.nodes.get("Principled BSDF")
        if bsdf:
            bsdf.inputs["Base Color"].default_value = (0.05, 0.6, 1.0, 1.0)
            # Emission Strength/Color inputs exist across Blender 4.x.
            if "Emission Color" in bsdf.inputs:
                bsdf.inputs["Emission Color"].default_value = (0.1, 0.7, 1.0, 1.0)
            if "Emission Strength" in bsdf.inputs:
                bsdf.inputs["Emission Strength"].default_value = 6.0

        # One shared greeble mesh, instanced by many objects, so the scatter is
        # cheap regardless of count. A deterministic PRNG keeps the render of a
        # given seed reproducible across machines.
        bpy.ops.object.select_all(action="DESELECT")
        bpy.ops.mesh.primitive_cube_add(size=self.size)
        cube = bpy.context.active_object
        cube.data.materials.append(mat)

        placed = 0
        polys = mesh.polygons
        for _ in range(self.count):
            poly = polys[rng.randrange(len(polys))]
            # World-space face center + a nudge along the face normal so the
            # greeble sits proud of the surface.
            local = poly.center + poly.normal * (self.size * 0.5)
            world = target.matrix_world @ local
            inst = cube.copy()
            inst.data = cube.data  # share mesh data (instancing)
            inst.location = world
            # Vary each greeble's size so the scatter looks like layered detail
            # rather than a uniform grid; deterministic from the seed.
            s = rng.uniform(0.4, 1.6)
            inst.scale = (s, s, rng.uniform(1.0, 3.0) * s)
            inst.rotation_euler = (
                rng.uniform(0, math.pi),
                rng.uniform(0, math.pi),
                rng.uniform(0, math.pi),
            )
            context.collection.objects.link(inst)
            placed += 1

        # Remove the template cube; keep only the instances.
        bpy.data.objects.remove(cube, do_unlink=True)
        self.report({"INFO"}, f"Scattered {placed} greebles over {self.target}")
        return {"FINISHED"}


def register():
    bpy.utils.register_class(MOONRISE_OT_scatter)


def unregister():
    bpy.utils.unregister_class(MOONRISE_OT_scatter)


if __name__ == "__main__":
    register()
