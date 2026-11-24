# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
"""The app's end of the bridge, over real OS pipes (no Qt, no Kit)."""

from __future__ import annotations

import os
import time

import pytest

from deadline.isaac_sim_submitter.app import protocol as pr
from deadline.isaac_sim_submitter.app.bridge import KitLink


class Pipes:
    """Kit's side: ``write`` reaches the link's stdin, ``read`` gets what the link sent."""

    def __init__(self):
        r1, w1 = os.pipe()
        r2, w2 = os.pipe()
        self.link_rx, self.kit_tx = os.fdopen(r1, "rb"), os.fdopen(w1, "wb")
        self.kit_rx, self.link_tx = os.fdopen(r2, "rb"), os.fdopen(w2, "wb")
        self._messages = pr.read_messages(self.kit_rx)

    def write(self, data: bytes) -> None:
        self.kit_tx.write(data)
        self.kit_tx.flush()

    def send(self, msg: dict) -> None:
        self.write(pr.encode(msg))

    def read(self) -> dict:
        msg, err = next(self._messages)
        assert msg is not None, err
        return msg

    def close(self) -> None:
        for f in (self.kit_tx, self.link_tx, self.kit_rx, self.link_rx):
            try:
                f.close()
            except OSError:
                # Teardown is best-effort; a pipe end may already be closed by the test.
                pass


@pytest.fixture
def pipes():
    p = Pipes()
    yield p
    p.close()


def _link(pipes, root="/downloads", **kw):
    logged: list = []
    roots = [root]
    link = KitLink(pipes.link_rx, pipes.link_tx, "1.2.3", lambda: roots[0], log=logged.append)
    link.logged, link.roots = logged, roots  # type: ignore[attr-defined]
    for k, v in kw.items():
        setattr(link, k, v)
    return link.start()


def _until(link, cond, timeout=5.0):
    t0 = time.monotonic()
    while not cond():
        assert time.monotonic() - t0 < timeout, "timed out"
        link.poll()
        time.sleep(0.01)


def test_hello_connects_and_acks(pipes):
    changes: list = []
    link = _link(pipes, on_change=lambda: changes.append(1))
    assert not link.connected and not link.has(pr.CAP_REPLAY)
    pipes.send(pr.hello("6.2.0", "0.3.0", [pr.CAP_REPLAY, pr.CAP_STAGE_PATH]))
    _until(link, lambda: link.connected)
    assert pipes.read() == pr.hello_ack("1.2.3", "/downloads")
    assert link.kit_version == "6.2.0" and link.extension_version == "0.3.0" and changes
    assert link.has(pr.CAP_REPLAY) and not link.has(pr.CAP_ADD_USD)


def test_requests_get_their_own_result(pipes):
    link = _link(pipes)
    pipes.send(pr.hello("6.2.0", "", pr.CAPABILITIES))
    _until(link, lambda: link.connected)
    pipes.read()  # hello_ack
    got: list = []
    link.fetch_stage(got.append)
    link.request(pr.LOAD, got.append, kind="usd", path="/downloads/a.usd")
    first, second = pipes.read(), pipes.read()
    assert first["type"] == pr.GET_STAGE and second == pr.load(
        second["id"], "usd", "/downloads/a.usd"
    )
    assert first["id"] != second["id"]
    pipes.send(pr.result(second["id"], False, "nope"))
    pipes.send(pr.result("stray-id", True))  # an unknown id is ignored
    pipes.send(pr.result(first["id"], True, "", path="/s/scene.usd"))
    _until(link, lambda: len(got) == 2)
    assert got[0]["message"] == "nope" and got[1] == "/s/scene.usd"


def test_download_root_change_is_sent_before_the_next_request(pipes):
    link = _link(pipes)
    pipes.send(pr.hello("6.2.0", "", pr.CAPABILITIES))
    _until(link, lambda: link.connected)
    assert pipes.read()["download_root"] == "/downloads"
    link.roots[0] = "/elsewhere"
    link.request(pr.REPLAY_CONTROL, lambda r: None, action="play")
    assert pipes.read() == pr.hello_ack("1.2.3", "/elsewhere")
    assert pipes.read()["type"] == pr.REPLAY_CONTROL


def test_not_connected_and_timeout(pipes, monkeypatch):
    link = _link(pipes)
    got: list = []
    link.fetch_stage(got.append)
    link.request(pr.LOAD, got.append, kind="usd", path="/x.usd")
    assert got[0] == "" and "Not connected" in got[1]["message"]
    pipes.send(pr.hello("6.2.0", "", pr.CAPABILITIES))
    _until(link, lambda: link.connected)
    link.request(pr.GET_STAGE, got.append, timeout_s=0.05)
    time.sleep(0.1)
    link.poll()
    assert got[2]["ok"] is False and "did not answer" in got[2]["message"]


def test_focus_unknown_and_malformed(pipes):
    focused: list = []
    link = _link(pipes, on_focus=lambda: focused.append(1))
    pipes.write(b"{oops\n")
    pipes.send(pr.message("future_feature", id="x"))
    pipes.send(pr.focus())
    _until(link, lambda: focused)
    assert any("not UTF-8 JSON" in m for m in link.logged) and not link.connected


def test_eof_fails_pending_and_ends(pipes):
    ended: list = []
    link = _link(pipes, on_eof=lambda: ended.append(1))
    pipes.send(pr.hello("6.2.0", "", pr.CAPABILITIES))
    _until(link, lambda: link.connected)
    got: list = []
    link.request(pr.GET_STAGE, got.append)
    pipes.kit_tx.close()  # Isaac Sim quit
    _until(link, lambda: ended)
    assert link.closed and not link.connected and "closed the connection" in got[0]["message"]


def test_a_failing_handler_does_not_stop_the_link(pipes):
    link = _link(pipes)

    def boom():
        raise RuntimeError("view broke")

    link.on_focus = boom
    pipes.send(pr.focus())
    pipes.send(pr.hello("6.2.0", "", pr.CAPABILITIES))
    _until(link, lambda: link.connected)
    assert any("view broke" in m for m in link.logged)


def test_send_failure_is_reported(pipes):
    link = _link(pipes)
    pipes.send(pr.hello("6.2.0", "", pr.CAPABILITIES))
    _until(link, lambda: link.connected)
    pipes.kit_rx.close()  # nobody reads any more
    got: list = []
    assert not link.send(pr.load("r", "usd", "x" * pr.MAX_LINE))  # oversize: refused locally
    for _ in range(200):  # fill the pipe until the write fails
        link.request(pr.GET_STAGE, got.append)
        if got:
            break
    assert got and got[-1]["ok"] is False
