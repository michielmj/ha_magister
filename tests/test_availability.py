"""Entities stay available on recent data through outages."""

from __future__ import annotations

from datetime import timedelta
from unittest.mock import patch

import pytest
from aioresponses import aioresponses
from freezegun.api import FrozenDateTimeFactory
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.setup import async_setup_component
from pytest_homeassistant_custom_component.common import (
    async_fire_time_changed,
    async_mock_service,
)

from custom_components.magister.api import MagisterClient
from custom_components.magister.diagnostics import async_get_config_entry_diagnostics

from .ha_helpers import FakeMagister, make_entry
from .test_sensor import SENSOR_ID, add_sensor

CALENDAR_ID = "calendar.kind_school_agenda"


@pytest.fixture(autouse=True)
async def frozen_now(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> FrozenDateTimeFactory:
    """Friday 13 November 2026, 06:00 in Amsterdam."""
    await hass.config.async_set_time_zone("Europe/Amsterdam")
    freezer.move_to("2026-11-13 05:00:00+00:00")
    return freezer


async def _tick(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, delta: timedelta
) -> None:
    freezer.tick(delta)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)


async def _setup(hass: HomeAssistant, mocked: aioresponses) -> FakeMagister:
    fake = FakeMagister(mocked)
    entry = make_entry()
    add_sensor(entry, 0)
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return fake


async def test_failed_refresh_keeps_entities_available(
    hass: HomeAssistant, mocked: aioresponses, frozen_now: FrozenDateTimeFactory
) -> None:
    """An outage keeps value and availability; after 24 h they become unavailable."""
    fake = await _setup(hass, mocked)
    before = hass.states.get(SENSOR_ID)
    assert before is not None
    assert before.state == "2026-11-13T08:15:00+00:00"

    fake.appointment_status = 503
    await _tick(hass, frozen_now, timedelta(minutes=31))
    coordinator = hass.config_entries.async_entries("magister")[
        0
    ].runtime_data.coordinator
    assert not coordinator.last_update_success
    for entity_id in (SENSOR_ID, CALENDAR_ID):
        state = hass.states.get(entity_id)
        assert state is not None
        assert state.state != "unavailable"
    after = hass.states.get(SENSOR_ID)
    assert after is not None
    assert after.state == before.state
    assert after.last_changed == before.last_changed

    await _tick(hass, frozen_now, timedelta(hours=22))
    # 22 h 31 min old: still available, and rolled over to Saturday (no lessons)
    assert hass.states.get(SENSOR_ID).state == "unknown"
    assert hass.states.get(CALENDAR_ID).state != "unavailable"

    await _tick(hass, frozen_now, timedelta(hours=2))
    assert hass.states.get(SENSOR_ID).state == "unavailable"
    assert hass.states.get(CALENDAR_ID).state == "unavailable"

    fake.appointment_status = 200
    await _tick(hass, frozen_now, timedelta(minutes=31))
    assert hass.states.get(SENSOR_ID).state != "unavailable"
    assert hass.states.get(CALENDAR_ID).state != "unavailable"


async def test_stopped_polling_expires_by_timer(
    hass: HomeAssistant, mocked: aioresponses, frozen_now: FrozenDateTimeFactory
) -> None:
    """After a reauth error nothing refreshes, but the data still ages out."""
    await _setup(hass, mocked)
    with patch.object(
        MagisterClient, "async_get_appointments", side_effect=ConfigEntryAuthFailed
    ):
        await _tick(hass, frozen_now, timedelta(minutes=31))
    assert hass.states.get(SENSOR_ID).state == "2026-11-13T08:15:00+00:00"
    await _tick(hass, frozen_now, timedelta(hours=23, minutes=40))
    assert hass.states.get(SENSOR_ID).state == "unavailable"


async def test_time_trigger_survives_a_failed_refresh(
    hass: HomeAssistant, mocked: aioresponses, frozen_now: FrozenDateTimeFactory
) -> None:
    """A time trigger on the sensor with an offset still fires after an outage."""
    fake = await _setup(hass, mocked)
    calls = async_mock_service(hass, "test", "alarm")
    assert await async_setup_component(
        hass,
        "automation",
        {
            "automation": {
                "trigger": {
                    "platform": "time",
                    "at": {"entity_id": SENSOR_ID, "offset": "-01:30:00"},
                },
                "action": {"service": "test.alarm"},
            }
        },
    )
    await hass.async_block_till_done()

    # first lesson 08:15 UTC, alarm at 06:45 UTC; outage from 05:31 UTC on
    fake.appointment_status = 503
    await _tick(hass, frozen_now, timedelta(minutes=31))
    await _tick(hass, frozen_now, timedelta(minutes=31))
    assert hass.states.get(SENSOR_ID).state == "2026-11-13T08:15:00+00:00"
    assert not calls
    await _tick(hass, frozen_now, timedelta(minutes=40))  # 06:42 UTC
    assert not calls
    await _tick(hass, frozen_now, timedelta(minutes=5))  # 06:47 UTC
    assert len(calls) == 1


async def test_diagnostics_show_the_age_of_the_data(
    hass: HomeAssistant, mocked: aioresponses, frozen_now: FrozenDateTimeFactory
) -> None:
    """Diagnostics tell how old the last good data is."""
    await _setup(hass, mocked)
    entry = hass.config_entries.async_entries("magister")[0]
    frozen_now.tick(timedelta(minutes=10))
    diagnostics = await async_get_config_entry_diagnostics(hass, entry)
    assert diagnostics["coordinator"]["last_success_age_seconds"] == 600


async def test_outage_spanning_midnight_shows_next_days_first_lesson(
    hass: HomeAssistant, mocked: aioresponses, frozen_now: FrozenDateTimeFactory
) -> None:
    """Cached data answers for the new day after midnight, still available."""
    frozen_now.move_to("2026-11-12 05:00:00+00:00")  # Thursday 06:00 Amsterdam
    fake = await _setup(hass, mocked)
    assert hass.states.get(SENSOR_ID).state != "unavailable"

    fake.appointment_status = 503
    for _ in range(37):  # to Friday 00:30 Amsterdam (Thu 23:30 UTC)
        await _tick(hass, frozen_now, timedelta(minutes=30))
    state = hass.states.get(SENSOR_ID)
    assert state is not None
    assert state.state == "2026-11-13T08:15:00+00:00"
    assert state.attributes["date"] == "2026-11-13"


async def test_expiry_timer_reschedules_while_available(
    hass: HomeAssistant, mocked: aioresponses, frozen_now: FrozenDateTimeFactory
) -> None:
    """If the data is still fresh when the timer fires, a new timer is set."""
    await _setup(hass, mocked)
    entity = hass.data["sensor"].get_entity(SENSOR_ID)
    assert entity is not None
    entity._unsub_expiry = None
    entity._handle_expiry(frozen_now())
    assert entity._unsub_expiry is not None
    entity._cancel_expiry()
