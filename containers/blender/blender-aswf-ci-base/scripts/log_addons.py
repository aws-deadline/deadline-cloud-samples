import addon_utils
import bpy

def _log_addons():
    enabled = [mod.__name__ for mod in addon_utils.modules() if addon_utils.check(mod.__name__)[1]]
    print(f"[container] Blender started with {len(enabled)} addons enabled: {enabled}")

def register():
    bpy.app.timers.register(_log_addons, first_interval=0)

def unregister():
    pass
