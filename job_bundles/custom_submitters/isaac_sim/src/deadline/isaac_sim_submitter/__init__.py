# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
"""AWS Deadline Cloud submitter for Isaac Sim.

The submitter is the Isaac Sim Kit extension ``isaacsim.deadline.submitter``, shipped as
package data under ``kit_extension/`` (a Kit extension folder, not an importable Python
package, so it never shadows Isaac Sim's own ``isaacsim`` package). Isaac Sim loads it
from there through a directory link (see :mod:`deadline.isaac_sim_submitter.install`) or
``--ext-folder``.

This module only locates the folder. Nothing here imports Isaac Sim, Kit or AWS libraries.
"""

from __future__ import annotations

from pathlib import Path

EXTENSION_NAME = "isaacsim.deadline.submitter"
_MANIFEST = ("config", "extension.toml")


def extension_folder() -> Path:
    """The folder that contains the ``isaacsim.deadline.submitter`` extension folder, for
    Isaac Sim's ``--ext-folder``. Raises ``RuntimeError`` if the extension is missing."""
    folder = Path(__file__).resolve().parent / "kit_extension"
    if not folder.joinpath(EXTENSION_NAME, *_MANIFEST).is_file():
        raise RuntimeError(f"the {EXTENSION_NAME} extension is missing from {folder}")
    return folder


def extension_path() -> Path:
    """The extension's own folder (the one holding ``config/extension.toml``)."""
    return extension_folder() / EXTENSION_NAME
