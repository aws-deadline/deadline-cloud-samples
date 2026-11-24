# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
"""Stamp the Kit extension's ``extension.toml`` with the package version when building a wheel.

The extension folder ships as package data under
``deadline/isaac_sim_submitter/kit_extension/``. Its ``[package] version`` is the
placeholder ``0.0.0`` in source; the wheel gets a copy with the package version (from
pyproject.toml) in Kit's semantic-version form: ``1.2.3`` stays ``1.2.3``, and a development
version such as ``0.0.post4+g475c0fa`` becomes ``0.0.0-post4+g475c0fa``. Editable installs
are left alone: they use the source folder directly.
"""

from __future__ import annotations

import os
import re
import shutil
import tempfile
from typing import Any

from hatchling.builders.hooks.plugin.interface import BuildHookInterface

MANIFEST = (
    "deadline/isaac_sim_submitter/kit_extension/isaacsim.deadline.submitter/config/extension.toml"
)
_VERSION_LINE = re.compile(r'^version\s*=\s*"[^"\n]*"[ \t]*$', re.MULTILINE)


def kit_version(version: str) -> str:
    """A PEP 440 version as a semantic version Kit accepts."""
    from packaging.version import Version

    v = Version(version)
    release = (list(v.release) + [0, 0, 0])[:3]
    out = ".".join(str(n) for n in release)
    pre = []
    if v.pre is not None:
        pre.append(f"{v.pre[0]}{v.pre[1]}")
    if v.post is not None:
        pre.append(f"post{v.post}")
    if v.dev is not None:
        pre.append(f"dev{v.dev}")
    if pre:
        out += "-" + ".".join(pre)
    if v.local:
        out += "+" + v.local
    return out


def stamp(text: str, version: str) -> str:
    """``text`` with the ``[package]`` table's ``version`` set to ``version``."""
    start = text.find("[package]")
    if start < 0:
        raise ValueError("extension.toml has no [package] table")
    end = text.find("\n[", start + 1)
    end = len(text) if end < 0 else end
    section, n = _VERSION_LINE.subn(f'version = "{version}"', text[start:end], count=1)
    if n != 1:
        raise ValueError("extension.toml [package] has no version line")
    return text[:start] + section + text[end:]


class CustomBuildHook(BuildHookInterface):
    def initialize(self, version: str, build_data: dict[str, Any]) -> None:
        if self.target_name != "wheel" or version == "editable":
            return
        src = os.path.join(self.root, "src", *MANIFEST.split("/"))
        with open(src, encoding="utf-8") as fh:
            text = stamp(fh.read(), kit_version(self.metadata.version))
        self._tmp = tempfile.mkdtemp(prefix="dcfis-build-")
        out = os.path.join(self._tmp, "extension.toml")
        with open(out, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(text)
        build_data["force_include"][out] = MANIFEST

    def finalize(self, version: str, build_data: dict[str, Any], artifact_path: str) -> None:
        tmp = getattr(self, "_tmp", None)
        if tmp:
            shutil.rmtree(tmp, ignore_errors=True)
