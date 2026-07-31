"""Minimal Cinema 4D Plugin Sync smoke test."""

import os
from pathlib import Path


MESSAGE = "CINEMA4D_PLUGIN_SYNC_TEST_LOADED"

print("Hello from the Cinema 4D Plugin Sync dummy plugin!", flush=True)
print(MESSAGE, flush=True)

session_working_dir = os.environ.get("OPENJD_SESSION_WORKING_DIR")
if session_working_dir:
    marker_path = Path(session_working_dir, "cinema4d-plugin-sync-test.loaded")
    try:
        marker_path.write_text(f"{MESSAGE}\n", encoding="utf-8")
        print(f"Plugin Sync test marker: {marker_path}", flush=True)
    except OSError as exc:
        print(f"Plugin Sync test could not write its marker: {exc}", flush=True)
