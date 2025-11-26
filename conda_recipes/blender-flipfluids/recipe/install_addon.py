import bpy
import sys

print("Installing Addon")
bpy.ops.preferences.addon_install(enable_on_install=True, filepath=sys.argv[-1])
print("Saving Preferences")
bpy.ops.wm.save_userpref()
print("Complete")
