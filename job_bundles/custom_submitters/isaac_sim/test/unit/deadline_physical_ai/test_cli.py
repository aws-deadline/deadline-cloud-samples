# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
"""``deadline-physical-ai``: the JSON contract the app reads, and ``gui`` startup. No AWS."""

import json

import pytest
from botocore.exceptions import ClientError, NoCredentialsError, ProfileNotFound

from deadline.job_attachments.exceptions import JobAttachmentsS3ClientError, MissingManifestError
from deadline.physical_ai import cli, outputs


def _one_json(text):
    lines = [ln for ln in text.splitlines() if ln.strip()]
    assert len(lines) == 1, text
    return json.loads(lines[0])


def test_progress_printer_throttles_and_emits_final(capsys):
    show = cli._progress_printer(interval_s=1e9)
    show(0, 100, 0, 4)
    show(10, 100, 1, 4)
    show(50, 100, 2, 4)
    show(100, 100, 4, 4)
    err = capsys.readouterr().err.splitlines()
    assert all(ln.startswith("PROGRESS ") for ln in err)
    got = [json.loads(ln[len("PROGRESS ") :]) for ln in err]
    assert got == [
        {"bytes": 0, "total": 100, "files": 0, "file_total": 4},
        {"bytes": 100, "total": 100, "files": 4, "file_total": 4},
    ]


def test_cli_outputs_fetch_json(monkeypatch, capsys):
    seen: dict = {}

    def fetch(job_id, paths, **kw):
        seen.update(kw, job_id=job_id, paths=paths)
        kw["progress"](5, 10, 0, 1)
        kw["progress"](10, 10, 1, 1)
        return {
            "job_id": job_id,
            "dest": kw["dest"],
            "downloaded_bytes": 10,
            "items": {"a": "D/a"},
            "missing": ["b"],
            "file_count": 1,
        }

    monkeypatch.setattr(outputs, "fetch", fetch)
    code = cli.main(
        [
            "outputs",
            "fetch",
            "job-abc",
            "--path",
            "a",
            "--path",
            "b",
            "--dest",
            "D",
            "--farm-id",
            "f",
            "--queue-id",
            "q",
            "--progress",
            "--json",
        ]
    )
    cap = capsys.readouterr()
    assert code == 0
    assert _one_json(cap.out)["items"] == {"a": "D/a"}
    assert seen["job_id"] == "job-abc" and seen["paths"] == ["a", "b"] and seen["dest"] == "D"
    assert seen["farm_id"] == "f" and seen["queue_id"] == "q" and callable(seen["progress"])
    assert (
        cap.err.splitlines()[-1]
        == 'PROGRESS {"bytes": 10, "total": 10, "files": 1, "file_total": 1}'
    )


def _client_error(code="AccessDeniedException"):
    return ClientError({"Error": {"Code": code, "Message": "nope"}}, "GetQueue")


ERRORS = [
    (_client_error(), "ClientError", False),
    (_client_error("ExpiredTokenException"), "ClientError", True),
    (NoCredentialsError(), "NoCredentialsError", True),
    (ProfileNotFound(profile="no-such"), "ProfileNotFound", True),
    (
        JobAttachmentsS3ClientError("get_object", 403, "b", "k"),
        "JobAttachmentsS3ClientError",
        False,
    ),
    (MissingManifestError("no manifest"), "MissingManifestError", False),
    (KeyError("surprise"), "KeyError", False),
]


@pytest.mark.parametrize(
    "exc,type_name,hint", ERRORS, ids=[e[1] + ("+hint" if e[2] else "") for e in ERRORS]
)
def test_cli_outputs_list_error_json(monkeypatch, capsys, exc, type_name, hint):
    def boom(*a, **k):
        raise exc

    monkeypatch.setattr(outputs, "job_outputs", boom)
    code = cli.main(["outputs", "list", "job-abc", "--farm-id", "f", "--queue-id", "q", "--json"])
    obj = _one_json(capsys.readouterr().out)
    assert code == cli.EXIT_ERROR and obj["status"] == "error"
    assert obj["error_type"] == type_name and type_name in obj["error"]
    assert ("hint" in obj) is hint


def test_cli_outputs_fetch_error_is_human_readable(monkeypatch, capsys):
    def boom(*a, **k):
        raise NoCredentialsError()

    monkeypatch.setattr(outputs, "fetch", boom)
    code = cli.main(["outputs", "fetch", "job-abc", "--path", "a"])
    out = capsys.readouterr().out
    assert (
        code == cli.EXIT_ERROR and "status: error" in out and "Unable to locate credentials" in out
    )
    assert not out.lstrip().startswith("{")


def test_package_errors_keep_their_message(monkeypatch, capsys):
    def boom(*a, **k):
        raise ValueError("job job-abc: no output files under ['x']")

    monkeypatch.setattr(outputs, "fetch", boom)
    cli.main(["outputs", "fetch", "job-abc", "--path", "x", "--json"])
    assert _one_json(capsys.readouterr().out)["error"] == "job job-abc: no output files under ['x']"


def test_extension_path_plain_and_json(capsys):
    from deadline import isaac_sim_submitter as sub

    folder = sub.extension_folder()
    assert cli.main(["isaac-sim", "extension-path"]) == cli.EXIT_OK
    assert capsys.readouterr().out == f"{folder}\n"
    assert cli.main(["isaac-sim", "extension-path", "--json"]) == cli.EXIT_OK
    assert json.loads(capsys.readouterr().out) == {
        "status": "ok",
        "extension": "isaacsim.deadline.submitter",
        "ext_folder": str(folder),
        "extension_path": str(folder / "isaacsim.deadline.submitter"),
    }


def test_missing_extension_is_one_error_object(monkeypatch, capsys):
    from deadline import isaac_sim_submitter as sub

    def missing():
        raise RuntimeError("the isaacsim.deadline.submitter extension is missing from x")

    monkeypatch.setattr(sub, "extension_folder", missing)
    assert cli.main(["isaac-sim", "extension-path", "--json"]) == cli.EXIT_ERROR
    assert _one_json(capsys.readouterr().out)["status"] == "error"


def test_install_extension_human_output(monkeypatch, capsys, tmp_path):
    from deadline.isaac_sim_submitter import install

    monkeypatch.setattr(install, "find_isaacsim", lambda: None)
    assert cli.main(["isaac-sim", "install-extension", "--kit-user-folder", str(tmp_path)]) == 0
    out = capsys.readouterr().out
    assert out.startswith("Extension link (created): ") and "->" in out
    assert (
        cli.main(
            ["isaac-sim", "install-extension", "--kit-user-folder", str(tmp_path), "--uninstall"]
        )
        == 0
    )
    out = capsys.readouterr().out
    assert out.startswith("Extension link (removed): ") and "Note: " in out


def test_kit_stubs_do_not_leak_into_other_tests():
    """The Kit extension tests stub carb, omni and isaacsim only for their own modules."""
    import sys

    leaked = sorted(n for n in sys.modules if n.split(".")[0] in ("carb", "omni", "isaacsim"))
    assert leaked == []
    assert not any(p.endswith("isaacsim.deadline.submitter") for p in sys.path)


def test_usage_error_with_json_is_one_error_object(capsys):
    """argparse's own exit 2 prints usage on stderr and nothing on stdout, which breaks
    the one-JSON-object contract the extension reads."""
    assert cli.main(["outputs", "fetch", "job-abc", "--json"]) == cli.EXIT_ERROR
    obj = _one_json(capsys.readouterr().out)
    assert obj["status"] == "error" and obj["error_type"] == "UsageError"
    assert "--path" in obj["error"]


def test_usage_error_with_json_in_sys_argv(monkeypatch, capsys):
    """The flag is read from argv before parsing, so even a bad subcommand reports JSON."""
    import sys

    monkeypatch.setattr(sys, "argv", ["deadline-physical-ai", "outputs", "--json"])
    assert cli.main() == cli.EXIT_ERROR
    assert _one_json(capsys.readouterr().out)["error_type"] == "UsageError"


def test_usage_error_without_json_keeps_argparse_behavior(capsys):
    with pytest.raises(SystemExit) as caught:
        cli.main(["outputs", "fetch", "job-abc"])
    assert caught.value.code == 2
    cap = capsys.readouterr()
    assert cap.out == "" and "--path" in cap.err


def test_gui_without_pyside_says_to_install_the_extra(monkeypatch, capsys):
    import sys

    monkeypatch.setitem(sys.modules, "PySide6.QtWidgets", None)  # import fails
    assert "deadline-cloud-for-isaac-sim[gui]" in cli._qt_problem()
    assert cli.main(["gui", "--json"]) == cli.EXIT_ERROR
    out = _one_json(capsys.readouterr().out)
    assert out["status"] == "error" and out["error_type"] == "MissingDependency"
    # Without --json the message goes to stderr: with --bridge, stdout is the bridge's.
    assert cli.main(["gui", "--bridge"]) == cli.EXIT_ERROR
    captured = capsys.readouterr()
    assert captured.out == "" and "needs PySide6" in captured.err


def test_gui_starts_the_app(monkeypatch):
    import sys
    import types

    started: list = []

    def main(bridge=False):
        started.append(bridge)
        return 0

    fake = types.ModuleType("qt_app")
    fake.main = main  # type: ignore[attr-defined]
    monkeypatch.setattr(cli, "_qt_problem", lambda: "")
    monkeypatch.setitem(sys.modules, "deadline.isaac_sim_submitter.app.qt_app", fake)
    import deadline.isaac_sim_submitter.app as app_pkg

    monkeypatch.setattr(app_pkg, "qt_app", fake, raising=False)
    assert cli.main(["gui", "--bridge"]) == 0 and started == [True]
    assert cli.main(["gui"]) == 0 and started == [True, False]
