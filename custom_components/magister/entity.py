"""Base entity for Magister."""

from __future__ import annotations

from datetime import datetime

from homeassistant.core import CALLBACK_TYPE, callback
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.event import async_track_point_in_utc_time
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from .const import DATA_MAX_AGE, DOMAIN, MANUFACTURER, host_prefix
from .coordinator import MagisterCoordinator


def child_device_info(host: str, child_id: int, short_name: str) -> DeviceInfo:
    """Device info of a child (one device per school and child)."""
    return DeviceInfo(
        identifiers={(DOMAIN, child_key(host, child_id))},
        name=f"{short_name} ({host_prefix(host)})",
        manufacturer=MANUFACTURER,
        entry_type=DeviceEntryType.SERVICE,
    )


def child_key(host: str, child_id: int) -> str:
    """Stable identifier of a tenant-child combination."""
    return f"{host}:{child_id}"


class MagisterEntity(CoordinatorEntity[MagisterCoordinator]):
    """An entity that belongs to one child (and so to one device)."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: MagisterCoordinator,
        host: str,
        child_id: int,
        short_name: str,
    ) -> None:
        """Create the entity and its device info."""
        super().__init__(coordinator)
        self._host = host
        self._unsub_expiry: CALLBACK_TYPE | None = None
        self._child_id = child_id
        key = child_key(host, child_id)
        self._attr_unique_id = key
        self._attr_device_info = child_device_info(host, child_id, short_name)

    @property
    def available(self) -> bool:
        """Available while the last good data is younger than ``DATA_MAX_AGE``.

        A failed refresh does not make the entity unavailable: automations that
        depend on the state (time triggers) must not be cancelled by an outage.
        """
        last = self.coordinator.last_success
        return (
            self.coordinator.data is not None
            and last is not None
            and dt_util.utcnow() - last < DATA_MAX_AGE
        )

    async def async_added_to_hass(self) -> None:
        """Watch the age of the data."""
        await super().async_added_to_hass()
        self._schedule_expiry()
        self.async_on_remove(self._cancel_expiry)

    @callback
    def _schedule_expiry(self) -> None:
        """Write the state again when the data becomes too old."""
        self._cancel_expiry()
        last = self.coordinator.last_success
        if last is not None:
            self._unsub_expiry = async_track_point_in_utc_time(
                self.hass, self._handle_expiry, last + DATA_MAX_AGE
            )

    @callback
    def _cancel_expiry(self) -> None:
        if self._unsub_expiry is not None:
            self._unsub_expiry()
            self._unsub_expiry = None

    @callback
    def _handle_expiry(self, _now: datetime) -> None:
        self._unsub_expiry = None
        self.async_write_ha_state()

    @callback
    def _handle_coordinator_update(self) -> None:
        self._schedule_expiry()
        super()._handle_coordinator_update()
