"""Client for the Magister data API (Bearer-token based)."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Final

import aiohttp

from .auth import REQUEST_TIMEOUT, USER_AGENT, MagisterAuth
from .errors import (
    AUTH_INVALID,
    MagisterApiError,
    MagisterAuthError,
    MagisterConnectionError,
)
from .models import Account, Appointment, Person
from .utils import format_api_timestamp, normalize_host

_LOGGER = logging.getLogger(__name__)

DEFAULT_STATUS_FILTER: Final = 1


class MagisterClient:
    """Reads the account, children and agenda of a Magister school."""

    def __init__(
        self, session: aiohttp.ClientSession, auth: MagisterAuth, host: str
    ) -> None:
        """Create the client. ``host`` is the school host (``school.magister.net``)."""
        self._session = session
        self._auth = auth
        self._host = normalize_host(host)

    def __repr__(self) -> str:
        """Representation without credentials."""
        return f"MagisterClient(host={self._host!r})"

    async def async_get_account(self) -> Account:
        """Return the logged-in account."""
        data = await self._get_json("/api/account")
        return Account.from_json(data)

    async def async_get_children(self, parent_id: int) -> list[Person]:
        """Return the children of a parent account."""
        data = await self._get_json(f"/api/personen/{int(parent_id)}/kinderen")
        return [Person.from_json(item) for item in _items(data)]

    async def async_get_appointments(
        self,
        person_id: int,
        start: datetime,
        end: datetime,
        *,
        status: int | None = DEFAULT_STATUS_FILTER,
    ) -> list[Appointment]:
        """Return the appointments of a person between two aware datetimes.

        ``status`` is the ``status=`` query parameter of the reference script
        (``1``); pass ``None`` to omit it.
        """
        params: dict[str, str] = {
            "van": format_api_timestamp(start),
            "tot": format_api_timestamp(end),
        }
        if status is not None:
            params["status"] = str(status)
        data = await self._get_json(
            f"/api/personen/{int(person_id)}/afspraken", params=params
        )
        return [Appointment.from_json(item) for item in _items(data)]

    async def async_get_raw(
        self, path: str, params: dict[str, str] | None = None
    ) -> dict[str, Any]:
        """GET a data API path and return the decoded JSON (for the dump tool)."""
        return await self._get_json(path, params=params)

    async def _get_json(
        self, path: str, params: dict[str, str] | None = None
    ) -> dict[str, Any]:
        token = await self._auth.async_get_token()
        status, body = await self._request(path, params, token)
        if status == 401:
            _LOGGER.debug("Got 401 for %s, re-authenticating once", path)
            token = await self._auth.async_get_token(force_refresh=True)
            status, body = await self._request(path, params, token)
            if status == 401:
                raise MagisterAuthError(
                    AUTH_INVALID, "Magister rejected the access token after re-login"
                )
        if status == 429:
            raise MagisterApiError("Magister rate limit hit", status=429)
        if status >= 500:
            raise MagisterConnectionError(f"Magister server error {status}")
        if status != 200:
            raise MagisterApiError(f"Unexpected HTTP status {status}", status=status)
        if not isinstance(body, dict):
            raise MagisterApiError("Unexpected response format", status=status)
        return body

    async def _request(
        self, path: str, params: dict[str, str] | None, token: str
    ) -> tuple[int, Any]:
        url = f"https://{self._host}{path}"
        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
            "User-Agent": USER_AGENT,
        }
        try:
            async with self._session.get(
                url, params=params, headers=headers, timeout=REQUEST_TIMEOUT
            ) as resp:
                if resp.status != 200:
                    return resp.status, None
                try:
                    return resp.status, await resp.json(content_type=None)
                except ValueError as err:
                    raise MagisterApiError(
                        "Response was not valid JSON", status=resp.status
                    ) from err
        except TimeoutError as err:
            raise MagisterConnectionError("Timeout talking to Magister") from err
        except aiohttp.ClientError as err:
            raise MagisterConnectionError(
                f"Connection to Magister failed ({type(err).__name__})"
            ) from err


def _items(data: dict[str, Any]) -> list[dict[str, Any]]:
    items = data.get("Items", [])
    if not isinstance(items, list):
        raise MagisterApiError("Unexpected response format")
    return [item for item in items if isinstance(item, dict)]
