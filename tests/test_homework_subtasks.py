"""Subtasks: store, WebSocket commands, services, to-do list, sensors and midnight."""

from __future__ import annotations

import copy
from datetime import timedelta
from typing import Any

import pytest
from aioresponses import aioresponses
from freezegun.api import FrozenDateTimeFactory
from homeassistant.components.todo.const import DATA_COMPONENT
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from pytest_homeassistant_custom_component.common import (
    MockUser,
    async_fire_time_changed,
)
from pytest_homeassistant_custom_component.typing import WebSocketGenerator

from custom_components.magister.const import CONF_WEIGHTS, DOMAIN
from custom_components.magister.diagnostics import async_get_config_entry_diagnostics
from custom_components.magister.homework import async_subscribe
from custom_components.magister.todo import MagisterHomeworkTodo

from .ha_helpers import CHILD_ID, NOW, FakeMagister, make_entry
from .test_homework import (
    NEXT_DAY,
    NEXT_WEEK,
    TODO_ID,
    WEEK,
    sensor,
    set_progress,
    setup_homework,
    todo_items,
    uid,
)
from .test_homework_labels import SUBSCRIBE, call, call_events

ADD = "magister/homework/add_subtask"
UPDATE = "magister/homework/update_subtask"
DELETE = "magister/homework/delete_subtask"
SET_PROGRESS = "magister/homework/set_progress"

HOMEWORK = 100065  # wiskunde, Monday 16 Nov, Huiswerk
PROEFWERK = 100084  # Duitse taal, Thursday 19 Nov, Proefwerk
TODAY_ITEM = uid(HOMEWORK)  # replaced below by an item due on Friday 13 Nov


@pytest.fixture(autouse=True)
async def frozen_now(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> FrozenDateTimeFactory:
    """Friday 13 November 2026."""
    await hass.config.async_set_time_zone("Europe/Amsterdam")
    freezer.move_to(NOW)
    return freezer


async def add(client: Any, item: int, title: str = "H4", **fields: Any) -> Any:
    """``add_subtask`` for a fixture appointment."""
    return await call(client, ADD, item=uid(item), title=title, **fields)


async def add_ok(client: Any, item: int, title: str = "H4", **fields: Any) -> Any:
    """``add_subtask`` that must work: the new subtask."""
    response = await add(client, item, title, **fields)
    assert response["success"], response
    return response["result"]["subtasks"][-1]


def payload_item(payload: dict[str, Any], appointment: int) -> dict[str, Any]:
    """An item of a payload."""
    return next(i for i in payload["items"] if i["uid"] == uid(appointment))


async def subscribe(client: Any) -> dict[str, Any]:
    """Subscribe and return the first payload."""
    await client.send_json_auto_id({"type": SUBSCRIBE, "entity_id": TODO_ID})
    assert (await client.receive_json())["success"]
    event: dict[str, Any] = (await client.receive_json())["event"]
    return event


def current_payload(hass: HomeAssistant) -> dict[str, Any]:
    """The payload a new subscriber would get now."""
    entity = hass.data[DATA_COMPONENT].get_entity(TODO_ID)
    assert isinstance(entity, MagisterHomeworkTodo)
    return entity.payload()


# -- add, update, delete -----------------------------------------------------------


async def test_add_subtask_returns_the_item_and_pushes(
    hass: HomeAssistant, mocked: aioresponses, hass_ws_client: WebSocketGenerator
) -> None:
    """The result is the parent item; the date defaults to today; an event follows."""
    await setup_homework(hass, mocked)
    client = await hass_ws_client(hass)
    await subscribe(client)
    response, events = await call_events(
        client, ADD, item=uid(HOMEWORK), title="  H4 woordjes  "
    )
    item = response["result"]
    assert item["uid"] == uid(HOMEWORK)
    assert item["derived"] is True
    (sub,) = item["subtasks"]
    assert len(sub["uid"].removeprefix(f"{uid(HOMEWORK)}:sub:")) == 8
    assert {k: v for k, v in sub.items() if k != "uid"} == {
        "title": "H4 woordjes",
        "planned": "2026-11-13",
        "date": "2026-11-13",
        "overdue": False,
        "progress": 0,
        "completed": False,
        "last_partial": 0,
    }
    (event,) = events
    assert payload_item(event, HOMEWORK)["subtasks"] == [sub]
    # a later date, and the item date itself
    response, _ = await call_events(
        client, ADD, item=uid(HOMEWORK), title="b", date="2026-11-15"
    )
    later = response["result"]["subtasks"][-1]
    assert (later["planned"], later["date"]) == ("2026-11-15", "2026-11-15")
    response, _ = await call_events(
        client, ADD, item=uid(HOMEWORK), title="c", date="2026-11-16"
    )
    assert response["result"]["subtasks"][-1]["date"] == "2026-11-16"


@pytest.mark.parametrize(
    ("fields", "code"),
    [
        ({"title": ""}, "invalid_format"),
        ({"title": "   "}, "invalid_format"),
        ({"title": "x" * 101}, "invalid_format"),
        ({"title": 5}, "invalid_format"),
        ({"title": "x", "date": "tomorrow"}, "invalid_format"),
        ({"title": "x", "date": "2026-11-12"}, "invalid_date"),  # past
        ({"title": "x", "date": "2026-11-17"}, "invalid_date"),  # after the item
    ],
)
async def test_add_subtask_validation(
    hass: HomeAssistant,
    mocked: aioresponses,
    hass_ws_client: WebSocketGenerator,
    fields: dict[str, Any],
    code: str,
) -> None:
    """Title and date rules."""
    await setup_homework(hass, mocked)
    client = await hass_ws_client(hass)
    response = await call(client, ADD, item=uid(HOMEWORK), **fields)
    assert response["error"]["code"] == code


async def test_title_boundaries_and_item_errors(
    hass: HomeAssistant, mocked: aioresponses, hass_ws_client: WebSocketGenerator
) -> None:
    """100 characters are fine; unknown items and entities are errors."""
    await setup_homework(hass, mocked)
    client = await hass_ws_client(hass)
    assert (await add_ok(client, HOMEWORK, "x" * 100))["title"] == "x" * 100
    assert (await add_ok(client, HOMEWORK, "é"))["title"] == "é"
    response = await call(client, ADD, item="school.magister.net:1001:1", title="x")
    assert response["error"]["code"] == "item_not_found"
    # an item of another child cannot be used
    response = await call(client, ADD, item="school.magister.net:9:100065", title="x")
    assert response["error"]["code"] == "item_not_found"
    await client.send_json_auto_id(
        {"type": ADD, "entity_id": "todo.nope", "item": "x", "title": "x"}
    )
    assert (await client.receive_json())["error"]["code"] == "not_found"


async def test_at_most_twenty_subtasks(
    hass: HomeAssistant, mocked: aioresponses, hass_ws_client: WebSocketGenerator
) -> None:
    """The 21st subtask is refused; deleting one makes room."""
    await setup_homework(hass, mocked)
    client = await hass_ws_client(hass)
    for n in range(20):
        sub = await add_ok(client, HOMEWORK, f"s{n}")
    response = await add(client, HOMEWORK, "one more")
    assert response["error"]["code"] == "too_many_subtasks"
    assert (await call(client, DELETE, subtask=sub["uid"]))["success"]
    assert (await add(client, HOMEWORK, "again"))["success"]


async def test_date_rules_when_the_item_is_today_or_past(
    hass: HomeAssistant,
    mocked: aioresponses,
    hass_ws_client: WebSocketGenerator,
    frozen_now: FrozenDateTimeFactory,
) -> None:
    """An item that is due today only takes today; a past item only its own date."""
    _, entry = await setup_homework(hass, mocked)
    client = await hass_ws_client(hass)
    today_item = next(
        i
        for i in entry.runtime_data.homework.items(CHILD_ID)
        if i.due_date.isoformat() == "2026-11-13"
    )
    past_item = next(
        i
        for i in entry.runtime_data.homework.items(CHILD_ID)
        if i.due_date.isoformat() == "2026-11-12"
    )
    response = await call(client, ADD, item=today_item.uid, title="x")
    assert response["result"]["subtasks"][0]["date"] == "2026-11-13"
    response = await call(client, ADD, item=past_item.uid, title="x")
    assert response["error"]["code"] == "invalid_date"
    response = await call(client, ADD, item=past_item.uid, title="x", date="2026-11-12")
    (sub,) = response["result"]["subtasks"]
    assert (sub["date"], sub["overdue"]) == ("2026-11-12", True)


async def test_update_subtask(
    hass: HomeAssistant, mocked: aioresponses, hass_ws_client: WebSocketGenerator
) -> None:
    """Change the title, the date, or both; the item is returned."""
    await setup_homework(hass, mocked)
    client = await hass_ws_client(hass)
    sub = await add_ok(client, HOMEWORK)
    response = await call(client, UPDATE, subtask=sub["uid"], title=" nieuw ")
    (changed,) = response["result"]["subtasks"]
    assert (changed["title"], changed["planned"]) == ("nieuw", "2026-11-13")
    response = await call(client, UPDATE, subtask=sub["uid"], date="2026-11-15")
    (changed,) = response["result"]["subtasks"]
    assert (changed["title"], changed["planned"]) == ("nieuw", "2026-11-15")
    response = await call(
        client, UPDATE, subtask=sub["uid"], title="t", date="2026-11-16"
    )
    (changed,) = response["result"]["subtasks"]
    assert (changed["title"], changed["date"]) == ("t", "2026-11-16")
    assert response["result"]["uid"] == uid(HOMEWORK)


@pytest.mark.parametrize(
    ("fields", "code"),
    [
        ({}, "invalid_format"),  # nothing to change
        ({"title": ""}, "invalid_format"),
        ({"title": "x" * 101}, "invalid_format"),
        ({"date": "nope"}, "invalid_format"),
        ({"date": "2026-11-12"}, "invalid_date"),
        ({"date": "2026-11-17"}, "invalid_date"),
    ],
)
async def test_update_subtask_validation(
    hass: HomeAssistant,
    mocked: aioresponses,
    hass_ws_client: WebSocketGenerator,
    fields: dict[str, Any],
    code: str,
) -> None:
    """Every invalid update is refused and changes nothing."""
    await setup_homework(hass, mocked)
    client = await hass_ws_client(hass)
    sub = await add_ok(client, HOMEWORK)
    response = await call(client, UPDATE, subtask=sub["uid"], **fields)
    assert response["error"]["code"] == code


async def test_unknown_subtasks_and_items(
    hass: HomeAssistant, mocked: aioresponses, hass_ws_client: WebSocketGenerator
) -> None:
    """subtask_not_found for an unknown id or a plain uid; item_not_found for items."""
    await setup_homework(hass, mocked)
    client = await hass_ws_client(hass)
    await add_ok(client, HOMEWORK)
    for command, fields in ((UPDATE, {"title": "x"}), (DELETE, {})):
        for subtask, code in (
            (f"{uid(HOMEWORK)}:sub:nope", "subtask_not_found"),
            (uid(HOMEWORK), "subtask_not_found"),
            ("garbage", "subtask_not_found"),
            ("school.magister.net:1001:1:sub:abc", "item_not_found"),
        ):
            response = await call(client, command, subtask=subtask, **fields)
            assert response["error"]["code"] == code, (command, subtask)
    for command, fields in ((UPDATE, {"title": "x"}), (DELETE, {})):
        await client.send_json_auto_id(
            {"type": command, "entity_id": "todo.nope", "subtask": "x", **fields}
        )
        assert (await client.receive_json())["error"]["code"] == "not_found"


async def test_delete_all_subtasks_restores_the_own_progress(
    hass: HomeAssistant, mocked: aioresponses, hass_ws_client: WebSocketGenerator
) -> None:
    """The item's own progress applies again when the last subtask is gone."""
    _, entry = await setup_homework(hass, mocked)
    manager = entry.runtime_data.homework
    await set_progress(hass, uid(HOMEWORK), 50)
    client = await hass_ws_client(hass)
    first = await add_ok(client, HOMEWORK, "a")
    second = await add_ok(client, HOMEWORK, "b")
    assert manager.progress(uid(HOMEWORK)) == 0  # derived
    await set_progress(hass, first["uid"], 100)
    assert manager.progress(uid(HOMEWORK)) == 50  # (100 + 0) / 2
    response = await call(client, DELETE, subtask=first["uid"])
    item = response["result"]
    assert (item["derived"], item["progress"]) == (True, 0)
    response = await call(client, DELETE, subtask=second["uid"])
    item = response["result"]
    assert (item["derived"], item["subtasks"]) == (False, [])
    assert (item["progress"], item["last_partial"]) == (50, 50)


async def test_commands_need_control_permission(
    hass: HomeAssistant,
    mocked: aioresponses,
    hass_ws_client: WebSocketGenerator,
    hass_admin_user: MockUser,
) -> None:
    """Read permission is not enough."""
    await setup_homework(hass, mocked)
    client = await hass_ws_client(hass)
    sub = await add_ok(client, HOMEWORK)
    hass_admin_user.mock_policy({"entities": {"entity_ids": {TODO_ID: {"read": True}}}})
    for command, fields in (
        (ADD, {"item": uid(HOMEWORK), "title": "x"}),
        (UPDATE, {"subtask": sub["uid"], "title": "x"}),
        (DELETE, {"subtask": sub["uid"]}),
        (SET_PROGRESS, {"item": sub["uid"], "progress": 50}),
    ):
        response = await call(client, command, **fields)
        assert response["error"]["code"] == "unauthorized", command


# -- progress -----------------------------------------------------------------------


async def test_set_progress_on_a_subtask(
    hass: HomeAssistant, mocked: aioresponses, hass_ws_client: WebSocketGenerator
) -> None:
    """Subtask progress is stored; the item's progress is derived; tick/untick."""
    _, entry = await setup_homework(hass, mocked)
    manager = entry.runtime_data.homework
    client = await hass_ws_client(hass)
    first = await add_ok(client, HOMEWORK, "a")
    second = await add_ok(client, HOMEWORK, "b")
    response = await call(client, SET_PROGRESS, item=first["uid"], progress=75)
    assert response["result"] == {"progress": 75, "completed": False}
    response = await call(client, SET_PROGRESS, item=first["uid"], progress=100)
    assert response["result"] == {"progress": 100, "completed": True}
    item = current_payload(hass)["items"]
    item = next(i for i in item if i["uid"] == uid(HOMEWORK))
    assert (item["progress"], item["completed"], item["derived"]) == (50, False, True)
    done = item["subtasks"][0]
    assert (done["progress"], done["completed"], done["last_partial"]) == (
        100,
        True,
        75,
    )
    # untick restores the last partial value, and clears the completion date
    response = await call(client, SET_PROGRESS, item=first["uid"], progress=75)
    assert response["result"] == {"progress": 75, "completed": False}
    assert manager.find_subtask(first["uid"]).completed_on is None  # type: ignore[union-attr]
    await call(client, SET_PROGRESS, item=first["uid"], progress=100)
    await call(client, SET_PROGRESS, item=second["uid"], progress=100)
    assert manager.progress(uid(HOMEWORK)) == 100
    assert manager.is_completed(manager.find_item(CHILD_ID, uid(HOMEWORK)))  # type: ignore[arg-type]
    # the stored own progress of the item is untouched
    assert manager.find_subtask(first["uid"]).completed_on.isoformat() == "2026-11-13"  # type: ignore[union-attr]


async def test_set_progress_errors(
    hass: HomeAssistant, mocked: aioresponses, hass_ws_client: WebSocketGenerator
) -> None:
    """Items with subtasks are refused; unknown subtasks are not found."""
    await setup_homework(hass, mocked)
    client = await hass_ws_client(hass)
    sub = await add_ok(client, HOMEWORK)
    response = await call(client, SET_PROGRESS, item=uid(HOMEWORK), progress=50)
    assert response["error"]["code"] == "item_has_subtasks"
    for item in (f"{uid(HOMEWORK)}:sub:nope", "school.magister.net:1001:1:sub:x"):
        response = await call(client, SET_PROGRESS, item=item, progress=50)
        assert response["error"]["code"] == "item_not_found"
    assert (await call(client, SET_PROGRESS, item=sub["uid"], progress=50))["success"]
    # the service refuses it too, with a translated error
    with pytest.raises(ServiceValidationError) as err:
        await set_progress(hass, uid(HOMEWORK), 50)
    assert err.value.translation_key == "homework_item_has_subtasks"
    # the same value again is a no-op that still answers
    assert (await call(client, SET_PROGRESS, item=sub["uid"], progress=50))["success"]
    await call(client, DELETE, subtask=sub["uid"])
    assert (await call(client, SET_PROGRESS, item=uid(HOMEWORK), progress=50))[
        "success"
    ]


# -- disabled items -----------------------------------------------------------------


async def test_disabled_items_hide_their_subtasks(
    hass: HomeAssistant, mocked: aioresponses, hass_ws_client: WebSocketGenerator
) -> None:
    """Disabled: no subtasks in the payload, list or counts; errors; restored."""
    _, entry = await setup_homework(hass, mocked)
    manager = entry.runtime_data.homework
    client = await hass_ws_client(hass)
    sub = await add_ok(client, PROEFWERK)
    await add_ok(client, PROEFWERK, "second", date="2026-11-14")
    count = sensor(hass, TODO_ID).state
    week = dict(sensor(hass, NEXT_WEEK).attributes)
    assert (await todo_items(hass))[sub["uid"]]["summary"].startswith("↳ ")
    await hass.services.async_call(
        DOMAIN,
        "set_homework_override",
        {"entity_id": TODO_ID, "appointment": uid(PROEFWERK), "mode": "disable"},
        blocking=True,
    )
    await hass.async_block_till_done()
    items = await todo_items(hass)
    assert sub["uid"] not in items
    assert items[uid(PROEFWERK)]["status"] == "completed"
    assert sensor(hass, TODO_ID).state == str(int(count) - 2)
    payload = current_payload(hass)
    item = payload_item(payload, PROEFWERK)
    assert (item["subtasks"], item["derived"], item["completed"]) == ([], False, True)
    # no subtask operations
    for command, fields in (
        (ADD, {"item": uid(PROEFWERK), "title": "x"}),
        (UPDATE, {"subtask": sub["uid"], "title": "x"}),
        (DELETE, {"subtask": sub["uid"]}),
        (SET_PROGRESS, {"item": sub["uid"], "progress": 50}),
    ):
        response = await call(client, command, **fields)
        assert response["error"]["code"] == "item_disabled", command
    assert manager.find_subtask(sub["uid"]) is None
    # restored: everything is back, subtasks included
    await hass.services.async_call(
        DOMAIN,
        "set_homework_override",
        {"entity_id": TODO_ID, "appointment": uid(PROEFWERK), "mode": "clear"},
        blocking=True,
    )
    await hass.async_block_till_done()
    assert sensor(hass, TODO_ID).state == count
    assert dict(sensor(hass, NEXT_WEEK).attributes) == week
    assert sub["uid"] in await todo_items(hass)


# -- to-do list and count -----------------------------------------------------------


async def test_subtasks_in_the_todo_list(
    hass: HomeAssistant, mocked: aioresponses, hass_ws_client: WebSocketGenerator
) -> None:
    """Rows like ``↳ Proefwerk: title`` due on the current date; ticking works."""
    _, entry = await setup_homework(hass, mocked)
    client = await hass_ws_client(hass)
    first = await add_ok(client, PROEFWERK, "woordjes")
    second = await add_ok(client, PROEFWERK, "grammatica", date="2026-11-18")
    items = await todo_items(hass)
    row = items[first["uid"]]
    assert row["summary"] == "↳ Duitse taal: woordjes"
    assert (row["status"], row["due"]) == ("needs_action", "2026-11-13")
    assert items[second["uid"]]["due"] == "2026-11-18"
    parent = items[uid(PROEFWERK)]
    assert parent["status"] == "needs_action"
    assert parent["due"].startswith("2026-11-19")
    # tick and untick through HA's to-do service
    await hass.services.async_call(
        "todo",
        "update_item",
        {"entity_id": TODO_ID, "item": first["uid"], "status": "completed"},
        blocking=True,
    )
    items = await todo_items(hass)
    assert items[first["uid"]]["status"] == "completed"
    assert items[uid(PROEFWERK)]["description"].endswith("(50 %)")
    await hass.services.async_call(
        "todo",
        "update_item",
        {"entity_id": TODO_ID, "item": second["uid"], "status": "completed"},
        blocking=True,
    )
    assert (await todo_items(hass))[uid(PROEFWERK)]["status"] == "completed"
    await hass.services.async_call(
        "todo",
        "update_item",
        {"entity_id": TODO_ID, "item": second["uid"], "status": "needs_action"},
        blocking=True,
    )
    items = await todo_items(hass)
    assert items[second["uid"]]["status"] == "needs_action"
    assert items[uid(PROEFWERK)]["status"] == "needs_action"
    # a partial subtask shows its percentage; renaming it from HA is refused
    await set_progress(hass, second["uid"], 25)
    assert (await todo_items(hass))[second["uid"]]["description"] == "(25 %)"
    with pytest.raises(ServiceValidationError) as err:
        await hass.services.async_call(
            "todo",
            "update_item",
            {"entity_id": TODO_ID, "item": second["uid"], "rename": "x"},
            blocking=True,
        )
    assert err.value.translation_key == "homework_status_only"
    assert entry.runtime_data.homework.progress(second["uid"]) == 25


async def test_ticking_a_parent_with_subtasks_is_refused(
    hass: HomeAssistant, mocked: aioresponses, hass_ws_client: WebSocketGenerator
) -> None:
    """HA's to-do list cannot tick an item that has subtasks."""
    await setup_homework(hass, mocked)
    client = await hass_ws_client(hass)
    await add_ok(client, PROEFWERK)
    with pytest.raises(ServiceValidationError) as err:
        await hass.services.async_call(
            "todo",
            "update_item",
            {"entity_id": TODO_ID, "item": uid(PROEFWERK), "status": "completed"},
            blocking=True,
        )
    assert err.value.translation_key == "homework_item_has_subtasks"


async def test_count_counts_open_entries_from_today(
    hass: HomeAssistant, mocked: aioresponses, hass_ws_client: WebSocketGenerator
) -> None:
    """An item with subtasks is replaced by its open subtasks in the count."""
    await setup_homework(hass, mocked)
    client = await hass_ws_client(hass)
    before = int(sensor(hass, TODO_ID).state)
    first = await add_ok(client, PROEFWERK, "a")  # 1 open item -> 1 open subtask
    assert int(sensor(hass, TODO_ID).state) == before
    second = await add_ok(client, PROEFWERK, "b")
    third = await add_ok(client, PROEFWERK, "c", date="2026-11-15")
    assert int(sensor(hass, TODO_ID).state) == before + 2
    await set_progress(hass, first["uid"], 100)
    assert int(sensor(hass, TODO_ID).state) == before + 1
    for sub in (second, third):
        await set_progress(hass, sub["uid"], 100)
    assert int(sensor(hass, TODO_ID).state) == before - 1  # the item is done
    await set_progress(hass, third["uid"], 0)
    assert int(sensor(hass, TODO_ID).state) == before


# -- sensors and the payload progress ---------------------------------------------


async def test_sensors_and_payload_progress_use_the_entries(
    hass: HomeAssistant, mocked: aioresponses, hass_ws_client: WebSocketGenerator
) -> None:
    """The bars, the sensors and the payload come from the same entries."""
    _, entry = await setup_homework(hass, mocked)
    manager = entry.runtime_data.homework
    client = await hass_ws_client(hass)
    before = {
        name: (sensor(hass, name).state, dict(sensor(hass, name).attributes))
        for name in (NEXT_DAY, WEEK, NEXT_WEEK)
    }
    test = manager.find_item(CHILD_ID, uid(PROEFWERK))
    assert test is not None and test.due_date.isoformat() == "2026-11-19"
    first = await add_ok(client, PROEFWERK, "a")  # Friday: this week (Sat 7 - Fri 13)
    await add_ok(client, PROEFWERK, "b", date="2026-11-15")  # next week
    await add_ok(client, PROEFWERK, "c", date="2026-11-18")  # next week
    # the test (one entry in next week) became 1 entry in this week + 2 in next week
    week, next_week = sensor(hass, WEEK), sensor(hass, NEXT_WEEK)
    assert week.attributes["items"] == before[WEEK][1]["items"] + 1
    assert next_week.attributes["items"] == before[NEXT_WEEK][1]["items"] + 1
    assert next_week.attributes["tests"] == before[NEXT_WEEK][1]["tests"] + 1
    await set_progress(hass, first["uid"], 100)
    assert sensor(hass, WEEK).attributes["completed"] == (
        before[WEEK][1]["completed"] + 1
    )
    assert float(sensor(hass, WEEK).state) > float(before[WEEK][0])
    payload = current_payload(hass)
    for name, period in (
        (NEXT_DAY, "next_day"),
        (WEEK, "week"),
        (NEXT_WEEK, "next_week"),
    ):
        state = sensor(hass, name)
        assert payload["progress"][period] == {
            "value": float(state.state),
            "items": state.attributes["items"],
            "completed": state.attributes["completed"],
        }
    # the weights in use still list the subject of the item
    assert "Duitse taal" in sensor(hass, NEXT_WEEK).attributes["weights"]["subjects"]


async def test_weights_of_a_split_item_add_up(
    hass: HomeAssistant, mocked: aioresponses, hass_ws_client: WebSocketGenerator
) -> None:
    """Splitting an item over periods keeps its weight: the average is unchanged."""
    _, entry = await setup_homework(
        hass,
        mocked,
        options={CONF_WEIGHTS: {str(CHILD_ID): {"types": {"test": 4.0}}}},
    )
    manager = entry.runtime_data.homework
    client = await hass_ws_client(hass)
    today = manager.today()
    total = sum(e.weight for e in manager.entries(CHILD_ID, today))
    for n, day in enumerate(("2026-11-13", "2026-11-14", "2026-11-18", "2026-11-19")):
        await add_ok(client, PROEFWERK, f"s{n}", date=day)
    assert sum(e.weight for e in manager.entries(CHILD_ID, today)) == pytest.approx(
        total
    )
    mine = [e for e in manager.entries(CHILD_ID, today) if e.item_uid == uid(PROEFWERK)]
    assert [e.weight for e in mine] == [1.0, 1.0, 1.0, 1.0]


# -- midnight -----------------------------------------------------------------------


async def test_subtasks_roll_over_at_midnight(
    hass: HomeAssistant,
    mocked: aioresponses,
    hass_ws_client: WebSocketGenerator,
    frozen_now: FrozenDateTimeFactory,
) -> None:
    """Only the midnight timer moves open subtasks: list, payload, count, sensors."""
    _, entry = await setup_homework(hass, mocked)
    client = await hass_ws_client(hass)
    open_sub = await add_ok(client, HOMEWORK, "open")  # planned Friday
    done_sub = await add_ok(client, HOMEWORK, "done")
    await set_progress(hass, done_sub["uid"], 100)  # completed on Friday
    count = int(sensor(hass, TODO_ID).state)
    manager = entry.runtime_data.homework
    # the other open entries of Friday stop counting at midnight; the subtask rolls on
    friday = [
        e
        for e in manager.entries(CHILD_ID, manager.today())
        if e.day.isoformat() == "2026-11-13"
        and e.progress < 100
        and e.uid != open_sub["uid"]
    ]
    assert (await todo_items(hass))[open_sub["uid"]]["due"] == "2026-11-13"
    # shortly before midnight nothing changes (a step under 30 minutes: no refresh)
    frozen_now.move_to("2026-11-13 22:45:00+00:00")
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert (await todo_items(hass))[open_sub["uid"]]["due"] == "2026-11-13"
    frozen_now.move_to("2026-11-13 23:00:01+00:00")  # Saturday 00:00:01
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    items = await todo_items(hass)
    assert items[open_sub["uid"]]["due"] == "2026-11-14"
    assert items[done_sub["uid"]]["due"] == "2026-11-13"  # done: sticky
    item = payload_item(current_payload(hass), HOMEWORK)
    by_title = {s["title"]: s for s in item["subtasks"]}
    assert by_title["open"]["date"] == "2026-11-14"
    assert by_title["open"]["planned"] == "2026-11-13"
    assert by_title["done"]["date"] == "2026-11-13"
    assert int(sensor(hass, TODO_ID).state) == count - len(friday)
    # the item's date (Monday) passes: overdue, stays on the item date
    frozen_now.move_to("2026-11-16 22:45:00+00:00")
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    frozen_now.move_to("2026-11-16 23:00:01+00:00")  # Tuesday 00:00:01
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    item = payload_item(current_payload(hass), HOMEWORK)
    by_title = {s["title"]: s for s in item["subtasks"]}
    assert (by_title["open"]["date"], by_title["open"]["overdue"]) == (
        "2026-11-16",
        True,
    )
    assert by_title["done"]["overdue"] is False
    assert (await todo_items(hass))[open_sub["uid"]]["due"] == "2026-11-16"


async def test_midnight_pushes_a_changed_payload(
    hass: HomeAssistant,
    mocked: aioresponses,
    hass_ws_client: WebSocketGenerator,
    frozen_now: FrozenDateTimeFactory,
) -> None:
    """The existing subscriber gets a new event when a subtask rolls over."""
    await setup_homework(hass, mocked)
    client = await hass_ws_client(hass)
    await add_ok(client, HOMEWORK, "open")
    pushed: list[dict[str, Any]] = []
    async_subscribe(hass, TODO_ID, pushed.append)
    frozen_now.move_to("2026-11-13 22:45:00+00:00")
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert pushed == []  # nothing changed yet: no duplicate push
    frozen_now.move_to("2026-11-13 23:00:01+00:00")
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    (event,) = pushed
    assert payload_item(event, HOMEWORK)["subtasks"][0]["date"] == "2026-11-14"


# -- services -----------------------------------------------------------------------


async def test_subtask_services(hass: HomeAssistant, mocked: aioresponses) -> None:
    """add, update and delete as services; errors are translated."""
    _, entry = await setup_homework(hass, mocked)
    manager = entry.runtime_data.homework

    async def run(name: str, **data: Any) -> None:
        await hass.services.async_call(
            DOMAIN, name, {"entity_id": TODO_ID, **data}, blocking=True
        )
        await hass.async_block_till_done()

    await run("add_homework_subtask", item=uid(HOMEWORK), title=" H4 ")
    await run("add_homework_subtask", item=uid(HOMEWORK), title="H5", date="2026-11-15")
    item = manager.find_item(CHILD_ID, uid(HOMEWORK))
    assert item is not None
    first, second = item.subtasks
    assert (first.title, first.planned.isoformat()) == ("H4", "2026-11-13")
    assert second.planned.isoformat() == "2026-11-15"
    sub_uid = f"{uid(HOMEWORK)}:sub:{first.id}"
    await run(
        "update_homework_subtask", subtask=sub_uid, title="H4 af", date="2026-11-14"
    )
    item = manager.find_item(CHILD_ID, uid(HOMEWORK))
    assert item is not None
    assert (item.subtasks[0].title, item.subtasks[0].planned.isoformat()) == (
        "H4 af",
        "2026-11-14",
    )
    await run("delete_homework_subtask", subtask=sub_uid)
    item = manager.find_item(CHILD_ID, uid(HOMEWORK))
    assert item is not None and len(item.subtasks) == 1

    cases: list[tuple[str, dict[str, Any], str]] = [
        (
            "add_homework_subtask",
            {"item": "x", "title": "t"},
            "homework_item_not_found",
        ),
        (
            "add_homework_subtask",
            {"item": uid(HOMEWORK), "title": "t", "date": "2026-11-12"},
            "homework_invalid_date",
        ),
        (
            "update_homework_subtask",
            {"subtask": f"{uid(HOMEWORK)}:sub:zz", "title": "t"},
            "homework_subtask_not_found",
        ),
        (
            "update_homework_subtask",
            {"subtask": f"{uid(HOMEWORK)}:sub:{second.id}"},
            "homework_nothing_to_update",
        ),
        (
            "delete_homework_subtask",
            {"subtask": f"{uid(HOMEWORK)}:sub:zz"},
            "homework_subtask_not_found",
        ),
    ]
    for name, data, key in cases:
        with pytest.raises(ServiceValidationError) as err:
            await run(name, **data)
        assert err.value.translation_key == key, name
    # the 21st
    for n in range(19):
        await run("add_homework_subtask", item=uid(HOMEWORK), title=f"s{n}")
    with pytest.raises(ServiceValidationError) as err:
        await run("add_homework_subtask", item=uid(HOMEWORK), title="more")
    assert err.value.translation_key == "homework_too_many_subtasks"
    # invalid titles are rejected by the schema
    for title in ("", "   ", "x" * 101):
        with pytest.raises(Exception, match="title"):
            await run("add_homework_subtask", item=uid(HOMEWORK), title=title)


async def test_disabled_item_services(
    hass: HomeAssistant, mocked: aioresponses
) -> None:
    """The services refuse a disabled item with the translated error."""
    await setup_homework(hass, mocked)
    await hass.services.async_call(
        DOMAIN,
        "set_homework_override",
        {"entity_id": TODO_ID, "appointment": uid(PROEFWERK), "mode": "disable"},
        blocking=True,
    )
    with pytest.raises(ServiceValidationError) as err:
        await hass.services.async_call(
            DOMAIN,
            "add_homework_subtask",
            {"entity_id": TODO_ID, "item": uid(PROEFWERK), "title": "t"},
            blocking=True,
        )
    assert err.value.translation_key == "homework_item_disabled"


# -- store --------------------------------------------------------------------------

KEY = "magister.homework"


def stored_file(entry_id: str, items: dict[str, Any], minor: int) -> dict[str, Any]:
    """A store file with the given items."""
    key = f"{DOMAIN}.homework.{entry_id}"
    return {
        "version": 1,
        "minor_version": minor,
        "key": key,
        "data": {"items": items},
    }


BASE = {"progress": 0, "last_partial": 0, "updated": "", "labels": []}


async def test_store_1_4_0_loads_and_is_saved_as_minor_4(
    hass: HomeAssistant, mocked: aioresponses, hass_storage: dict[str, Any]
) -> None:
    """A 1.4.0 file (minor 3, no subtasks) loads unchanged; subtasks persist."""
    entry = make_entry()
    key = f"{DOMAIN}.homework.{entry.entry_id}"
    hass_storage[key] = stored_file(
        entry.entry_id,
        {
            uid(HOMEWORK): {**BASE, "progress": 50, "last_partial": 50},
            uid(PROEFWERK): {**BASE, "override": {"mode": "disable"}},
        },
        3,
    )
    FakeMagister(mocked)
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    manager = entry.runtime_data.homework
    assert manager.progress(uid(HOMEWORK)) == 50
    assert manager.stored_entries == 2
    item = manager.find_item(CHILD_ID, uid(HOMEWORK))
    assert item is not None and item.subtasks == ()
    manager.add_subtask(CHILD_ID, uid(HOMEWORK), "t", None)
    assert await hass.config_entries.async_unload(entry.entry_id)
    saved = hass_storage[key]
    assert (saved["version"], saved["minor_version"]) == (1, 4)
    (stored_sub,) = saved["data"]["items"][uid(HOMEWORK)]["subtasks"]
    assert set(stored_sub) == {
        "id",
        "title",
        "planned",
        "progress",
        "last_partial",
        "completed_on",
    }
    assert "subtasks" not in saved["data"]["items"][uid(PROEFWERK)]


async def test_store_loads_subtasks_leniently(
    hass: HomeAssistant, mocked: aioresponses, hass_storage: dict[str, Any]
) -> None:
    """Unusable subtasks are dropped, values are clamped, at most 20 are kept."""
    entry = make_entry()
    good = {
        "id": "a1",
        "title": "  ok  ",
        "planned": "2026-11-14",
        "progress": 400,
        "last_partial": 150,
        "completed_on": "2026-11-13",
    }
    many = [{"id": f"m{n}", "title": "t", "planned": "2026-11-13"} for n in range(25)]
    hass_storage[f"{DOMAIN}.homework.{entry.entry_id}"] = stored_file(
        entry.entry_id,
        {
            uid(HOMEWORK): {
                **BASE,
                "subtasks": [
                    good,
                    good,  # duplicate id
                    "junk",
                    {"id": "", "title": "t", "planned": "2026-11-13"},
                    {"id": "b", "title": "", "planned": "2026-11-13"},
                    {"id": "c", "title": 5, "planned": "2026-11-13"},
                    {"id": "d", "title": "t", "planned": "nope"},
                    {"id": "e", "title": "x" * 150, "planned": "2026-11-13"},
                    {
                        "id": "f",
                        "title": "t",
                        "planned": "2026-11-13",
                        "progress": 50,
                        "completed_on": "2026-11-13",  # not done: dropped
                    },
                ],
            },
            uid(PROEFWERK): {**BASE, "subtasks": many},
            uid(100066): {**BASE, "subtasks": "junk"},
            uid(100067): "junk",
            uid(100068): {**BASE, "subtasks": [{"id": "x"}]},
        },
        3,
    )
    FakeMagister(mocked)
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    manager = entry.runtime_data.homework
    item = manager.find_item(CHILD_ID, uid(HOMEWORK))
    assert item is not None
    by_id = {s.id: s for s in item.subtasks}
    assert list(by_id) == ["a1", "e", "f"]
    assert (by_id["a1"].title, by_id["a1"].progress, by_id["a1"].last_partial) == (
        "ok",
        100,
        99,
    )
    assert by_id["a1"].completed_on is not None
    assert len(by_id["e"].title) == 100
    assert (by_id["f"].progress, by_id["f"].completed_on) == (50, None)
    big = manager.find_item(CHILD_ID, uid(PROEFWERK))
    assert big is not None and len(big.subtasks) == 20
    # entries without usable subtasks are plain entries
    assert manager.stored_entries == 4  # the junk entry is dropped


async def test_pruning_keeps_the_entry_while_it_has_subtasks(
    hass: HomeAssistant,
    mocked: aioresponses,
    frozen_now: FrozenDateTimeFactory,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """The item entry stays while subtasks exist; subtasks go with the item entry."""
    fake, entry = await setup_homework(hass, mocked)
    manager = entry.runtime_data.homework
    client = await hass_ws_client(hass)
    sub = await add_ok(client, HOMEWORK)
    assert manager.stored_entries == 1
    # deleting the only subtask of an otherwise empty entry drops the entry
    await call(client, DELETE, subtask=sub["uid"])
    assert manager.stored_entries == 0
    sub = await add_ok(client, HOMEWORK)
    # a subtask on an item with progress: the entry survives progress being reset
    await set_progress(hass, uid(PROEFWERK), 50)
    await set_progress(hass, uid(PROEFWERK), 0)
    original = copy.deepcopy(fake.appointments[CHILD_ID])
    fake.appointments[CHILD_ID] = [a for a in original if a["Id"] != HOMEWORK]
    coordinator = entry.runtime_data.coordinator
    await coordinator.async_refresh()
    await hass.async_block_till_done()
    assert uid(HOMEWORK) not in await todo_items(hass)
    assert manager.stored_entries == 1
    frozen_now.tick(timedelta(days=13))
    await coordinator.async_refresh()
    assert manager.stored_entries == 1
    # back again: the subtask is still there
    fake.appointments[CHILD_ID] = original
    await coordinator.async_refresh()
    await hass.async_block_till_done()
    assert sub["uid"] in await todo_items(hass)
    # gone for more than 14 days: the entry and its subtasks are pruned
    fake.appointments[CHILD_ID] = [a for a in original if a["Id"] != HOMEWORK]
    await coordinator.async_refresh()
    frozen_now.tick(timedelta(days=15))
    await coordinator.async_refresh()
    await hass.async_block_till_done()
    assert manager.stored_entries == 0


# -- diagnostics --------------------------------------------------------------------


async def test_diagnostics_have_subtask_counts_only(
    hass: HomeAssistant, mocked: aioresponses, hass_ws_client: WebSocketGenerator
) -> None:
    """Counts of subtasks; no titles."""
    _, entry = await setup_homework(hass, mocked)
    client = await hass_ws_client(hass)
    first = await add_ok(client, HOMEWORK, "geheime titel")
    await add_ok(client, HOMEWORK, "tweede")
    await add_ok(client, PROEFWERK, "derde")
    await set_progress(hass, first["uid"], 100)
    diagnostics = await async_get_config_entry_diagnostics(hass, entry)
    (child,) = diagnostics["children"]
    assert child["homework"]["subtasks"] == {
        "items_with_subtasks": 2,
        "total": 3,
        "done": 1,
        "overdue": 0,
    }
    text = str(diagnostics)
    assert "geheime" not in text and "tweede" not in text and "derde" not in text


async def test_manager_ignores_own_progress_of_an_item_with_subtasks(
    hass: HomeAssistant, mocked: aioresponses
) -> None:
    """Defensive: the manager does not store own progress while subtasks exist."""
    _, entry = await setup_homework(hass, mocked)
    manager = entry.runtime_data.homework
    manager.add_subtask(CHILD_ID, uid(HOMEWORK), "t", None)
    manager.set_progress(uid(HOMEWORK), 80)
    assert manager.progress(uid(HOMEWORK)) == 0
    assert manager.stored_entries == 1
    sub = manager.find_item(CHILD_ID, uid(HOMEWORK)).subtasks[0]  # type: ignore[union-attr]
    manager.delete_subtask(CHILD_ID, f"{uid(HOMEWORK)}:sub:{sub.id}")
    assert manager.progress(uid(HOMEWORK)) == 0
