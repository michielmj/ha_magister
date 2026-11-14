"""Homework planner backend: to-do list, service, sensors, store, weights, repair."""

from __future__ import annotations

from datetime import timedelta
from typing import Any

import probatio
import pytest
from aioresponses import aioresponses
from freezegun.api import FrozenDateTimeFactory
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers import issue_registry as ir
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_fire_time_changed,
)

from custom_components.magister.api.mapping import LOCAL_TZ
from custom_components.magister.const import (
    CONF_INTERVAL,
    CONF_WEEKS_AHEAD,
    CONF_WEIGHTS,
    DOMAIN,
)
from custom_components.magister.diagnostics import async_get_config_entry_diagnostics
from custom_components.magister.homework import (
    async_publish,
    async_subscribe,
    service_progress,
)
from custom_components.magister.homework_sensor import next_week_issue_id

from .ha_helpers import CHILD_ID, NOW, FakeMagister, make_entry

TODO_ID = "todo.kind_school_homework"
NEXT_DAY = "sensor.kind_school_homework_next_school_day"
WEEK = "sensor.kind_school_homework_this_week"
NEXT_WEEK = "sensor.kind_school_homework_next_week"
HOST = "school.magister.net"


def uid(appointment_id: int, child_id: int = CHILD_ID) -> str:
    """The item uid of a fixture appointment."""
    return f"{HOST}:{child_id}:{appointment_id}"


@pytest.fixture(autouse=True)
async def frozen_now(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> FrozenDateTimeFactory:
    """Friday 13 November 2026, 10:30 in Amsterdam."""
    await hass.config.async_set_time_zone("Europe/Amsterdam")
    freezer.move_to(NOW)
    return freezer


async def setup_homework(
    hass: HomeAssistant,
    mocked: aioresponses,
    *,
    school: str = "school_a",
    options: dict[str, Any] | None = None,
) -> tuple[FakeMagister, MockConfigEntry]:
    """Set up an entry on a fixture school."""
    fake = FakeMagister(mocked, school)
    entry = make_entry(options=options)
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return fake, entry


async def todo_items(hass: HomeAssistant) -> dict[str, dict[str, Any]]:
    """The to-do items by uid, through the todo.get_items service."""
    response = await hass.services.async_call(
        "todo",
        "get_items",
        {"entity_id": TODO_ID},
        blocking=True,
        return_response=True,
    )
    return {item["uid"]: item for item in response[TODO_ID]["items"]}


async def set_progress(hass: HomeAssistant, item_uid: str, progress: int) -> None:
    """Call the magister.set_homework_progress service."""
    await hass.services.async_call(
        DOMAIN,
        "set_homework_progress",
        {"entity_id": TODO_ID, "item": item_uid, "progress": progress},
        blocking=True,
    )
    await hass.async_block_till_done()


def sensor(hass: HomeAssistant, entity_id: str) -> Any:
    """The state of a sensor."""
    state = hass.states.get(entity_id)
    assert state is not None
    return state


async def test_entities_per_child(hass: HomeAssistant, mocked: aioresponses) -> None:
    """A to-do list and three progress sensors appear for each child."""
    _, entry = await setup_homework(hass, mocked)
    registry = er.async_get(hass)
    entities = er.async_entries_for_config_entry(registry, entry.entry_id)
    assert {e.entity_id for e in entities} >= {TODO_ID, NEXT_DAY, WEEK, NEXT_WEEK}
    assert sensor(hass, TODO_ID).attributes["friendly_name"] == "Kind (school) Homework"
    assert sensor(hass, WEEK).attributes["friendly_name"] == (
        "Kind (school) Homework this week"
    )
    assert sensor(hass, TODO_ID).attributes["supported_features"] == 4


async def test_todo_items(hass: HomeAssistant, mocked: aioresponses) -> None:
    """Items follow the spec: summary, due, description, status."""
    _, entry = await setup_homework(hass, mocked)
    items = await todo_items(hass)
    handler = entry.runtime_data.homework
    assert len(items) == len(handler.items(CHILD_ID)) == 53
    math = items[uid(100065)]
    assert math["summary"] == "[Huiswerk] wiskunde"
    assert math["status"] == "needs_action"
    assert math["due"] == "2026-11-16T10:00:00+01:00"
    assert math["description"].startswith("maken: H3, opgave 31,32,33")
    test = items[uid(100084)]
    assert test["summary"] == "[Proefwerk] Duitse taal"
    # not-started, no progress marker
    assert "%" not in (test["description"] or "")
    # Homework on a cancelled lesson is marked.
    cancelled = items[uid(100131)]
    assert "Les vervallen" in cancelled["description"].splitlines()
    # only open items due today (Fri 13 Nov) or later are counted, not all 53
    due = [i for i in handler.items(CHILD_ID) if i.due_date.isoformat() >= "2026-11-13"]
    assert sensor(hass, TODO_ID).state == str(len(due)) == "18"


async def test_tick_untick_restores_last_partial(
    hass: HomeAssistant, mocked: aioresponses
) -> None:
    """Completing sets 100 %; reopening restores the last value below 100."""
    _, entry = await setup_homework(hass, mocked)
    item = uid(100065)
    await set_progress(hass, item, 50)
    items = await todo_items(hass)
    assert items[item]["status"] == "needs_action"
    assert items[item]["description"].endswith("(50 %)")

    await hass.services.async_call(
        "todo",
        "update_item",
        {"entity_id": TODO_ID, "item": item, "status": "completed"},
        blocking=True,
    )
    items = await todo_items(hass)
    assert items[item]["status"] == "completed"
    assert "%" not in items[item]["description"]
    assert items[item]["completed"] is not None
    assert entry.runtime_data.homework.progress(item) == 100
    assert sensor(hass, TODO_ID).state == "17"  # due 16 Nov, so counted before

    await hass.services.async_call(
        "todo",
        "update_item",
        {"entity_id": TODO_ID, "item": item, "status": "needs_action"},
        blocking=True,
    )
    assert entry.runtime_data.homework.progress(item) == 50
    # Unticking an item that is not done changes nothing.
    await hass.services.async_call(
        "todo",
        "update_item",
        {"entity_id": TODO_ID, "item": item, "status": "needs_action"},
        blocking=True,
    )
    assert entry.runtime_data.homework.progress(item) == 50
    # Complete from untouched, then untick: back to 0 and the entry is dropped.
    other = uid(100066)
    for status, expected in (("completed", 100), ("needs_action", 0)):
        await hass.services.async_call(
            "todo",
            "update_item",
            {"entity_id": TODO_ID, "item": other, "status": status},
            blocking=True,
        )
        assert entry.runtime_data.homework.progress(other) == expected
    assert entry.runtime_data.homework.stored_entries == 1


async def test_service_validation(hass: HomeAssistant, mocked: aioresponses) -> None:
    """Unknown items and out-of-range values are rejected."""
    await setup_homework(hass, mocked)
    with pytest.raises(ServiceValidationError):
        await set_progress(hass, "unknown", 50)
    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            "todo",
            "update_item",
            {"entity_id": TODO_ID, "item": "x", "status": "completed"},
            blocking=True,
        )
    for bad in (101, -1):
        with pytest.raises(Exception, match="progress"):
            await set_progress(hass, uid(100065), bad)


async def test_progress_sensors_without_weights(
    hass: HomeAssistant, mocked: aioresponses
) -> None:
    """On Friday the next school day is Monday; week and next week are Sat-Fri."""
    await setup_homework(hass, mocked)
    next_day = sensor(hass, NEXT_DAY)
    assert next_day.state == "0.0"
    assert next_day.attributes["items"] == 6  # Friday (2) and Monday (4)
    assert next_day.attributes["unit_of_measurement"] == "%"
    assert next_day.attributes["state_class"] == "measurement"
    assert next_day.attributes["period_start"] == "2026-11-13"
    assert next_day.attributes["period_end"] == "2026-11-16"

    week = sensor(hass, WEEK)
    assert week.state == "0.0"
    assert week.attributes["period_start"] == "2026-11-07"
    assert week.attributes["period_end"] == "2026-11-13"
    assert (week.attributes["items"], week.attributes["tests"]) == (
        week.attributes["open"],
        0,
    )
    nxt = sensor(hass, NEXT_WEEK)
    assert nxt.attributes["items"] == 12
    assert nxt.attributes["tests"] == 2  # a Proefwerk and an SO

    first_week_items = week.attributes["items"]
    await set_progress(hass, uid(100061), 100)  # Friday 13 Nov, in this week
    week = sensor(hass, WEEK)
    assert week.attributes["completed"] == 1
    assert week.attributes["open"] == first_week_items - 1
    assert week.state == str(round(100 / first_week_items, 1))


async def test_weighted_sensors_and_no_reload(
    hass: HomeAssistant, mocked: aioresponses
) -> None:
    """New weights recompute the sensors: no reload and no Magister request."""
    fake, entry = await setup_homework(hass, mocked)
    runtime = entry.runtime_data
    requests = len(fake.appointment_requests)
    await set_progress(hass, uid(100061), 100)  # geschiedenis
    plain = float(sensor(hass, WEEK).state)

    hass.config_entries.async_update_entry(
        entry,
        options={
            **entry.options,
            CONF_WEIGHTS: {
                str(CHILD_ID): {
                    "types": {"homework": 2},
                    "subjects": {"GESCHIEDENIS": 10, "wiskunde": 0},
                }
            },
        },
    )
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.LOADED
    assert entry.runtime_data is runtime
    assert len(fake.appointment_requests) == requests
    week = sensor(hass, WEEK)
    assert float(week.state) > plain
    weights = week.attributes["weights"]
    assert weights["types"]["homework"] == 2.0
    assert weights["subjects"]["geschiedenis"] == 10.0
    assert weights["subjects"]["wiskunde"] == 0.0
    assert weights["subjects"]["economie"] == 1.0

    # Back to no weights.
    hass.config_entries.async_update_entry(
        entry, options={k: v for k, v in entry.options.items() if k != CONF_WEIGHTS}
    )
    await hass.async_block_till_done()
    assert entry.runtime_data is runtime
    assert float(sensor(hass, WEEK).state) == plain


async def test_other_option_changes_still_reload(
    hass: HomeAssistant, mocked: aioresponses
) -> None:
    """Only the weights are exempt from the reload."""
    _, entry = await setup_homework(hass, mocked)
    runtime = entry.runtime_data
    hass.config_entries.async_update_entry(
        entry, options={**entry.options, CONF_INTERVAL: 60}
    )
    await hass.async_block_till_done()
    assert entry.runtime_data is not runtime


async def test_school_b_subjects_from_description(
    hass: HomeAssistant, mocked: aioresponses
) -> None:
    """Schools without Vakken weigh by the subject from the description."""
    await setup_homework(
        hass,
        mocked,
        school="school_b",
        options={CONF_WEIGHTS: {str(CHILD_ID): {"subjects": {"NAT": 0}}}},
    )
    week = sensor(hass, WEEK)
    assert week.attributes["weights"]["subjects"]["nat"] == 0.0
    assert week.attributes["weights"]["types"]["test"] == 1.0
    assert week.attributes["items"] > 0


async def test_midnight_rolls_the_periods(
    hass: HomeAssistant, mocked: aioresponses, frozen_now: FrozenDateTimeFactory
) -> None:
    """At Amsterdam midnight the periods move on."""
    await setup_homework(hass, mocked)
    assert sensor(hass, NEXT_DAY).attributes["items"] == 6  # Friday + Monday
    frozen_now.move_to("2026-11-14 23:00:01+00:00")  # Sunday 00:00:01 in Amsterdam
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    next_day = sensor(hass, NEXT_DAY)
    assert next_day.attributes["period_start"] == "2026-11-15"
    assert next_day.attributes["period_end"] == "2026-11-16"
    assert next_day.attributes["items"] == 4
    assert sensor(hass, WEEK).attributes["period_start"] == "2026-11-14"
    frozen_now.move_to("2026-11-15 23:00:01+00:00")  # Monday 00:00:01
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    next_day = sensor(hass, NEXT_DAY)
    assert next_day.attributes["period_start"] == "2026-11-16"
    assert next_day.attributes["period_end"] == "2026-11-17"
    assert sensor(hass, WEEK).attributes["period_start"] == "2026-11-14"


async def test_next_week_outside_window(
    hass: HomeAssistant, mocked: aioresponses
) -> None:
    """With one week ahead next week is unavailable and a repair is raised."""
    _, entry = await setup_homework(hass, mocked, options={CONF_WEEKS_AHEAD: 1})
    assert sensor(hass, NEXT_WEEK).state == "unavailable"
    assert sensor(hass, WEEK).state != "unavailable"
    issue = ir.async_get(hass).async_get_issue(
        DOMAIN, next_week_issue_id(entry.entry_id)
    )
    assert issue is not None
    assert issue.translation_key == "homework_next_week_outside_window"
    assert issue.translation_placeholders == {
        "entry": entry.title,
        "weeks_ahead": "1",
    }
    # Unloading clears the repair.
    assert await hass.config_entries.async_unload(entry.entry_id)
    assert (
        ir.async_get(hass).async_get_issue(DOMAIN, next_week_issue_id(entry.entry_id))
        is None
    )


async def test_no_issue_when_it_fits(hass: HomeAssistant, mocked: aioresponses) -> None:
    """Two weeks ahead is enough."""
    _, entry = await setup_homework(hass, mocked, options={CONF_WEEKS_AHEAD: 2})
    assert sensor(hass, NEXT_WEEK).state != "unavailable"
    assert (
        ir.async_get(hass).async_get_issue(DOMAIN, next_week_issue_id(entry.entry_id))
        is None
    )


async def test_availability_follows_the_24_hour_rule(
    hass: HomeAssistant, mocked: aioresponses, frozen_now: FrozenDateTimeFactory
) -> None:
    """The list and sensors expire with the other entities, not before."""
    fake, _ = await setup_homework(hass, mocked)
    fake.appointment_status = 500
    for _ in range(3):  # failed refreshes keep the last good data
        frozen_now.tick(timedelta(hours=7))
        async_fire_time_changed(hass)
        await hass.async_block_till_done(wait_background_tasks=True)
        assert sensor(hass, WEEK).state != "unavailable"
        assert sensor(hass, TODO_ID).state != "unavailable"
    frozen_now.tick(timedelta(hours=4))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)
    for entity_id in (TODO_ID, NEXT_DAY, WEEK, NEXT_WEEK):
        assert sensor(hass, entity_id).state == "unavailable"


async def test_progress_survives_reload_and_restart(
    hass: HomeAssistant, mocked: aioresponses, hass_storage: dict[str, Any]
) -> None:
    """Progress is stored, flushed on unload and read again after a restart."""
    _, entry = await setup_homework(hass, mocked)
    await set_progress(hass, uid(100065), 50)
    await set_progress(hass, uid(100066), 100)
    assert await hass.config_entries.async_unload(entry.entry_id)
    key = f"{DOMAIN}.homework.{entry.entry_id}"
    stored = hass_storage[key]["data"]["items"]
    assert stored[uid(100065)]["progress"] == 50
    assert stored[uid(100066)] | {"updated": ""} == {
        "progress": 100,
        "last_partial": 0,
        "updated": "",
        "labels": [],
    }
    assert uid(100061) not in stored

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    items = await todo_items(hass)
    assert items[uid(100065)]["description"].endswith("(50 %)")
    assert items[uid(100066)]["status"] == "completed"


async def test_store_is_written_after_a_delay(
    hass: HomeAssistant,
    mocked: aioresponses,
    hass_storage: dict[str, Any],
    frozen_now: FrozenDateTimeFactory,
) -> None:
    """Changes are saved shortly after, without an unload."""
    _, entry = await setup_homework(hass, mocked)
    await set_progress(hass, uid(100065), 25)
    key = f"{DOMAIN}.homework.{entry.entry_id}"
    assert key not in hass_storage
    frozen_now.tick(timedelta(seconds=10))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert hass_storage[key]["data"]["items"][uid(100065)]["progress"] == 25


async def test_damaged_store_is_tolerated(
    hass: HomeAssistant, mocked: aioresponses, hass_storage: dict[str, Any]
) -> None:
    """Unusable stored entries are skipped or clamped."""
    entry = make_entry()
    hass_storage[f"{DOMAIN}.homework.{entry.entry_id}"] = {
        "version": 1,
        "minor_version": 1,
        "key": f"{DOMAIN}.homework.{entry.entry_id}",
        "data": {
            "items": {
                uid(100065): {"progress": 250, "last_partial": "x", "updated": None},
                uid(100066): "junk",
                uid(100068): {"progress": 40, "last_partial": 40, "gone": "2026-11-01"},
            }
        },
    }
    FakeMagister(mocked)
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    homework = entry.runtime_data.homework
    assert homework.progress(uid(100065)) == 100
    assert homework.progress(uid(100066)) == 0
    # present items lose the "gone" mark
    assert homework.progress(uid(100068)) == 40
    assert homework.stored_entries == 2


async def test_items_leaving_the_window_are_pruned_after_14_days(
    hass: HomeAssistant,
    mocked: aioresponses,
    hass_storage: dict[str, Any],
    frozen_now: FrozenDateTimeFactory,
) -> None:
    """A vanished item disappears at once; its progress goes after 14 days."""
    fake, entry = await setup_homework(hass, mocked)
    homework = entry.runtime_data.homework
    original = list(fake.appointments[CHILD_ID])
    await set_progress(hass, uid(100065), 50)
    fake.appointments[CHILD_ID] = [
        a for a in fake.appointments[CHILD_ID] if a["Id"] != 100065
    ]
    coordinator = entry.runtime_data.coordinator
    await coordinator.async_refresh()
    await hass.async_block_till_done()
    assert uid(100065) not in await todo_items(hass)
    assert homework.progress(uid(100065)) == 50  # kept for a while
    frozen_now.tick(timedelta(days=13))
    await coordinator.async_refresh()
    assert homework.progress(uid(100065)) == 50
    # It comes back: the progress is still there and the "gone" mark is cleared.
    fake.appointments[CHILD_ID] = original
    await coordinator.async_refresh()
    await hass.async_block_till_done()
    assert uid(100065) in await todo_items(hass)
    assert homework.progress(uid(100065)) == 50
    # Long after, the present item is not pruned.
    frozen_now.tick(timedelta(days=30))
    await coordinator.async_refresh()
    assert homework.progress(uid(100065)) == 50
    # Gone again: after more than 14 days the progress is dropped.
    fake.appointments[CHILD_ID] = [a for a in original if a["Id"] != 100065]
    await coordinator.async_refresh()
    frozen_now.tick(timedelta(days=15))
    await coordinator.async_refresh()
    await hass.async_block_till_done()
    assert homework.progress(uid(100065)) == 0
    assert homework.stored_entries == 0


async def test_store_is_deleted_with_the_entry(
    hass: HomeAssistant, mocked: aioresponses, hass_storage: dict[str, Any]
) -> None:
    """Removing the config entry removes its progress store."""
    _, entry = await setup_homework(hass, mocked)
    await set_progress(hass, uid(100065), 50)
    assert await hass.config_entries.async_unload(entry.entry_id)
    key = f"{DOMAIN}.homework.{entry.entry_id}"
    assert key in hass_storage
    assert await hass.config_entries.async_remove(entry.entry_id)
    await hass.async_block_till_done()
    assert key not in hass_storage


async def test_service_exists_before_any_entry(hass: HomeAssistant) -> None:
    """The action is registered at integration setup."""
    assert await async_setup_component(hass, DOMAIN, {})
    assert hass.services.has_service(DOMAIN, "set_homework_progress")


async def test_service_rejects_booleans(
    hass: HomeAssistant, mocked: aioresponses
) -> None:
    """True is not a progress value; whole numbers as text are fine."""
    _, entry = await setup_homework(hass, mocked)
    with pytest.raises(Exception, match="integer"):
        await set_progress(hass, uid(100065), True)  # type: ignore[arg-type]
    await set_progress(hass, uid(100065), "25")  # type: ignore[arg-type]
    assert entry.runtime_data.homework.progress(uid(100065)) == 25
    with pytest.raises(Exception, match="integer"):
        await set_progress(hass, uid(100065), 2.5)  # type: ignore[arg-type]


async def test_only_the_status_can_be_changed(
    hass: HomeAssistant, mocked: aioresponses
) -> None:
    """Renaming (or other fields) is refused with a translated error."""
    await setup_homework(hass, mocked)
    with pytest.raises(ServiceValidationError) as err:
        await hass.services.async_call(
            "todo",
            "update_item",
            {"entity_id": TODO_ID, "item": uid(100065), "rename": "andere titel"},
            blocking=True,
        )
    assert err.value.translation_key == "homework_status_only"


async def test_item_keeps_progress_when_text_changes(
    hass: HomeAssistant, mocked: aioresponses
) -> None:
    """The key is the appointment id: new text keeps the progress."""
    fake, entry = await setup_homework(hass, mocked)
    await set_progress(hass, uid(100065), 75)
    for appointment in fake.appointments[CHILD_ID]:
        if appointment["Id"] == 100065:
            appointment["Inhoud"] = "<p>nieuwe tekst</p>"
    await entry.runtime_data.coordinator.async_refresh()
    await hass.async_block_till_done()
    item = (await todo_items(hass))[uid(100065)]
    assert item["description"] == "nieuwe tekst\n(75 %)"


async def test_diagnostics_have_homework_statistics_only(
    hass: HomeAssistant, mocked: aioresponses
) -> None:
    """Counts and progress statistics, no names, texts or child ids."""
    _, entry = await setup_homework(
        hass,
        mocked,
        options={CONF_WEIGHTS: {str(CHILD_ID): {"subjects": {"Duitse taal": 2}}}},
    )
    await set_progress(hass, uid(100065), 50)
    await set_progress(hass, uid(100066), 100)
    diagnostics = await async_get_config_entry_diagnostics(hass, entry)
    (child,) = diagnostics["children"]
    stats = child["homework"]
    assert stats["items"] == 53
    assert stats["cancelled"] == 3
    assert stats["by_info_type"]["1"] == 47
    assert stats["progress"] == {
        "not_started": 51,
        "partial": 1,
        "done": 1,
        "average": round(150 / 53, 1),
    }
    assert stats["weights"] == {
        "types_set": 0,
        "labels_set": 0,
        "subjects_set": 1,
    }
    assert stats["manual_labels"] == {"homework": 0, "test": 0}
    assert diagnostics["homework_store"] == {"stored_entries": 2}
    assert CONF_WEIGHTS not in diagnostics["entry"]["options"]
    text = str(diagnostics)
    assert "Duitse" not in text and "wiskunde" not in text and "1001" not in text


@pytest.mark.parametrize("value", [None, "abc", [], {}])
def test_service_progress_rejects_non_numbers(value: Any) -> None:
    """Values that are no number at all are invalid (TypeError/ValueError path)."""
    with pytest.raises(probatio.Invalid, match="integer"):
        service_progress(value)


async def test_same_progress_is_a_no_op(
    hass: HomeAssistant, mocked: aioresponses
) -> None:
    """Setting the stored value again changes nothing and notifies nobody."""
    _, entry = await setup_homework(hass, mocked)
    homework = entry.runtime_data.homework
    await set_progress(hass, uid(100065), 50)
    calls: list[dict[str, Any]] = []
    remove = async_subscribe(hass, TODO_ID, calls.append)
    await set_progress(hass, uid(100065), 50)
    assert calls == []
    assert homework.progress(uid(100065)) == 50
    remove()


async def test_prune_without_data_does_nothing(
    hass: HomeAssistant, mocked: aioresponses
) -> None:
    """Before the first refresh there is nothing to prune."""
    _, entry = await setup_homework(hass, mocked)
    homework = entry.runtime_data.homework
    entry.runtime_data.coordinator.data = None
    homework.async_prune()
    assert homework.progress(uid(100065)) == 0


async def test_unsubscribing_keeps_a_newer_subscriber_list(hass: HomeAssistant) -> None:
    """A stale remove callback must not drop the list of a newer subscription."""
    first = async_subscribe(hass, TODO_ID, lambda _: None)
    first()  # the list is empty and removed
    calls: list[dict[str, Any]] = []
    second = async_subscribe(hass, TODO_ID, calls.append)
    first()  # stale: the subscriber is already gone, the new list stays
    async_publish(hass, TODO_ID, {"x": 1})
    assert calls == [{"x": 1}]
    second()
    async_publish(hass, TODO_ID, {"x": 2})
    assert calls == [{"x": 1}]


async def test_count_ignores_past_and_completed_items(
    hass: HomeAssistant, mocked: aioresponses
) -> None:
    """Past open items stay in the list but do not count; completed ones neither."""
    _, entry = await setup_homework(hass, mocked)
    items = entry.runtime_data.homework.items(CHILD_ID)
    past = next(i for i in items if i.due_date.isoformat() < "2026-11-13")
    today = next(i for i in items if i.due_date.isoformat() == "2026-11-13")
    assert sensor(hass, TODO_ID).state == "18"
    # the list itself is unchanged
    assert past.uid in await todo_items(hass)
    assert (await todo_items(hass))[past.uid]["status"] == "needs_action"
    # ticking a past item does not change the count
    await set_progress(hass, past.uid, 100)
    assert sensor(hass, TODO_ID).state == "18"
    # an item due today is counted, and drops out when completed
    await set_progress(hass, today.uid, 100)
    assert sensor(hass, TODO_ID).state == "17"
    await set_progress(hass, today.uid, 50)
    assert sensor(hass, TODO_ID).state == "18"


async def test_count_rolls_over_at_midnight(
    hass: HomeAssistant, mocked: aioresponses, frozen_now: FrozenDateTimeFactory
) -> None:
    """Items due Friday stop counting once Amsterdam midnight passes."""
    _, entry = await setup_homework(hass, mocked)
    items = entry.runtime_data.homework.items(CHILD_ID)
    on_friday = sum(1 for i in items if i.due_date.isoformat() == "2026-11-13")
    assert on_friday > 0
    assert sensor(hass, TODO_ID).state == "18"
    # Just before midnight nothing changes; the next step is under 30 minutes, so only
    # the midnight timer (no coordinator refresh) can move the count.
    for before, at in (
        ("2026-11-13 22:45:00+00:00", "2026-11-13 23:00:01+00:00"),  # Fri to Sat
        ("2026-11-14 22:45:00+00:00", "2026-11-14 23:00:01+00:00"),  # Sat to Sun
    ):
        frozen_now.move_to(before)
        async_fire_time_changed(hass)
        await hass.async_block_till_done()
        day = (
            (dt_util.parse_datetime(at) or dt_util.utcnow()).astimezone(LOCAL_TZ).date()
        )
        previous = str(day - timedelta(days=1))
        due_before = sensor(hass, TODO_ID).state
        assert due_before == str(
            sum(1 for i in items if i.due_date.isoformat() >= previous)
        )
        frozen_now.move_to(at)
        async_fire_time_changed(hass)
        await hass.async_block_till_done()
        assert sensor(hass, TODO_ID).state == str(
            sum(1 for i in items if i.due_date.isoformat() >= str(day))
        )
    assert sensor(hass, TODO_ID).state != "18"
