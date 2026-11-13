"""Data update coordinator for Magister."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, time, timedelta
from typing import TYPE_CHECKING

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryError
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .api import (
    Appointment,
    MagisterApiError,
    MagisterAuth,
    MagisterAuthError,
    MagisterClient,
    MagisterConnectionError,
    MagisterLoginPageError,
)
from .api.auth import RETRY_AFTER_MAX
from .api.mapping import LOCAL_TZ
from .const import (
    CHILD_ID,
    CONF_CHILDREN,
    CONF_INTERVAL,
    CONF_WEEKS_AHEAD,
    CONF_WEEKS_BACK,
    DOMAIN,
    INTERVAL_MINUTES,
    WEEKS_AHEAD,
    WEEKS_BACK,
)

if TYPE_CHECKING:
    import aiohttp

_LOGGER = logging.getLogger(__name__)

type MagisterData = dict[int, list[Appointment]]


@dataclass
class MagisterRuntimeData:
    """Objects that live as long as the config entry is loaded."""

    session: aiohttp.ClientSession
    auth: MagisterAuth
    client: MagisterClient
    coordinator: MagisterCoordinator
    snapshot: str = ""


type MagisterConfigEntry = ConfigEntry[MagisterRuntimeData]


def fetch_window(
    now: datetime,
    weeks_back: int = WEEKS_BACK,
    weeks_ahead: int = WEEKS_AHEAD,
) -> tuple[datetime, datetime]:
    """Return the window to fetch, in Europe/Amsterdam.

    From Monday 00:00 of ``weeks_back`` weeks ago up to local midnight of the day
    ``7 * weeks_ahead + 1`` days from today, so that every first-appointment offset
    up to ``7 * weeks_ahead - 1`` is covered, also right after midnight.
    """
    today = now.astimezone(LOCAL_TZ).date()
    monday = today - timedelta(days=today.weekday())
    start = datetime.combine(monday - timedelta(weeks=weeks_back), time.min, LOCAL_TZ)
    end = datetime.combine(
        today + timedelta(days=7 * weeks_ahead + 1), time.min, LOCAL_TZ
    )
    return start, end


def login_page_issue_id(entry_id: str) -> str:
    """Issue id of the "login page changed" repair for an entry."""
    return f"login_page_changed_{entry_id}"


class MagisterCoordinator(DataUpdateCoordinator[MagisterData]):
    """Fetches the agenda of all selected children of one config entry."""

    config_entry: MagisterConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        entry: MagisterConfigEntry,
        client: MagisterClient,
        auth: MagisterAuth,
    ) -> None:
        """Create the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=f"{DOMAIN} {entry.title}",
            update_interval=timedelta(
                minutes=int(entry.options.get(CONF_INTERVAL, INTERVAL_MINUTES))
            ),
        )
        self.last_success: datetime | None = None
        self.weeks_back = int(entry.options.get(CONF_WEEKS_BACK, WEEKS_BACK))
        self.weeks_ahead = int(entry.options.get(CONF_WEEKS_AHEAD, WEEKS_AHEAD))
        self._client = client
        self._auth = auth
        self.child_ids: list[int] = [
            int(child[CHILD_ID]) for child in entry.data[CONF_CHILDREN]
        ]

    async def _async_update_data(self) -> MagisterData:
        """Fetch the window for each child, one after the other."""
        start, end = fetch_window(dt_util.now(), self.weeks_back, self.weeks_ahead)
        data: MagisterData = {}
        try:
            for child_id in self.child_ids:
                appointments = await self._client.async_get_appointments(
                    child_id, start, end, status=None
                )
                data[child_id] = sorted(appointments, key=lambda a: (a.start, a.id))
        except MagisterAuthError as err:
            self._auth.final_failure_reported = True
            raise ConfigEntryAuthFailed(
                translation_domain=DOMAIN, translation_key="auth_failed"
            ) from err
        except (MagisterConnectionError, MagisterApiError) as err:
            if isinstance(err, MagisterLoginPageError):
                self._async_report_login_page_changed()
            if self._auth.has_final_failure:
                # A remembered failure after the password step is never retried.
                self._auth.final_failure_reported = True
                if self.data is None:
                    # During setup: not a credentials problem (5xx/timeout).
                    raise ConfigEntryError(
                        translation_domain=DOMAIN, translation_key="login_blocked"
                    ) from err
                raise ConfigEntryAuthFailed(
                    translation_domain=DOMAIN, translation_key="auth_failed"
                ) from err
            if isinstance(err, MagisterConnectionError):
                raise UpdateFailed(
                    translation_domain=DOMAIN, translation_key="connection_failed"
                ) from err
            retry_after = err.retry_after
            if retry_after is not None:
                retry_after = min(retry_after, RETRY_AFTER_MAX)
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="api_error",
                retry_after=retry_after,
            ) from err
        self.last_success = dt_util.utcnow()
        ir.async_delete_issue(
            self.hass, DOMAIN, login_page_issue_id(self.config_entry.entry_id)
        )
        _LOGGER.debug(
            "Fetched %d appointments for %d children",
            sum(len(items) for items in data.values()),
            len(data),
        )
        return data

    def _async_report_login_page_changed(self) -> None:
        """Tell the user that Magister changed its login page."""
        ir.async_create_issue(
            self.hass,
            DOMAIN,
            login_page_issue_id(self.config_entry.entry_id),
            is_fixable=False,
            severity=ir.IssueSeverity.ERROR,
            translation_key="login_page_changed",
            translation_placeholders={"entry": self.config_entry.title},
            learn_more_url="https://github.com/michielmj/ha_magister/issues",
        )
