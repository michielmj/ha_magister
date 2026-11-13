"""The Magister integration."""

from __future__ import annotations

import json
import logging

from homeassistant.const import CONF_PASSWORD, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.aiohttp_client import async_create_clientsession
from homeassistant.helpers.typing import ConfigType

from .api import MagisterAuth, MagisterClient
from .const import (
    CHILD_ID,
    CHILD_SHORT_NAME,
    CONF_CHILD_ID,
    CONF_CHILDREN,
    CONF_HOST,
    CONF_TOTP_SECRET,
    CONF_WEIGHTS,
    DOMAIN,
)
from .coordinator import (
    MagisterConfigEntry,
    MagisterCoordinator,
    MagisterRuntimeData,
    login_page_issue_id,
)
from .entity import child_device_info
from .homework import HomeworkManager, async_remove_store
from .options_flow import children_in_other_entries
from .pending import (
    PendingLogin,
    async_register_shutdown,
    drop_login,
    get_retained_login,
    retain_login,
    take_pending_login,
)
from .todo import async_register_homework_service
from .ws_api import async_register_websocket_api

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

PLATFORMS: list[Platform] = [Platform.CALENDAR, Platform.SENSOR, Platform.TODO]


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Magister integration."""
    async_register_shutdown(hass)
    async_register_websocket_api(hass)
    async_register_homework_service(hass)
    return True


_LOGGER = logging.getLogger(__name__)


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

    if login.auth.is_credential_failure:
        # Rejected credentials are never sent again: only new credentials (the
        # reauth hand-over or a changed config entry) lead to a new login.
        login.auth.final_failure_reported = True
        raise ConfigEntryAuthFailed(
            translation_domain=DOMAIN, translation_key="auth_failed"
        )
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

    homework = HomeworkManager(hass, entry, coordinator)
    await homework.async_load()
    homework.async_start()

    _async_remove_dropped_children(hass, entry)
    entry.runtime_data = MagisterRuntimeData(
        session=login.session,
        auth=login.auth,
        client=login.client,
        coordinator=coordinator,
        homework=homework,
        snapshot=config_snapshot(entry),
    )
    # The calendar and the sensors are set up concurrently and share these devices.
    device_registry = dr.async_get(hass)
    for child in entry.data[CONF_CHILDREN]:
        device_registry.async_get_or_create(
            config_entry_id=entry.entry_id,
            **child_device_info(
                host, int(child[CHILD_ID]), str(child[CHILD_SHORT_NAME])
            ),
        )
    async_sync_duplicate_issues(hass)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    return True


def duplicate_issue_id(entry_id: str) -> str:
    """Issue id of the "child in several logins" repair for an entry."""
    return f"child_in_multiple_entries_{entry_id}"


@callback
def async_sync_duplicate_issues(
    hass: HomeAssistant, exclude_entry_id: str | None = None
) -> None:
    """Create or clear the repair for children that two logins of a school share."""
    for entry in hass.config_entries.async_entries(DOMAIN):
        if entry.entry_id == exclude_entry_id:
            continue
        own = {int(c[CHILD_ID]) for c in entry.data[CONF_CHILDREN]}
        taken = children_in_other_entries(
            hass, entry.data[CONF_HOST], entry.entry_id, exclude_entry_id
        )
        issue_id = duplicate_issue_id(entry.entry_id)
        if own & taken:
            if ir.async_get(hass).async_get_issue(DOMAIN, issue_id) is None:
                _LOGGER.warning(
                    "A child is configured under more than one Magister login "
                    "for the same school; remove it from one login via Configure"
                )
            ir.async_create_issue(
                hass,
                DOMAIN,
                issue_id,
                is_fixable=False,
                severity=ir.IssueSeverity.WARNING,
                translation_key="child_in_multiple_entries",
            )
        else:
            ir.async_delete_issue(hass, DOMAIN, issue_id)


def config_snapshot(entry: MagisterConfigEntry) -> str:
    """The parts of an entry that need a reload when they change.

    Credentials are left out: reauth and reconfigure schedule their own reload. So are
    the homework weights, which are applied to the sensors without a reload.
    """
    return json.dumps(
        {
            "options": {
                key: value
                for key, value in entry.options.items()
                if key != CONF_WEIGHTS
            },
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
    """Reload after options, children or sensors changed; apply new weights live."""
    async_sync_duplicate_issues(hass)
    if config_snapshot(entry) != entry.runtime_data.snapshot:
        hass.config_entries.async_schedule_reload(entry.entry_id)
    else:
        entry.runtime_data.homework.async_weights_changed()


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
    """Remove entities, devices and sensors of children that were unselected."""
    selected = {int(child[CHILD_ID]) for child in entry.data[CONF_CHILDREN]}
    for subentry_id, subentry in list(entry.subentries.items()):
        if int(subentry.data.get(CONF_CHILD_ID, -1)) not in selected:
            hass.config_entries.async_remove_subentry(entry, subentry_id)
    entity_registry = er.async_get(hass)
    for entity in er.async_entries_for_config_entry(entity_registry, entry.entry_id):
        child_id = _child_of_unique_id(entity.unique_id)
        if child_id is not None and child_id not in selected:
            entity_registry.async_remove(entity.entity_id)
    device_registry = dr.async_get(hass)
    for device in dr.async_entries_for_config_entry(device_registry, entry.entry_id):
        for domain, key in device.identifiers:
            child_id = _child_of_unique_id(key) if domain == DOMAIN else None
            if child_id is not None and child_id not in selected:
                device_registry.async_remove_device(device.id)
                break


async def async_unload_entry(hass: HomeAssistant, entry: MagisterConfigEntry) -> bool:
    """Unload a Magister config entry (unsaved homework progress is written first)."""
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        await entry.runtime_data.homework.async_flush()
    return unloaded


async def async_remove_entry(hass: HomeAssistant, entry: MagisterConfigEntry) -> None:
    """Release the kept login when the entry is removed."""
    drop_login(hass, entry.entry_id)
    await async_remove_store(hass, entry.entry_id)
    ir.async_delete_issue(hass, DOMAIN, duplicate_issue_id(entry.entry_id))
    async_sync_duplicate_issues(hass, exclude_entry_id=entry.entry_id)
    if (pending := take_pending_login(hass, entry.unique_id)) is not None:
        pending.session.detach()
    ir.async_delete_issue(hass, DOMAIN, login_page_issue_id(entry.entry_id))
