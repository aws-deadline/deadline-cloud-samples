"""Submit a shot to Deadline Cloud as a parameterized static job bundle.

This is the key "launch can also submit a job" path. It does NOT build a job
bundle on the fly — it takes the *static* bundle that lives in the repo
(job_bundle/blender_shot_render) and fills its parameters from the resolved
shot context. Keeping the bundle static means it is reviewable, diffable, and
versioned on the shared drive; the only thing that varies per submission is the
parameter values.

How software and assets reach the worker:

The shot's .blend asset is a PATH parameter with `dataFlow: IN`; passing its
on-disk path makes the Deadline Cloud client hash it, upload it as a job
attachment, and path-map it onto the worker. Software (Blender + plugins) does
NOT travel with the job — it is delivered by the Conda queue environment attached
to the queue. This launcher fills the CondaPackages/CondaChannels parameters from
the resolved context; the queue environment solves and caches the environment on
the worker before the render runs.

The Flow parameters are filled separately by the bundle's preSubmission hook
from the FLOW_* environment variables (which `studio-pipe launch`/`resolve`
also export), so they are not passed here.
"""
from __future__ import annotations

import os
import subprocess

from .context import ShotContext, resolve, studio_root
from .launch import shot_environment
from .software import conda_channels, conda_packages, plugin_modules


def bundle_dir() -> str:
    """Absolute path to the static job bundle.

    Anchored on STUDIO_ROOT rather than on this module's location, so it resolves
    the same whether studio_pipe is installed with `pip install ./studio_pipe`,
    `pip install -e`, or run from a source checkout (a non-editable install copies
    the module into site-packages, where a module-relative path would miss the
    bundle). In this sample the bundle is a sibling of the studio root:

        <repo>/job_bundles/vfx_pipeline/studio                       <- STUDIO_ROOT
        <repo>/job_bundles/vfx_pipeline/job_bundle/blender_shot_render <- the bundle

    A real studio keeps the bundle wherever its pipeline is versioned; set
    STUDIO_PIPE_BUNDLE_DIR to point the launcher at it.
    """
    override = os.environ.get("STUDIO_PIPE_BUNDLE_DIR")
    if override:
        return os.path.abspath(override)
    return os.path.normpath(
        os.path.join(studio_root(), "..", "job_bundle", "blender_shot_render")
    )


def build_parameters(ctx: ShotContext) -> list[tuple[str, str]]:
    """Map the resolved context to (name, value) job-parameter pairs.

    These correspond to the parameterDefinitions in the static template. Render
    settings and the software (Conda) specs come from the context; the shot asset
    is an on-disk path that becomes a job attachment.
    """
    res = ctx.render("resolution", [1920, 1080])
    params: list[tuple[str, str]] = [
        ("ShotId", ctx.shot_id),
        ("FrameRange", str(ctx.render("frame_range", "1-48"))),
        ("ResolutionX", str(res[0])),
        ("ResolutionY", str(res[1])),
        ("Samples", str(ctx.render("samples", 64))),
        ("FrameRate", str(ctx.render("frame_rate", 24))),
        # The shot asset (becomes a job attachment via the template's IN PATH param).
        ("ShotAsset", ctx.asset_path),
        # Output directory. Submitting it under studio/renders/<shot_id> means
        # the official auto-downloader (`deadline queue sync-output`, which
        # restores outputs to their submission-side path) lands finished frames
        # straight on the shared drive — no separate copy step. See
        # autodownload.py.
        ("OutputDir", os.path.join(studio_root(), "renders", ctx.shot_id)),
    ]

    # Software (DCC + plugins) is delivered by the Conda queue environment. We
    # only pass what to install and where from; the queue environment does the
    # solve, install, and per-host caching. The add-on module names tell the
    # render step which plugins to enable once the environment is active.
    params.append(("CondaPackages", conda_packages(ctx)))
    params.append(("CondaChannels", conda_channels(ctx)))
    params.append(("PluginModules", plugin_modules(ctx)))

    return params


def submit(shot_path: str, extra_args: list[str] | None = None, dry_run: bool = False) -> int:
    """Submit the shot. Returns the deadline CLI exit code (0 on dry-run).

    The submission inherits the shot's FLOW_*/SHOT_* environment (so the
    bundle's preSubmission hook can read it); we merge it into the child env.
    Any FLOW_* variable explicitly set in the caller's environment takes
    precedence over the shot-derived value, so both the documented
    ``export FLOW_PROJECT_ID=...`` setup (a "set project" step) and the
    ``FLOW_PUBLISH=FALSE studio-pipe submit ...`` escape hatch survive the
    merge instead of being clobbered by config defaults.
    """
    ctx = resolve(shot_path)
    params = build_parameters(ctx)

    cmd = ["deadline", "bundle", "submit", bundle_dir()]
    for name, value in params:
        cmd += ["-p", f"{name}={value}"]
    if extra_args:
        cmd += extra_args

    env = dict(os.environ)
    shot_env = shot_environment(ctx)
    caller_flow = {k: v for k, v in os.environ.items() if k.startswith("FLOW_")}
    env.update(shot_env)
    env.update(caller_flow)

    if dry_run:
        print("DRY RUN — would submit:")
        print(f"  STUDIO context: {ctx.shot_id}")
        for name, value in params:
            print(f"  -p {name}={value}")
        print("  command: " + " ".join(cmd))
        return 0

    print(f"Submitting {ctx.shot_id} from static bundle {bundle_dir()}")
    return subprocess.run(cmd, env=env).returncode
