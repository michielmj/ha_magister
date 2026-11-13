"""Calendar entity tests."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

import pytest
from aioresponses import aioresponses
from freezegun.api import FrozenDateTimeFactory
from homeassistant.components.calendar import DOMAIN as CALENDAR_DOMAIN
from homeassistant.components.calendar import CalendarEvent
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import async_fire_time_changed

from custom_components.magister.api import Appointment
from custom_components.magister.calendar import to_calendar_event

from .ha_helpers import CHILD_ID, NOW, FakeMagister, make_entry

ENTITY_ID = "calendar.kind_school_agenda"


@pytest.fixture(autouse=True)
def frozen_now(freezer: FrozenDateTimeFactory) -> FrozenDateTimeFactory:
    """Freeze time on Friday 13 November 2026, 09:30 UTC (10:30 in Amsterdam)."""
    freezer.move_to(NOW)
    return freezer


async def _setup(
    hass: HomeAssistant, mocked: aioresponses, school: str = "school_a"
) -> FakeMagister:
    fake = FakeMagister(mocked, school)
    entry = make_entry()
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return fake


async def _events(hass: HomeAssistant, start: str, end: str) -> list[dict[str, Any]]:
    response = await hass.services.async_call(
        CALENDAR_DOMAIN,
        "get_events",
        {"entity_id": ENTITY_ID, "start_date_time": start, "end_date_time": end},
        blocking=True,
        return_response=True,
    )
    events: list[dict[str, Any]] = response[ENTITY_ID]["events"]
    return events


async def test_device_and_entity_registry(
    hass: HomeAssistant, mocked: aioresponses
) -> None:
    """One device per child, one translated calendar entity."""
    await _setup(hass, mocked)
    entity = er.async_get(hass).async_get(ENTITY_ID)
    assert entity is not None
    assert entity.unique_id == f"school.magister.net:{CHILD_ID}"
    assert entity.translation_key == "agenda"
    assert entity.has_entity_name

    device = dr.async_get(hass).async_get(entity.device_id)
    assert device is not None
    assert device.name == "Kind (school)"
    assert device.manufacturer == "Magister"
    assert device.entry_type is dr.DeviceEntryType.SERVICE
    assert device.identifiers == {("magister", f"school.magister.net:{CHILD_ID}")}
    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.attributes["friendly_name"] == "Kind (school) Agenda"


async def test_current_event(hass: HomeAssistant, mocked: aioresponses) -> None:
    """09:30 UTC falls in the 09:00-09:45 UTC lesson."""
    await _setup(hass, mocked)
    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.state == "on"
    assert state.attributes["message"] == "scheikunde"
    assert state.attributes["all_day"] is False
    assert state.attributes["location"] == "017"
    assert state.attributes["description"].startswith("Lesuur 3\n")
    # The API sends UTC; HA shows its own time zone.
    start = dt_util.as_local(datetime(2026, 11, 13, 9, 0, tzinfo=dt_util.UTC))
    assert state.attributes["start_time"] == start.strftime("%Y-%m-%d %H:%M:%S")


async def test_next_event_between_lessons(
    hass: HomeAssistant, mocked: aioresponses, frozen_now: FrozenDateTimeFactory
) -> None:
    """Between two lessons the calendar is off and shows the next one."""
    await _setup(hass, mocked)
    frozen_now.move_to("2026-11-13 09:50:00+00:00")
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.state == "off"
    assert state.attributes["message"] == "Engelse taal"


async def test_no_event_after_the_window(
    hass: HomeAssistant, mocked: aioresponses, frozen_now: FrozenDateTimeFactory
) -> None:
    """When everything is in the past there is no current or next event."""
    await _setup(hass, mocked)
    frozen_now.move_to("2026-12-31 12:00:00+00:00")
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.state == "off"
    assert "message" not in state.attributes


async def test_get_events_overlap(hass: HomeAssistant, mocked: aioresponses) -> None:
    """Events overlapping the range are returned, from cached data only."""
    fake = await _setup(hass, mocked)
    day = await _events(hass, "2026-11-13T00:00:00+00:00", "2026-11-14T00:00:00+00:00")
    assert [e["summary"] for e in day] == [
        "[Huiswerk] Nederlandse taal",
        "scheikunde",
        "Engelse taal",
        "[Huiswerk] geschiedenis",
        "lichamelijke opvoeding",
        "lichamelijke opvoeding",
    ]
    # touching ranges do not overlap: 09:45 is the end of one and 10:05 the
    # start of the next lesson
    assert not await _events(
        hass, "2026-11-13T09:45:00+00:00", "2026-11-13T10:05:00+00:00"
    )
    one = await _events(hass, "2026-11-13T09:44:00+00:00", "2026-11-13T09:46:00+00:00")
    assert [e["summary"] for e in one] == ["scheikunde"]
    # a range outside the fetched window is empty and costs no API call
    calls = len(fake.appointment_requests)
    assert not await _events(
        hass, "2027-03-01T00:00:00+00:00", "2027-03-02T00:00:00+00:00"
    )
    assert len(fake.appointment_requests) == calls


async def test_cancelled_lesson_with_homework(
    hass: HomeAssistant, mocked: aioresponses
) -> None:
    """Cancelled lessons stay in the calendar with their prefixes."""
    await _setup(hass, mocked)
    events = await _events(
        hass, "2026-11-09T10:00:00+00:00", "2026-11-09T12:00:00+00:00"
    )
    cancelled = next(e for e in events if e["summary"].startswith("[Vervallen]"))
    assert cancelled["summary"] == "[Vervallen] [Huiswerk] scheikunde"
    assert cancelled["start"].startswith("2026-11-09T")
    assert "Vervallen" in cancelled["description"]
    assert "Maken paragraaf 2.1" in cancelled["description"]


async def test_school_b_titles_and_se_items(
    hass: HomeAssistant, mocked: aioresponses
) -> None:
    """School B has no Vakken: titles come from Omschrijving."""
    await _setup(hass, mocked, "school_b")
    events = await _events(
        hass, "2026-11-02T00:00:00+00:00", "2026-12-01T00:00:00+00:00"
    )
    summaries = {e["summary"] for e in events}
    assert "wisB" in summaries
    assert "SE NAT" in summaries
    assert "[Vervallen] [Huiswerk] biol" in summaries
    assert "Schoolfotograaf" in summaries


async def test_all_day_event(hass: HomeAssistant, mocked: aioresponses) -> None:
    """An all-day item (synthetic) is a date-only event with an exclusive end."""
    fake = FakeMagister(mocked)
    fake.appointments[CHILD_ID].append(
        {
            "Id": 999,
            "Start": "2026-11-12T23:00:00.0000000Z",
            "Einde": "2026-11-13T23:00:00.0000000Z",
            "DuurtHeleDag": True,
            "Omschrijving": "Studiedag",
            "Status": 1,
            "Type": 1,
            "InfoType": 0,
            "Vakken": [],
        }
    )
    entry = make_entry()
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    events = await _events(
        hass, "2026-11-13T00:00:00+00:00", "2026-11-14T00:00:00+00:00"
    )
    study_day = next(e for e in events if e["summary"] == "Studiedag")
    assert study_day["start"] == "2026-11-13"
    assert study_day["end"] == "2026-11-14"
    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.attributes["message"] == "Studiedag"
    assert state.attributes["all_day"] is True


async def test_calendar_follows_coordinator_updates(
    hass: HomeAssistant, mocked: aioresponses, frozen_now: FrozenDateTimeFactory
) -> None:
    """New data from the next refresh shows up in the calendar."""
    fake = await _setup(hass, mocked)
    fake.appointments[CHILD_ID] = [
        item for item in fake.appointments[CHILD_ID] if item["Id"] != 100059
    ]
    frozen_now.tick(timedelta(minutes=31))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    day = await _events(hass, "2026-11-13T00:00:00+00:00", "2026-11-14T00:00:00+00:00")
    assert "scheikunde" not in [e["summary"] for e in day]


def test_to_calendar_event_omits_empty_fields() -> None:
    """Empty description and location become None for Home Assistant."""
    appointment = Appointment.from_json(
        {
            "Id": 5,
            "Start": "2026-11-13T09:00:00.0000000Z",
            "Einde": "2026-11-13T10:00:00.0000000Z",
        }
    )
    event = to_calendar_event(appointment, "school.magister.net")
    assert isinstance(event, CalendarEvent)
    assert event.summary == "Afspraak"
    assert event.description is None
    assert event.location is None
    assert event.uid == "magister-5@school.magister.net"
