"""Tests for MagisterClient."""

from __future__ import annotations

import re
from datetime import UTC, datetime
from unittest.mock import AsyncMock

import aiohttp
import pytest
from aioresponses import aioresponses

from custom_components.magister.api import (
    MagisterApiError,
    MagisterAuth,
    MagisterAuthError,
    MagisterClient,
    MagisterConnectionError,
)

from .helpers import HOST
from .test_models import lesson

BASE = f"https://{HOST}"


def make_client(
    session: aiohttp.ClientSession, tokens: list[str] | None = None
) -> tuple[MagisterClient, AsyncMock]:
    """Create a client whose auth hands out the given tokens."""
    auth = AsyncMock(spec=MagisterAuth)
    auth.async_get_token.side_effect = tokens or ["tok-1", "tok-2"]
    return MagisterClient(session, auth, HOST), auth.async_get_token


async def test_get_account(
    mocked: aioresponses, session: aiohttp.ClientSession
) -> None:
    """The account is fetched with a Bearer header."""
    mocked.get(
        f"{BASE}/api/account",
        payload={
            "Persoon": {"Id": 7, "Roepnaam": "Ouder"},
            "Groep": [{"Naam": "Ouder"}],
        },
    )
    client, _ = make_client(session)
    account = await client.async_get_account()
    assert account.is_parent
    assert account.person.id == 7
    request = next(iter(mocked.requests.values()))[0]
    assert request.kwargs["headers"]["Authorization"] == "Bearer tok-1"
    assert "tok-1" not in repr(client)


async def test_get_children(
    mocked: aioresponses, session: aiohttp.ClientSession
) -> None:
    """Children come from the Items list."""
    mocked.get(
        f"{BASE}/api/personen/7/kinderen",
        payload={
            "Items": [{"Id": 11, "Roepnaam": "A"}, {"Id": 12, "Roepnaam": "B"}, "junk"]
        },
    )
    client, _ = make_client(session)
    children = await client.async_get_children(7)
    assert [c.id for c in children] == [11, 12]


async def test_get_appointments(
    mocked: aioresponses, session: aiohttp.ClientSession
) -> None:
    """Appointments are requested with UTC timestamps and the status filter."""
    pattern = re.compile(rf"^{re.escape(BASE)}/api/personen/11/afspraken\?.*$")
    mocked.get(pattern, payload={"Items": [lesson(), lesson(Id=2, DuurtHeleDag=True)]})
    client, _ = make_client(session)
    items = await client.async_get_appointments(
        11,
        datetime(2026, 11, 9, tzinfo=UTC),
        datetime(2026, 11, 16, tzinfo=UTC),
    )
    assert [a.id for a in items] == [1001, 2]
    url = next(iter(mocked.requests.keys()))[1]
    assert url.query["van"] == "2026-11-09T00:00:00.000Z"
    assert url.query["tot"] == "2026-11-16T00:00:00.000Z"
    assert url.query["status"] == "1"


async def test_get_appointments_without_status_and_raw(
    mocked: aioresponses, session: aiohttp.ClientSession
) -> None:
    """status=None omits the parameter; the raw getter returns the JSON."""
    pattern = re.compile(rf"^{re.escape(BASE)}/api/personen/11/afspraken\?.*$")
    mocked.get(pattern, payload={"Items": []})
    client, _ = make_client(session)
    await client.async_get_appointments(
        11,
        datetime(2026, 1, 1, tzinfo=UTC),
        datetime(2026, 1, 2, tzinfo=UTC),
        status=None,
    )
    url = next(iter(mocked.requests.keys()))[1]
    assert "status" not in url.query

    mocked.get(f"{BASE}/api/x", payload={"a": 1})
    assert await client.async_get_raw("/api/x") == {"a": 1}


async def test_401_triggers_one_reauth(
    mocked: aioresponses, session: aiohttp.ClientSession
) -> None:
    """A 401 forces a token refresh and one retry."""
    mocked.get(f"{BASE}/api/account", status=401)
    mocked.get(f"{BASE}/api/account", payload={"Persoon": {"Id": 7}})
    client, get_token = make_client(session)
    account = await client.async_get_account()
    assert account.person.id == 7
    assert get_token.await_args_list[0].kwargs == {}
    assert get_token.await_args_list[1].kwargs == {"force_refresh": True}
    requests = next(iter(mocked.requests.values()))
    assert requests[1].kwargs["headers"]["Authorization"] == "Bearer tok-2"


async def test_second_401_raises_auth_error(
    mocked: aioresponses, session: aiohttp.ClientSession
) -> None:
    """A 401 after the retry means the credentials do not work."""
    mocked.get(f"{BASE}/api/account", status=401, repeat=True)
    client, get_token = make_client(session)
    with pytest.raises(MagisterAuthError) as err:
        await client.async_get_account()
    assert err.value.code == "invalid_auth"
    assert get_token.await_count == 2


@pytest.mark.parametrize(
    ("status", "expected"),
    [
        (429, MagisterApiError),
        (500, MagisterConnectionError),
        (502, MagisterConnectionError),
        (404, MagisterApiError),
        (403, MagisterApiError),
    ],
)
async def test_error_statuses(
    mocked: aioresponses,
    session: aiohttp.ClientSession,
    status: int,
    expected: type[Exception],
) -> None:
    """HTTP errors map to the right exception, keeping the status."""
    mocked.get(f"{BASE}/api/account", status=status)
    client, _ = make_client(session)
    with pytest.raises(expected) as err:
        await client.async_get_account()
    if isinstance(err.value, MagisterApiError):
        assert err.value.status == status


@pytest.mark.parametrize("exc", [aiohttp.ClientConnectionError("x"), TimeoutError()])
async def test_network_errors(
    mocked: aioresponses, session: aiohttp.ClientSession, exc: Exception
) -> None:
    """Connection problems and timeouts become MagisterConnectionError."""
    mocked.get(f"{BASE}/api/account", exception=exc)
    client, _ = make_client(session)
    with pytest.raises(MagisterConnectionError):
        await client.async_get_account()


async def test_bad_bodies(mocked: aioresponses, session: aiohttp.ClientSession) -> None:
    """Invalid JSON and unexpected shapes raise API errors."""
    mocked.get(f"{BASE}/api/account", body="<html>", content_type="text/html")
    client, _ = make_client(session, ["t"] * 6)
    with pytest.raises(MagisterApiError):
        await client.async_get_account()

    mocked.get(f"{BASE}/api/account", payload=[1, 2])
    with pytest.raises(MagisterApiError):
        await client.async_get_account()

    mocked.get(f"{BASE}/api/personen/7/kinderen", payload={"Items": "nope"})
    with pytest.raises(MagisterApiError):
        await client.async_get_children(7)


def test_invalid_host(session: aiohttp.ClientSession) -> None:
    """The client refuses non-Magister hosts."""
    with pytest.raises(ValueError):
        MagisterClient(session, AsyncMock(spec=MagisterAuth), "evil.example.com")
