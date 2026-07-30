"""studio-pipe command-line interface.

Subcommands:

  resolve       Print the resolved context for a shot (debugging the hierarchy).
  launch        Set up a shot's environment and launch the DCC (workstation).
  submit        Submit a shot to Deadline Cloud as a parameterized static bundle.
  autodownload  Download finished outputs to the drive via the official
                `deadline queue sync-output` auto-downloader (optionally waiting
                on a specific job first).

Software (DCC + plugins) is delivered by a Conda queue environment, not by this
launcher: build the packages from conda_recipes/ with rattler-build and publish
them to an S3 Conda channel with `aws s3 sync`, then attach
queue_environments/conda_queue_env_improved_caching.yaml to the queue. The
launcher only resolves the shot and fills the job's CondaPackages/CondaChannels.
"""
from __future__ import annotations

import argparse
import json
import sys

from . import autodownload
from .context import ContextError, resolve


def _cmd_resolve(args: argparse.Namespace) -> int:
    ctx = resolve(args.shot)
    print(json.dumps(
        {"project": ctx.project, "sequence": ctx.sequence, "shot": ctx.shot,
         "shot_id": ctx.shot_id, "asset_path": ctx.asset_path, "data": ctx.data},
        indent=2,
    ))
    return 0


def _cmd_launch(args: argparse.Namespace) -> int:
    from .launch import launch
    env = launch(args.shot, exec_dcc=not args.print_env)
    if args.print_env:
        # Emit only the studio-relevant additions, as shell exports.
        for key in sorted(env):
            if key.startswith(("STUDIO_", "SHOT_", "FLOW_")) or key == "PATH":
                print(f"export {key}={env[key]!r}")
    return 0


def _cmd_submit(args: argparse.Namespace) -> int:
    from .submit import submit
    return submit(args.shot, extra_args=args.deadline_args, dry_run=args.dry_run)


def _cmd_autodownload(args: argparse.Namespace) -> int:
    return autodownload.autodownload(
        job_id=args.job_id,
        farm_id=args.farm_id,
        queue_id=args.queue_id,
        lookback_minutes=args.lookback_minutes,
        checkpoint_dir=args.checkpoint_dir,
        ignore_storage_profiles=not args.use_storage_profiles,
    )


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="studio-pipe", description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="command", required=True)

    sp = sub.add_parser("resolve", help="Print a shot's resolved context.")
    sp.add_argument("shot", help="Shot path: project/sequence/shot")
    sp.set_defaults(func=_cmd_resolve)

    sp = sub.add_parser("launch", help="Launch the DCC for a shot.")
    sp.add_argument("shot", help="Shot path: project/sequence/shot")
    sp.add_argument("--print-env", action="store_true",
                    help="Print the launch environment instead of exec'ing the DCC.")
    sp.set_defaults(func=_cmd_launch)

    sp = sub.add_parser("submit", help="Submit a shot as a parameterized static bundle.")
    sp.add_argument("shot", help="Shot path: project/sequence/shot")
    sp.add_argument("--dry-run", action="store_true",
                    help="Print the parameters and command without submitting.")
    sp.add_argument("deadline_args", nargs="*",
                    help="Extra args passed through to `deadline bundle submit`. "
                         "Put them after a `--` separator so argparse does not treat "
                         "flags as options to studio-pipe, e.g. "
                         "`studio-pipe submit <shot> -- --yes --farm-id ...`.")
    sp.set_defaults(func=_cmd_submit)

    sp = sub.add_parser(
        "autodownload",
        help="Download finished outputs to the drive via `deadline queue sync-output`.")
    sp.add_argument("--job-id", default=None,
                    help="Optional: first `deadline job wait` on this job, then sync. "
                         "Omit to just sync every newly finished output in the queue.")
    sp.add_argument("--farm-id", default=None, help="Defaults to the deadline CLI's configured farm.")
    sp.add_argument("--queue-id", default=None, help="Defaults to the deadline CLI's configured queue.")
    sp.add_argument("--lookback-minutes", type=float,
                    default=autodownload.DEFAULT_LOOKBACK_MINUTES,
                    help="First-run window: download outputs finished within this many "
                         "minutes. Ignored once a checkpoint exists. Default: 60.")
    sp.add_argument("--checkpoint-dir", default=None,
                    help="Where sync-output stores its incremental-download checkpoint. "
                         "Defaults to the deadline CLI's location.")
    sp.add_argument("--use-storage-profiles", action="store_true",
                    help="Map output paths via a configured storage profile instead of "
                         "downloading to unmapped paths. Use when artists submit and "
                         "download on different machines/OSes.")
    sp.set_defaults(func=_cmd_autodownload)

    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except ContextError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
