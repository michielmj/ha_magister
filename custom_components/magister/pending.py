"""Hand a validated login from the config flow to the config entry setup.

The config flow logs in to validate the credentials. Logging in again right away
would waste a login, and with a TOTP secret the second login would reuse the same
30 s code, which Magister rejects. So the authenticated objects wait here until the
entry is set up.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from homeassistant.core import HomeAssistant

from .const import DOMAIN

if TYPE_CHECKING:
    import aiohttp

    from .api import MagisterAuth, MagisterClient

_KEY = f"{DOMAIN}_pending_logins"


@dataclass
class PendingLogin:
    """A logged-in session, auth helper and client."""

    session: aiohttp.ClientSession
    auth: MagisterAuth
    client: MagisterClient


def store_pending_login(
    hass: HomeAssistant, unique_id: str, login: PendingLogin
) -> None:
    """Keep ``login`` for the entry with ``unique_id``."""
    hass.data.setdefault(_KEY, {})[unique_id] = login


def take_pending_login(
    hass: HomeAssistant, unique_id: str | None
) -> PendingLogin | None:
    """Return and forget the login stored for ``unique_id``, if any."""
    if unique_id is None:
        return None
    logins: dict[str, PendingLogin] = hass.data.get(_KEY, {})
    return logins.pop(unique_id, None)
