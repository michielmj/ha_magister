"""Calendar platform for Magister: one calendar per tenant-child."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime

from homeassistant.components.calendar import CalendarEntity, CalendarEvent
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util

from .api import Appointment, map_appointment
from .api.mapping import CANCELLED_STATUSES
from .const import CHILD_ID, CHILD_SHORT_NAME, CONF_CHILDREN, CONF_HOST
from .coordinator import MagisterConfigEntry, MagisterCoordinator
from .entity import MagisterEntity
from .homework import HomeworkManager

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
            coordinator,
            entry.runtime_data.homework,
            host,
            int(child[CHILD_ID]),
            str(child[CHILD_SHORT_NAME]),
        )
        for child in entry.data[CONF_CHILDREN]
    )


def to_calendar_event(
    appointment: Appointment, host: str, manual_labels: Sequence[str] = ()
) -> CalendarEvent:
    """Convert an appointment to a Home Assistant calendar event."""
    fields = map_appointment(appointment, host, manual_labels)
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
        manager: HomeworkManager,
        host: str,
        child_id: int,
        short_name: str,
    ) -> None:
        """Create the calendar."""
        super().__init__(coordinator, host, child_id, short_name)
        self._manager = manager
        self._events: list[CalendarEvent] = []
        self._current_candidates: list[CalendarEvent] = []
        self._build_events()

    def _build_events(self) -> None:
        appointments = (self.coordinator.data or {}).get(self._child_id, [])
        self._events = [
            to_calendar_event(
                item,
                self._host,
                self._manager.manual_label_names(self._child_id, item.id),
            )
            for item in appointments
        ]
        # Cancelled lessons stay in the calendar but are not "current" or "next".
        self._current_candidates = [
            event
            for event, item in zip(self._events, appointments, strict=True)
            if item.status not in CANCELLED_STATUSES
        ]

    async def async_added_to_hass(self) -> None:
        """Follow label changes (the titles carry the manual labels)."""
        await super().async_added_to_hass()
        self.async_on_remove(
            self._manager.async_add_label_listener(self._handle_labels)
        )

    @callback
    def _handle_labels(self) -> None:
        self._build_events()
        self.async_write_ha_state()

    @callback
    def _handle_coordinator_update(self) -> None:
        self._build_events()
        super()._handle_coordinator_update()

    @property
    def event(self) -> CalendarEvent | None:
        """Return the current event, else the next one."""
        now = dt_util.now()
        upcoming = (e for e in self._current_candidates if e.end_datetime_local > now)
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
