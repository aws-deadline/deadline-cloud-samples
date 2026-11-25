# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
"""Tests for the Kit extension with no Kit and no AWS.

Kit modules are stubbed so the extension imports; the logic under test (the bridge, the
menu glue, USD replay binding) uses only the standard library, numpy and usd-core
(``pxr``).

The stubs (``carb``, ``omni.*``, ``isaacsim.*``) and the extension's folder on ``sys.path``
are only in place while this directory's modules are imported and run. Everywhere else in
the session ``sys.modules`` and ``sys.path`` look as if this file never ran, so other tests
see no Kit modules whatever order pytest runs them in.
"""

from __future__ import annotations

import os
import sys
from typing import Any
from unittest import mock

import pytest

from deadline.isaac_sim_submitter import extension_path

_HERE = os.path.dirname(os.path.abspath(__file__))
EXT_ROOT = str(extension_path())
_PREFIXES = ("carb", "omni", "isaacsim")


def _ours(name: str) -> bool:
    return any(name == p or name.startswith(p + ".") for p in _PREFIXES)


def _build_stubs() -> dict:
    stubs: dict = {}
    for name in (
        "carb",
        "carb.settings",
        "omni",
        "omni.ext",
        "omni.ui",
        "omni.usd",
        "omni.timeline",
        "omni.kit",
        "omni.kit.app",
        "omni.kit.actions",
        "omni.kit.actions.core",
        "omni.kit.menu",
        "omni.kit.menu.utils",
        "isaacsim.gui",
        "isaacsim.gui.components",
        "isaacsim.gui.components.menu",
    ):
        stubs[name] = sys.modules.get(name) or mock.MagicMock(name=name)
    # Link each stub to its parent so ``import omni.ext`` then ``omni.ext.IExt`` finds the
    # stub configured below, not an auto-created MagicMock attribute.
    for name, stub in stubs.items():
        parent, _, child = name.rpartition(".")
        if isinstance(stubs.get(parent), mock.MagicMock):
            setattr(stubs[parent], child, stub)
    # settings.py falls back to an in-process dict when carb.settings is unusable.
    stubs["carb.settings"].get_settings.side_effect = RuntimeError("no Kit")
    stubs["carb"].settings = stubs["carb.settings"]
    stubs["omni.ext"].IExt = object
    return stubs


class _KitScope:
    """Swaps this directory's Kit stubs and extension modules in and out of ``sys.modules``."""

    def __init__(self) -> None:
        self.mine = _build_stubs()
        self.saved: dict | None = None
        self.depth = 0

    def enter(self) -> None:
        self.depth += 1
        if self.depth > 1:
            return
        self.saved = {n: m for n, m in sys.modules.items() if _ours(n)}
        for name in self.saved:
            del sys.modules[name]
        sys.modules.update(self.mine)
        sys.path.insert(0, EXT_ROOT)

    def exit(self) -> None:
        self.depth -= 1
        if self.depth > 0:
            return
        # Keep what was imported in scope (the extension's modules) for the next enter().
        self.mine = {n: m for n, m in sys.modules.items() if _ours(n)}
        for name in self.mine:
            del sys.modules[name]
        sys.modules.update(self.saved or {})
        self.saved = None
        if EXT_ROOT in sys.path:
            sys.path.remove(EXT_ROOT)


_SCOPE = _KitScope()


def _in_this_dir(path: Any) -> bool:
    return str(path).startswith(_HERE + os.sep)


@pytest.hookimpl(wrapper=True)
def pytest_make_collect_report(collector: Any) -> Any:
    """Importing a test module here needs the stubs; collecting anything else must not."""
    if not (isinstance(collector, pytest.Module) and _in_this_dir(collector.path)):
        return (yield)
    _SCOPE.enter()
    try:
        return (yield)
    finally:
        _SCOPE.exit()


@pytest.fixture(scope="module", autouse=True)
def _kit_stubs() -> Any:
    _SCOPE.enter()
    yield
    _SCOPE.exit()


@pytest.fixture(autouse=True)
def _fresh_state(_kit_stubs: Any) -> Any:
    """Each test starts with no stored settings: they are a module global."""
    from isaacsim.deadline.submitter import settings

    settings._FALLBACK.clear()
    yield
    settings._FALLBACK.clear()
