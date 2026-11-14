"""WebSocket API of the homework planner."""

from __future__ import annotations

import copy
from typing import Any

import pytest
from aioresponses import aioresponses
from freezegun.api import FrozenDateTimeFactory
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import (
    MockUser,
    async_fire_time_changed,
)
from pytest_homeassistant_custom_component.typing import WebSocketGenerator

from custom_components.magister.const import CONF_WEEKS_AHEAD, CONF_WEIGHTS, DOMAIN
from custom_components.magister.homework import async_subscribe

from .ha_helpers import CHILD_ID, NOW
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
        "manual_labels": [],
        "override": None,
        "disabled": False,
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


async def test_set_progress_rejects_booleans_and_returns_stored_values(
    hass: HomeAssistant, mocked: aioresponses, hass_ws_client: WebSocketGenerator
) -> None:
    """True is invalid; the result is what the manager stored."""
    _, entry = await setup_homework(hass, mocked)
    client = await hass_ws_client(hass)
    await client.send_json_auto_id(
        {
            "type": SET_PROGRESS,
            "entity_id": TODO_ID,
            "item": uid(100065),
            "progress": True,
        }
    )
    result = await client.receive_json()
    assert result["error"]["code"] == "invalid_format"
    assert entry.runtime_data.homework.progress(uid(100065)) == 0


async def test_unsubscribe_and_close_clear_the_hub(
    hass: HomeAssistant, mocked: aioresponses, hass_ws_client: WebSocketGenerator
) -> None:
    """The subscriber list is emptied by unsubscribe and by closing the socket."""
    await setup_homework(hass, mocked)
    hub = hass.data[f"{DOMAIN}_homework_subscribers"]
    client = await hass_ws_client(hass)
    await client.send_json({"id": 5, "type": SUBSCRIBE, "entity_id": TODO_ID})
    await client.receive_json()
    await client.receive_json()
    assert len(hub[TODO_ID]) == 1
    await client.send_json({"id": 6, "type": "unsubscribe_events", "subscription": 5})
    assert (await client.receive_json())["success"]
    assert TODO_ID not in hub

    await client.send_json({"id": 7, "type": SUBSCRIBE, "entity_id": TODO_ID})
    await client.receive_json()
    await client.receive_json()
    assert len(hub[TODO_ID]) == 1
    await client.close()
    await hass.async_block_till_done()
    assert TODO_ID not in hub


async def test_removal_pushes_unavailable(
    hass: HomeAssistant, mocked: aioresponses, hass_ws_client: WebSocketGenerator
) -> None:
    """Unloading the entry tells subscribers; they keep the last items."""
    _, entry = await setup_homework(hass, mocked)
    client = await hass_ws_client(hass)
    await client.send_json_auto_id({"type": SUBSCRIBE, "entity_id": TODO_ID})
    await client.receive_json()
    await client.receive_json()
    assert await hass.config_entries.async_unload(entry.entry_id)
    event = await client.receive_json()
    assert event["event"]["available"] is False
    assert len(event["event"]["items"]) == 53


async def test_permissions(
    hass: HomeAssistant,
    mocked: aioresponses,
    hass_ws_client: WebSocketGenerator,
    hass_admin_user: MockUser,
) -> None:
    """Subscribe needs read, set_progress needs control permission."""
    await setup_homework(hass, mocked)
    client = await hass_ws_client(hass)
    hass_admin_user.mock_policy({"entities": {"entity_ids": {TODO_ID: {"read": True}}}})
    await client.send_json_auto_id(
        {"type": SET_PROGRESS, "entity_id": TODO_ID, "item": uid(100065), "progress": 5}
    )
    assert (await client.receive_json())["error"]["code"] == "unauthorized"
    await client.send_json_auto_id({"type": SUBSCRIBE, "entity_id": TODO_ID})
    assert (await client.receive_json())["success"]
    await client.receive_json()

    hass_admin_user.mock_policy({"entities": {"entity_ids": {"todo.other": True}}})
    await client.send_json_auto_id({"type": SUBSCRIBE, "entity_id": TODO_ID})
    assert (await client.receive_json())["error"]["code"] == "unauthorized"


async def _subscribe(client: Any) -> dict[str, Any]:
    await client.send_json_auto_id({"type": SUBSCRIBE, "entity_id": TODO_ID})
    assert (await client.receive_json())["success"]
    event: dict[str, Any] = (await client.receive_json())["event"]
    return event


async def test_progress_matches_the_sensors(
    hass: HomeAssistant, mocked: aioresponses, hass_ws_client: WebSocketGenerator
) -> None:
    """The payload holds the sensor values; ticking pushes new numbers."""
    await setup_homework(hass, mocked)
    client = await hass_ws_client(hass)
    progress = (await _subscribe(client))["progress"]
    assert set(progress) == {"next_day", "week", "next_week"}
    for key, entity in (
        ("next_day", "sensor.kind_school_homework_next_school_day"),
        ("week", "sensor.kind_school_homework_this_week"),
        ("next_week", "sensor.kind_school_homework_next_week"),
    ):
        state = hass.states.get(entity)
        assert state is not None
        assert progress[key] == {
            "value": float(state.state),
            "items": state.attributes["items"],
            "completed": state.attributes["completed"],
        }
    assert progress["next_day"] == {"value": 0.0, "items": 6, "completed": 0}

    await set_progress(hass, uid(100061), 100)  # Friday, this week
    after = (await client.receive_json())["event"]["progress"]
    assert after["week"]["completed"] == progress["week"]["completed"] + 1
    assert after["week"]["value"] > progress["week"]["value"]
    assert after["next_week"] == progress["next_week"]


async def test_progress_follows_weights_and_midnight(
    hass: HomeAssistant,
    mocked: aioresponses,
    hass_ws_client: WebSocketGenerator,
    hass_admin_user: MockUser,
    frozen_now: FrozenDateTimeFactory,
) -> None:
    """A weight change and the midnight rollover push new progress values."""
    frozen_now.move_to("2026-11-15 22:45:00+00:00")  # Sunday 23:45 in Amsterdam
    _, entry = await setup_homework(hass, mocked)
    # The fixture token was issued on Friday and has expired: issue a fresh one.
    refresh = next(iter(hass_admin_user.refresh_tokens.values()))
    token = hass.auth.async_create_access_token(refresh)
    client = await hass_ws_client(hass, token)
    first = await _subscribe(client)
    await set_progress(hass, uid(100065), 100)
    before = (await client.receive_json())["event"]["progress"]

    subject = entry.runtime_data.homework.find_item(CHILD_ID, uid(100065))
    assert subject is not None
    hass.config_entries.async_update_entry(
        entry,
        options={
            **entry.options,
            CONF_WEIGHTS: {str(CHILD_ID): {"subjects": {subject.subject: 0}}},
        },
    )
    await hass.async_block_till_done()
    weighted = hass.states.get("sensor.kind_school_homework_this_week")
    assert weighted is not None
    pushed = (await client.receive_json())["event"]["progress"]
    assert pushed["week"]["value"] == float(weighted.state) != before["week"]["value"]
    assert first["progress"]["week"] is not None

    # Sunday to Monday: "next_day" (Sunday + Monday) becomes Monday + Tuesday. The
    # step is 15 minutes, so only the midnight timer (no coordinator refresh) can
    # push the new values.
    assert first["progress"]["next_day"]["items"] == 4  # Monday 16 Nov
    # A collector next to the socket: a missing push then fails instead of waiting.
    pushed_events: list[dict[str, Any]] = []
    async_subscribe(hass, TODO_ID, pushed_events.append)
    frozen_now.move_to("2026-11-15 23:00:01+00:00")
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert len(pushed_events) == 1
    event = pushed_events[0]
    assert event == (await client.receive_json())["event"]
    assert event["available"] is True
    tuesday = sum(
        1
        for i in entry.runtime_data.homework.items(CHILD_ID)
        if i.due_date.isoformat() == "2026-11-17"
    )
    assert tuesday > 0
    assert event["progress"]["next_day"]["items"] == 4 + tuesday


async def test_progress_is_null_where_unavailable(
    hass: HomeAssistant, mocked: aioresponses, hass_ws_client: WebSocketGenerator
) -> None:
    """Next week is null outside the window; everything is null when unavailable."""
    _, entry = await setup_homework(hass, mocked, options={CONF_WEEKS_AHEAD: 1})
    client = await hass_ws_client(hass)
    progress = (await _subscribe(client))["progress"]
    assert progress["next_week"] is None
    assert progress["week"] is not None and progress["next_day"] is not None
    assert await hass.config_entries.async_unload(entry.entry_id)
    event = (await client.receive_json())["event"]
    assert event["available"] is False
    assert event["progress"] == {"next_day": None, "week": None, "next_week": None}
