"""Small helpers shared by the API modules."""

from __future__ import annotations

import re
from datetime import UTC, datetime

_HOST_RE = re.compile(
    r"^[a-z0-9]([a-z0-9-]*[a-z0-9])?(\.[a-z0-9]([a-z0-9-]*[a-z0-9])?)*$"
)
_SUFFIX = ".magister.net"


def normalize_host(tenant: str) -> str:
    """Turn ``myschool``, ``myschool.magister.net`` or a URL into a Magister host.

    Raises ``ValueError`` when the result is not a ``*.magister.net`` host name, so
    credentials and tokens are never sent to an arbitrary server.
    """
    host = tenant.strip().lower()
    host = re.sub(r"^https?://", "", host).split("/")[0].split("?")[0]
    if "." not in host:
        host = f"{host}{_SUFFIX}"
    if (
        not host.endswith(_SUFFIX)
        or host == _SUFFIX.lstrip(".")
        or host == "accounts.magister.net"
        or not _HOST_RE.match(host)
    ):
        raise ValueError("Not a Magister school host name")
    return host


def format_api_timestamp(value: datetime) -> str:
    """Format an aware datetime the way the Magister API expects (UTC, ``Z``)."""
    if value.tzinfo is None:
        raise ValueError("datetime must be timezone-aware")
    return value.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%S.000Z")
