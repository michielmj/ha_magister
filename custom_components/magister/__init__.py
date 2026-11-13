"""The Magister integration."""

from __future__ import annotations

from homeassistant.const import CONF_PASSWORD, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_create_clientsession
from homeassistant.helpers.typing import ConfigType

from .api import MagisterAuth, MagisterClient
from .const import CONF_HOST, CONF_TOTP_SECRET, DOMAIN
from .coordinator import MagisterConfigEntry, MagisterCoordinator, MagisterRuntimeData
from .pending import take_pending_login

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

PLATFORMS: list[Platform] = [Platform.CALENDAR]


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Magister integration."""
    return True


async def async_setup_entry(hass: HomeAssistant, entry: MagisterConfigEntry) -> bool:
    """Set up Magister from a config entry."""
    if pending := take_pending_login(hass, entry.unique_id):
        session, auth, client = pending.session, pending.auth, pending.client
        entry.async_on_unload(session.detach)
    else:
        host: str = entry.data[CONF_HOST]
        # Own cookie jar: the silent token renewal relies on the login session cookies.
        session = async_create_clientsession(hass)
        auth = MagisterAuth(
            session,
            host,
            entry.data[CONF_USERNAME],
            entry.data[CONF_PASSWORD],
            entry.data.get(CONF_TOTP_SECRET) or None,
        )
        client = MagisterClient(session, auth, host)

    coordinator = MagisterCoordinator(hass, entry, client)
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = MagisterRuntimeData(
        session=session, auth=auth, client=client, coordinator=coordinator
    )
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: MagisterConfigEntry) -> bool:
    """Unload a Magister config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
