"""WebSocket API of the homework planner."""

from __future__ import annotations

import copy
from typing import Any

import pytest
from aioresponses import aioresponses
from freezegun.api import FrozenDateTimeFactory
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.typing import WebSocketGenerator

from .ha_helpers import NOW
from .test_homework import TODO_ID, set_progress, setup_homework, uid

SUBSCRIBE = "magister/homework/subscribe"
SET_PROGRESS = "magister/homework/set_progress"


@pytest.fixture(autouse=True)
async def frozen_now(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> FrozenDateTimeFactory:
    """Friday 13 November 2026."""
    await hass.config.async_set_time_zone("Europe/Amsterdam")
    freezer.move_to(NOW)
    return freezer


async def test_subscribe_sends_the_list_and_pushes_changes(
    hass: HomeAssistant, mocked: aioresponses, hass_ws_client: WebSocketGenerator
) -> None:
    """The first event has every item; later events follow progress changes."""
    await setup_homework(hass, mocked)
    client = await hass_ws_client(hass)
    await client.send_json_auto_id({"type": SUBSCRIBE, "entity_id": TODO_ID})
    result = await client.receive_json()
    assert result["success"]
    event = await client.receive_json()
    payload = event["event"]
    assert payload["available"] is True
    assert len(payload["items"]) == 53
    item = next(i for i in payload["items"] if i["uid"] == uid(100065))
    assert item == {
        "uid": uid(100065),
        "due": "2026-11-16T10:00:00+01:00",
        "date": "2026-11-16",
        "all_day": False,
        "lesson_hour": 3,
        "subject": "wiskunde",
        "info_type": 1,
        "label": "Huiswerk",
        "is_test": False,
        "text": item["text"],
        "cancelled": False,
        "has_attachments": False,
        "progress": 0,
        "completed": False,
        "last_partial": 0,
    }
    assert item["text"].startswith("maken: H3, opgave 31")
    cancelled = next(i for i in payload["items"] if i["uid"] == uid(100131))
    assert cancelled["cancelled"] is True
    test = next(i for i in payload["items"] if i["uid"] == uid(100084))
    assert (test["label"], test["is_test"], test["info_type"]) == ("Proefwerk", True, 2)

    await set_progress(hass, uid(100065), 50)
    event = await client.receive_json()
    changed = next(i for i in event["event"]["items"] if i["uid"] == uid(100065))
    assert (changed["progress"], changed["completed"]) == (50, False)
    assert changed["last_partial"] == 50

    await set_progress(hass, uid(100065), 100)
    event = await client.receive_json()
    changed = next(i for i in event["event"]["items"] if i["uid"] == uid(100065))
    assert (changed["progress"], changed["completed"], changed["last_partial"]) == (
        100,
        True,
        50,
    )


async def test_set_progress_command(
    hass: HomeAssistant, mocked: aioresponses, hass_ws_client: WebSocketGenerator
) -> None:
    """The command sets the progress and answers with the new state."""
    _, entry = await setup_homework(hass, mocked)
    client = await hass_ws_client(hass)
    await client.send_json_auto_id(
        {
            "type": SET_PROGRESS,
            "entity_id": TODO_ID,
            "item": uid(100065),
            "progress": 75,
        }
    )
    result = await client.receive_json()
    assert result["success"]
    assert result["result"] == {"progress": 75, "completed": False}
    assert entry.runtime_data.homework.progress(uid(100065)) == 75
    await client.send_json_auto_id(
        {
            "type": SET_PROGRESS,
            "entity_id": TODO_ID,
            "item": uid(100065),
            "progress": 100,
        }
    )
    result = await client.receive_json()
    assert result["result"] == {"progress": 100, "completed": True}


@pytest.mark.parametrize(
    ("message", "code"),
    [
        ({"entity_id": "todo.nope", "item": "x", "progress": 1}, "not_found"),
        (
            {"entity_id": "todo.kind_school_homework", "item": "x", "progress": 1},
            "item_not_found",
        ),
        (
            {"entity_id": "todo.kind_school_homework", "item": "x", "progress": 101},
            "invalid_format",
        ),
        (
            {"entity_id": "todo.kind_school_homework", "item": "x", "progress": -1},
            "invalid_format",
        ),
        (
            {"entity_id": "todo.kind_school_homework", "item": "x", "progress": "5"},
            "invalid_format",
        ),
        (
            {
                "entity_id": "sensor.kind_school_homework_week",
                "item": "x",
                "progress": 1,
            },
            "invalid_format",
        ),
    ],
)
async def test_set_progress_errors(
    hass: HomeAssistant,
    mocked: aioresponses,
    hass_ws_client: WebSocketGenerator,
    message: dict[str, Any],
    code: str,
) -> None:
    """Unknown lists, unknown items and bad values are errors."""
    await setup_homework(hass, mocked)
    client = await hass_ws_client(hass)
    await client.send_json_auto_id({"type": SET_PROGRESS, **message})
    result = await client.receive_json()
    assert not result["success"]
    assert result["error"]["code"] == code


async def test_item_of_another_list_is_not_writable(
    hass: HomeAssistant, mocked: aioresponses, hass_ws_client: WebSocketGenerator
) -> None:
    """Only the child's own items can be changed through that child's list."""
    await setup_homework(hass, mocked)
    client = await hass_ws_client(hass)
    foreign = "school.magister.net:9999:100065"
    await client.send_json_auto_id(
        {"type": SET_PROGRESS, "entity_id": TODO_ID, "item": foreign, "progress": 50}
    )
    result = await client.receive_json()
    assert result["error"]["code"] == "item_not_found"


async def test_subscribe_errors_and_unsubscribe(
    hass: HomeAssistant, mocked: aioresponses, hass_ws_client: WebSocketGenerator
) -> None:
    """Unknown entities fail; an unsubscribed client gets no more events."""
    await setup_homework(hass, mocked)
    client = await hass_ws_client(hass)
    await client.send_json_auto_id({"type": SUBSCRIBE, "entity_id": "todo.nope"})
    assert (await client.receive_json())["error"]["code"] == "not_found"
    await client.send_json_auto_id(
        {"type": SUBSCRIBE, "entity_id": "calendar.kind_school_agenda"}
    )
    assert (await client.receive_json())["error"]["code"] == "invalid_format"

    await client.send_json(
        {"id": 50, "type": SUBSCRIBE, "entity_id": TODO_ID},
    )
    assert (await client.receive_json())["success"]
    await client.receive_json()
    await client.send_json({"id": 51, "type": "unsubscribe_events", "subscription": 50})
    assert (await client.receive_json())["success"]
    await set_progress(hass, uid(100065), 25)
    await client.send_json({"id": 52, "type": "ping"})
    assert (await client.receive_json())["type"] == "pong"


async def test_subscription_survives_a_reload(
    hass: HomeAssistant, mocked: aioresponses, hass_ws_client: WebSocketGenerator
) -> None:
    """After a reload the same subscription gets the list of the new entity."""
    _, entry = await setup_homework(hass, mocked)
    client = await hass_ws_client(hass)
    await client.send_json_auto_id({"type": SUBSCRIBE, "entity_id": TODO_ID})
    await client.receive_json()
    await client.receive_json()
    await set_progress(hass, uid(100065), 50)
    await client.receive_json()
    assert await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()
    event = await client.receive_json()
    changed = next(i for i in event["event"]["items"] if i["uid"] == uid(100065))
    assert changed["progress"] == 50


async def test_coordinator_refresh_is_pushed(
    hass: HomeAssistant, mocked: aioresponses, hass_ws_client: WebSocketGenerator
) -> None:
    """New Magister data reaches the card."""
    fake, entry = await setup_homework(hass, mocked)
    client = await hass_ws_client(hass)
    await client.send_json_auto_id({"type": SUBSCRIBE, "entity_id": TODO_ID})
    await client.receive_json()
    await client.receive_json()
    fake.appointments[next(iter(fake.appointments))] = copy.deepcopy(
        [a for a in next(iter(fake.appointments.values())) if a["Id"] != 100065]
    )
    await entry.runtime_data.coordinator.async_refresh()
    await hass.async_block_till_done()
    event = await client.receive_json()
    assert len(event["event"]["items"]) == 52
