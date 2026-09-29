"""Plugin Sync Test Addon — verifies the activate script's auto-enable mechanism.

When this addon is enabled, it:
1. Writes a marker file proving the addon loaded
2. Registers a render_init handler that writes a second marker proving it ran during render
3. Stamps "PLUGIN SYNC: OK" text onto the rendered image as visual proof
"""

bl_info = {
    "name": "Plugin Sync Test",
    "author": "Deadline Cloud Team",
    "version": (1, 1, 0),
    "blender": (3, 6, 0),
    "location": "None (headless test addon)",
    "description": "Test addon for verifying plugin sync delivery on Deadline Cloud",
    "category": "Testing",
}

import bpy
import os
import json
from datetime import datetime


def _marker_dir():
    """Return the session working directory or /tmp as fallback."""
    return os.environ.get("OPENJD_SESSION_WORKING_DIR", "/tmp")


def _write_marker(filename, data):
    """Write a JSON marker file to the session directory."""
    path = os.path.join(_marker_dir(), filename)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump(data, f, indent=2)
    print(f"Plugin Sync Test: wrote {path}")


def _on_render_init(scene):
    """Handler called when a render starts. Changes world background to green as visual proof."""
    _write_marker("plugin-sync-test-render-init.json", {
        "event": "render_init",
        "timestamp": datetime.now().isoformat(),
        "scene": scene.name,
        "blender_user_scripts": os.environ.get("BLENDER_USER_SCRIPTS", ""),
    })

    # Set world background to bright green as visual proof the addon is active
    try:
        world = scene.world
        if world is None:
            world = bpy.data.worlds.new("SimplePluginsTestWorld")
            scene.world = world
        world.use_nodes = True
        bg_node = world.node_tree.nodes.get("Background")
        if bg_node:
            bg_node.inputs["Color"].default_value = (0.0, 0.8, 0.0, 1.0)  # Bright green
            bg_node.inputs["Strength"].default_value = 1.0
            print("Plugin Sync Test: Set world background to GREEN")
    except Exception as e:
        print(f"Plugin Sync Test: Background change failed (non-fatal): {e}")


class SimplePluginsTestPreferences(bpy.types.AddonPreferences):
    """Addon preferences — tests that preferences are accessible during register()."""
    bl_idname = "plugin_sync_test_addon"

    test_setting: bpy.props.StringProperty(
        name="Test Setting",
        default="plugin_sync_works",
    )


def register():
    """Called when the addon is enabled."""
    # Register preferences class first
    bpy.utils.register_class(SimplePluginsTestPreferences)

    # Access preferences during register() — this is the pattern that fails
    # without addon_install() on some Blender versions
    prefs_accessible = False
    try:
        prefs = bpy.context.preferences.addons.get("plugin_sync_test_addon")
        if prefs and prefs.preferences:
            val = prefs.preferences.test_setting
            prefs_accessible = True
            print(f"Plugin Sync Test: Preferences accessible (test_setting={val})")
        else:
            print("Plugin Sync Test: Preferences entry not found (addon not in prefs DB)")
    except Exception as e:
        print(f"Plugin Sync Test: Preferences access failed: {e}")

    _write_marker("plugin-sync-test-loaded.json", {
        "event": "addon_registered",
        "timestamp": datetime.now().isoformat(),
        "addon": "plugin_sync_test_addon",
        "blender_version": ".".join(str(v) for v in bpy.app.version),
        "blender_user_scripts": os.environ.get("BLENDER_USER_SCRIPTS", ""),
        "preferences_accessible": prefs_accessible,
    })
    bpy.app.handlers.render_init.append(_on_render_init)
    print("Plugin Sync Test: addon registered (with render stamp)")


def unregister():
    """Called when the addon is disabled."""
    if _on_render_init in bpy.app.handlers.render_init:
        bpy.app.handlers.render_init.remove(_on_render_init)
    bpy.utils.unregister_class(SimplePluginsTestPreferences)
    print("Plugin Sync Test: addon unregistered")
