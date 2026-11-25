# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
"""The app's end of the Isaac Sim bridge (see :mod:`.protocol`).

A thread reads Kit's messages from the app's stdin into a queue; :meth:`KitLink.poll`, on
the UI thread, handles them. Nothing here imports Qt, so tests drive it with pipes.
"""

from __future__ import annotations

import itertools
import queue
import threading
import time
from collections.abc import Callable
from typing import IO, Any

from . import protocol as pr

_EOF = object()


class KitLink:
    """Talks to the Isaac Sim extension that started this app.

    ``rx`` and ``tx`` are binary streams (the app's stdin and its private copy of stdout).
    ``download_root()`` names the folder Kit accepts ``load`` paths under; it is sent in
    ``hello_ack`` and again before a request whenever it has changed."""

    REQUEST_TIMEOUT_S = 15.0

    def __init__(
        self,
        rx: IO[bytes],
        tx: IO[bytes],
        app_version: str,
        download_root: Callable[[], str],
        log: Callable[[str], None] = print,
    ) -> None:
        self._rx, self._tx = rx, tx
        self.app_version, self.download_root, self.log = app_version, download_root, log
        self._q: queue.Queue = queue.Queue()
        self._lock = threading.Lock()
        self._ids = itertools.count(1)
        self._pending: dict[str, tuple[Callable[[dict], None], float]] = {}
        self._sent_root: str | None = None
        self.connected = False
        self.closed = False
        self.kit_version = ""
        self.extension_version = ""
        self.capabilities: list = []
        self.on_change: Callable[[], None] = lambda: None
        self.on_focus: Callable[[], None] = lambda: None
        self.on_eof: Callable[[], None] = lambda: None
        self._thread = threading.Thread(target=self._read, name="kit-link", daemon=True)

    def start(self) -> KitLink:
        self._thread.start()
        return self

    def _read(self) -> None:
        try:
            for msg, err in pr.read_messages(self._rx):
                self._q.put((msg, err))
        except (OSError, ValueError) as exc:
            self._q.put((None, f"stdin: {exc}"))
        finally:
            self._q.put(_EOF)

    # -- UI thread --
    def has(self, capability: str) -> bool:
        return self.connected and capability in self.capabilities

    def poll(self) -> None:
        while True:
            try:
                item = self._q.get_nowait()
            except queue.Empty:
                break
            if item is _EOF:
                self._closed()
                return
            msg, err = item
            if msg is None:
                self.log(f"bridge: ignored a message from Isaac Sim: {err}")
                continue
            try:
                self._handle(msg)
            except Exception as exc:  # noqa: BLE001 - one bad message must not stop the app
                self.log(f"bridge: handling {msg.get('type')!r} failed: {exc!r}")
        now = time.monotonic()
        for id_, (cb, deadline) in list(self._pending.items()):
            if now > deadline:
                del self._pending[id_]
                cb(pr.result(id_, False, "Isaac Sim did not answer in time."))

    def _handle(self, msg: dict) -> None:
        kind = msg["type"]
        if kind == pr.HELLO:
            caps = msg.get("capabilities")
            self.capabilities = [str(c) for c in caps] if isinstance(caps, list) else []
            self.kit_version = str(msg.get("kit_version") or "")
            self.extension_version = str(msg.get("extension_version") or "")
            self.connected = True
            self._sent_root = None
            self.sync_root()
            self.on_change()
        elif kind == pr.FOCUS:
            self.on_focus()
        elif kind == pr.RESULT:
            entry = self._pending.pop(str(msg.get("id")), None)
            if entry is not None:
                entry[0](msg)
        # Unknown types are ignored: a newer extension may send more.

    def _closed(self) -> None:
        self.connected, self.closed = False, True
        pending, self._pending = self._pending, {}
        for id_, (cb, _) in pending.items():
            cb(pr.result(id_, False, "Isaac Sim closed the connection."))
        self.on_change()
        self.on_eof()

    def send(self, msg: dict) -> bool:
        try:
            data = pr.encode(msg)
        except pr.ProtocolError as exc:
            self.log(f"bridge: not sent: {exc}")
            return False
        with self._lock:
            try:
                self._tx.write(data)
                self._tx.flush()
            except (OSError, ValueError) as exc:
                self.log(f"bridge: send failed: {exc}")
                return False
        return True

    def sync_root(self) -> None:
        root = self.download_root()
        if root != self._sent_root and self.send(pr.hello_ack(self.app_version, root)):
            self._sent_root = root

    def request(
        self,
        msg_type: str,
        callback: Callable[[dict], None],
        timeout_s: float | None = None,
        **fields: Any,
    ) -> None:
        """Send a request and call ``callback(result)`` once: with Kit's reply, or with a
        failed result when not connected, on timeout, or when Kit goes away."""
        if not self.connected:
            callback(pr.result(None, False, "Not connected to Isaac Sim."))
            return
        self.sync_root()
        id_ = f"r{next(self._ids)}"
        if not self.send(pr.message(msg_type, id=id_, **fields)):
            callback(pr.result(id_, False, "Could not send the request to Isaac Sim."))
            return
        self._pending[id_] = (
            callback,
            time.monotonic() + (timeout_s or self.REQUEST_TIMEOUT_S),
        )

    def fetch_stage(self, callback: Callable[[str], None]) -> None:
        """The open stage's file ("" for an unsaved stage or no answer)."""

        def got(r: dict) -> None:
            path = r.get("path") if r.get("ok") else ""
            callback(path if isinstance(path, str) else "")

        self.request(pr.GET_STAGE, got)
