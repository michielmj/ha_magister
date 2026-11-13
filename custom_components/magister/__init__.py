"""The Magister integration."""

from __future__ import annotations

from homeassistant.const import CONF_PASSWORD, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_create_clientsession
from homeassistant.helpers.typing import ConfigType

from .api import MagisterAuth, MagisterClient
from .const import CONF_HOST, CONF_TOTP_SECRET, DOMAIN
from .coordinator import MagisterConfigEntry, MagisterCoordinator, MagisterRuntimeData
from .pending import (
    PendingLogin,
    async_register_shutdown,
    drop_login,
    get_retained_login,
    retain_login,
    take_pending_login,
)

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

PLATFORMS: list[Platform] = [Platform.CALENDAR]


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Magister integration."""
    async_register_shutdown(hass)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: MagisterConfigEntry) -> bool:
    """Set up Magister from a config entry."""
    host: str = entry.data[CONF_HOST]
    credentials = (
        host,
        entry.data[CONF_USERNAME],
        entry.data[CONF_PASSWORD],
        entry.data.get(CONF_TOTP_SECRET) or None,
    )
    # A login from the config flow, or the one kept by an earlier (failed) setup:
    # a retry must not resend the password or reuse a TOTP code.
    login = take_pending_login(hass, entry.unique_id) or get_retained_login(
        hass, entry.entry_id, credentials
    )
    if login is None:
        # Own cookie jar: the silent token renewal relies on the login cookies.
        session = async_create_clientsession(hass, auto_cleanup=False)
        auth = MagisterAuth(session, host, *credentials[1:])
        login = PendingLogin(session, auth, MagisterClient(session, auth, host))
    login.credentials = credentials
    retain_login(hass, entry.entry_id, login)

    if login.auth.has_final_failure:
        raise ConfigEntryError(
            translation_domain=DOMAIN, translation_key="login_blocked"
        )

    coordinator = MagisterCoordinator(hass, entry, login.client, login.auth)
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = MagisterRuntimeData(
        session=login.session,
        auth=login.auth,
        client=login.client,
        coordinator=coordinator,
    )
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: MagisterConfigEntry) -> bool:
    """Unload a Magister config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_remove_entry(hass: HomeAssistant, entry: MagisterConfigEntry) -> None:
    """Release the kept login when the entry is removed."""
    drop_login(hass, entry.entry_id)
