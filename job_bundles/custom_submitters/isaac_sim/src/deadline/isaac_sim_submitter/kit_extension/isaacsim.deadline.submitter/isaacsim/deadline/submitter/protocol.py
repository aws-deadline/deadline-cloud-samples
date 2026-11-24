# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
"""The bridge between the Isaac Sim extension and the app, over the app's stdin and stdout.

The extension starts ``deadline-physical-ai gui --bridge`` as its child and keeps both
pipes; nothing else can reach them (no sockets, no ports, no files). Each message is one
line of UTF-8 JSON, an object with ``"v": 1`` and a ``"type"``, at most :data:`MAX_LINE`
bytes. Requests carry an ``"id"``; the reply is ``{"type": "result", "id", "ok",
"message", ...}``. A receiver ignores unknown types and logs and skips malformed lines.

Kit to app: ``hello`` (once, at launch), ``focus``, ``result``.
App to Kit: ``hello_ack`` (after ``hello``, and again when the download folder changes),
``get_stage``, ``load``, ``replay_control``, ``get_replay_prims``, ``set_replay_prims``,
``get_selection``.

Shared by the app (``deadline.isaac_sim_submitter.app.protocol``) and the extension
(``isaacsim.deadline.submitter.protocol``); the two files must stay identical (a unit
test checks), so this module imports only the standard library.
"""

from __future__ import annotations

import json
import os
from collections.abc import Iterator
from typing import IO, Any

VERSION = 1
MAX_LINE = 64 * 1024

HELLO = "hello"
HELLO_ACK = "hello_ack"
FOCUS = "focus"
GET_STAGE = "get_stage"
LOAD = "load"
REPLAY_CONTROL = "replay_control"
GET_REPLAY_PRIMS = "get_replay_prims"
SET_REPLAY_PRIMS = "set_replay_prims"
GET_SELECTION = "get_selection"
RESULT = "result"

#: What the extension can do, as advertised in ``hello``.
CAP_REPLAY = "replay"
CAP_ADD_USD = "add_usd"
CAP_STAGE_PATH = "stage_path"
#: Read and set the replay's robot, object and reference prims, and read the selection.
CAP_REPLAY_PRIMS = "replay_prims"
CAPABILITIES = (CAP_REPLAY, CAP_ADD_USD, CAP_STAGE_PATH, CAP_REPLAY_PRIMS)

#: The prims a replay uses, by role. ``set_replay_prims`` and its reply carry
#: ``prims: {role: path}``; replies also carry ``exists: {role: bool}`` for the open stage.
REPLAY_ROLES = ("robot", "object", "reference")
#: Longest prim path accepted, and most selected paths returned.
MAX_PRIM_PATH = 1024
MAX_SELECTION = 16

#: ``load`` kinds, the capability each needs, and the file names each accepts.
KIND_CAPABILITY = {"trajectory": CAP_REPLAY, "usd": CAP_ADD_USD}
KIND_SUFFIXES = {"trajectory": (".npz",), "usd": (".usd", ".usda", ".usdc", ".usdz")}
REPLAY_ACTIONS = ("play", "stop")


class ProtocolError(ValueError):
    """A message that is malformed or not allowed; the text is safe to show."""


# --------------------------------------------------------------- constructors --


def message(type_: str, **fields: Any) -> dict:
    return {"v": VERSION, "type": type_, **fields}


def hello(kit_version: str, extension_version: str, capabilities: list | tuple) -> dict:
    return message(
        HELLO,
        kit_version=kit_version,
        extension_version=extension_version,
        capabilities=list(capabilities),
    )


def hello_ack(app_version: str, download_root: str) -> dict:
    return message(HELLO_ACK, app_version=app_version, download_root=download_root)


def focus() -> dict:
    return message(FOCUS)


def get_stage(id_: str) -> dict:
    return message(GET_STAGE, id=id_)


def load(id_: str, kind: str, path: str) -> dict:
    return message(LOAD, id=id_, kind=kind, path=path)


def replay_control(id_: str, action: str) -> dict:
    return message(REPLAY_CONTROL, id=id_, action=action)


def get_replay_prims(id_: str) -> dict:
    return message(GET_REPLAY_PRIMS, id=id_)


def set_replay_prims(id_: str, prims: dict) -> dict:
    return message(SET_REPLAY_PRIMS, id=id_, prims=dict(prims))


def get_selection(id_: str) -> dict:
    return message(GET_SELECTION, id=id_)


def result(id_: Any, ok: bool, message_: str = "", **extra: Any) -> dict:
    return message(RESULT, id=id_, ok=bool(ok), message=message_, **extra)


# -------------------------------------------------------------------- framing --


def encode(msg: dict) -> bytes:
    """One line of UTF-8 JSON. ``ProtocolError`` if it would exceed :data:`MAX_LINE`."""
    data = (json.dumps(msg, ensure_ascii=False, separators=(",", ":")) + "\n").encode("utf-8")
    if len(data) > MAX_LINE:
        raise ProtocolError(f"message of {len(data)} bytes exceeds {MAX_LINE}")
    return data


def decode(line: bytes) -> dict:
    """Parse one line; ``ProtocolError`` unless it is a version-1 message object."""
    try:
        obj = json.loads(line.decode("utf-8"))
    except (UnicodeDecodeError, ValueError) as exc:
        raise ProtocolError(f"not UTF-8 JSON: {exc}") from None
    if not isinstance(obj, dict):
        raise ProtocolError("not a JSON object")
    if obj.get("v") != VERSION:
        raise ProtocolError(f"unsupported protocol version {obj.get('v')!r}")
    if not isinstance(obj.get("type"), str) or not obj["type"]:
        raise ProtocolError("no message type")
    return obj


def read_messages(stream: IO[bytes], max_line: int = MAX_LINE) -> Iterator[tuple[dict | None, str]]:
    """``(message, "")`` for each good line of a binary stream and ``(None, error)`` for
    each bad one, until EOF. A line over ``max_line`` bytes is skipped to its end without
    holding it in memory. Blank lines are ignored."""
    while True:
        line = stream.readline(max_line + 1)
        if not line:
            return
        if len(line) > max_line:  # the newline counts
            more = line
            while more and not more.endswith(b"\n"):  # drop the rest of the line
                more = stream.readline(max_line + 1)
            yield None, f"line longer than {max_line} bytes skipped"
            if not more:
                return
            continue
        if not line.strip():
            continue
        try:
            yield decode(line.rstrip(b"\r\n")), ""
        except ProtocolError as exc:
            yield None, str(exc)


# ----------------------------------------------------------------- validation --


def _inside(path: str, root: str) -> bool:
    a, b = os.path.normcase(path), os.path.normcase(root)
    try:
        return os.path.commonpath([a, b]) == b
    except ValueError:  # different drives, or a mix of absolute and relative
        return False


def validate_load(msg: dict, capabilities: list | tuple, download_root: str) -> tuple[str, str]:
    """``(kind, real path)`` for a ``load`` request the extension may act on, else
    ``ProtocolError``. The path must be absolute, an existing file whose name fits the kind,
    and resolve (symlinks and ``..`` included) inside ``download_root``."""
    kind, path = msg.get("kind"), msg.get("path")
    if kind not in KIND_CAPABILITY:
        raise ProtocolError(f"unknown load kind {kind!r}")
    if KIND_CAPABILITY[kind] not in capabilities:
        raise ProtocolError(f"this Isaac Sim does not offer {KIND_CAPABILITY[kind]}")
    if not isinstance(path, str) or not path or "\x00" in path:
        raise ProtocolError("no path")
    if not os.path.isabs(path):
        raise ProtocolError(f"not an absolute path: {path}")
    if not (isinstance(download_root, str) and download_root and os.path.isabs(download_root)):
        raise ProtocolError("no download folder yet: the app has not sent hello_ack")
    real, root = os.path.realpath(path), os.path.realpath(download_root)
    if not _inside(real, root):
        raise ProtocolError(f"not inside the download folder {download_root}: {path}")
    if not os.path.isfile(real):
        raise ProtocolError(f"not a file: {path}")
    suffixes = KIND_SUFFIXES[kind]
    for name in (os.path.basename(path), os.path.basename(real)):
        if not name.lower().endswith(suffixes):
            raise ProtocolError(f"a {kind} must end with {' or '.join(suffixes)}: {name}")
    return kind, real


def validate_replay_control(msg: dict) -> str:
    action = msg.get("action")
    if action not in REPLAY_ACTIONS:
        raise ProtocolError(f"unknown replay action {action!r}")
    return str(action)


def valid_prim_path(path: Any) -> bool:
    """An absolute USD prim path (``/World/Robot``), or ``""`` for none."""
    if path == "":
        return True
    return (
        isinstance(path, str)
        and path.startswith("/")
        and len(path) <= MAX_PRIM_PATH
        and "\x00" not in path
        and not any(c in path for c in "\r\n")
        and "//" not in path
    )


def validate_replay_prims(msg: dict) -> dict:
    """``{role: path}`` from a ``set_replay_prims`` request: only known roles, each a valid
    prim path or ``""`` (none). Roles left out keep their current value."""
    prims = msg.get("prims")
    if not isinstance(prims, dict) or not prims:
        raise ProtocolError("no prims")
    out = {}
    for role, path in prims.items():
        if role not in REPLAY_ROLES:
            raise ProtocolError(f"unknown replay role {role!r}")
        if not valid_prim_path(path):
            raise ProtocolError(f"not an absolute prim path for {role}: {path!r}")
        out[role] = path
    return out
