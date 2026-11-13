"""Keep logged-in objects across config flow, setup retries and reloads.

* The config flow logs in to validate the credentials. Logging in again right away
  would waste a login, and with a TOTP secret the second login would reuse the same
  30 s code, which Magister rejects. So the validated login waits here (``pending``)
  until the entry is set up.
* A failed setup is retried by HA with a new call of ``async_setup_entry``. The auth
  helper (backoff, remembered failure, last TOTP step) and its session are kept per
  entry (``retained``) so a retry does not resend the password.

Sessions are created with ``auto_cleanup=False`` and detached by ``drop_login`` (entry
removal, changed credentials) or when Home Assistant closes.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from homeassistant.const import EVENT_HOMEASSISTANT_CLOSE
from homeassistant.core import Event, HomeAssistant, callback

from .const import DOMAIN

if TYPE_CHECKING:
    import aiohttp

    from .api import MagisterAuth, MagisterClient

_PENDING = f"{DOMAIN}_pending_logins"
_RETAINED = f"{DOMAIN}_retained_logins"


@dataclass
class PendingLogin:
    """A session, auth helper and client, with the credentials they were made for."""

    session: aiohttp.ClientSession
    auth: MagisterAuth
    client: MagisterClient
    credentials: tuple[Any, ...] | None = None


def store_pending_login(
    hass: HomeAssistant, unique_id: str, login: PendingLogin
) -> None:
    """Keep ``login`` for the entry with ``unique_id`` (from the config flow)."""
    hass.data.setdefault(_PENDING, {})[unique_id] = login


def take_pending_login(
    hass: HomeAssistant, unique_id: str | None
) -> PendingLogin | None:
    """Return and forget the login stored for ``unique_id``, if any."""
    if unique_id is None:
        return None
    logins: dict[str, PendingLogin] = hass.data.get(_PENDING, {})
    return logins.pop(unique_id, None)


def get_retained_login(
    hass: HomeAssistant, entry_id: str, credentials: tuple[Any, ...]
) -> PendingLogin | None:
    """Return the login kept for an entry, unless the credentials changed."""
    logins: dict[str, PendingLogin] = hass.data.get(_RETAINED, {})
    login = logins.get(entry_id)
    if login is None:
        return None
    if login.credentials is not None and login.credentials != credentials:
        drop_login(hass, entry_id)
        return None
    return login


def retain_login(hass: HomeAssistant, entry_id: str, login: PendingLogin) -> None:
    """Keep ``login`` for later setup retries and reloads of the entry."""
    logins: dict[str, PendingLogin] = hass.data.setdefault(_RETAINED, {})
    logins[entry_id] = login


def drop_login(hass: HomeAssistant, entry_id: str) -> None:
    """Forget and release the login kept for an entry."""
    logins: dict[str, PendingLogin] = hass.data.get(_RETAINED, {})
    if (login := logins.pop(entry_id, None)) is not None:
        login.session.detach()


@callback
def async_register_shutdown(hass: HomeAssistant) -> None:
    """Release all kept sessions when Home Assistant closes."""

    @callback
    def _release(_: Event) -> None:
        for entry_id in list(hass.data.get(_RETAINED, {})):
            drop_login(hass, entry_id)

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_CLOSE, _release)
