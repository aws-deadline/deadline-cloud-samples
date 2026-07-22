"""Workstation launch — set up a shot's environment and start the DCC.

This is the artist-facing side of the launcher, the stand-in for what a studio
normally does with a desktop app ("set project", then "launch Blender"). It:

  1. resolves the shot context,
  2. exports the shot context into the environment as STUDIO_* / SHOT_* /
     FLOW_* variables, and
  3. exec's the DCC with the shot's asset.

On the workstation the DCC is whatever the artist has active — typically the same
Conda environment the farm uses (`conda activate`, or a pixi shell), so
`blender` is already on PATH. The launcher does not stage software at the desk;
it sets the shot context and launches. On the farm the Conda queue environment
provides the DCC (see submit.py). One config drives both.

The FLOW_* and SHOT_* variables it exports are deliberately the same ones the
submission hook reads (see submit.py and the bundle's hooks.yaml): an artist who
launched a shot can submit it without re-entering anything, because the launch
already populated the environment.
"""
from __future__ import annotations

import os

from .context import ShotContext, resolve


def shot_environment(ctx: ShotContext) -> dict[str, str]:
    """The SHOT_*/FLOW_* environment a shot exports, before software staging.

    These mirror the job's hook inputs so workstation launch and farm submission
    read identical context. Resolution travels as shot data (SHOT_RESOLUTION),
    not as a magic DCC setting — the scene/render applies it.
    """
    res = ctx.render("resolution", [1920, 1080])
    env = {
        "STUDIO_PROJECT": ctx.project,
        "STUDIO_SEQUENCE": ctx.sequence,
        "STUDIO_SHOT": ctx.shot,
        "SHOT_ID": ctx.shot_id,
        "SHOT_ASSET": ctx.asset_path,
        "SHOT_FRAME_RANGE": str(ctx.render("frame_range", "1-48")),
        "SHOT_RESOLUTION_X": str(res[0]),
        "SHOT_RESOLUTION_Y": str(res[1]),
        "SHOT_SAMPLES": str(ctx.render("samples", 64)),
        "SHOT_FRAME_RATE": str(ctx.render("frame_rate", 24)),
    }

    # Flow context, consumed by the submission hook. Only exported when the shot
    # has Flow enabled and a project id.
    if ctx.flow("enabled", True):
        env["FLOW_PUBLISH"] = "TRUE"
        env["FLOW_PROJECT_ID"] = str(ctx.flow("project_id", 0))
        env["FLOW_ASSET_NAME"] = str(ctx.flow("asset_name", ""))
        env["FLOW_ASSET_TYPE"] = str(ctx.flow("asset_type", "Prop"))
        env["FLOW_TASK_NAME"] = str(ctx.flow("task_name", "Turntable"))
        env["FLOW_STEP_SHORT_NAME"] = str(ctx.flow("step_short_name", "MDL"))
        env["FLOW_TASK_STATUS"] = str(ctx.flow("task_status", "fin"))
    else:
        env["FLOW_PUBLISH"] = "FALSE"
    return env


def build_launch_env(ctx: ShotContext, base: dict[str, str] | None = None) -> dict[str, str]:
    """Full environment for launching the DCC: base + the shot's context vars."""
    environ = dict(base if base is not None else os.environ)
    environ.update(shot_environment(ctx))
    return environ


def launch(shot_path: str, exec_dcc: bool = True) -> dict[str, str]:
    """Resolve, build the environment, and (optionally) exec the DCC.

    Returns the computed environment. When exec_dcc is False (the default for
    tests and for `--print-env`), it does everything except replace the process.
    """
    ctx = resolve(shot_path)
    env = build_launch_env(ctx)

    if not exec_dcc:
        return env

    # Find the DCC executable from the staged PATH and open the shot's asset.
    dcc = ctx.data.get("software", {}).get("dcc", {}).get("name", "blender")
    args = [dcc, env["SHOT_ASSET"]]
    print(f"Launching {dcc} for {ctx.shot_id}: {env['SHOT_ASSET']}")
    os.execvpe(dcc, args, env)  # replaces the current process; does not return
    return env  # unreachable, but keeps every path returning the environment
