"""The Magister integration."""

from __future__ import annotations

import json

from homeassistant.const import CONF_PASSWORD, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.aiohttp_client import async_create_clientsession
from homeassistant.helpers.typing import ConfigType

from .api import MagisterAuth, MagisterClient
from .const import (
    CHILD_ID,
    CONF_CHILD_ID,
    CONF_CHILDREN,
    CONF_HOST,
    CONF_TOTP_SECRET,
    DOMAIN,
)
from .coordinator import (
    MagisterConfigEntry,
    MagisterCoordinator,
    MagisterRuntimeData,
    login_page_issue_id,
)
from .pending import (
    PendingLogin,
    async_register_shutdown,
    drop_login,
    get_retained_login,
    retain_login,
    take_pending_login,
)

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

PLATFORMS: list[Platform] = [Platform.CALENDAR, Platform.SENSOR]


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

    if login.auth.has_final_failure and login.auth.final_failure_reported:
        # The failure was already reported (setup error / reauth state), so this
        # setup is user-initiated (reload): allow exactly one new login.
        login.auth.clear_final_failure()
    if login.auth.has_final_failure:
        login.auth.final_failure_reported = True
        raise ConfigEntryError(
            translation_domain=DOMAIN, translation_key="login_blocked"
        )

    coordinator = MagisterCoordinator(hass, entry, login.client, login.auth)
    await coordinator.async_config_entry_first_refresh()

    _async_remove_dropped_children(hass, entry)
    entry.runtime_data = MagisterRuntimeData(
        session=login.session,
        auth=login.auth,
        client=login.client,
        coordinator=coordinator,
        snapshot=config_snapshot(entry),
    )
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    return True


def config_snapshot(entry: MagisterConfigEntry) -> str:
    """The parts of an entry that need a reload when they change.

    Credentials are left out: reauth and reconfigure schedule their own reload.
    """
    return json.dumps(
        {
            "options": dict(entry.options),
            "children": [child[CHILD_ID] for child in entry.data[CONF_CHILDREN]],
            "subentries": {
                sid: [sub.subentry_type, sub.title, dict(sub.data)]
                for sid, sub in entry.subentries.items()
            },
        },
        sort_keys=True,
        default=str,
    )


async def _async_update_listener(
    hass: HomeAssistant, entry: MagisterConfigEntry
) -> None:
    """Reload after options, children or sensors changed."""
    if config_snapshot(entry) != entry.runtime_data.snapshot:
        hass.config_entries.async_schedule_reload(entry.entry_id)


def _child_of_unique_id(unique_id: str) -> int | None:
    """Return the child id from ``<host>:<childId>[:...]``."""
    parts = unique_id.split(":")
    try:
        return int(parts[1])
    except IndexError, ValueError:
        return None


@callback
def _async_remove_dropped_children(
    hass: HomeAssistant, entry: MagisterConfigEntry
) -> None:
    """Remove entities of unselected children and of deleted sensors."""
    selected = {int(child[CHILD_ID]) for child in entry.data[CONF_CHILDREN]}
    for subentry_id, subentry in list(entry.subentries.items()):
        if int(subentry.data.get(CONF_CHILD_ID, -1)) not in selected:
            hass.config_entries.async_remove_subentry(entry, subentry_id)
    entity_registry = er.async_get(hass)
    for entity in er.async_entries_for_config_entry(entity_registry, entry.entry_id):
        child_id = _child_of_unique_id(entity.unique_id)
        if child_id is not None and child_id not in selected:
            entity_registry.async_remove(entity.entity_id)
        elif (
            ":first:" in entity.unique_id
            and entity.unique_id.rpartition(":")[2] not in entry.subentries
        ):
            # The sensor of a deleted sub-entry
            entity_registry.async_remove(entity.entity_id)
    device_registry = dr.async_get(hass)
    for device in dr.async_entries_for_config_entry(device_registry, entry.entry_id):
        for domain, key in device.identifiers:
            child_id = _child_of_unique_id(key) if domain == DOMAIN else None
            if child_id is not None and child_id not in selected:
                device_registry.async_remove_device(device.id)
                break


async def async_unload_entry(hass: HomeAssistant, entry: MagisterConfigEntry) -> bool:
    """Unload a Magister config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_remove_entry(hass: HomeAssistant, entry: MagisterConfigEntry) -> None:
    """Release the kept login when the entry is removed."""
    drop_login(hass, entry.entry_id)
    ir.async_delete_issue(hass, DOMAIN, login_page_issue_id(entry.entry_id))
