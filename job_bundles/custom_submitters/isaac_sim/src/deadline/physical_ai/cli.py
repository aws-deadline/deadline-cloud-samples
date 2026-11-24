# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
"""``deadline-physical-ai``: list and fetch job outputs, run the app, and install the Isaac
Sim extension.

The app (``gui``) runs ``outputs list`` and ``outputs fetch`` with ``--json`` and reads one
JSON object from stdout, so those shapes are a contract, and every failure still
prints exactly one object: ``{"status": "error", "error": "...", "error_type": "..."}``
(plus ``"hint"`` for credential problems). ``--progress`` adds ``PROGRESS {json}`` lines
on stderr. A bad command line does the same (``"error_type": "UsageError"``) whenever
``--json`` is in argv; without it, argparse's usage text and exit 2 are kept.

Exit codes: 0 ok, 1 error.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Callable
from typing import Any, NoReturn

EXIT_OK = 0
EXIT_ERROR = 1

Result = tuple[dict | None, int]
#: ``jobs list --status`` choices (the same keys as ``jobs.STATUSES``; kept here so parsing
#: arguments doesn't import boto3).
_JOB_STATUSES = ("succeeded", "failed", "canceled", "any")


def _emit(obj: dict, as_json: bool) -> None:
    if as_json:
        sys.stdout.write(json.dumps(obj, sort_keys=True) + "\n")
        return
    for key, value in obj.items():
        if isinstance(value, (list, dict)):
            value = json.dumps(value, indent=2, sort_keys=True)
        sys.stdout.write(f"{key}: {value}\n")


# ------------------------------------------------------------------ commands --


def _cmd_outputs_list(args: argparse.Namespace) -> Result:
    from . import outputs

    return (
        outputs.job_outputs(
            args.job_id,
            farm_id=args.farm_id,
            queue_id=args.queue_id,
            profile=args.profile,
            region=args.region,
        ),
        EXIT_OK,
    )


def _cmd_jobs_list(args: argparse.Namespace) -> Result:
    from . import jobs

    return (
        jobs.finished_jobs(
            status=args.status,
            farm_id=args.farm_id,
            queue_id=args.queue_id,
            profile=args.profile,
            region=args.region,
            limit=args.limit,
            offset=args.offset,
        ),
        EXIT_OK,
    )


def _cmd_jobs_params(args: argparse.Namespace) -> Result:
    from . import jobs

    return (
        jobs.job_parameters(
            args.job_ids,
            farm_id=args.farm_id,
            queue_id=args.queue_id,
            profile=args.profile,
            region=args.region,
        ),
        EXIT_OK,
    )


def _cmd_jobs_evals(args: argparse.Namespace) -> Result:
    from . import evals

    return (
        evals.queue_evals(
            farm_id=args.farm_id,
            queue_id=args.queue_id,
            profile=args.profile,
            region=args.region,
            limit=args.limit,
            offset=args.offset,
        ),
        EXIT_OK,
    )


def _cmd_outputs_fetch(args: argparse.Namespace) -> Result:
    from . import outputs

    return (
        outputs.fetch(
            args.job_id,
            args.path,
            dest=args.dest or "",
            farm_id=args.farm_id,
            queue_id=args.queue_id,
            profile=args.profile,
            region=args.region,
            progress=_progress_printer() if args.progress else None,
        ),
        EXIT_OK,
    )


def _progress_printer(interval_s: float = 0.25) -> Callable[[int, int, int, int], None]:
    """``PROGRESS {"bytes", "total", "files", "file_total"}`` lines on stderr, at most every
    ``interval_s`` plus the final one, for a parent process (the Isaac Sim window) to show."""
    import threading
    import time

    lock, last = threading.Lock(), {"t": float("-inf")}  # the first call always prints

    def show(done_b: int, total_b: int, done_n: int, total_n: int) -> None:
        now = time.monotonic()
        with lock:
            if now - last["t"] < interval_s and done_n < total_n:
                return
            last["t"] = now
            sys.stderr.write(
                "PROGRESS "
                + json.dumps(
                    {"bytes": done_b, "total": total_b, "files": done_n, "file_total": total_n}
                )
                + "\n"
            )
            sys.stderr.flush()

    return show


GUI_EXTRA_HINT = (
    'install the gui extra: pip install "deadline-cloud-for-isaac-sim[gui]" (it adds PySide6)'
)


def _qt_problem() -> str:
    """Why the Qt app cannot start here ("" when it can)."""
    try:
        import PySide6.QtWidgets  # noqa: F401
    except ImportError as exc:
        return f"the app needs PySide6, which did not import ({exc}): {GUI_EXTRA_HINT}"
    return ""


def _cmd_gui(args: argparse.Namespace) -> Result:
    problem = _qt_problem()
    if problem:
        if args.json:
            obj = {"status": "error", "error_type": "MissingDependency", "error": problem}
            return obj, EXIT_ERROR
        # stderr, not stdout: with --bridge, stdout belongs to the Isaac Sim extension.
        sys.stderr.write(f"deadline-physical-ai gui: {problem}\n")
        return None, EXIT_ERROR
    from deadline.isaac_sim_submitter.app import qt_app

    return None, qt_app.main(bridge=args.bridge)


def _cmd_extension_path(args: argparse.Namespace) -> Result:
    from deadline import isaac_sim_submitter as sub

    folder = sub.extension_folder()
    if not args.json:
        # Only the path, so it works as --ext-folder "$(deadline-physical-ai isaac-sim extension-path)".
        sys.stdout.write(f"{folder}\n")
        return None, EXIT_OK
    return {
        "status": "ok",
        "extension": sub.EXTENSION_NAME,
        "ext_folder": str(folder),
        "extension_path": str(folder / sub.EXTENSION_NAME),
    }, EXIT_OK


def _cmd_install_extension(args: argparse.Namespace) -> Result:
    from deadline.isaac_sim_submitter import install

    result = install.install(
        enable=args.enable,
        uninstall=args.uninstall,
        isaac_sim_python=args.isaac_sim_python or "",
        kit_user_folder=args.kit_user_folder or "",
        isaac_sim_version=args.isaac_sim_version or "",
    )
    obj = result.to_dict()
    if args.json:
        return obj, EXIT_OK
    w = sys.stdout.write
    if result.action == "install":
        w(f"Extension link ({result.link_status}): {result.link}\n  -> {result.extension_path}\n")
    else:
        w(f"Extension link ({result.link_status}): {result.link}\n")
    if result.user_config:
        w(f"Enabled entry ({result.enabled}): {result.user_config}\n")
    for note in result.notes:
        w(f"Note: {note}\n")
    return None, EXIT_OK


# -------------------------------------------------------------------- parser --


def _target_flags(p: argparse.ArgumentParser) -> None:
    p.add_argument("--farm-id", help="Default: the Deadline Cloud default farm.")
    p.add_argument("--queue-id", help="Default: the Deadline Cloud default queue.")
    p.add_argument("--profile", help="Default: the Deadline Cloud configured profile.")
    p.add_argument("--region")


def _json_flag(p: argparse.ArgumentParser) -> None:
    p.add_argument("--json", action="store_true", help="Print one JSON object.")


def build_parser(json_errors: bool = False) -> argparse.ArgumentParser:
    """The parser. With ``json_errors``, a usage error prints one JSON error object on
    stdout and exits 1 instead of argparse's usage text on stderr and exit 2, so
    ``--json`` always means exactly one JSON object on stdout."""

    class Parser(argparse.ArgumentParser):
        # Subparsers are made with ``parser_class=type(self)``, so they behave the same.
        def error(self, message: str) -> NoReturn:
            if not json_errors:
                super().error(message)
            _emit({"status": "error", "error_type": "UsageError", "error": message}, True)
            raise SystemExit(EXIT_ERROR)

    parser = Parser(
        prog="deadline-physical-ai",
        description="List and fetch AWS Deadline Cloud job outputs, run the Deadline Cloud for "
        "Isaac Sim app, and install the Isaac Sim extension.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    jobs_p = sub.add_parser("jobs", help="List jobs in a queue.")
    jobs_sub = jobs_p.add_subparsers(dest="jobs_command", required=True)
    p = jobs_sub.add_parser("list", help="Finished jobs, newest finished first (read-only).")
    _json_flag(p)
    p.add_argument(
        "--status",
        choices=list(_JOB_STATUSES),
        default="succeeded",
        help="succeeded (default), failed, canceled, or any of those.",
    )
    p.add_argument("--limit", type=int, default=50, help="Jobs per page (default 50).")
    p.add_argument("--offset", type=int, default=0, help="Skip this many (from next_offset).")
    _target_flags(p)
    p.set_defaults(func=_cmd_jobs_list)
    p = jobs_sub.add_parser("params", help="Jobs' names and parameters (read-only).")
    _json_flag(p)
    p.add_argument("job_ids", nargs="+", metavar="JOB_ID")
    _target_flags(p)
    p.set_defaults(func=_cmd_jobs_params)
    p = jobs_sub.add_parser(
        "evals",
        help="Completed jobs with their parameters and eval files (read-only; downloads "
        "only those files).",
    )
    _json_flag(p)
    p.add_argument("--limit", type=int, default=50, help="Jobs per page (default 50).")
    p.add_argument("--offset", type=int, default=0, help="Skip this many (from next_offset).")
    _target_flags(p)
    p.set_defaults(func=_cmd_jobs_evals)

    out_p = sub.add_parser("outputs", help="List a job's loadable outputs, or fetch chosen items.")
    out_sub = out_p.add_subparsers(dest="outputs_command", required=True)
    p = out_sub.add_parser("list", help="Detected items, without downloading them (read-only).")
    _json_flag(p)
    p.add_argument("job_id")
    _target_flags(p)
    p.set_defaults(func=_cmd_outputs_list)
    p = out_sub.add_parser("fetch", help="Download only the files under the given item paths.")
    _json_flag(p)
    p.add_argument("job_id")
    p.add_argument(
        "--path",
        action="append",
        required=True,
        help="Item path from `outputs list`. Repeatable.",
    )
    p.add_argument(
        "--dest",
        help="Folder to download into (default: ~/.deadline/physical-ai/job_outputs/<job>).",
    )
    p.add_argument("--progress", action="store_true", help="Print PROGRESS JSON lines on stderr.")
    _target_flags(p)
    p.set_defaults(func=_cmd_outputs_fetch)

    p = sub.add_parser(
        "gui",
        help="Open the app: browse and download job outputs, and submit job bundles.",
        description="Open the Deadline Cloud for Isaac Sim app. It runs without Isaac Sim; "
        "Isaac Sim's Tools > Deadline Cloud > Open Deadline Cloud starts it with --bridge, "
        "which adds replay and loading into the open stage. Needs the gui extra (PySide6).",
    )
    p.add_argument("--json", action="store_true", help="Report a startup error as one JSON object.")
    p.add_argument(
        "--bridge",
        action="store_true",
        help="Talk to the Isaac Sim extension that started this app over stdin and stdout, and "
        "exit when stdin closes. Used by the extension.",
    )
    p.set_defaults(func=_cmd_gui)

    isaac_p = sub.add_parser("isaac-sim", help="The Isaac Sim extension shipped with this package.")
    isaac_sub = isaac_p.add_subparsers(dest="isaac_sim_command", required=True)
    p = isaac_sub.add_parser(
        "extension-path",
        help="Print the folder holding the isaacsim.deadline.submitter extension, for Isaac "
        "Sim's --ext-folder.",
    )
    _json_flag(p)
    p.set_defaults(func=_cmd_extension_path)
    p = isaac_sub.add_parser(
        "install-extension",
        help="Link the extension into Isaac Sim (no files are copied).",
        description="Link isaacsim.deadline.submitter into <isaacsim package>/extsUser when the "
        "isaacsim pip package is importable, else into the per-user Kit extension folder.",
    )
    _json_flag(p)
    where = p.add_mutually_exclusive_group()
    where.add_argument(
        "--isaac-sim-python",
        metavar="PATH",
        help="A Python with the isaacsim pip package installed (default: this Python).",
    )
    where.add_argument(
        "--kit-user-folder",
        metavar="PATH",
        help="Link into this Kit extension folder instead (default when isaacsim is not "
        "installed: ~/Documents/Kit/shared/exts).",
    )
    p.add_argument(
        "--enable",
        action="store_true",
        help="Also enable the extension in the Isaac Sim GUI app's user.config.json.",
    )
    p.add_argument(
        "--isaac-sim-version",
        metavar="X.Y",
        help="Isaac Sim version for --enable/--uninstall (default: the isaacsim package's).",
    )
    p.add_argument(
        "--uninstall", action="store_true", help="Remove the link and the enabled entry."
    )
    p.set_defaults(func=_cmd_install_extension)
    return parser


# -------------------------------------------------------------------- errors --


def _aws_errors() -> tuple:
    """botocore and job attachments exception bases, when installed."""
    found: list = []
    try:
        from botocore.exceptions import BotoCoreError, ClientError

        found += [BotoCoreError, ClientError]
    except ImportError:  # pragma: no cover
        pass
    try:
        from deadline.job_attachments import exceptions as ja

        for name in ("AssetSyncError", "JobAttachmentsError", "ManifestCreationException"):
            cls = getattr(ja, name, None)
            if isinstance(cls, type):
                found.append(cls)
    except ImportError:  # pragma: no cover
        pass
    return tuple(found)


_CREDENTIAL_ERRORS = {
    "NoCredentialsError",
    "PartialCredentialsError",
    "ProfileNotFound",
    "TokenRetrievalError",
    "SSOTokenLoadError",
    "UnauthorizedSSOTokenError",
    "CredentialRetrievalError",
}
_CREDENTIAL_CODES = {
    "ExpiredToken",
    "ExpiredTokenException",
    "InvalidClientTokenId",
    "UnrecognizedClientException",
    "InvalidAccessKeyId",
    "InvalidToken",
}


def _credential_hint(exc: BaseException) -> str:
    response: Any = getattr(exc, "response", None) or {}
    code = (
        str((response.get("Error") or {}).get("Code") or "") if isinstance(response, dict) else ""
    )
    if code in _CREDENTIAL_CODES or any(
        c.__name__ in _CREDENTIAL_ERRORS for c in type(exc).__mro__
    ):
        return (
            "AWS credentials are missing, expired or for an unknown profile: sign in again "
            "(Deadline Cloud Monitor, or `aws sso login`) or pass --profile"
        )
    return ""


def _error(exc: BaseException, *, typed: bool) -> dict:
    """The one error object. ``typed`` prefixes the message with the exception type, for
    errors from AWS or unexpected ones whose message alone is often unclear."""
    obj = {
        "status": "error",
        "error_type": type(exc).__name__,
        "error": f"{type(exc).__name__}: {exc}" if typed else str(exc),
    }
    hint = _credential_hint(exc)
    if hint:
        obj["hint"] = hint
    return obj


def main(argv: list | None = None) -> int:
    from .job_outputs import OutputsError

    # Read before parsing: a usage error must also obey the one-JSON-object contract.
    as_json = "--json" in (sys.argv[1:] if argv is None else list(argv))
    parser = build_parser(json_errors=as_json)
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        if as_json and exc.code == EXIT_ERROR:
            return EXIT_ERROR  # the parser printed the one error object
        raise  # --help, or argparse's own exit 2 without --json
    as_json = bool(getattr(args, "json", False))
    try:
        obj, code = args.func(args)
    except (OutputsError, ValueError, RuntimeError, OSError) as exc:
        _emit(_error(exc, typed=False), as_json)
        return EXIT_ERROR
    except _aws_errors() as exc:
        _emit(_error(exc, typed=True), as_json)
        return EXIT_ERROR
    except Exception as exc:  # noqa: BLE001 - last resort: the caller still gets one error object
        _emit(_error(exc, typed=True), as_json)
        return EXIT_ERROR
    if obj is not None:
        _emit(obj, as_json)
    return code


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
