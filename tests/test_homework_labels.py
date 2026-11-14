"""Manual labels: store migration, WebSocket commands, services, calendar, weights."""

from __future__ import annotations

from datetime import timedelta
from typing import Any

import pytest
from aioresponses import aioresponses
from freezegun.api import FrozenDateTimeFactory
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from pytest_homeassistant_custom_component.common import MockUser
from pytest_homeassistant_custom_component.typing import WebSocketGenerator

from custom_components.magister.const import CONF_LABELS, CONF_WEIGHTS, DOMAIN
from custom_components.magister.diagnostics import async_get_config_entry_diagnostics

from .ha_helpers import CHILD_ID, NOW
from .test_homework import TODO_ID, sensor, setup_homework, uid

APPOINTMENTS = "magister/homework/appointments"
ADD_LABEL = "magister/homework/add_label"
REMOVE_LABEL = "magister/homework/remove_label"
SUBSCRIBE = "magister/homework/subscribe"
CALENDAR = "calendar.kind_school_agenda"

MONDAY_NO_LABEL = 100067  # scheikunde, Monday 16 Nov, no Magister label
MONDAY_HOMEWORK = 100065  # wiskunde, Monday 16 Nov, Huiswerk
MONDAY_OTHER = 100069  # Franse taal, no Magister label
TOETSWEEK = {"id": "tw", "name": "Toetsweek", "kind": "test"}
EXTRA = {"id": "ex", "name": "Extra", "kind": "homework"}
OPTIONS = {CONF_LABELS: {str(CHILD_ID): [TOETSWEEK, EXTRA]}}


@pytest.fixture(autouse=True)
async def frozen_now(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> FrozenDateTimeFactory:
    """Friday 13 November 2026."""
    await hass.config.async_set_time_zone("Europe/Amsterdam")
    freezer.move_to(NOW)
    return freezer


async def call(client: Any, command: str, **fields: Any) -> dict[str, Any]:
    """Send a command and return the whole response."""
    await client.send_json_auto_id({"type": command, "entity_id": TODO_ID, **fields})
    response: dict[str, Any] = await client.receive_json()
    return response


async def call_events(
    client: Any, command: str, **fields: Any
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Like ``call`` on a subscribed socket: pushed events come before the result."""
    await client.send_json_auto_id({"type": command, "entity_id": TODO_ID, **fields})
    events: list[dict[str, Any]] = []
    while (message := await client.receive_json())["type"] == "event":
        events.append(message["event"])
    return message, events


async def add(client: Any, appointment: int, label: str, **fields: Any) -> Any:
    """``add_label`` for a fixture appointment."""
    return await call(
        client, ADD_LABEL, appointment=uid(appointment), label=label, **fields
    )


# -- store migration -------------------------------------------------------------


async def test_store_migrates_from_v1(
    hass: HomeAssistant, mocked: aioresponses, hass_storage: dict[str, Any]
) -> None:
    """A v1 store (progress only) is read and rewritten as v2 with labels."""
    from .ha_helpers import make_entry

    entry = make_entry()
    key = f"{DOMAIN}.homework.{entry.entry_id}"
    hass_storage[key] = {
        "version": 1,
        "minor_version": 1,
        "key": key,
        "data": {
            "items": {
                uid(MONDAY_HOMEWORK): {
                    "progress": 50,
                    "last_partial": 50,
                    "updated": "2026-11-12T10:00:00+00:00",
                },
                "junk": "no entry",
            }
        },
    }
    from .ha_helpers import FakeMagister

    FakeMagister(mocked)
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    manager = entry.runtime_data.homework
    assert manager.progress(uid(MONDAY_HOMEWORK)) == 50
    assert manager.stored_entries == 1
    assert await hass.config_entries.async_unload(entry.entry_id)
    saved = hass_storage[key]
    assert saved["version"] == 2
    assert saved["data"]["items"][uid(MONDAY_HOMEWORK)]["labels"] == []


async def test_store_loads_labels_leniently(
    hass: HomeAssistant, mocked: aioresponses, hass_storage: dict[str, Any]
) -> None:
    """Broken stored labels are dropped, good ones kept; notes are capped."""
    from .ha_helpers import FakeMagister, make_entry

    entry = make_entry(options=OPTIONS)
    key = f"{DOMAIN}.homework.{entry.entry_id}"
    hass_storage[key] = {
        "version": 2,
        "minor_version": 1,
        "key": key,
        "data": {
            "items": {
                uid(MONDAY_NO_LABEL): {
                    "labels": [
                        {"id": "tw", "note": "x" * 300, "added": "2026-11-13"},
                        {"id": "tw", "note": "duplicate"},
                        {"id": "gone", "note": "unknown option"},
                        {"note": "no id"},
                        "junk",
                    ]
                },
                uid(MONDAY_OTHER): {"labels": "junk"},
            }
        },
    }
    FakeMagister(mocked)
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    item = entry.runtime_data.homework.find_item(CHILD_ID, uid(MONDAY_NO_LABEL))
    assert item is not None
    assert [(label.id, len(label.note)) for label in item.manual_labels] == [
        ("tw", 200)
    ]
    # The unknown option is kept in the store but does not make an item.
    assert entry.runtime_data.homework.find_item(CHILD_ID, uid(MONDAY_OTHER)) is None


# -- WebSocket ---------------------------------------------------------------------


async def test_add_and_remove_label_over_websocket(
    hass: HomeAssistant, mocked: aioresponses, hass_ws_client: WebSocketGenerator
) -> None:
    """Add (with a trimmed note), see it pushed, remove; the item leaves the planner."""
    _, entry = await setup_homework(hass, mocked, options=OPTIONS)
    client = await hass_ws_client(hass)
    await client.send_json_auto_id({"type": SUBSCRIBE, "entity_id": TODO_ID})
    assert (await client.receive_json())["success"]
    first = (await client.receive_json())["event"]
    assert first["labels"] == [TOETSWEEK, EXTRA]
    assert uid(MONDAY_NO_LABEL) not in {i["uid"] for i in first["items"]}

    response, events = await call_events(
        client,
        ADD_LABEL,
        appointment=uid(MONDAY_NO_LABEL),
        label="tw",
        note="  H3 + H4  ",
    )
    assert response["success"]
    item = response["result"]
    assert item["uid"] == uid(MONDAY_NO_LABEL)
    assert (item["info_type"], item["label"], item["is_test"]) == (None, None, True)
    assert item["manual_labels"] == [{**TOETSWEEK, "note": "H3 + H4"}]
    assert item["text"] == ""
    (pushed,) = events
    assert uid(MONDAY_NO_LABEL) in {i["uid"] for i in pushed["items"]}
    assert len(pushed["items"]) == len(first["items"]) + 1

    # a second label, on an item that already has a Magister label
    response, _ = await call_events(
        client, ADD_LABEL, appointment=uid(MONDAY_HOMEWORK), label="ex"
    )
    item = response["result"]
    assert item["label"] == "Huiswerk" and item["info_type"] == 1
    assert item["manual_labels"] == [{**EXTRA, "note": ""}]
    assert item["is_test"] is False
    response, _ = await call_events(
        client, ADD_LABEL, appointment=uid(MONDAY_HOMEWORK), label="tw"
    )
    assert [m["id"] for m in response["result"]["manual_labels"]] == ["ex", "tw"]
    assert response["result"]["is_test"] is True

    # remove: the Magister label stays, the item stays
    response, _ = await call_events(
        client, REMOVE_LABEL, appointment=uid(MONDAY_HOMEWORK), label="ex"
    )
    assert [m["id"] for m in response["result"]["item"]["manual_labels"]] == ["tw"]
    # remove the last label of an unlabeled appointment: it leaves the planner
    response, events = await call_events(
        client, REMOVE_LABEL, appointment=uid(MONDAY_NO_LABEL), label="tw"
    )
    assert response["result"] == {"item": None}
    assert uid(MONDAY_NO_LABEL) not in {i["uid"] for i in events[-1]["items"]}
    assert entry.runtime_data.homework.stored_entries == 1


async def test_label_errors(
    hass: HomeAssistant, mocked: aioresponses, hass_ws_client: WebSocketGenerator
) -> None:
    """Every error of the contract, and invalid input."""
    await setup_homework(hass, mocked, options=OPTIONS)
    client = await hass_ws_client(hass)

    async def error(response: dict[str, Any]) -> str:
        assert response["success"] is False
        code: str = response["error"]["code"]
        return code

    assert await error(await add(client, 1, "tw")) == "appointment_not_found"
    assert await error(await add(client, MONDAY_NO_LABEL, "nope")) == "label_not_found"
    assert await error(await add(client, MONDAY_NO_LABEL, "Toetsweek")) == (
        "label_not_found"  # by id only over WebSocket
    )
    assert (await add(client, MONDAY_NO_LABEL, "tw"))["success"]
    assert await error(await add(client, MONDAY_NO_LABEL, "tw")) == "label_exists"
    assert await error(
        await call(client, REMOVE_LABEL, appointment=uid(1), label="tw")
    ) == ("appointment_not_found")
    assert await error(
        await call(client, REMOVE_LABEL, appointment=uid(MONDAY_NO_LABEL), label="ex")
    ) == ("label_not_on_appointment")
    # Magister labels cannot be removed, there is no id for them either
    assert await error(
        await call(
            client,
            REMOVE_LABEL,
            appointment=uid(MONDAY_HOMEWORK),
            label="default_homework",
        )
    ) == ("label_not_found")
    # invalid input
    assert (
        await error(await add(client, MONDAY_NO_LABEL, "ex", note="x" * 201))
        == "invalid_format"
    )
    assert (await add(client, MONDAY_NO_LABEL, "ex", note="x" * 200))["success"]
    assert await error(await add(client, MONDAY_NO_LABEL, "ex", note=5)) == (
        "invalid_format"
    )
    # unknown entity
    await client.send_json_auto_id(
        {
            "type": ADD_LABEL,
            "entity_id": "todo.nope",
            "appointment": uid(1),
            "label": "tw",
        }
    )
    assert await error(await client.receive_json()) == "not_found"
    await client.send_json_auto_id(
        {
            "type": REMOVE_LABEL,
            "entity_id": "todo.nope",
            "appointment": "a",
            "label": "b",
        }
    )
    assert await error(await client.receive_json()) == "not_found"
    await client.send_json_auto_id(
        {"type": APPOINTMENTS, "entity_id": "todo.nope", "date": "2026-11-16"}
    )
    assert await error(await client.receive_json()) == "not_found"
    await client.send_json_auto_id(
        {"type": APPOINTMENTS, "entity_id": "sensor.x", "date": "2026-11-16"}
    )
    assert await error(await client.receive_json()) == "invalid_format"


async def test_appointments_command(
    hass: HomeAssistant, mocked: aioresponses, hass_ws_client: WebSocketGenerator
) -> None:
    """All of a day's appointments, labelled or not; dates outside the window fail."""
    await setup_homework(hass, mocked, options=OPTIONS)
    client = await hass_ws_client(hass)
    assert (await add(client, MONDAY_NO_LABEL, "tw", note="n"))["success"]
    response = await call(client, APPOINTMENTS, date="2026-11-16")
    assert response["success"]
    appointments = response["result"]["appointments"]
    by_uid = {a["uid"]: a for a in appointments}
    assert set(by_uid) >= {uid(MONDAY_NO_LABEL), uid(MONDAY_OTHER), uid(100064)}
    # sorted like items: start, lesson hour, uid
    keys = [(a["start"], a["lesson_hour"] or 0, a["uid"]) for a in appointments]
    assert keys == sorted(keys)
    assert by_uid[uid(MONDAY_OTHER)] == {
        "uid": uid(MONDAY_OTHER),
        "start": "2026-11-16T13:50:00+01:00",
        "end": by_uid[uid(MONDAY_OTHER)]["end"],
        "all_day": False,
        "lesson_hour": 7,
        "subject": "Franse taal",
        "cancelled": False,
        "info_type": None,
        "manual_labels": [],
    }
    assert by_uid[uid(MONDAY_NO_LABEL)]["manual_labels"] == [{**TOETSWEEK, "note": "n"}]
    assert by_uid[uid(MONDAY_HOMEWORK)]["info_type"] == 1
    # window: 1 week back from this Monday up to today + 22 days (exclusive)
    assert (await call(client, APPOINTMENTS, date="2026-11-02"))["success"]
    for outside in ("2026-11-01", "2026-12-05"):
        response = await call(client, APPOINTMENTS, date=outside)
        assert response["error"]["code"] == "invalid_date"
    assert (await call(client, APPOINTMENTS, date="2026-12-04"))["success"]
    response = await call(client, APPOINTMENTS, date="not a date")
    assert response["error"]["code"] == "invalid_format"
    empty = await call(client, APPOINTMENTS, date="2026-11-15")  # a Sunday
    assert empty["result"] == {"appointments": []}


async def test_label_permissions(
    hass: HomeAssistant,
    mocked: aioresponses,
    hass_ws_client: WebSocketGenerator,
    hass_admin_user: MockUser,
) -> None:
    """Appointments need read; add and remove need control permission."""
    await setup_homework(hass, mocked, options=OPTIONS)
    client = await hass_ws_client(hass)
    assert (await add(client, MONDAY_NO_LABEL, "tw"))["success"]
    hass_admin_user.mock_policy({"entities": {"entity_ids": {TODO_ID: {"read": True}}}})
    assert (await call(client, APPOINTMENTS, date="2026-11-16"))["success"]
    response = await add(client, MONDAY_OTHER, "tw")
    assert response["error"]["code"] == "unauthorized"
    response = await call(
        client, REMOVE_LABEL, appointment=uid(MONDAY_NO_LABEL), label="tw"
    )
    assert response["error"]["code"] == "unauthorized"
    hass_admin_user.mock_policy({"entities": {"entity_ids": {"todo.other": True}}})
    response = await call(client, APPOINTMENTS, date="2026-11-16")
    assert response["error"]["code"] == "unauthorized"


# -- services ----------------------------------------------------------------------


async def label_service(
    hass: HomeAssistant, name: str, appointment: int, label: str, **extra: Any
) -> None:
    """Call ``magister.add_homework_label`` / ``remove_homework_label``."""
    await hass.services.async_call(
        DOMAIN,
        name,
        {
            "entity_id": TODO_ID,
            "appointment": uid(appointment),
            "label": label,
            **extra,
        },
        blocking=True,
    )
    await hass.async_block_till_done()


async def test_label_services(hass: HomeAssistant, mocked: aioresponses) -> None:
    """Labels by id or by name (any case); the same validation as WebSocket."""
    _, entry = await setup_homework(hass, mocked, options=OPTIONS)
    manager = entry.runtime_data.homework
    await label_service(
        hass, "add_homework_label", MONDAY_NO_LABEL, "tOeTsWeEk", note=" n "
    )
    item = manager.find_item(CHILD_ID, uid(MONDAY_NO_LABEL))
    assert item is not None and item.manual_labels[0].note == "n"
    await label_service(hass, "add_homework_label", MONDAY_NO_LABEL, "ex")
    with pytest.raises(ServiceValidationError, match="already has this label"):
        await label_service(hass, "add_homework_label", MONDAY_NO_LABEL, "EXTRA")
    with pytest.raises(ServiceValidationError, match="not one of the labels"):
        await label_service(hass, "add_homework_label", MONDAY_NO_LABEL, "nope")
    with pytest.raises(ServiceValidationError, match="does not exist"):
        await label_service(hass, "add_homework_label", 1, "ex")
    with pytest.raises(Exception, match="note"):
        await label_service(
            hass, "add_homework_label", MONDAY_OTHER, "ex", note="x" * 201
        )
    await label_service(hass, "remove_homework_label", MONDAY_NO_LABEL, "extra")
    await label_service(hass, "remove_homework_label", MONDAY_NO_LABEL, "tw")
    assert manager.find_item(CHILD_ID, uid(MONDAY_NO_LABEL)) is None
    with pytest.raises(ServiceValidationError, match="Magister labels cannot"):
        await label_service(hass, "remove_homework_label", MONDAY_NO_LABEL, "tw")
    with pytest.raises(ServiceValidationError, match="does not exist"):
        await label_service(hass, "remove_homework_label", 1, "tw")


# -- items, sensors, weights -----------------------------------------------------


async def test_default_labels_when_not_configured(
    hass: HomeAssistant, mocked: aioresponses, hass_ws_client: WebSocketGenerator
) -> None:
    """Without options the five Magister names are the label options."""
    await setup_homework(hass, mocked)
    client = await hass_ws_client(hass)
    await client.send_json_auto_id({"type": SUBSCRIBE, "entity_id": TODO_ID})
    assert (await client.receive_json())["success"]
    labels = (await client.receive_json())["event"]["labels"]
    assert [(o["name"], o["kind"]) for o in labels] == [
        ("Huiswerk", "homework"),
        ("Proefwerk", "test"),
        ("Tentamen", "test"),
        ("SO", "test"),
        ("MO", "test"),
    ]
    response, _ = await call_events(
        client, ADD_LABEL, appointment=uid(MONDAY_NO_LABEL), label=labels[1]["id"]
    )
    assert response["success"]


async def test_manual_labels_count_in_the_sensors(
    hass: HomeAssistant, mocked: aioresponses
) -> None:
    """A labelled appointment joins the periods; the highest label weight rules."""
    _, entry = await setup_homework(hass, mocked, options=OPTIONS)
    week = sensor(hass, "sensor.kind_school_homework_next_week")
    before = (week.attributes["items"], week.attributes["tests"])
    await label_service(hass, "add_homework_label", MONDAY_NO_LABEL, "tw")
    week = sensor(hass, "sensor.kind_school_homework_next_week")
    assert (week.attributes["items"], week.attributes["tests"]) == (
        before[0] + 1,
        before[1] + 1,
    )
    assert week.attributes["weights"]["labels"] == {"Toetsweek": 1.0}
    next_day = sensor(hass, "sensor.kind_school_homework_next_school_day")
    assert next_day.attributes["items"] == 7  # Friday (2) + Monday (4 + 1)

    # Weights: label tw 4, type homework 2 -> a Huiswerk item with tw counts 4.
    # Completing only the labelled item (weight 4 x subject 1) against the others.
    await label_service(hass, "add_homework_label", MONDAY_HOMEWORK, "tw")
    hass.config_entries.async_update_entry(
        entry,
        options={
            **entry.options,
            CONF_WEIGHTS: {
                str(CHILD_ID): {
                    "types": {"homework": 2},
                    "labels": {"tw": 4, "ex": 0.5},
                }
            },
        },
    )
    await hass.async_block_till_done()
    weights = entry.runtime_data.homework.weights(CHILD_ID)
    items = {i.uid: i for i in entry.runtime_data.homework.items(CHILD_ID)}
    assert weights.item_weight(items[uid(MONDAY_HOMEWORK)]) == 4.0  # max(2, 4)
    assert weights.item_weight(items[uid(MONDAY_NO_LABEL)]) == 4.0
    assert weights.item_weight(items[uid(100064)]) == 2.0  # homework type only
    await label_service(hass, "add_homework_label", MONDAY_HOMEWORK, "ex")
    items = {i.uid: i for i in entry.runtime_data.homework.items(CHILD_ID)}
    assert weights.item_weight(items[uid(MONDAY_HOMEWORK)]) == 4.0  # max(2, 4, 0.5)


async def test_label_option_changes_apply_without_reload(
    hass: HomeAssistant, mocked: aioresponses, hass_ws_client: WebSocketGenerator
) -> None:
    """A rename and a kind change show at once: no reload, no Magister request."""
    fake, entry = await setup_homework(hass, mocked, options=OPTIONS)
    runtime = entry.runtime_data
    client = await hass_ws_client(hass)
    assert (await add(client, MONDAY_NO_LABEL, "tw", note="n"))["success"]
    await client.send_json_auto_id({"type": SUBSCRIBE, "entity_id": TODO_ID})
    assert (await client.receive_json())["success"]
    await client.receive_json()
    requests = len(fake.appointment_requests)
    hass.config_entries.async_update_entry(
        entry,
        options={
            CONF_LABELS: {
                str(CHILD_ID): [
                    {"id": "tw", "name": "Toetsen", "kind": "homework"},
                    EXTRA,
                ]
            }
        },
    )
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.LOADED
    assert entry.runtime_data is runtime
    assert len(fake.appointment_requests) == requests
    event = (await client.receive_json())["event"]
    assert event["labels"][0] == {"id": "tw", "name": "Toetsen", "kind": "homework"}
    item = next(i for i in event["items"] if i["uid"] == uid(MONDAY_NO_LABEL))
    assert item["manual_labels"] == [
        {"id": "tw", "name": "Toetsen", "kind": "homework", "note": "n"}
    ]
    assert item["is_test"] is False
    state = hass.states.get(CALENDAR)
    assert state is not None


async def test_todo_items_show_the_manual_labels(
    hass: HomeAssistant, mocked: aioresponses
) -> None:
    """The to-do summary lists Magister then manual labels; notes follow the text."""
    from .test_homework import todo_items

    await setup_homework(hass, mocked, options=OPTIONS)
    await label_service(
        hass, "add_homework_label", MONDAY_HOMEWORK, "tw", note="H3 + H4"
    )
    await label_service(hass, "add_homework_label", MONDAY_NO_LABEL, "ex")
    items = await todo_items(hass)
    homework = items[uid(MONDAY_HOMEWORK)]
    assert homework["summary"] == "[Huiswerk] [Toetsweek] wiskunde"
    assert homework["description"].splitlines()[-1] == "H3 + H4"
    assert items[uid(MONDAY_NO_LABEL)]["summary"] == "[Extra] scheikunde"
    assert "description" not in items[uid(MONDAY_NO_LABEL)]


# -- calendar --------------------------------------------------------------------


async def test_calendar_titles_carry_the_manual_labels(
    hass: HomeAssistant, mocked: aioresponses
) -> None:
    """Manual labels come after the Magister one and follow label changes."""
    _, entry = await setup_homework(hass, mocked, options=OPTIONS)

    async def titles() -> dict[str, str]:
        response = await hass.services.async_call(
            "calendar",
            "get_events",
            {
                "entity_id": CALENDAR,
                "start_date_time": "2026-11-16T00:00:00+01:00",
                "end_date_time": "2026-11-17T00:00:00+01:00",
            },
            blocking=True,
            return_response=True,
        )
        return {
            e["summary"].split("] ")[-1]: e["summary"]
            for e in response[CALENDAR]["events"]
        }

    assert (await titles())["wiskunde"] == "[Huiswerk] wiskunde"
    await label_service(hass, "add_homework_label", MONDAY_HOMEWORK, "tw")
    await label_service(hass, "add_homework_label", MONDAY_HOMEWORK, "ex")
    await label_service(hass, "add_homework_label", MONDAY_NO_LABEL, "tw")
    found = await titles()
    assert found["wiskunde"] == "[Huiswerk] [Toetsweek] [Extra] wiskunde"
    assert found["scheikunde"] == "[Toetsweek] scheikunde"
    # a rename updates the titles too
    hass.config_entries.async_update_entry(
        entry,
        options={
            CONF_LABELS: {str(CHILD_ID): [{**TOETSWEEK, "name": "Toets-week"}, EXTRA]}
        },
    )
    await hass.async_block_till_done()
    assert (await titles())["scheikunde"] == "[Toets-week] scheikunde"
    await label_service(hass, "remove_homework_label", MONDAY_NO_LABEL, "tw")
    assert (await titles())["scheikunde"] == "scheikunde"


# -- pruning ---------------------------------------------------------------------


async def test_labels_are_pruned_like_progress(
    hass: HomeAssistant,
    mocked: aioresponses,
    hass_storage: dict[str, Any],
    frozen_now: FrozenDateTimeFactory,
) -> None:
    """Labels of a vanished appointment stay 14 days, then they are deleted."""
    fake, entry = await setup_homework(hass, mocked, options=OPTIONS)
    manager = entry.runtime_data.homework
    await label_service(hass, "add_homework_label", MONDAY_NO_LABEL, "tw")
    await label_service(hass, "add_homework_label", MONDAY_OTHER, "tw")
    assert manager.stored_entries == 2
    fake.appointments[CHILD_ID] = [
        a for a in fake.appointments[CHILD_ID] if a["Id"] != MONDAY_NO_LABEL
    ]
    coordinator = entry.runtime_data.coordinator
    await coordinator.async_refresh()
    await hass.async_block_till_done()
    assert manager.stored_entries == 2  # gone-marker set, kept
    assert manager.find_item(CHILD_ID, uid(MONDAY_NO_LABEL)) is None
    assert manager.label_in_use(CHILD_ID, "tw")
    frozen_now.tick(timedelta(days=13))
    await coordinator.async_refresh()
    await hass.async_block_till_done()
    assert manager.stored_entries == 2
    frozen_now.tick(timedelta(days=2))
    await coordinator.async_refresh()
    await hass.async_block_till_done()
    assert manager.stored_entries == 1
    assert manager.find_item(CHILD_ID, uid(MONDAY_OTHER)) is not None


async def test_label_progress_and_removal_keep_the_store_consistent(
    hass: HomeAssistant, mocked: aioresponses
) -> None:
    """Progress set on a labelled item survives removing the label (normal pruning)."""
    from .test_homework import set_progress

    _, entry = await setup_homework(hass, mocked, options=OPTIONS)
    manager = entry.runtime_data.homework
    await label_service(hass, "add_homework_label", MONDAY_NO_LABEL, "tw")
    await set_progress(hass, uid(MONDAY_NO_LABEL), 60)
    assert manager.progress(uid(MONDAY_NO_LABEL)) == 60
    await label_service(hass, "remove_homework_label", MONDAY_NO_LABEL, "tw")
    assert manager.find_item(CHILD_ID, uid(MONDAY_NO_LABEL)) is None
    assert manager.progress(uid(MONDAY_NO_LABEL)) == 60  # kept in the store
    await label_service(hass, "add_homework_label", MONDAY_NO_LABEL, "tw")
    item = manager.find_item(CHILD_ID, uid(MONDAY_NO_LABEL))
    assert item is not None and manager.progress(item.uid) == 60
    # progress back to 0 while labelled keeps the entry (the label lives there)
    await set_progress(hass, uid(MONDAY_NO_LABEL), 0)
    assert manager.find_item(CHILD_ID, uid(MONDAY_NO_LABEL)) is not None


# -- diagnostics -----------------------------------------------------------------


async def test_diagnostics_count_manual_labels_only(
    hass: HomeAssistant, mocked: aioresponses
) -> None:
    """Counts per kind; no names, notes or ids."""
    _, entry = await setup_homework(hass, mocked, options=OPTIONS)
    await label_service(
        hass, "add_homework_label", MONDAY_NO_LABEL, "tw", note="geheim"
    )
    await label_service(hass, "add_homework_label", MONDAY_HOMEWORK, "tw")
    await label_service(hass, "add_homework_label", MONDAY_HOMEWORK, "ex")
    diagnostics = await async_get_config_entry_diagnostics(hass, entry)
    stats = diagnostics["children"][0]["homework"]
    assert stats["manual_labels"] == {"homework": 1, "test": 2}
    assert CONF_LABELS not in diagnostics["entry"]["options"]
    text = str(diagnostics)
    assert "geheim" not in text and "Toetsweek" not in text and "Extra" not in text
