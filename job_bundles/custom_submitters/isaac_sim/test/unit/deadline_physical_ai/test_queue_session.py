# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
"""Job attachments are read with the queue role, as Deadline Cloud Monitor sign-ins need."""

from __future__ import annotations

import datetime
from types import SimpleNamespace
from typing import Any

import pytest
from botocore.exceptions import ClientError

from deadline.physical_ai import session as ses


class _Deadline:
    def __init__(self, error: str = "") -> None:
        self.error, self.calls = error, 0

    def assume_queue_role_for_user(self, **kw: Any) -> dict:
        self.calls += 1
        assert kw == {"farmId": "farm-1", "queueId": "queue-1"}
        if self.error:
            raise ClientError({"Error": {"Code": self.error}}, "AssumeQueueRoleForUser")
        expiry = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=1)
        return {
            "credentials": {
                "accessKeyId": "AKIAEXAMPLE",
                "secretAccessKey": "secret",
                "sessionToken": "token",
                "expiration": expiry,
            }
        }


def _base(deadline: _Deadline) -> Any:
    return SimpleNamespace(client=lambda name, **kw: deadline, region_name="us-west-2")


def test_queue_session_uses_the_queue_roles_credentials() -> None:
    deadline = _Deadline()
    s = ses.queue_session(_base(deadline), "farm-1", "queue-1")
    creds = s.get_credentials().get_frozen_credentials()
    assert (creds.access_key, creds.token) == ("AKIAEXAMPLE", "token")
    assert s.region_name == "us-west-2" and deadline.calls == 1


@pytest.mark.parametrize(
    "code", ["AccessDeniedException", "ValidationException", "ResourceNotFoundException"]
)
def test_queue_session_falls_back_to_the_callers_session(code: str) -> None:
    base = _base(_Deadline(code))
    assert ses.queue_session(base, "farm-1", "queue-1") is base


def test_queue_session_surfaces_other_errors() -> None:
    with pytest.raises(ClientError):
        ses.queue_session(_base(_Deadline("ThrottlingException")), "farm-1", "queue-1")
