"""Coordinator tests."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any
from unittest.mock import patch

import pytest
from aioresponses import aioresponses
from freezegun.api import FrozenDateTimeFactory
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import UpdateFailed
from pytest_homeassistant_custom_component.common import async_fire_time_changed

from custom_components.magister.api import (
    MagisterApiError,
    MagisterAuthError,
    MagisterClient,
)
from custom_components.magister.api.mapping import LOCAL_TZ
from custom_components.magister.const import UPDATE_INTERVAL
from custom_components.magister.coordinator import fetch_window

from .api.helpers import PASSWORD, TOKEN
from .ha_helpers import NOW, FakeMagister, make_entry


@pytest.fixture(autouse=True)
def frozen_now(freezer: FrozenDateTimeFactory) -> FrozenDateTimeFactory:
    """Freeze time on Friday 13 November 2026."""
    freezer.move_to(NOW)
    return freezer


@pytest.mark.parametrize(
    ("now", "start", "end"),
    [
        # Friday 13 Nov 2026: Monday 2 Nov up to Monday 30 Nov
        ("2026-11-13T09:30:00+00:00", "2026-11-02T00:00", "2026-11-30T00:00"),
        # Monday itself belongs to the current week
        ("2026-11-09T00:00:00+01:00", "2026-11-02T00:00", "2026-11-30T00:00"),
        # Sunday 23:30 local time is still the same week
        ("2026-11-15T22:30:00+00:00", "2026-11-02T00:00", "2026-11-30T00:00"),
        # around the end of daylight saving time (25 Oct 2026)
        ("2026-10-27T10:00:00+00:00", "2026-10-19T00:00", "2026-11-16T00:00"),
    ],
)
def test_fetch_window(now: str, start: str, end: str) -> None:
    """The window is Monday-aligned in Europe/Amsterdam."""
    got_start, got_end = fetch_window(datetime.fromisoformat(now))
    assert got_start == datetime.fromisoformat(start).replace(tzinfo=LOCAL_TZ)
    assert got_end == datetime.fromisoformat(end).replace(tzinfo=LOCAL_TZ)


def test_fetch_window_local_week_boundary() -> None:
    """The week changes at midnight in Amsterdam, not in UTC."""
    sunday = fetch_window(datetime.fromisoformat("2026-11-15T22:30:00+00:00"))
    monday = fetch_window(datetime.fromisoformat("2026-11-15T23:30:00+00:00"))
    assert sunday[0].date().isoformat() == "2026-11-02"
    assert monday[0].date().isoformat() == "2026-11-09"


async def test_refresh_fetches_sequentially_without_status_filter(
    hass: HomeAssistant, mocked: aioresponses
) -> None:
    """Each child is fetched once, in order, for the Amsterdam window."""
    fake = FakeMagister(mocked, children=[])
    fake.appointments = {
        1: fake.appointments.get(1, []),
        2: [],
    }
    fake.appointments[1] = list(reversed(_two_items()))
    entry = make_entry(children=[(1, "Een"), (2, "Twee")])
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)

    assert [pid for pid, _ in fake.appointment_requests] == [1, 2]
    params = fake.appointment_requests[0][1]
    assert set(params) == {"van", "tot"}
    assert params["van"] == "2026-11-01T23:00:00.000Z"  # Mon 2 Nov 00:00 CET
    assert params["tot"] == "2026-11-29T23:00:00.000Z"  # Mon 30 Nov 00:00 CET
    data = entry.runtime_data.coordinator.data
    assert [a.start for a in data[1]] == sorted(a.start for a in data[1])
    assert data[2] == []


def _two_items() -> list[dict[str, Any]]:
    base = {"Omschrijving": "x", "Status": 1, "InfoType": 0, "Type": 13}
    return [
        {
            **base,
            "Id": 1,
            "Start": "2026-11-09T08:00:00.0000000Z",
            "Einde": "2026-11-09T09:00:00.0000000Z",
        },
        {
            **base,
            "Id": 2,
            "Start": "2026-11-10T08:00:00.0000000Z",
            "Einde": "2026-11-10T09:00:00.0000000Z",
        },
    ]


async def test_connection_failure_keeps_last_data(
    hass: HomeAssistant, mocked: aioresponses, frozen_now: FrozenDateTimeFactory
) -> None:
    """After an outage the coordinator fails but keeps the last good data."""
    fake = FakeMagister(mocked)
    entry = make_entry()
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    coordinator = entry.runtime_data.coordinator
    before = coordinator.data
    assert coordinator.last_update_success

    fake.appointment_status = 503
    frozen_now.tick(UPDATE_INTERVAL + timedelta(seconds=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert not coordinator.last_update_success
    assert isinstance(coordinator.last_exception, UpdateFailed)
    assert coordinator.data is before
    assert entry.state is ConfigEntryState.LOADED

    fake.appointment_status = 200
    frozen_now.tick(UPDATE_INTERVAL + timedelta(seconds=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert coordinator.last_update_success


async def test_api_error_is_update_failed(
    hass: HomeAssistant, mocked: aioresponses
) -> None:
    """A strange status (not 5xx) is an UpdateFailed too."""
    fake = FakeMagister(mocked)
    entry = make_entry()
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    coordinator = entry.runtime_data.coordinator
    fake.appointment_status = 404
    await coordinator.async_refresh()
    assert isinstance(coordinator.last_exception, UpdateFailed)
    assert coordinator.data is not None


async def test_auth_failure_during_polling(
    hass: HomeAssistant, mocked: aioresponses
) -> None:
    """A final login failure while polling raises ConfigEntryAuthFailed."""
    FakeMagister(mocked)
    entry = make_entry()
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    coordinator = entry.runtime_data.coordinator

    with patch.object(
        MagisterClient,
        "async_get_appointments",
        side_effect=MagisterAuthError("invalid_auth"),
    ):
        await coordinator.async_refresh()
    assert not coordinator.last_update_success
    assert isinstance(coordinator.last_exception, ConfigEntryAuthFailed)
    assert coordinator.data  # last good data is kept


async def test_rate_limit_sets_retry_after(
    hass: HomeAssistant, mocked: aioresponses
) -> None:
    """429 with Retry-After is passed on to the coordinator."""
    FakeMagister(mocked)
    entry = make_entry()
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    coordinator = entry.runtime_data.coordinator
    with patch.object(
        MagisterClient,
        "async_get_appointments",
        side_effect=MagisterApiError("slow down", status=429, retry_after=120),
    ):
        await coordinator.async_refresh()
    assert isinstance(coordinator.last_exception, UpdateFailed)
    assert coordinator.last_exception.retry_after == 120


async def test_no_secrets_in_coordinator_logs(
    hass: HomeAssistant,
    mocked: aioresponses,
    caplog: pytest.LogCaptureFixture,
    frozen_now: FrozenDateTimeFactory,
) -> None:
    """Setup, successful and failing refreshes never log credentials or tokens."""
    caplog.set_level(logging.DEBUG)
    fake = FakeMagister(mocked)
    entry = make_entry(totp=True)
    entry.add_to_hass(hass)
    # TOTP secret in the data, but the fake login does not ask for a code
    assert await hass.config_entries.async_setup(entry.entry_id)
    coordinator = entry.runtime_data.coordinator
    fake.appointment_status = 503
    await coordinator.async_refresh()
    fake.appointment_status = 200
    await coordinator.async_refresh()

    assert "Fetched" in caplog.text
    secrets = (PASSWORD, TOKEN, "JBSWY3DPEHPK3PXP", "0123456789abcdef0123456789abcdef")
    for secret in secrets:
        assert secret not in caplog.text
