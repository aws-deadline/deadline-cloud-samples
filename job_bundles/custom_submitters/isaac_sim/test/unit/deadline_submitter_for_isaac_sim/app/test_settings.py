# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
import json
import os

from deadline.isaac_sim_submitter.app import settings as st


def test_defaults_persist_and_survive_a_bad_file(monkeypatch, tmp_path):
    path = tmp_path / "cfg" / "settings.json"
    monkeypatch.setenv(st.PATH_ENV, str(path))
    st.reload()
    assert st.get_str(st.BUNDLE_DIRS) == "~/DeadlineCloud/JobBundles"
    assert st.get_str(st.DOWNLOAD_DIR) == "" and st.get_str("nope", "x") == "x"
    st.set_str(st.DOWNLOAD_DIR, "~/dl")
    st.set_str(st.LAST_LOADED_JOB, "job-1")
    assert json.loads(path.read_text()) == {"downloadDir": "~/dl", "lastLoadedJob": "job-1"}
    st.reload()
    assert st.get_str(st.LAST_LOADED_JOB) == "job-1"
    assert [p.name for p in path.parent.iterdir()] == ["settings.json"]  # no temp files left
    path.write_text("{not json")
    st.reload()
    assert st.get_str(st.LAST_LOADED_JOB) == ""
    path.write_text("[1, 2]")
    st.reload()
    assert st.get_str(st.BUNDLE_DIRS) == "~/DeadlineCloud/JobBundles"


def test_settings_path_per_platform(monkeypatch):
    monkeypatch.delenv(st.PATH_ENV, raising=False)
    monkeypatch.setattr(st.sys, "platform", "win32")
    monkeypatch.setenv("APPDATA", os.path.join("C", "AppData", "Roaming"))
    assert st.settings_path() == os.path.join(
        "C", "AppData", "Roaming", "deadline-cloud-for-isaac-sim", "settings.json"
    )
    monkeypatch.setattr(st.sys, "platform", "linux")
    monkeypatch.setenv("XDG_CONFIG_HOME", os.path.join("h", "cfg"))
    assert st.settings_path() == os.path.join(
        "h", "cfg", "deadline-cloud-for-isaac-sim", "settings.json"
    )
    monkeypatch.delenv("XDG_CONFIG_HOME")
    assert st.settings_path() == os.path.join(
        os.path.expanduser("~"), ".config", "deadline-cloud-for-isaac-sim", "settings.json"
    )


def test_download_root(monkeypatch, tmp_path):
    monkeypatch.setenv("DEADLINE_PHYSICAL_AI_HOME", str(tmp_path / "pai"))
    assert st.download_root() == str(tmp_path / "pai" / "job_outputs")
    st.set_str(st.DOWNLOAD_DIR, str(tmp_path / "mine"))
    assert st.download_root() == str(tmp_path / "mine")
