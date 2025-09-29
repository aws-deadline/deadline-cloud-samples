import bpy
import sys

print("Uninstalling Addon")
bpy.ops.preferences.addon_remove(module=sys.argv[-1])
print("Saving Preferences")
bpy.ops.wm.save_userpref()
print("Complete")
