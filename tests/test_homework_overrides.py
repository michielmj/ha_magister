"""Overrides of Magister labels: store, WebSocket, services, to-do, calendar."""

from __future__ import annotations

from typing import Any

import pytest
from aioresponses import aioresponses
from freezegun.api import FrozenDateTimeFactory
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.exceptions import ServiceValidationError
from pytest_homeassistant_custom_component.common import MockUser
from pytest_homeassistant_custom_component.typing import WebSocketGenerator

from custom_components.magister.api.homework import (
    default_label_options,
    label_options_to_stored,
)
from custom_components.magister.const import CONF_LABELS, DOMAIN
from custom_components.magister.diagnostics import async_get_config_entry_diagnostics

from .ha_helpers import CHILD_ID, NOW, FakeMagister, make_entry
from .test_homework import (
    NEXT_DAY,
    NEXT_WEEK,
    TODO_ID,
    sensor,
    setup_homework,
    todo_items,
    uid,
)
from .test_homework_labels import (
    CALENDAR,
    EXTRA,
    SUBSCRIBE,
    TOETSWEEK,
    call,
    call_events,
    label_service,
)
from .test_options_flow import _labels_action, _open_labels

SET_OVERRIDE = "magister/homework/set_override"
SET_PROGRESS = "magister/homework/set_progress"
APPOINTMENTS = "magister/homework/appointments"

PROEFWERK = 100084  # Duitse taal, Thursday 19 Nov, Proefwerk (type 2)
HOMEWORK = 100065  # wiskunde, Monday 16 Nov, Huiswerk (type 1)
NO_LABEL = 100067  # scheikunde, Monday 16 Nov, no Magister label
DEFAULTS = label_options_to_stored(default_label_options())
OPTIONS = {CONF_LABELS: {str(CHILD_ID): [*DEFAULTS, TOETSWEEK, EXTRA]}}
REPLACE_WITH = {"id": "default_homework", "name": "Huiswerk", "kind": "homework"}


@pytest.fixture(autouse=True)
async def frozen_now(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> FrozenDateTimeFactory:
    """Friday 13 November 2026."""
    await hass.config.async_set_time_zone("Europe/Amsterdam")
    freezer.move_to(NOW)
    return freezer


async def override(client: Any, appointment: int, mode: str, **fields: Any) -> Any:
    """``set_override`` for a fixture appointment."""
    return await call(
        client, SET_OVERRIDE, appointment=uid(appointment), mode=mode, **fields
    )


async def override_service(
    hass: HomeAssistant, appointment: int, mode: str, label: str | None = None
) -> None:
    """Call ``magister.set_homework_override``."""
    data: dict[str, Any] = {
        "entity_id": TODO_ID,
        "appointment": uid(appointment),
        "mode": mode,
    }
    if label is not None:
        data["label"] = label
    await hass.services.async_call(DOMAIN, "set_homework_override", data, blocking=True)
    await hass.async_block_till_done()


# -- store -------------------------------------------------------------------------


async def test_store_1_3_format_loads_and_is_saved_as_minor_3(
    hass: HomeAssistant, mocked: aioresponses, hass_storage: dict[str, Any]
) -> None:
    """A 1.3.0 file (major 1, minor 2, no overrides) loads; overrides persist."""
    entry = make_entry(options=OPTIONS)
    key = f"{DOMAIN}.homework.{entry.entry_id}"
    hass_storage[key] = {
        "version": 1,
        "minor_version": 2,
        "key": key,
        "data": {
            "items": {
                uid(PROEFWERK): {
                    "progress": 50,
                    "last_partial": 50,
                    "updated": "",
                    "labels": [],
                }
            }
        },
    }
    FakeMagister(mocked)
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    manager = entry.runtime_data.homework
    assert manager.progress(uid(PROEFWERK)) == 50
    await override_service(hass, PROEFWERK, "replace", "default_homework")
    await override_service(hass, HOMEWORK, "disable")
    assert await hass.config_entries.async_unload(entry.entry_id)
    saved = hass_storage[key]
    assert (saved["version"], saved["minor_version"]) == (1, 3)
    items = saved["data"]["items"]
    assert items[uid(PROEFWERK)]["override"] == {
        "mode": "replace",
        "label": "default_homework",
    }
    assert items[uid(PROEFWERK)]["progress"] == 50  # progress and override together
    assert items[uid(HOMEWORK)]["override"] == {"mode": "disable"}


async def test_store_loads_overrides_leniently(
    hass: HomeAssistant, mocked: aioresponses, hass_storage: dict[str, Any]
) -> None:
    """Broken stored overrides are dropped; a missing option falls back."""
    entry = make_entry(options=OPTIONS)
    key = f"{DOMAIN}.homework.{entry.entry_id}"
    base = {"progress": 0, "last_partial": 0, "updated": "", "labels": []}
    hass_storage[key] = {
        "version": 1,
        "minor_version": 3,
        "key": key,
        "data": {
            "items": {
                uid(PROEFWERK): {
                    **base,
                    "override": {"mode": "replace", "label": "gone"},
                },
                uid(HOMEWORK): {**base, "override": {"mode": "bogus"}},
                uid(NO_LABEL): {**base, "override": "x"},
                uid(100066): {**base, "override": {"mode": "replace", "label": ""}},
                uid(100068): {**base, "override": {"mode": "disable"}},
            }
        },
    }
    FakeMagister(mocked)
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    manager = entry.runtime_data.homework
    # a replacement pointing to a missing option falls back to the original label
    item = manager.find_item(CHILD_ID, uid(PROEFWERK))
    assert item is not None and item.override is None
    assert not manager.effective(item).disabled
    broken = manager.find_item(CHILD_ID, uid(HOMEWORK))
    assert broken is not None and broken.override is None
    disabled = manager.find_item(CHILD_ID, uid(100068))
    assert disabled is not None and manager.effective(disabled).disabled


async def test_overrides_are_pruned_like_progress(
    hass: HomeAssistant,
    mocked: aioresponses,
    frozen_now: FrozenDateTimeFactory,
) -> None:
    """The override of a vanished appointment stays 14 days, then it is deleted."""
    from datetime import timedelta

    fake, entry = await setup_homework(hass, mocked, options=OPTIONS)
    manager = entry.runtime_data.homework
    await override_service(hass, HOMEWORK, "disable")
    assert manager.stored_entries == 1
    fake.appointments[CHILD_ID] = [
        a for a in fake.appointments[CHILD_ID] if a["Id"] != HOMEWORK
    ]
    coordinator = entry.runtime_data.coordinator
    await coordinator.async_refresh()
    await hass.async_block_till_done()
    assert manager.stored_entries == 1
    frozen_now.tick(timedelta(days=15))
    await coordinator.async_refresh()
    await hass.async_block_till_done()
    assert manager.stored_entries == 0


# -- WebSocket ---------------------------------------------------------------------


async def test_set_override_over_websocket(
    hass: HomeAssistant, mocked: aioresponses, hass_ws_client: WebSocketGenerator
) -> None:
    """Replace, disable and clear; the result is the item, an event follows."""
    await setup_homework(hass, mocked, options=OPTIONS)
    client = await hass_ws_client(hass)
    await client.send_json_auto_id({"type": SUBSCRIBE, "entity_id": TODO_ID})
    assert (await client.receive_json())["success"]
    first = (await client.receive_json())["event"]
    item = next(i for i in first["items"] if i["uid"] == uid(PROEFWERK))
    assert item["override"] is None and item["is_test"] is True

    response, events = await call_events(
        client,
        SET_OVERRIDE,
        appointment=uid(PROEFWERK),
        mode="replace",
        label="default_homework",
    )
    assert response["success"]
    result = response["result"]["item"]
    assert result["override"] == {"mode": "replace", "label": REPLACE_WITH}
    assert (result["is_test"], result["disabled"], result["completed"]) == (
        False,
        False,
        False,
    )
    assert result["info_type"] == 2 and result["label"] == "Proefwerk"
    pushed = next(i for i in events[-1]["items"] if i["uid"] == uid(PROEFWERK))
    assert pushed == result

    response, _ = await call_events(
        client, SET_OVERRIDE, appointment=uid(PROEFWERK), mode="disable"
    )
    result = response["result"]["item"]
    assert result["override"] == {"mode": "disable"}
    assert (result["disabled"], result["completed"], result["progress"]) == (
        True,
        True,
        0,
    )

    response, _ = await call_events(
        client, SET_OVERRIDE, appointment=uid(PROEFWERK), mode="clear"
    )
    result = response["result"]["item"]
    assert result["override"] is None and result["is_test"] is True
    # clearing without an override succeeds and changes nothing
    response, events = await call_events(
        client, SET_OVERRIDE, appointment=uid(PROEFWERK), mode="clear"
    )
    assert response["success"] and response["result"]["item"] == result
    assert events == []


async def test_set_override_by_name_and_appointments_result(
    hass: HomeAssistant, mocked: aioresponses, hass_ws_client: WebSocketGenerator
) -> None:
    """The appointments result carries the override; ids only over WebSocket."""
    await setup_homework(hass, mocked, options=OPTIONS)
    client = await hass_ws_client(hass)
    response = await override(client, HOMEWORK, "replace", label="tw")
    assert response["result"]["item"]["override"] == {
        "mode": "replace",
        "label": TOETSWEEK,
    }
    response = await call(client, APPOINTMENTS, date="2026-11-16")
    by_uid = {a["uid"]: a for a in response["result"]["appointments"]}
    assert by_uid[uid(HOMEWORK)]["override"] == {"mode": "replace", "label": TOETSWEEK}
    assert by_uid[uid(NO_LABEL)]["override"] is None
    # a name is not accepted as label id (only the service takes names)
    response = await override(client, HOMEWORK, "replace", label="Toetsweek")
    assert response["error"]["code"] == "label_not_found"


async def test_set_override_errors(
    hass: HomeAssistant, mocked: aioresponses, hass_ws_client: WebSocketGenerator
) -> None:
    """Each error code of the contract."""
    await setup_homework(hass, mocked, options=OPTIONS)
    client = await hass_ws_client(hass)

    async def code(response: Any) -> str:
        assert not response["success"]
        return str(response["error"]["code"])

    assert await code(await override(client, 1, "disable")) == "appointment_not_found"
    assert (
        await code(await override(client, NO_LABEL, "disable")) == "no_magister_label"
    )
    assert (
        await code(await override(client, HOMEWORK, "replace", label="nope"))
        == "label_not_found"
    )
    assert await code(await override(client, HOMEWORK, "replace")) == "invalid_format"
    # replacing with the original's own default label
    own = await override(client, PROEFWERK, "replace", label="default_test")
    assert await code(own) == "invalid_format"
    assert await code(await override(client, HOMEWORK, "bogus")) == "invalid_format"
    await client.send_json_auto_id(
        {
            "type": SET_OVERRIDE,
            "entity_id": "todo.nope",
            "appointment": uid(HOMEWORK),
            "mode": "disable",
        }
    )
    assert (await client.receive_json())["error"]["code"] == "not_found"


async def test_set_override_needs_control_permission(
    hass: HomeAssistant,
    mocked: aioresponses,
    hass_ws_client: WebSocketGenerator,
    hass_admin_user: MockUser,
) -> None:
    """Read permission is not enough."""
    await setup_homework(hass, mocked)
    client = await hass_ws_client(hass)
    hass_admin_user.mock_policy({"entities": {"entity_ids": {TODO_ID: {"read": True}}}})
    response = await override(client, HOMEWORK, "disable")
    assert response["error"]["code"] == "unauthorized"


# -- completion, progress and the to-do entity -----------------------------------


async def test_disabled_item_is_completed_everywhere(
    hass: HomeAssistant, mocked: aioresponses, hass_ws_client: WebSocketGenerator
) -> None:
    """Progress is kept; the to-do shows it completed; the count and bars ignore it."""
    from .test_homework import set_progress

    _, entry = await setup_homework(hass, mocked)
    manager = entry.runtime_data.homework
    assert sensor(hass, TODO_ID).state == "18"
    week_before = dict(sensor(hass, NEXT_WEEK).attributes)
    next_day_before = sensor(hass, NEXT_DAY).attributes["items"]
    await set_progress(hass, uid(HOMEWORK), 50)
    await override_service(hass, HOMEWORK, "disable")

    items = await todo_items(hass)
    assert items[uid(HOMEWORK)]["status"] == "completed"
    assert items[uid(HOMEWORK)]["summary"] == "wiskunde"
    assert "%" not in (items[uid(HOMEWORK)]["description"] or "")
    assert sensor(hass, TODO_ID).state == "17"
    assert manager.progress(uid(HOMEWORK)) == 50  # kept
    week = sensor(hass, NEXT_WEEK).attributes
    assert week["items"] == week_before["items"] - 1
    assert sensor(hass, NEXT_DAY).attributes["items"] == next_day_before - 1

    client = await hass_ws_client(hass)
    await client.send_json_auto_id({"type": SUBSCRIBE, "entity_id": TODO_ID})
    await client.receive_json()
    payload = (await client.receive_json())["event"]
    item = next(i for i in payload["items"] if i["uid"] == uid(HOMEWORK))
    assert (item["completed"], item["disabled"], item["progress"]) == (True, True, 50)

    await override_service(hass, HOMEWORK, "clear")
    items = await todo_items(hass)
    assert items[uid(HOMEWORK)]["status"] == "needs_action"
    assert items[uid(HOMEWORK)]["description"].endswith("(50 %)")
    assert sensor(hass, TODO_ID).state == "18"
    assert dict(sensor(hass, NEXT_WEEK).attributes) == week_before


async def test_progress_on_a_disabled_item_is_refused(
    hass: HomeAssistant, mocked: aioresponses, hass_ws_client: WebSocketGenerator
) -> None:
    """``item_disabled`` over WebSocket; translated errors in HA's to-do/services."""
    await setup_homework(hass, mocked)
    client = await hass_ws_client(hass)
    await override_service(hass, HOMEWORK, "disable")
    await call(client, SET_PROGRESS, item=uid(HOMEWORK), progress=25)
    response = await call(client, SET_PROGRESS, item=uid(HOMEWORK), progress=25)
    assert response["error"]["code"] == "item_disabled"
    for status in ("completed", "needs_action"):
        with pytest.raises(ServiceValidationError) as err:
            await hass.services.async_call(
                "todo",
                "update_item",
                {"entity_id": TODO_ID, "item": uid(HOMEWORK), "status": status},
                blocking=True,
            )
        assert err.value.translation_key == "homework_item_disabled"
    with pytest.raises(ServiceValidationError) as err:
        await hass.services.async_call(
            DOMAIN,
            "set_homework_progress",
            {"entity_id": TODO_ID, "item": uid(HOMEWORK), "progress": 25},
            blocking=True,
        )
    assert err.value.translation_key == "homework_item_disabled"
    # restored: progress works again
    await override_service(hass, HOMEWORK, "clear")
    response = await call(client, SET_PROGRESS, item=uid(HOMEWORK), progress=25)
    assert response["result"] == {"progress": 25, "completed": False}


async def test_disabled_label_with_a_manual_label_stays_active(
    hass: HomeAssistant, mocked: aioresponses
) -> None:
    """Decision 5: the item stays active, the weight comes from the manual labels."""
    _, entry = await setup_homework(hass, mocked, options=OPTIONS)
    manager = entry.runtime_data.homework
    await label_service(hass, "add_homework_label", PROEFWERK, "ex")
    await override_service(hass, PROEFWERK, "disable")
    item = manager.find_item(CHILD_ID, uid(PROEFWERK))
    assert item is not None
    state = manager.effective(item)
    assert (state.disabled, state.is_test) == (False, False)
    assert [label.id for label in state.active_labels] == ["ex"]
    items = await todo_items(hass)
    assert items[uid(PROEFWERK)]["status"] == "needs_action"
    assert items[uid(PROEFWERK)]["summary"] == "[Extra] Duitse taal"
    # removing the last manual label: the item stays in the planner, disabled
    await label_service(hass, "remove_homework_label", PROEFWERK, "ex")
    item = manager.find_item(CHILD_ID, uid(PROEFWERK))
    assert item is not None and manager.effective(item).disabled
    assert (await todo_items(hass))[uid(PROEFWERK)]["status"] == "completed"


async def test_replacement_follows_in_weights_tests_and_titles(
    hass: HomeAssistant, mocked: aioresponses
) -> None:
    """A Proefwerk replaced by Huiswerk is no test any more and weighs as homework."""
    _, entry = await setup_homework(hass, mocked)
    before = sensor(hass, NEXT_WEEK).attributes["tests"]
    await override_service(hass, PROEFWERK, "replace", "huiswerk")  # by name
    assert sensor(hass, NEXT_WEEK).attributes["tests"] == before - 1
    items = await todo_items(hass)
    assert items[uid(PROEFWERK)]["summary"] == "[Proefwerk→Huiswerk] Duitse taal"
    await override_service(hass, PROEFWERK, "clear")
    assert (await todo_items(hass))[uid(PROEFWERK)]["summary"] == (
        "[Proefwerk] Duitse taal"
    )
    assert entry.runtime_data.homework.stored_entries == 0


async def test_service_errors(hass: HomeAssistant, mocked: aioresponses) -> None:
    """Translated errors for the same cases as the WebSocket codes."""
    await setup_homework(hass, mocked)
    for appointment, mode, label, key in (
        (1, "disable", None, "homework_appointment_not_found"),
        (NO_LABEL, "disable", None, "homework_no_magister_label"),
        (HOMEWORK, "replace", "nope", "homework_label_not_found"),
        (HOMEWORK, "replace", None, "homework_label_required"),
        (PROEFWERK, "replace", "default_test", "homework_label_is_original"),
    ):
        with pytest.raises(ServiceValidationError) as err:
            await override_service(hass, appointment, mode, label)
        assert err.value.translation_key == key
    with pytest.raises(Exception, match="mode"):
        await hass.services.async_call(
            DOMAIN,
            "set_homework_override",
            {"entity_id": TODO_ID, "appointment": uid(HOMEWORK), "mode": "x"},
            blocking=True,
        )


# -- calendar ----------------------------------------------------------------------


async def test_calendar_titles_follow_overrides(
    hass: HomeAssistant, mocked: aioresponses
) -> None:
    """``[Proefwerk->Huiswerk]``, nothing when disabled, manual labels as before."""
    await setup_homework(hass, mocked, options=OPTIONS)

    async def title(day: str, subject: str) -> str:
        response = await hass.services.async_call(
            "calendar",
            "get_events",
            {
                "entity_id": CALENDAR,
                "start_date_time": f"{day}T00:00:00+01:00",
                "end_date_time": f"{day}T23:59:00+01:00",
            },
            blocking=True,
            return_response=True,
        )
        (found,) = [
            e["summary"]
            for e in response[CALENDAR]["events"]
            if e["summary"].endswith(subject)
        ]
        return str(found)

    assert await title("2026-11-19", "Duitse taal") == "[Proefwerk] Duitse taal"
    await override_service(hass, PROEFWERK, "replace", "default_homework")
    assert await title("2026-11-19", "Duitse taal") == (
        "[Proefwerk→Huiswerk] Duitse taal"
    )
    await label_service(hass, "add_homework_label", PROEFWERK, "ex")
    assert await title("2026-11-19", "Duitse taal") == (
        "[Proefwerk→Huiswerk] [Extra] Duitse taal"
    )
    await override_service(hass, PROEFWERK, "disable")
    assert await title("2026-11-19", "Duitse taal") == "[Extra] Duitse taal"
    await override_service(hass, PROEFWERK, "clear")
    await label_service(hass, "remove_homework_label", PROEFWERK, "ex")
    assert await title("2026-11-19", "Duitse taal") == "[Proefwerk] Duitse taal"


# -- label options -----------------------------------------------------------------


async def test_a_replacement_label_cannot_be_deleted(
    hass: HomeAssistant, mocked: aioresponses
) -> None:
    """In use as a replacement on a present appointment: refused; absent: dropped."""
    fake, entry = await setup_homework(hass, mocked, options=OPTIONS)
    manager = entry.runtime_data.homework
    await override_service(hass, HOMEWORK, "replace", "ex")
    assert manager.label_in_use(CHILD_ID, EXTRA["id"])
    assert not manager.label_in_use(CHILD_ID, TOETSWEEK["id"])
    result = await _labels_action(hass, await _open_labels(hass, entry), "label_delete")
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"label": "ex"}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "label_in_use"}
    assert "ex" in [o["id"] for o in entry.options[CONF_LABELS][str(CHILD_ID)]]
    # the appointment leaves the window: the reference is no longer "in use"
    fake.appointments[CHILD_ID] = [
        a for a in fake.appointments[CHILD_ID] if a["Id"] != HOMEWORK
    ]
    await entry.runtime_data.coordinator.async_refresh()
    await hass.async_block_till_done()
    assert not manager.label_in_use(CHILD_ID, "ex")
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"label": "ex"}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert manager.stored_entries == 0  # the stale override was dropped with it


async def test_a_deleted_replacement_falls_back_to_the_original(
    hass: HomeAssistant, mocked: aioresponses
) -> None:
    """Options changed behind the back: the original Magister label shows again."""
    _, entry = await setup_homework(hass, mocked, options=OPTIONS)
    manager = entry.runtime_data.homework
    await override_service(hass, HOMEWORK, "replace", "ex")
    item = manager.find_item(CHILD_ID, uid(HOMEWORK))
    assert item is not None and item.override is not None
    hass.config_entries.async_update_entry(
        entry, options={CONF_LABELS: {str(CHILD_ID): [TOETSWEEK]}}
    )
    await hass.async_block_till_done()
    item = manager.find_item(CHILD_ID, uid(HOMEWORK))
    assert item is not None and item.override is None
    assert (await todo_items(hass))[uid(HOMEWORK)]["summary"] == "[Huiswerk] wiskunde"


async def test_renamed_replacement_shows_its_current_name(
    hass: HomeAssistant, mocked: aioresponses
) -> None:
    """The replacement is resolved by id against the current options."""
    _, entry = await setup_homework(hass, mocked, options=OPTIONS)
    await override_service(hass, HOMEWORK, "replace", "ex")
    hass.config_entries.async_update_entry(
        entry,
        options={CONF_LABELS: {str(CHILD_ID): [TOETSWEEK, {**EXTRA, "name": "Meer"}]}},
    )
    await hass.async_block_till_done()
    assert (await todo_items(hass))[uid(HOMEWORK)]["summary"] == (
        "[Huiswerk→Meer] wiskunde"
    )


# -- diagnostics -------------------------------------------------------------------


async def test_diagnostics_count_overrides_per_mode(
    hass: HomeAssistant, mocked: aioresponses
) -> None:
    """Counts per mode only: no ids, names or labels."""
    _, entry = await setup_homework(hass, mocked, options=OPTIONS)
    await override_service(hass, HOMEWORK, "replace", "tw")
    await override_service(hass, PROEFWERK, "disable")
    await override_service(hass, 100066, "disable")
    diagnostics = await async_get_config_entry_diagnostics(hass, entry)
    stats = diagnostics["children"][0]["homework"]
    assert stats["overrides"] == {"replace": 1, "disable": 2}
    assert "Toetsweek" not in str(diagnostics)


async def test_clear_is_not_blocked_by_a_lost_magister_label(
    hass: HomeAssistant,
    mocked: aioresponses,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """A stored override of an appointment without a Magister label is not stuck."""
    fake, entry = await setup_homework(hass, mocked, options=OPTIONS)
    manager = entry.runtime_data.homework
    client = await hass_ws_client(hass)
    # clear without any override, on an appointment without a Magister label
    response = await override(client, NO_LABEL, "clear")
    assert response["success"] and response["result"] == {"item": None}
    await override_service(hass, HOMEWORK, "replace", "ex")
    assert manager.label_in_use(CHILD_ID, "ex")
    for appointment in fake.appointments[CHILD_ID]:
        if appointment["Id"] == HOMEWORK:
            appointment["InfoType"] = 0  # Magister dropped the label
    await entry.runtime_data.coordinator.async_refresh()
    await hass.async_block_till_done()
    assert manager.find_item(CHILD_ID, uid(HOMEWORK)) is None
    # the ignored override no longer blocks deleting its option
    assert not manager.label_in_use(CHILD_ID, "ex")
    result = await _labels_action(hass, await _open_labels(hass, entry), "label_delete")
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"label": "ex"}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    # replacing needs a Magister label; clearing does not
    assert (await override(client, HOMEWORK, "replace", label="tw"))["error"][
        "code"
    ] == ("no_magister_label")
    manager.set_override(CHILD_ID, uid(HOMEWORK), None)
    assert manager.stored_entries == 0


async def test_clear_removes_a_stuck_override_and_returns_the_item(
    hass: HomeAssistant,
    mocked: aioresponses,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """clear deletes a stored override without a Magister label; the item may remain."""
    fake, entry = await setup_homework(hass, mocked, options=OPTIONS)
    manager = entry.runtime_data.homework
    client = await hass_ws_client(hass)
    await label_service(hass, "add_homework_label", HOMEWORK, "ex")
    await override_service(hass, HOMEWORK, "disable")
    for appointment in fake.appointments[CHILD_ID]:
        if appointment["Id"] == HOMEWORK:
            appointment["InfoType"] = 0
    await entry.runtime_data.coordinator.async_refresh()
    await hass.async_block_till_done()
    response = await override(client, HOMEWORK, "clear")
    item = response["result"]["item"]
    assert item["override"] is None and item["info_type"] is None
    assert [label["id"] for label in item["manual_labels"]] == ["ex"]
    assert manager.stored_entries == 1  # the manual label stays
