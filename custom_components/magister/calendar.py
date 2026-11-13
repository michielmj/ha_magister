"""Calendar platform for Magister: one calendar per tenant-child."""

from __future__ import annotations

from datetime import datetime

from homeassistant.components.calendar import CalendarEntity, CalendarEvent
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util

from .api import Appointment, map_appointment
from .const import CHILD_ID, CHILD_SHORT_NAME, CONF_CHILDREN, CONF_HOST
from .coordinator import MagisterConfigEntry, MagisterCoordinator
from .entity import MagisterEntity

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: MagisterConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Add a calendar for each selected child."""
    coordinator = entry.runtime_data.coordinator
    host: str = entry.data[CONF_HOST]
    async_add_entities(
        MagisterCalendar(
            coordinator, host, int(child[CHILD_ID]), str(child[CHILD_SHORT_NAME])
        )
        for child in entry.data[CONF_CHILDREN]
    )


def to_calendar_event(appointment: Appointment, host: str) -> CalendarEvent:
    """Convert an appointment to a Home Assistant calendar event."""
    fields = map_appointment(appointment, host)
    return CalendarEvent(
        start=fields.start,
        end=fields.end,
        summary=fields.summary,
        description=fields.description or None,
        location=fields.location or None,
        uid=fields.uid,
    )


class MagisterCalendar(MagisterEntity, CalendarEntity):
    """The agenda of one child."""

    _attr_translation_key = "agenda"

    def __init__(
        self,
        coordinator: MagisterCoordinator,
        host: str,
        child_id: int,
        short_name: str,
    ) -> None:
        """Create the calendar."""
        super().__init__(coordinator, host, child_id, short_name)
        self._events: list[CalendarEvent] = []
        self._build_events()

    def _build_events(self) -> None:
        appointments = (self.coordinator.data or {}).get(self._child_id, [])
        self._events = [to_calendar_event(item, self._host) for item in appointments]

    @callback
    def _handle_coordinator_update(self) -> None:
        self._build_events()
        super()._handle_coordinator_update()

    @property
    def event(self) -> CalendarEvent | None:
        """Return the current event, else the next one."""
        now = dt_util.now()
        upcoming = (e for e in self._events if e.end_datetime_local > now)
        return next(upcoming, None)

    async def async_get_events(
        self, hass: HomeAssistant, start_date: datetime, end_date: datetime
    ) -> list[CalendarEvent]:
        """Return events that overlap the range, from the coordinator data."""
        return [
            event
            for event in self._events
            if event.start_datetime_local < end_date
            and event.end_datetime_local > start_date
        ]
