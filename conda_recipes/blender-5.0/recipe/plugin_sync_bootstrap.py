"""Plugin Sync bootstrap.

Run via `blender -b --python plugin_sync_bootstrap.py` from the
zzz-blender-plugin-sync-activate.sh script during conda env-enter.

Installs and enables every addon found in BLENDER_USER_SCRIPTS/addons/,
then persists the result via save_userpref() so all subsequent Blender
calls in the session see the addons enabled at boot.

Why we run this from --python (not from a startup script):
  On Blender 5.0.x (and older 4.x), scripts in BLENDER_USER_SCRIPTS/startup/
  run with bpy.context set to _RestrictContext. From there:
    - bpy.ops.preferences.addon_install raises AttributeError because it
      reads bpy.context.view_layer/scene attributes that don't exist on
      the restricted context.
    - addon_utils.enable() can't import the addon module either because
      Blender hasn't registered it in the preferences DB yet (only
      addon_install does that).
  Running install + enable from --python bypasses the restricted-context
  startup phase. save_userpref() then persists the enabled-addon state
  so all later `blender` calls in the session pick it up automatically.
"""
import os
import sys

import addon_utils
import bpy


def _discover_addons(addons_dir):
    """Return [(module_name, install_path), ...] for everything found in
    addons_dir.

    Discovers:
      - Directory packages with an __init__.py
      - Standalone .py files (module name == basename without .py)
      - .zip files (module name == basename without .zip)
    """
    addons = []
    if not os.path.isdir(addons_dir):
        return addons
    for entry in sorted(os.listdir(addons_dir)):
        entry_path = os.path.join(addons_dir, entry)
        if os.path.isdir(entry_path) and os.path.isfile(
            os.path.join(entry_path, "__init__.py")
        ):
            addons.append((entry, os.path.join(entry_path, "__init__.py")))
        elif entry.endswith(".py"):
            addons.append((entry[:-3], entry_path))
        elif entry.endswith(".zip"):
            addons.append((entry[:-4], entry_path))
    return addons


def _bootstrap():
    user_scripts = os.environ.get("BLENDER_USER_SCRIPTS", "")
    addons_dir = os.path.join(user_scripts, "addons")
    addons = _discover_addons(addons_dir)
    if not addons:
        print("Plugin Sync bootstrap: no addons found")
        return

    for module_name, install_path in addons:
        try:
            bpy.ops.preferences.addon_install(filepath=install_path, overwrite=True)
            print(f"Plugin Sync bootstrap: addon_install OK for '{module_name}'")
        except Exception as e:
            print(
                f"Plugin Sync bootstrap: addon_install FAILED for '{module_name}' "
                f"({e.__class__.__name__}: {e})"
            )
            continue

        try:
            addon_utils.enable(module_name, default_set=True)
            _, enabled = addon_utils.check(module_name)
            if enabled:
                print(f"Plugin Sync bootstrap: enabled '{module_name}'")
            else:
                print(f"Plugin Sync bootstrap: WARNING '{module_name}' did not load")
        except Exception as e:
            print(
                f"Plugin Sync bootstrap: enable FAILED for '{module_name}' "
                f"({e.__class__.__name__}: {e})"
            )

    try:
        bpy.ops.wm.save_userpref()
        print("Plugin Sync bootstrap: save_userpref OK")
    except Exception as e:
        print(
            f"Plugin Sync bootstrap: save_userpref FAILED "
            f"({e.__class__.__name__}: {e})"
        )


if __name__ == "__main__":
    _bootstrap()
    sys.exit(0)
