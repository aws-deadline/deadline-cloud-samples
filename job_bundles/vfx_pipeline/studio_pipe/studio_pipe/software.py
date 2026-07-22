"""Resolve a shot's software into Conda package specs and channels.

The studio standardizes on a DCC and a set of plugins in the config hierarchy
(`software.dcc`, `software.plugins`, `software.conda_channels`). This module maps
that choice to the two values the render job passes to the Conda queue
environment:

  - CondaPackages: a space-separated list of Conda match specs, e.g.
    "blender=4.2 moonrise_scatter=1.0.0".
  - CondaChannels: the channels to resolve them from, e.g.
    "deadline-cloud <studio-channel>".

Software delivery itself is not this module's job: packages are built once from
the recipes under conda_recipes/ (rattler-build) and published to an S3-hosted
Conda channel (aws s3 sync); the Conda queue environment attached to the queue
pulls and caches them on the worker at run time. There is no per-job software
upload and no bespoke staging code — Conda is the package manager.
"""
from __future__ import annotations

from .context import ShotContext


def conda_packages(ctx: ShotContext) -> str:
    """The shot's DCC + plugins as a space-separated Conda match-spec string.

    Each entry is `name=version`, where `version` is whatever the config records
    (a Conda match spec such as "4.2" or "1.0.0"). The DCC comes first so it is
    the anchor of the solve; plugins that `requirements.run: blender` resolve
    against it.
    """
    software = ctx.data.get("software", {})
    specs: list[str] = []

    dcc = software.get("dcc")
    if dcc:
        specs.append(f"{dcc['name']}={dcc['version']}")

    for plugin in software.get("plugins", []) or []:
        specs.append(f"{plugin['name']}={plugin['version']}")

    return " ".join(specs)


def conda_channels(ctx: ShotContext) -> str:
    """Channels to resolve the shot's packages from.

    Defaults to the service-provided "deadline-cloud" channel plus any channels
    the studio configured (its own channel for in-house packages like
    moonrise_scatter). Order is priority order.
    """
    software = ctx.data.get("software", {})
    channels = software.get("conda_channels") or ["deadline-cloud"]
    return " ".join(channels)


def plugin_modules(ctx: ShotContext) -> str:
    """Space-separated add-on module names the render step should enable."""
    software = ctx.data.get("software", {})
    modules = [
        p.get("module", p["name"])
        for p in (software.get("plugins", []) or [])
    ]
    return " ".join(modules)
