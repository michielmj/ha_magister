"""Base entity for Magister."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MANUFACTURER, host_prefix
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
        self._child_id = child_id
        key = child_key(host, child_id)
        self._attr_unique_id = key
        self._attr_device_info = child_device_info(host, child_id, short_name)
