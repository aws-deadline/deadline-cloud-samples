"""Build a small V-Ray for Maya test scene and save it as mayaAscii.

Creating the vraySettings node is what records the `requires "vrayformaya"`
statement in the saved scene, which is what makes Maya load the V-Ray plugin
when the scene is read on a render worker.
"""

import maya.standalone

maya.standalone.initialize()

import maya.cmds as cmds  # noqa: E402
import maya.mel as mel  # noqa: E402

cmds.loadPlugin("vrayformaya")
print("vrayformaya loaded:", cmds.pluginInfo("vrayformaya", query=True, loaded=True), flush=True)

cmds.file(new=True, force=True)

# Ground plane
cmds.polyPlane(name="groundPlane", width=24, height=24, subdivisionsX=1, subdivisionsY=1)

# Three spheres sitting on the plane
for i, x in enumerate((-4.0, 0.0, 4.0)):
    sphere = cmds.polySphere(name="sphere%d" % (i + 1), radius=1.6)[0]
    cmds.setAttr(sphere + ".translateX", x)
    cmds.setAttr(sphere + ".translateY", 1.6)
    shader = cmds.shadingNode("lambert", asShader=True, name="sphereMat%d" % (i + 1))
    cmds.setAttr(shader + ".color", 0.9 - 0.3 * i, 0.25 + 0.3 * i, 0.35, type="double3")
    sg = cmds.sets(renderable=True, noSurfaceShader=True, empty=True, name=shader + "SG")
    cmds.connectAttr(shader + ".outColor", sg + ".surfaceShader", force=True)
    cmds.sets(sphere, edit=True, forceElement=sg)

# Lights. V-Ray renders standard Maya lights.
key = cmds.directionalLight(name="keyLightShape", intensity=1.2)
cmds.setAttr(cmds.listRelatives(key, parent=True)[0] + ".rotate", -45, -35, 0, type="double3")
fill = cmds.pointLight(name="fillLightShape", intensity=0.6)
cmds.setAttr(cmds.listRelatives(fill, parent=True)[0] + ".translate", -8, 10, 10, type="double3")

# Render camera
cam = cmds.camera()[0]
cam = cmds.rename(cam, "renderCamera")
cmds.setAttr(cam + ".translate", 0, 7, 22, type="double3")
cmds.setAttr(cam + ".rotate", -14, 0, 0, type="double3")
cmds.setAttr(cmds.listRelatives(cam, shapes=True)[0] + ".renderable", 1)
cmds.setAttr("perspShape.renderable", 0)

# V-Ray render settings
cmds.setAttr("defaultRenderGlobals.currentRenderer", "vray", type="string")
if not cmds.objExists("vraySettings"):
    mel.eval("vrayCreateVRaySettingsNode")
print("vraySettings exists:", cmds.objExists("vraySettings"), flush=True)

# The Deadline Cloud Maya adaptor requires EXR output for region (tile) renders.
cmds.setAttr("vraySettings.imageFormatStr", "exr", type="string")
cmds.setAttr("vraySettings.width", 480)
cmds.setAttr("vraySettings.height", 270)
# Keep sampling cheap; this scene only needs to prove that V-Ray renders.
cmds.setAttr("vraySettings.samplerType", 4)
cmds.setAttr("vraySettings.dmcMaxSubdivs", 4)
cmds.setAttr("vraySettings.dmcThreshold", 0.05)

import os  # noqa: E402

# Maya resolves a relative name against its workspace, not the working directory.
out = os.path.join(os.getcwd(), "vray_spheres.ma")
cmds.file(rename=out)
cmds.file(save=True, type="mayaAscii", force=True)
print("Saved", out, flush=True)

maya.standalone.uninitialize()
