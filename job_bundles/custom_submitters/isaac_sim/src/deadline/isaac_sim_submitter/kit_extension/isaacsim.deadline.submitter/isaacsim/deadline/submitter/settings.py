# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
"""Persistent settings, the only module that touches ``carb``.

Everything lives under ``/persistent/exts/isaacsim.deadline.submitter/``. Kit
autosaves changed ``/persistent`` settings to ``${data}/user.config.json`` every frame
(``/app/settings/persistent`` defaults to true), so there is no explicit save call.
``--reset-user`` wipes it (expected), which is why the startup test must not depend on
persisted state. The app's own settings (bundle folders, download folder) are in its
settings file, not here.
"""

from __future__ import annotations

from typing import Any

EXT_NAME = "isaacsim.deadline.submitter"
ROOT = f"/persistent/exts/{EXT_NAME}/"

#: Path to ``deadline-physical-ai``, when it is not found automatically.
PHYSICAL_AI_EXECUTABLE = "physicalAiExecutable"
#: Replay targets in the open stage. An empty object or reference prim skips placement.
ROBOT_PRIM = "robotPrim"
OBJECT_PRIM = "objectPrim"
REFERENCE_PRIM = "referencePrim"

DEFAULTS = {
    ROBOT_PRIM: "/World/Robot",
    OBJECT_PRIM: "",
    REFERENCE_PRIM: "",
}

_CARB: Any
_FALLBACK: dict = {}

try:  # pragma: no cover - carb is always present inside Kit
    import carb.settings

    _CARB = carb.settings.get_settings()
except Exception:  # noqa: BLE001  # pragma: no cover
    # Off-Kit fallback so the test suite can import this module without Kit. It is a
    # process-local dict: nothing persists. carb is *always* available in Kit, so this
    # branch never runs there. If you ever see settings not persisting inside Isaac Sim,
    # this except is not the cause; check the key path.
    _CARB = None


def get_str(key: str, default: str | None = None) -> str:
    """``carb`` returns ``None`` for a missing key, so the default is applied here."""
    if default is None:
        default = DEFAULTS.get(key, "")
    if _CARB is None:  # pragma: no cover
        return _FALLBACK.get(key, default)
    value = _CARB.get(ROOT + key)
    return default if value is None else str(value)


def set_str(key: str, value: str) -> None:
    if _CARB is None:  # pragma: no cover
        _FALLBACK[key] = value or ""
        return
    _CARB.set(ROOT + key, value or "")
