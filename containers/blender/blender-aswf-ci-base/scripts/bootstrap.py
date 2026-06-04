import os
import sys
import addon_utils
import bpy

def _discover_addons(addons_dir):
    addons = []
    if not os.path.isdir(addons_dir):
        return addons
    for entry in sorted(os.listdir(addons_dir)):
        entry_path = os.path.join(addons_dir, entry)
        if os.path.isdir(entry_path) and os.path.isfile(os.path.join(entry_path, "__init__.py")):
            addons.append((entry, os.path.join(entry_path, "__init__.py")))
        elif entry.endswith(".py"):
            addons.append((entry[:-3], entry_path))
        elif entry.endswith(".zip"):
            addons.append((entry[:-4], entry_path))
    return addons

def _bootstrap():
    addons_dir = os.path.join(os.environ.get("BLENDER_USER_SCRIPTS", ""), "addons")
    addons = _discover_addons(addons_dir)
    if not addons:
        print("Plugin bootstrap: no addons found")
        return
    for module_name, install_path in addons:
        try:
            bpy.ops.preferences.addon_install(filepath=install_path, overwrite=True)
            print(f"Plugin bootstrap: addon_install OK for '{module_name}'")
        except Exception as e:
            print(f"Plugin bootstrap: addon_install FAILED for '{module_name}' ({e})")
            continue
        try:
            addon_utils.enable(module_name, default_set=True)
            _, enabled = addon_utils.check(module_name)
            if enabled:
                print(f"Plugin bootstrap: enabled '{module_name}'")
            else:
                print(f"Plugin bootstrap: WARNING '{module_name}' did not enable")
        except Exception as e:
            print(f"Plugin bootstrap: enable FAILED for '{module_name}' ({e})")
    try:
        bpy.ops.wm.save_userpref()
        print("Plugin bootstrap: save_userpref OK")
    except Exception as e:
        print(f"Plugin bootstrap: save_userpref FAILED ({e})")

if __name__ == "__main__":
    _bootstrap()
    sys.exit(0)
