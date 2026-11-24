# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
"""The extension's end of the bridge to the app (see :mod:`.protocol`). No Kit imports.

* :class:`AppProcess` runs ``deadline-physical-ai gui --bridge`` with its stdin and stdout
  as the only channel, and reads its stdout on a thread.
* :class:`Host` answers the app's requests through callbacks, after validating them.
"""

from __future__ import annotations

import collections
import queue
import subprocess
import sys
import threading
from collections.abc import Callable

from . import procenv
from . import protocol as pr


class AppProcess:
    """The app child. :meth:`poll` (Kit's main thread) returns the messages that arrived."""

    STDERR_TAIL = 30

    def __init__(self, argv: list, env: dict | None = None, log: Callable[[str], None] = print):
        self.argv, self.log = list(argv), log
        self._q: queue.Queue = queue.Queue()
        self._lock = threading.Lock()
        self._stderr: collections.deque = collections.deque(maxlen=self.STDERR_TAIL)
        self._proc = subprocess.Popen(
            self.argv,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env,
            creationflags=procenv.NO_WINDOW,
        )
        self._threads = [
            threading.Thread(target=self._read_stdout, name="dcfis-app-out", daemon=True),
            threading.Thread(target=self._read_stderr, name="dcfis-app-err", daemon=True),
        ]
        for t in self._threads:
            t.start()

    @property
    def pid(self) -> int:
        return self._proc.pid

    def _read_stdout(self) -> None:
        try:
            for msg, err in pr.read_messages(self._proc.stdout):  # type: ignore[arg-type]
                self._q.put((msg, err))
        except (OSError, ValueError):
            # The pipe closes when the app exits; poll() reports the exit.
            pass

    def _read_stderr(self) -> None:
        try:
            for raw in iter(self._proc.stderr.readline, b""):  # type: ignore[union-attr]
                self._stderr.append(raw.decode("utf-8", "replace").rstrip())
        except (OSError, ValueError):
            # The pipe closes when the app exits; poll() reports the exit.
            pass

    def poll(self) -> list:
        out = []
        while True:
            try:
                msg, err = self._q.get_nowait()
            except queue.Empty:
                return out
            if msg is None:
                self.log(f"ignored a message from the app: {err}")
            else:
                out.append(msg)

    @property
    def alive(self) -> bool:
        return self._proc.poll() is None

    @property
    def returncode(self) -> int | None:
        return self._proc.poll()

    def stderr_tail(self) -> str:
        return "\n".join(self._stderr)

    def send(self, msg: dict) -> bool:
        try:
            data = pr.encode(msg)
        except pr.ProtocolError as exc:
            self.log(f"not sent to the app: {exc}")
            return False
        with self._lock:
            try:
                self._proc.stdin.write(data)  # type: ignore[union-attr]
                self._proc.stdin.flush()  # type: ignore[union-attr]
            except (OSError, ValueError):
                return False  # the app has gone; the next poll sees it exit
        return True

    def allow_foreground(self) -> None:
        """Windows lets only the foreground process raise another's window: let the app."""
        if sys.platform == "win32":
            try:
                import ctypes

                ctypes.windll.user32.AllowSetForegroundWindow(self.pid)
            except Exception as exc:  # noqa: BLE001 - focus is cosmetic
                self.log(f"AllowSetForegroundWindow failed: {exc!r}")

    def close(self, timeout_s: float = 2.0) -> None:
        """Close the app's stdin (it exits on EOF), wait briefly, then kill it."""
        with self._lock:
            try:
                self._proc.stdin.close()  # type: ignore[union-attr]
            except (OSError, ValueError):
                # Already closed because the app exited; the wait below still applies.
                pass
        try:
            self._proc.wait(timeout=timeout_s)
        except subprocess.TimeoutExpired:
            self._proc.kill()
            try:
                self._proc.wait(timeout=timeout_s)
            except subprocess.TimeoutExpired:  # pragma: no cover
                pass
        for t in self._threads:
            t.join(timeout=1.0)


class Host:
    """Answers the app's requests. ``stage_path()`` returns the open stage's file,
    ``load(kind, path)`` and ``replay_control(action)`` act and return the reply message;
    ``replay_prims()`` and ``set_replay_prims(prims)`` return ``{"prims", "exists"}``, and
    ``selection(limit)`` the selected prim paths. An exception from any of them becomes a
    failed reply. Without the replay prim callbacks, that capability is not offered."""

    def __init__(
        self,
        kit_version: str,
        extension_version: str,
        stage_path: Callable[[], str],
        load: Callable[[str, str], str],
        replay_control: Callable[[str], str],
        capabilities: tuple = pr.CAPABILITIES,
        log: Callable[[str], None] = print,
        replay_prims: Callable[[], dict] | None = None,
        set_replay_prims: Callable[[dict], dict] | None = None,
        selection: Callable[[int], list] | None = None,
    ) -> None:
        self.kit_version, self.extension_version = kit_version, extension_version
        if not (replay_prims and set_replay_prims and selection):
            capabilities = tuple(c for c in capabilities if c != pr.CAP_REPLAY_PRIMS)
        self.capabilities = tuple(capabilities)
        self.replay_prims, self.set_replay_prims = replay_prims, set_replay_prims
        self.selection = selection
        self.stage_path, self.load, self.replay_control = stage_path, load, replay_control
        self.log = log
        self.download_root = ""
        self.app_version = ""

    def hello(self) -> dict:
        return pr.hello(self.kit_version, self.extension_version, self.capabilities)

    def handle(self, msg: dict) -> dict | None:
        """The reply to send, or ``None``."""
        kind = msg.get("type")
        if kind == pr.HELLO_ACK:
            root = msg.get("download_root")
            if isinstance(root, str) and root:
                self.download_root = root
            self.app_version = str(msg.get("app_version") or "")
            return None
        if kind not in (
            pr.GET_STAGE,
            pr.LOAD,
            pr.REPLAY_CONTROL,
            pr.GET_REPLAY_PRIMS,
            pr.SET_REPLAY_PRIMS,
            pr.GET_SELECTION,
        ):
            return None  # unknown types are ignored
        id_ = msg.get("id")
        if not isinstance(id_, (str, int)) or isinstance(id_, bool):
            self.log(f"ignored a {kind} request without an id")
            return None
        try:
            if kind == pr.GET_STAGE:
                self._need(pr.CAP_STAGE_PATH)
                return pr.result(id_, True, "", path=str(self.stage_path() or ""))
            if kind == pr.LOAD:
                what, real = pr.validate_load(msg, self.capabilities, self.download_root)
                return pr.result(id_, True, self.load(what, real), kind=what, path=real)
            if kind == pr.GET_REPLAY_PRIMS:
                self._need(pr.CAP_REPLAY_PRIMS)
                return pr.result(id_, True, "", **self.replay_prims())  # type: ignore[misc]
            if kind == pr.SET_REPLAY_PRIMS:
                prims = pr.validate_replay_prims(msg)
                self._need(pr.CAP_REPLAY_PRIMS)
                return pr.result(id_, True, "", **self.set_replay_prims(prims))  # type: ignore[misc]
            if kind == pr.GET_SELECTION:
                self._need(pr.CAP_REPLAY_PRIMS)
                paths = self.selection(pr.MAX_SELECTION)  # type: ignore[misc]
                return pr.result(id_, True, "", paths=list(paths)[: pr.MAX_SELECTION])
            action = pr.validate_replay_control(msg)
            self._need(pr.CAP_REPLAY)
            return pr.result(id_, True, self.replay_control(action))
        except pr.ProtocolError as exc:
            self.log(f"refused {kind}: {exc}")
            return pr.result(id_, False, str(exc))
        except Exception as exc:  # noqa: BLE001 - the app shows it; Kit keeps running
            self.log(f"{kind} failed: {exc!r}")
            return pr.result(id_, False, str(exc) or type(exc).__name__)

    def _need(self, capability: str) -> None:
        if capability not in self.capabilities:
            raise pr.ProtocolError(f"this Isaac Sim does not offer {capability}")
