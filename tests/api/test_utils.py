"""Tests for the helper functions."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta, timezone

import pytest

from custom_components.magister.api.utils import format_api_timestamp, normalize_host


@pytest.mark.parametrize(
    "value",
    [
        "school",
        "SCHOOL",
        " school.magister.net ",
        "https://school.magister.net/magister/",
        "school.magister.net/x?y=1",
    ],
)
def test_normalize_host(value: str) -> None:
    """Various spellings normalize to the host."""
    assert normalize_host(value) == "school.magister.net"


@pytest.mark.parametrize(
    "value",
    ["evil.example.com", "magister.net", "accounts.magister.net", "a b", "-x", ""],
)
def test_normalize_host_rejects(value: str) -> None:
    """Hosts outside *.magister.net are refused."""
    with pytest.raises(ValueError):
        normalize_host(value)


def test_format_api_timestamp() -> None:
    """Aware datetimes are converted to UTC."""
    local = datetime(2026, 11, 9, 9, 0, tzinfo=timezone(timedelta(hours=1)))
    assert format_api_timestamp(local) == "2026-11-09T08:00:00.000Z"
    assert format_api_timestamp(datetime(2026, 1, 1, tzinfo=UTC)).endswith("00.000Z")
    with pytest.raises(ValueError):
        format_api_timestamp(datetime(2026, 1, 1))
