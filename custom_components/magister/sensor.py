"""Sensor platform for Magister: first-appointment sensors (config sub-entries)."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date, datetime, time, timedelta
from typing import Any

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.config_entries import ConfigSubentry
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.event import async_track_point_in_time
from homeassistant.util import dt as dt_util

from .api import (
    FirstAppointment,
    build_summary,
    find_first_appointment,
    lesson_hours,
)
from .api.mapping import LOCAL_TZ
from .const import (
    CHILD_ID,
    CHILD_SHORT_NAME,
    CONF_CHILD_ID,
    CONF_CHILDREN,
    CONF_EXCLUDED,
    CONF_HOST,
    CONF_OFFSET,
    DOMAIN,
    SUBENTRY_FIRST,
    max_offset,
)
from .coordinator import MagisterConfigEntry, MagisterCoordinator
from .entity import MagisterEntity, child_key

PARALLEL_UPDATES = 0


def offset_issue_id(subentry_id: str) -> str:
    """Issue id of the "offset outside the window" repair for a sensor."""
    return f"offset_outside_window_{subentry_id}"


async def async_setup_entry(
    hass: HomeAssistant,
    entry: MagisterConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Add a sensor for each first-appointment sub-entry."""
    coordinator = entry.runtime_data.coordinator
    host: str = entry.data[CONF_HOST]
    device_registry = dr.async_get(hass)
    children = {int(child[CHILD_ID]): child for child in entry.data[CONF_CHILDREN]}
    for subentry in entry.subentries.values():
        child = children.get(int(subentry.data.get(CONF_CHILD_ID, -1)))
        if subentry.subentry_type != SUBENTRY_FIRST or child is None:
            continue
        # The child's device belongs to the main entry (registered in setup); the
        # sensor only points to it, so HA removes the sensor with its sub-entry.
        device = device_registry.async_get_device_by_identifier(
            (DOMAIN, child_key(host, int(child[CHILD_ID]))), entry.entry_id
        )
        if device is None:  # pragma: no cover - registered before the platforms
            continue
        async_add_entities(
            [
                MagisterFirstAppointmentSensor(
                    coordinator, host, str(child[CHILD_SHORT_NAME]), subentry, device
                )
            ],
            config_subentry_id=subentry.subentry_id,
        )


class MagisterFirstAppointmentSensor(MagisterEntity, SensorEntity):
    """Start of the first appointment of the day ``offset`` days from today."""

    _attr_device_class = SensorDeviceClass.TIMESTAMP

    def __init__(
        self,
        coordinator: MagisterCoordinator,
        host: str,
        short_name: str,
        subentry: ConfigSubentry,
        device: dr.DeviceEntry,
    ) -> None:
        """Create the sensor (on the existing device of the child)."""
        child_id = int(subentry.data[CONF_CHILD_ID])
        super().__init__(coordinator, host, child_id, short_name)
        self._attr_device_info = None
        self.device_entry = device
        self._subentry_id = subentry.subentry_id
        self._offset = int(subentry.data[CONF_OFFSET])
        self._excluded: list[str] = [str(s) for s in subentry.data[CONF_EXCLUDED]]
        self._attr_unique_id = f"{host}:{child_id}:first:{subentry.subentry_id}"
        self._attr_name = subentry.title
        self._unsub_midnight: CALLBACK_TYPE | None = None
        self._day: date | None = None
        self._result: FirstAppointment | None = None
        self._fits = True
        self._recompute()

    @property
    def _issue_id(self) -> str:
        return offset_issue_id(self._subentry_id)

    def _recompute(self) -> None:
        """Find the first appointment again from the coordinator data."""
        self._fits = self._offset <= max_offset(self.coordinator.weeks_ahead)
        self._day = dt_util.now(LOCAL_TZ).date() + timedelta(days=self._offset)
        appointments = (self.coordinator.data or {}).get(self._child_id, [])
        if self._fits:
            self._result = find_first_appointment(
                appointments, self._day, self._excluded, LOCAL_TZ
            )
        else:
            self._result = None
        if self.hass is not None:
            self._sync_issue()

    def _sync_issue(self) -> None:
        """Create or clear the repair issue for an offset outside the window."""
        if self._fits:
            ir.async_delete_issue(self.hass, DOMAIN, self._issue_id)
            return
        ir.async_create_issue(
            self.hass,
            DOMAIN,
            self._issue_id,
            is_fixable=False,
            severity=ir.IssueSeverity.WARNING,
            translation_key="offset_outside_window",
            translation_placeholders={
                "name": str(self._attr_name),
                "offset": str(self._offset),
                "weeks_ahead": str(self.coordinator.weeks_ahead),
                "max_offset": str(max_offset(self.coordinator.weeks_ahead)),
            },
        )

    async def async_added_to_hass(self) -> None:
        """Recompute when the day rolls over, without any API call."""
        await super().async_added_to_hass()
        self._sync_issue()
        self._schedule_midnight()
        self.async_on_remove(self._cancel_midnight)
        self.async_on_remove(self._clear_issue)

    @callback
    def _clear_issue(self) -> None:
        ir.async_delete_issue(self.hass, DOMAIN, self._issue_id)

    @callback
    def _schedule_midnight(self) -> None:
        """Wake up at the next midnight in Europe/Amsterdam (the school's day)."""
        tomorrow = dt_util.now(LOCAL_TZ).date() + timedelta(days=1)
        self._unsub_midnight = async_track_point_in_time(
            self.hass,
            self._handle_midnight,
            datetime.combine(tomorrow, time.min, LOCAL_TZ),
        )

    @callback
    def _cancel_midnight(self) -> None:
        if self._unsub_midnight is not None:
            self._unsub_midnight()
            self._unsub_midnight = None

    @callback
    def _handle_midnight(self, _now: datetime) -> None:
        self._recompute()
        self.async_write_ha_state()
        self._schedule_midnight()

    @callback
    def _handle_coordinator_update(self) -> None:
        self._recompute()
        super()._handle_coordinator_update()

    @property
    def native_value(self) -> datetime | None:
        """Start of the first qualifying appointment, ``None`` when there is none."""
        if self._result is None or self._result.appointment is None:
            return None
        return self._result.appointment.start

    @property
    def extra_state_attributes(self) -> Mapping[str, Any]:
        """Details of the appointment and how many items were skipped."""
        attributes: dict[str, Any] = {
            "date": self._day.isoformat() if self._day else None,
            "skipped": self._result.skipped if self._result else 0,
        }
        item = self._result.appointment if self._result else None
        if item is not None:
            attributes |= {
                "end": dt_util.as_local(item.end).isoformat(),
                "subject": item.subject,
                "summary": build_summary(item),
                "location": item.location or None,
                "lesson_hours": lesson_hours(item),
            }
        return attributes
