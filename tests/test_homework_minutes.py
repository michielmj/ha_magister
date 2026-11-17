"""Subtask ``minutes`` and the daily maximum: model, store, WebSocket, services."""

from __future__ import annotations

from typing import Any

import pytest
from aioresponses import aioresponses
from freezegun.api import FrozenDateTimeFactory
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from pytest_homeassistant_custom_component.typing import WebSocketGenerator

from custom_components.magister.api.homework import (
    DAILY_MAX_DEFAULT,
    Weights,
    clean_daily_max,
    valid_minutes,
)
from custom_components.magister.const import CONF_WEIGHTS, DOMAIN

from .ha_helpers import CHILD_ID, NOW, FakeMagister, make_entry
from .test_homework import TODO_ID, setup_homework, uid
from .test_homework_labels import SUBSCRIBE, call
from .test_homework_subtasks import ADD, BASE, DELETE, UPDATE, stored_file

HOMEWORK = 100065
PROEFWERK = 100084
BAD_MINUTES: list[Any] = [0, 4, 7, 245, 250, -5, True, False, "30", 12.5, [5], {}]


@pytest.fixture(autouse=True)
async def frozen_now(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> FrozenDateTimeFactory:
    """Friday 13 November 2026."""
    await hass.config.async_set_time_zone("Europe/Amsterdam")
    freezer.move_to(NOW)
    return freezer


def test_valid_minutes() -> None:
    """5 to 240 in steps of 5; whole floats are fine; the rest is refused."""
    assert [valid_minutes(v) for v in (5, 30, 240, 45.0)] == [5, 30, 240, 45]
    assert all(valid_minutes(v) is None for v in [*BAD_MINUTES, None, float("nan")])


def test_daily_max_is_read_leniently() -> None:
    """Default 90; stored values are clamped to 15-480; rubbish reads as default."""
    assert clean_daily_max(None) == DAILY_MAX_DEFAULT == 90
    assert [clean_daily_max(v) for v in (15, 480, 120.0)] == [15, 480, 120]
    assert [clean_daily_max(v) for v in (1, 9999)] == [15, 480]
    # Rounded to the 15-minute step, so the options flow never suggests a refused value.
    assert [clean_daily_max(v) for v in (100, 107, 108, 100.0, 20)] == [
        105,
        105,
        105,
        105,
        15,
    ]
    assert all(
        clean_daily_max(v) == 90 for v in (True, "120", 100.5, [], {}, float("inf"))
    )
    assert clean_daily_max(10**400) == 480
    assert clean_daily_max(-(10**400)) == 15
    assert Weights.from_options({"daily_max_minutes": 135}).daily_max_minutes == 135
    assert Weights.from_options({"types": {}}).daily_max_minutes == 90
    assert Weights.from_options(None).daily_max_minutes == 90


# -- WebSocket ----------------------------------------------------------------------


async def test_ws_add_and_update_minutes(
    hass: HomeAssistant, mocked: aioresponses, hass_ws_client: WebSocketGenerator
) -> None:
    """Optional on add; update changes it, null clears it; the item shows it."""
    await setup_homework(hass, mocked)
    client = await hass_ws_client(hass)
    plain = await call(client, ADD, item=uid(HOMEWORK), title="a")
    assert plain["result"]["subtasks"][0]["minutes"] is None
    timed = await call(client, ADD, item=uid(HOMEWORK), title="b", minutes=30)
    assert timed["success"]
    first, second = timed["result"]["subtasks"]
    assert (first["minutes"], second["minutes"]) == (None, 30)

    changed = await call(client, UPDATE, subtask=second["uid"], minutes=45)
    assert changed["result"]["subtasks"][1]["minutes"] == 45
    # Only minutes is a valid update; the other fields are untouched.
    assert changed["result"]["subtasks"][1]["title"] == "b"
    cleared = await call(client, UPDATE, subtask=second["uid"], minutes=None)
    assert cleared["result"]["subtasks"][1]["minutes"] is None
    # Clearing something that is not set still counts as an update.
    again = await call(client, UPDATE, subtask=second["uid"], minutes=None)
    assert again["success"]
    both = await call(client, UPDATE, subtask=first["uid"], title="c", minutes=240)
    assert both["result"]["subtasks"][0]["title"] == "c"
    assert both["result"]["subtasks"][0]["minutes"] == 240
    # Without minutes the value stays.
    kept = await call(client, UPDATE, subtask=first["uid"], title="d")
    assert kept["result"]["subtasks"][0]["minutes"] == 240
    nothing = await call(client, UPDATE, subtask=first["uid"])
    assert nothing["error"]["code"] == "invalid_format"
    await call(client, DELETE, subtask=first["uid"])


async def test_ws_invalid_minutes(
    hass: HomeAssistant, mocked: aioresponses, hass_ws_client: WebSocketGenerator
) -> None:
    """A wrong value is `invalid_minutes` on add and update, and nothing is stored."""
    await setup_homework(hass, mocked)
    client = await hass_ws_client(hass)
    for bad in BAD_MINUTES:
        response = await call(client, ADD, item=uid(HOMEWORK), title="x", minutes=bad)
        assert response["error"]["code"] == "invalid_minutes", bad
    added = await call(client, ADD, item=uid(HOMEWORK), title="ok", minutes=10)
    (sub,) = added["result"]["subtasks"]
    for bad in BAD_MINUTES:
        response = await call(client, UPDATE, subtask=sub["uid"], minutes=bad)
        assert response["error"]["code"] == "invalid_minutes", bad
    current = await call(client, UPDATE, subtask=sub["uid"], title="ok2")
    assert [s["minutes"] for s in current["result"]["subtasks"]] == [10]
    # No subtask was added by the failed calls.
    assert len(current["result"]["subtasks"]) == 1


async def test_subscribe_has_daily_max(
    hass: HomeAssistant, mocked: aioresponses, hass_ws_client: WebSocketGenerator
) -> None:
    """The payload carries the child's daily maximum (default 90, or the stored)."""
    _, entry = await setup_homework(hass, mocked)
    client = await hass_ws_client(hass)
    await client.send_json_auto_id({"type": SUBSCRIBE, "entity_id": TODO_ID})
    assert (await client.receive_json())["success"]
    assert (await client.receive_json())["event"]["daily_max_minutes"] == 90
    # Changing the options applies without a reload and pushes the new maximum.
    runtime = entry.runtime_data
    hass.config_entries.async_update_entry(
        entry, options={CONF_WEIGHTS: {str(CHILD_ID): {"daily_max_minutes": 120}}}
    )
    await hass.async_block_till_done()
    assert entry.runtime_data is runtime
    event = (await client.receive_json())["event"]
    assert event["daily_max_minutes"] == 120


# -- services -----------------------------------------------------------------------


async def test_services_minutes(hass: HomeAssistant, mocked: aioresponses) -> None:
    """The services accept `minutes`; null clears; a bad value is translated."""
    _, entry = await setup_homework(hass, mocked)
    manager = entry.runtime_data.homework

    async def run(name: str, **data: Any) -> None:
        await hass.services.async_call(
            DOMAIN, name, {"entity_id": TODO_ID, **data}, blocking=True
        )
        await hass.async_block_till_done()

    def minutes() -> list[int | None]:
        item = manager.find_item(CHILD_ID, uid(HOMEWORK))
        assert item is not None
        return [s.minutes for s in item.subtasks]

    await run("add_homework_subtask", item=uid(HOMEWORK), title="a", minutes=25)
    await run("add_homework_subtask", item=uid(HOMEWORK), title="b")
    assert minutes() == [25, None]
    item = manager.find_item(CHILD_ID, uid(HOMEWORK))
    assert item is not None
    first, second = (f"{uid(HOMEWORK)}:sub:{s.id}" for s in item.subtasks)
    await run("update_homework_subtask", subtask=second, minutes=60)
    assert minutes() == [25, 60]
    await run("update_homework_subtask", subtask=first, minutes=None)
    assert minutes() == [None, 60]
    for name, data in (
        ("add_homework_subtask", {"item": uid(HOMEWORK), "title": "c"}),
        ("update_homework_subtask", {"subtask": first}),
    ):
        with pytest.raises(ServiceValidationError) as err:
            await run(name, **data, minutes=7)
        assert err.value.translation_key == "homework_invalid_minutes"
    assert minutes() == [None, 60]


# -- store --------------------------------------------------------------------------


async def test_store_1_5_file_loads_and_saves_minutes(
    hass: HomeAssistant, mocked: aioresponses, hass_storage: dict[str, Any]
) -> None:
    """A minor-5 file (no `minutes`) reads as unknown; saved as 1.6 with the field."""
    entry = make_entry()
    key = f"{DOMAIN}.homework.{entry.entry_id}"
    sub = {
        "id": "a1",
        "title": "t",
        "planned": "2026-11-14",
        "progress": 0,
        "last_partial": 0,
        "completed_on": None,
        "created_by": "parent",
    }
    hass_storage[key] = stored_file(
        entry.entry_id, {uid(HOMEWORK): {**BASE, "subtasks": [sub]}}, 5
    )
    FakeMagister(mocked)
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    manager = entry.runtime_data.homework
    found = manager.find_subtask(f"{uid(HOMEWORK)}:sub:a1")
    assert found is not None
    assert (found.minutes, found.created_by) == (None, "parent")
    manager.update_subtask(CHILD_ID, f"{uid(HOMEWORK)}:sub:a1", None, None, 35)
    assert await hass.config_entries.async_unload(entry.entry_id)
    saved = hass_storage[key]
    assert (saved["version"], saved["minor_version"]) == (1, 8)
    (stored,) = saved["data"]["items"][uid(HOMEWORK)]["subtasks"]
    # 1.6.0 reads this by key and ignores `minutes`: the fields it knows are all there.
    assert stored["minutes"] == 35
    assert {"id", "title", "planned", "progress", "created_by"} <= set(stored)


async def test_store_loads_minutes_leniently(
    hass: HomeAssistant, mocked: aioresponses, hass_storage: dict[str, Any]
) -> None:
    """A stored value that is not 5-240 in steps of 5 reads as unknown."""
    entry = make_entry()
    key = f"{DOMAIN}.homework.{entry.entry_id}"
    base = {
        "title": "t",
        "planned": "2026-11-14",
        "progress": 0,
        "last_partial": 0,
        "completed_on": None,
    }
    values = [30, 7, True, "30", 500, None, 45.0]
    subs = [{**base, "id": f"s{n}", "minutes": v} for n, v in enumerate(values)]
    hass_storage[key] = stored_file(
        entry.entry_id, {uid(HOMEWORK): {**BASE, "subtasks": subs}}, 6
    )
    FakeMagister(mocked)
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    item = entry.runtime_data.homework.find_item(CHILD_ID, uid(HOMEWORK))
    assert item is not None
    assert [s.minutes for s in item.subtasks] == [30, None, None, None, None, None, 45]
    stats = entry.runtime_data.homework.statistics(CHILD_ID)
    assert stats["subtasks"]["with_minutes"] == 2
    assert stats["daily_max_minutes"] == 90
