"""Homework progress sensors: weighted average completion per period and child."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import timedelta
from functools import partial
from typing import Any

from homeassistant.components.sensor import SensorEntity, SensorStateClass
from homeassistant.const import PERCENTAGE
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import issue_registry as ir
from homeassistant.util import dt as dt_util

from .api.homework import PeriodSummary, next_week_fits
from .api.mapping import LOCAL_TZ
from .const import DOMAIN
from .coordinator import MagisterConfigEntry, MagisterCoordinator
from .entity import MagisterMidnightEntity
from .homework import HomeworkManager


def next_week_issue_id(entry_id: str) -> str:
    """Issue id of the "next week does not fit the window" repair for an entry."""
    return f"homework_next_week_outside_window_{entry_id}"


@callback
def async_sync_next_week_issue(hass: HomeAssistant, entry: MagisterConfigEntry) -> None:
    """Raise a repair while next week lies outside the fetch window."""
    issue_id = next_week_issue_id(entry.entry_id)
    entry.async_on_unload(partial(ir.async_delete_issue, hass, DOMAIN, issue_id))
    weeks_ahead = entry.runtime_data.coordinator.weeks_ahead
    if next_week_fits(weeks_ahead):
        ir.async_delete_issue(hass, DOMAIN, issue_id)
        return
    ir.async_create_issue(
        hass,
        DOMAIN,
        issue_id,
        is_fixable=False,
        severity=ir.IssueSeverity.WARNING,
        translation_key="homework_next_week_outside_window",
        translation_placeholders={
            "entry": entry.title,
            "weeks_ahead": str(weeks_ahead),
        },
    )


class MagisterHomeworkSensor(MagisterMidnightEntity, SensorEntity):
    """Weighted homework progress of a child for tomorrow, this week or next week."""

    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_suggested_display_precision = 0

    def __init__(
        self,
        coordinator: MagisterCoordinator,
        manager: HomeworkManager,
        host: str,
        child_id: int,
        short_name: str,
        period: str,
    ) -> None:
        """Create the sensor."""
        super().__init__(coordinator, host, child_id, short_name)
        self._manager = manager
        self._period = period
        self._attr_unique_id = f"{host}:{child_id}:homework:{period}"
        self._attr_translation_key = f"homework_{period}"
        self._summary = PeriodSummary(100.0, 0, 0, 0, 0)
        self._attributes: dict[str, Any] = {}
        self._recompute()

    @property
    def available(self) -> bool:
        """Also unavailable while next week does not fit the fetch window."""
        if not self._manager.period_fits(self._period):
            return False
        return super().available

    def _recompute(self) -> None:
        today = dt_util.now(LOCAL_TZ).date()
        data = self._manager.period(self._child_id, self._period, today)
        self._summary = data.summary
        self._attributes = {
            "items": self._summary.items,
            "completed": self._summary.completed,
            "open": self._summary.open,
            "tests": self._summary.tests,
            "period_start": data.first.isoformat(),
            "period_end": (data.end - timedelta(days=1)).isoformat(),
            "weights": data.effective_weights,
        }

    async def async_added_to_hass(self) -> None:
        """Follow progress and weight changes and the day rolling over."""
        await super().async_added_to_hass()
        self.async_on_remove(self._manager.async_add_listener(self._handle_change))
        self._start_midnight()

    @callback
    def _on_new_day(self) -> None:
        self._handle_change()

    @callback
    def _handle_change(self) -> None:
        self._recompute()
        self.async_write_ha_state()

    @callback
    def _handle_coordinator_update(self) -> None:
        self._recompute()
        super()._handle_coordinator_update()

    @property
    def native_value(self) -> float:
        """Weighted average progress in percent (100 when nothing is due)."""
        return self._summary.value

    @property
    def extra_state_attributes(self) -> Mapping[str, Any]:
        """Item counts, the period and the weights in use."""
        return self._attributes
