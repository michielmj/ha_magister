"""Tests for the Magister integration setup."""

from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.magister import async_setup_entry, async_unload_entry
from custom_components.magister.const import DOMAIN


async def test_async_setup(hass: HomeAssistant) -> None:
    """The integration can be set up from YAML-less config."""
    assert await async_setup_component(hass, DOMAIN, {})


async def test_setup_and_unload_entry(hass: HomeAssistant) -> None:
    """The entry setup and unload stubs return True."""
    entry = MockConfigEntry(domain=DOMAIN)
    entry.add_to_hass(hass)

    assert await async_setup_entry(hass, entry)
    assert await async_unload_entry(hass, entry)
