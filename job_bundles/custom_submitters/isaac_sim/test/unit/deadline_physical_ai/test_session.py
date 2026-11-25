# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
"""Profile and region resolution. No AWS calls: boto3.Session is replaced."""

from __future__ import annotations

from typing import Any

import pytest

from deadline.physical_ai import config as cfg
from deadline.physical_ai import session as ses


@pytest.fixture()
def made(monkeypatch: pytest.MonkeyPatch) -> list:
    import boto3

    calls: list = []

    def session(**kw: Any) -> dict:
        calls.append(kw)
        return kw

    monkeypatch.setattr(boto3, "Session", session)
    return calls


def test_explicit_profile_wins(made: list, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(ses, "deadline_defaults", lambda: {"aws_profile_name": "cfg"})
    ses.make_session("mine", "us-west-2")
    assert made == [{"profile_name": "mine", "region_name": "us-west-2"}]


def test_deadline_config_profile_is_the_default(
    made: list, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The deadline CLI ignores AWS_PROFILE; so does this, by passing its profile explicitly."""
    monkeypatch.setenv("AWS_PROFILE", "env-profile")
    monkeypatch.setattr(ses, "deadline_defaults", lambda: {"aws_profile_name": "cfg"})
    ses.make_session()
    monkeypatch.setattr(ses, "deadline_defaults", lambda: {"aws_profile_name": "(default)"})
    ses.make_session()
    monkeypatch.setattr(ses, "deadline_defaults", lambda: {"aws_profile_name": ""})
    ses.make_session()
    assert [c["profile_name"] for c in made] == ["cfg", None, None]


def test_home_dir_and_defaults(monkeypatch: pytest.MonkeyPatch, tmp_path: Any) -> None:
    monkeypatch.setenv(cfg.HOME_ENV, str(tmp_path))
    assert cfg.home_dir() == str(tmp_path)
    monkeypatch.delenv(cfg.HOME_ENV)
    assert cfg.home_dir().endswith("physical-ai")
    d = cfg.deadline_defaults()
    assert set(d) == {"farm_id", "queue_id", "aws_profile_name"}
    assert all(isinstance(v, str) for v in d.values())
