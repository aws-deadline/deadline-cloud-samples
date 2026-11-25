# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
"""The boto3 session every command uses."""

from __future__ import annotations

from typing import Any

from .config import deadline_defaults

#: The Deadline Cloud client's name for boto3's default credential chain.
DEFAULT_PROFILE = "(default)"


def make_session(profile: str | None = None, region: str | None = None) -> Any:
    """A boto3 session: ``profile``, else the Deadline Cloud client's configured profile
    (``deadline config get defaults.aws_profile_name``), else boto3's default chain.

    The ``deadline`` CLI ignores ``AWS_PROFILE``; falling back to its profile is what makes
    these commands see the same account as ``deadline job list``. ``AWS_ENDPOINT_URL_DEADLINE``
    is honored by boto3.
    """
    import boto3

    if not profile:
        profile = deadline_defaults().get("aws_profile_name") or None
    if profile == DEFAULT_PROFILE:
        profile = None
    return boto3.Session(profile_name=profile or None, region_name=region or None)


#: AssumeQueueRoleForUser errors that mean "use the caller's own credentials instead":
#: the caller may not call it (e.g. an IAM principal with direct S3 access), or the queue
#: has no role.
_NO_QUEUE_ROLE = {"AccessDeniedException", "ValidationException", "ResourceNotFoundException"}


def queue_session(session: Any, farm_id: str, queue_id: str) -> Any:
    """A session with the queue role's credentials, for reading job attachments in S3.

    Deadline Cloud Monitor sign-ins can read a queue's job attachments only through the
    queue's role (``AssumeQueueRoleForUser``), the same way ``deadline job download-output``
    does. The credentials refresh themselves, so long downloads outlive their expiry.
    Falls back to ``session`` when the caller can't assume the queue role."""
    import boto3
    import botocore.session
    from botocore.credentials import RefreshableCredentials
    from botocore.exceptions import ClientError

    deadline = session.client("deadline")

    def fetch() -> dict:
        c = deadline.assume_queue_role_for_user(farmId=farm_id, queueId=queue_id)["credentials"]
        expiry = c["expiration"]
        return {
            "access_key": c["accessKeyId"],
            "secret_key": c["secretAccessKey"],
            "token": c["sessionToken"],
            "expiry_time": expiry.isoformat() if hasattr(expiry, "isoformat") else str(expiry),
        }

    try:
        meta = fetch()
    except ClientError as exc:
        if exc.response.get("Error", {}).get("Code") in _NO_QUEUE_ROLE:
            return session
        raise
    creds = RefreshableCredentials.create_from_metadata(
        meta, refresh_using=fetch, method="assume-queue-role-for-user"
    )
    core = botocore.session.Session()
    core._credentials = creds  # botocore has no public setter for refreshable credentials
    return boto3.Session(botocore_session=core, region_name=getattr(session, "region_name", None))
