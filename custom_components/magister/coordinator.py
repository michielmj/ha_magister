"""Data update coordinator for Magister."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, time, timedelta
from typing import TYPE_CHECKING

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .api import (
    Appointment,
    MagisterApiError,
    MagisterAuth,
    MagisterAuthError,
    MagisterClient,
    MagisterConnectionError,
)
from .api.mapping import LOCAL_TZ
from .const import (
    CHILD_ID,
    CONF_CHILDREN,
    DOMAIN,
    UPDATE_INTERVAL,
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


type MagisterConfigEntry = ConfigEntry[MagisterRuntimeData]


def fetch_window(
    now: datetime,
    weeks_back: int = WEEKS_BACK,
    weeks_ahead: int = WEEKS_AHEAD,
) -> tuple[datetime, datetime]:
    """Return the window to fetch, in Europe/Amsterdam.

    From Monday 00:00 of ``weeks_back`` weeks ago up to Monday 00:00 of the week
    ``weeks_ahead`` weeks after the current one.
    """
    today = now.astimezone(LOCAL_TZ).date()
    monday = today - timedelta(days=today.weekday())
    start = datetime.combine(monday - timedelta(weeks=weeks_back), time.min, LOCAL_TZ)
    end = datetime.combine(monday + timedelta(weeks=weeks_ahead), time.min, LOCAL_TZ)
    return start, end


class MagisterCoordinator(DataUpdateCoordinator[MagisterData]):
    """Fetches the agenda of all selected children of one config entry."""

    config_entry: MagisterConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        entry: MagisterConfigEntry,
        client: MagisterClient,
    ) -> None:
        """Create the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=f"{DOMAIN} {entry.title}",
            update_interval=UPDATE_INTERVAL,
        )
        self._client = client
        self.child_ids: list[int] = [
            int(child[CHILD_ID]) for child in entry.data[CONF_CHILDREN]
        ]

    async def _async_update_data(self) -> MagisterData:
        """Fetch the window for each child, one after the other."""
        start, end = fetch_window(dt_util.now())
        data: MagisterData = {}
        try:
            for child_id in self.child_ids:
                appointments = await self._client.async_get_appointments(
                    child_id, start, end, status=None
                )
                data[child_id] = sorted(appointments, key=lambda a: (a.start, a.id))
        except MagisterAuthError as err:
            raise ConfigEntryAuthFailed(
                translation_domain=DOMAIN, translation_key="auth_failed"
            ) from err
        except MagisterConnectionError as err:
            raise UpdateFailed(
                translation_domain=DOMAIN, translation_key="connection_failed"
            ) from err
        except MagisterApiError as err:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="api_error",
                retry_after=err.retry_after,
            ) from err
        _LOGGER.debug(
            "Fetched %d appointments for %d children",
            sum(len(items) for items in data.values()),
            len(data),
        )
        return data
