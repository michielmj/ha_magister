"""Tests for the Magister integration setup."""

from unittest.mock import AsyncMock, patch

from homeassistant.config_entries import ConfigEntryState, ConfigFlow
from homeassistant.core import HomeAssistant
from homeassistant.loader import Integration
from homeassistant.setup import async_setup_component
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    mock_config_flow,
)

from custom_components.magister.const import DOMAIN


async def test_async_setup(hass: HomeAssistant) -> None:
    """The integration can be set up from YAML-less config."""
    assert await async_setup_component(hass, DOMAIN, {})


class _PlaceholderFlow(ConfigFlow):
    """Placeholder config flow until M2 adds the real one."""


async def test_setup_and_unload_entry(hass: HomeAssistant) -> None:
    """A config entry can be set up and unloaded."""
    entry = MockConfigEntry(domain=DOMAIN, data={})
    entry.add_to_hass(hass)

    # Home Assistant needs a registered config flow handler to set up an entry.
    # The real flow is only added in M2, so register a placeholder for now
    # (and skip importing the not-yet-existing config_flow module).
    with (
        mock_config_flow(DOMAIN, _PlaceholderFlow),
        patch.object(Integration, "async_get_platform", AsyncMock()),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.LOADED

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.NOT_LOADED
