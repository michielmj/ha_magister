"""First-appointment sensor tests."""

from __future__ import annotations

import copy
from collections.abc import Iterable
from datetime import timedelta
from typing import Any

import pytest
from aioresponses import aioresponses
from freezegun.api import FrozenDateTimeFactory
from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.config_entries import ConfigSubentry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers import issue_registry as ir
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_fire_time_changed,
)

from custom_components.magister.const import (
    CONF_CHILD_ID,
    CONF_EXCLUDED,
    CONF_INTERVAL,
    CONF_OFFSET,
    CONF_WEEKS_AHEAD,
    CONF_WEEKS_BACK,
    DOMAIN,
    SUBENTRY_FIRST,
)

from .ha_helpers import CHILD_ID, NOW, FakeMagister, make_entry

SENSOR_ID = "sensor.kind_school_first"


@pytest.fixture(autouse=True)
async def frozen_now(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> FrozenDateTimeFactory:
    """Friday 13 November 2026, 10:30 in Amsterdam (HA's time zone as well)."""
    await hass.config.async_set_time_zone("Europe/Amsterdam")
    freezer.move_to(NOW)
    return freezer


def add_sensor(
    entry: MockConfigEntry,
    offset: int,
    excluded: Iterable[str] = (),
    *,
    subentry_id: str = "sub1",
    title: str = "First",
    child_id: int = CHILD_ID,
) -> None:
    """Add a first-appointment sub-entry to a mock entry."""
    entry.subentries = {
        **entry.subentries,
        subentry_id: ConfigSubentry(
            data={
                CONF_CHILD_ID: child_id,
                CONF_OFFSET: offset,
                CONF_EXCLUDED: list(excluded),
            },
            subentry_type=SUBENTRY_FIRST,
            title=title,
            unique_id=None,
            subentry_id=subentry_id,
        ),
    }


async def setup_sensor(
    hass: HomeAssistant,
    mocked: aioresponses,
    offset: int,
    excluded: Iterable[str] = (),
    *,
    options: dict[str, Any] | None = None,
) -> tuple[FakeMagister, MockConfigEntry]:
    """Set up an entry with one sensor and return the fake and the entry."""
    fake = FakeMagister(mocked)
    entry = make_entry()
    add_sensor(entry, offset, excluded)
    if options is not None:
        entry = MockConfigEntry(
            domain=DOMAIN,
            title=entry.title,
            unique_id=entry.unique_id,
            data=entry.data,
            options=options,
            subentries_data=[
                {
                    "data": dict(sub.data),
                    "subentry_type": sub.subentry_type,
                    "title": sub.title,
                    "unique_id": None,
                    "subentry_id": sub.subentry_id,
                }
                for sub in entry.subentries.values()
            ],
        )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return fake, entry


async def test_first_appointment_today(
    hass: HomeAssistant, mocked: aioresponses
) -> None:
    """Offset 0: the first timed lesson of today, with details."""
    fake, _entry = await setup_sensor(hass, mocked, 0)
    state = hass.states.get(SENSOR_ID)
    assert state is not None
    assert state.state == "2026-11-13T08:15:00+00:00"
    assert state.attributes["device_class"] == SensorDeviceClass.TIMESTAMP
    assert state.attributes["date"] == "2026-11-13"
    assert state.attributes["subject"] == "Nederlandse taal"
    assert state.attributes["summary"] == "[Huiswerk] Nederlandse taal"
    assert state.attributes["end"] == "2026-11-13T10:00:00+01:00"
    assert state.attributes["lesson_hours"] == "Lesuur 2"
    assert state.attributes["skipped"] == 0
    # the sensor uses the coordinator data: one fetch only, no status filter
    assert len(fake.appointment_requests) == 1

    registry = er.async_get(hass)
    entity = registry.async_get(SENSOR_ID)
    assert entity is not None
    assert entity.unique_id == "school.magister.net:1001:first:sub1"
    device = dr.async_get(hass).async_get(entity.device_id)
    assert device is not None
    assert device.name == "Kind (school)"
    # the same device as the calendar
    calendar = registry.async_get("calendar.kind_school_agenda")
    assert calendar is not None
    assert calendar.device_id == entity.device_id


async def test_weekend_is_unknown(hass: HomeAssistant, mocked: aioresponses) -> None:
    """Friday + 1 = Saturday: nothing planned, so the state is unknown."""
    await setup_sensor(hass, mocked, 1)
    state = hass.states.get(SENSOR_ID)
    assert state is not None
    assert state.state == "unknown"
    assert state.attributes["date"] == "2026-11-14"
    assert state.attributes["skipped"] == 0
    assert "subject" not in state.attributes


async def test_exclusion_picks_next_item(
    hass: HomeAssistant, mocked: aioresponses
) -> None:
    """Thursday 19 Nov starts with Franse taal; excluding it gives the next one."""
    await setup_sensor(hass, mocked, 6)
    state = hass.states.get(SENSOR_ID)
    assert state is not None
    assert state.state == "2026-11-19T07:30:00+00:00"
    assert state.attributes["subject"] == "Franse taal"


async def test_exclusion_is_exact_and_case_insensitive(
    hass: HomeAssistant, mocked: aioresponses
) -> None:
    """ "franse TAAL" matches, a part of a name ("taal") does not."""
    await setup_sensor(hass, mocked, 6, ["franse TAAL"])
    state = hass.states.get(SENSOR_ID)
    assert state is not None
    assert state.state == "2026-11-19T08:15:00+00:00"
    assert state.attributes["subject"] == "Nederlandse taal"
    assert state.attributes["skipped"] == 1


async def test_partial_exclusion_does_not_match(
    hass: HomeAssistant, mocked: aioresponses
) -> None:
    """Matching is exact: excluding "taal" skips nothing."""
    await setup_sensor(hass, mocked, 6, ["taal"])
    state = hass.states.get(SENSOR_ID)
    assert state is not None
    assert state.attributes["subject"] == "Franse taal"
    assert state.attributes["skipped"] == 0


async def test_cancelled_first_lesson_is_skipped(
    hass: HomeAssistant, mocked: aioresponses
) -> None:
    """A cancelled first lesson (Status 5) does not count."""
    fake = FakeMagister(mocked)
    first = next(
        item
        for item in fake.appointments[CHILD_ID]
        if item["Start"].startswith("2026-11-17T07:30")
    )
    first["Status"] = 5
    entry = make_entry()
    add_sensor(entry, 4)
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    state = hass.states.get(SENSOR_ID)
    assert state is not None
    assert state.state == "2026-11-17T08:15:00+00:00"
    assert state.attributes["subject"] == "aardrijkskunde"
    assert state.attributes["skipped"] == 1


async def test_everything_cancelled_is_unknown(
    hass: HomeAssistant, mocked: aioresponses
) -> None:
    """A day with only cancelled or excluded items has no first appointment."""
    fake = FakeMagister(mocked)
    for item in fake.appointments[CHILD_ID]:
        if item["Start"].startswith("2026-11-13"):
            item["Status"] = 4
    entry = make_entry()
    add_sensor(entry, 0)
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    state = hass.states.get(SENSOR_ID)
    assert state is not None
    assert state.state == "unknown"
    assert state.attributes["skipped"] == 6


async def test_all_day_items_do_not_count(
    hass: HomeAssistant, mocked: aioresponses
) -> None:
    """An all-day item (holiday, school event) is not an appointment."""
    fake = FakeMagister(mocked)
    template = copy.deepcopy(fake.appointments[CHILD_ID][0])
    template.update(
        {
            "Id": 999001,
            "Start": "2026-11-13T00:00:00.0000000Z",
            "Einde": "2026-11-14T00:00:00.0000000Z",
            "DuurtHeleDag": True,
        }
    )
    fake.appointments[CHILD_ID].append(template)
    entry = make_entry()
    add_sensor(entry, 0)
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    state = hass.states.get(SENSOR_ID)
    assert state is not None
    assert state.attributes["subject"] == "Nederlandse taal"
    assert state.attributes["skipped"] == 0


async def test_updates_with_coordinator_refresh(
    hass: HomeAssistant, mocked: aioresponses, frozen_now: FrozenDateTimeFactory
) -> None:
    """A new coordinator refresh recomputes the value."""
    fake, _ = await setup_sensor(hass, mocked, 0)
    for item in fake.appointments[CHILD_ID]:
        if item["Start"].startswith("2026-11-13T08:15"):
            item["Status"] = 5
    frozen_now.tick(timedelta(minutes=31))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    state = hass.states.get(SENSOR_ID)
    assert state is not None
    assert state.attributes["subject"] == "scheikunde"
    assert state.attributes["skipped"] == 1


async def test_midnight_rolls_the_day_over_without_api_calls(
    hass: HomeAssistant, mocked: aioresponses, frozen_now: FrozenDateTimeFactory
) -> None:
    """At local midnight "today" moves on; no request is made for it."""
    # Thursday 12 Nov 2026, 23:59:30 in Amsterdam (22:59:30 UTC)
    frozen_now.move_to("2026-11-12 22:59:30+00:00")
    fake, _ = await setup_sensor(hass, mocked, 0)
    state = hass.states.get(SENSOR_ID)
    assert state is not None
    assert state.attributes["date"] == "2026-11-12"
    assert state.state == "2026-11-12T07:30:00+00:00"
    requests = len(fake.appointment_requests)

    frozen_now.tick(timedelta(seconds=45))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    state = hass.states.get(SENSOR_ID)
    assert state is not None
    assert state.attributes["date"] == "2026-11-13"
    assert state.state == "2026-11-13T08:15:00+00:00"
    assert len(fake.appointment_requests) == requests


async def test_dst_day(
    hass: HomeAssistant, mocked: aioresponses, frozen_now: FrozenDateTimeFactory
) -> None:
    """Sunday 25 Oct 2026 (clocks go back): items count by their local date."""
    frozen_now.move_to("2026-10-24 12:00:00+00:00")
    fake = FakeMagister(mocked)
    base = fake.appointments[CHILD_ID][0]
    items = []
    for number, start in enumerate(
        (
            "2026-10-24T22:30:00.0000000Z",  # 00:30 CEST on 25 Oct
            "2026-10-25T05:00:00.0000000Z",  # 06:00 CET on 25 Oct
            "2026-10-25T23:30:00.0000000Z",  # 00:30 CET on 26 Oct
        )
    ):
        item = copy.deepcopy(base)
        hour = int(start[11:13])
        item.update(
            {
                "Id": 777000 + number,
                "Start": start,
                "Einde": start[:11] + f"{hour:02d}:45:00.0000000Z",
                "Status": 1,
                "DuurtHeleDag": False,
            }
        )
        items.append(item)
    fake.appointments[CHILD_ID] = items
    entry = make_entry()
    add_sensor(entry, 1, subentry_id="sun")
    add_sensor(entry, 2, subentry_id="mon", title="Second")
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    states = {
        sub: hass.states.get(f"sensor.kind_school_{name}")
        for sub, name in (("sun", "first"), ("mon", "second"))
    }
    assert states["sun"] is not None
    assert states["sun"].state == "2026-10-24T22:30:00+00:00"
    assert states["sun"].attributes["date"] == "2026-10-25"
    assert states["mon"] is not None
    assert states["mon"].state == "2026-10-25T23:30:00+00:00"
    assert states["mon"].attributes["date"] == "2026-10-26"


async def test_window_shrink_makes_sensor_unknown_with_repair_issue(
    hass: HomeAssistant, mocked: aioresponses
) -> None:
    """An offset beyond 7 x weeks_ahead - 1 gives unknown and a repair issue."""
    _fake, entry = await setup_sensor(hass, mocked, 14)
    state = hass.states.get(SENSOR_ID)
    assert state is not None
    assert state.state == "2026-11-27T08:15:00+00:00"
    issues = ir.async_get(hass)
    assert issues.async_get_issue(DOMAIN, "offset_outside_window_sub1") is None

    hass.config_entries.async_update_entry(
        entry,
        options={CONF_WEEKS_BACK: 1, CONF_WEEKS_AHEAD: 2, CONF_INTERVAL: 30},
    )
    await hass.async_block_till_done()
    state = hass.states.get(SENSOR_ID)
    assert state is not None
    assert state.state == "unknown"
    issue = issues.async_get_issue(DOMAIN, "offset_outside_window_sub1")
    assert issue is not None
    assert issue.translation_key == "offset_outside_window"
    assert issue.translation_placeholders == {
        "name": "First",
        "offset": "14",
        "weeks_ahead": "2",
        "max_offset": "13",
    }

    hass.config_entries.async_update_entry(
        entry,
        options={CONF_WEEKS_BACK: 1, CONF_WEEKS_AHEAD: 3, CONF_INTERVAL: 30},
    )
    await hass.async_block_till_done()
    state = hass.states.get(SENSOR_ID)
    assert state is not None
    assert state.state == "2026-11-27T08:15:00+00:00"
    assert issues.async_get_issue(DOMAIN, "offset_outside_window_sub1") is None


async def test_removing_the_sensor_clears_its_issue(
    hass: HomeAssistant, mocked: aioresponses
) -> None:
    """Deleting the sub-entry removes the entity and a pending repair issue."""
    _, entry = await setup_sensor(
        hass,
        mocked,
        14,
        options={CONF_WEEKS_BACK: 1, CONF_WEEKS_AHEAD: 2, CONF_INTERVAL: 30},
    )
    issues = ir.async_get(hass)
    assert issues.async_get_issue(DOMAIN, "offset_outside_window_sub1") is not None
    hass.config_entries.async_remove_subentry(entry, "sub1")
    await hass.async_block_till_done()
    assert hass.states.get(SENSOR_ID) is None
    assert issues.async_get_issue(DOMAIN, "offset_outside_window_sub1") is None
    assert er.async_get(hass).async_get(SENSOR_ID) is None
    # the calendar and the device stay
    assert hass.states.get("calendar.kind_school_agenda") is not None


async def test_sensor_of_unselected_child_is_ignored(
    hass: HomeAssistant, mocked: aioresponses
) -> None:
    """A sub-entry that points to an unknown child gets no entity."""
    FakeMagister(mocked)
    entry = make_entry()
    add_sensor(entry, 0, child_id=4242)
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert hass.states.get(SENSOR_ID) is None
    # and it is cleaned up because the child is not selected
    assert not entry.subentries


async def test_unknown_subentry_types_are_ignored(
    hass: HomeAssistant, mocked: aioresponses
) -> None:
    """Only first-appointment sub-entries get a sensor."""
    FakeMagister(mocked)
    entry = make_entry()
    add_sensor(entry, 0)
    entry.subentries = {
        "sub1": ConfigSubentry(
            data=entry.subentries["sub1"].data,
            subentry_type="something_else",
            title="Other",
            unique_id=None,
            subentry_id="sub1",
        )
    }
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert hass.states.get(SENSOR_ID) is None
