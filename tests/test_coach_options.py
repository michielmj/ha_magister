"""AI coach: options flow, stored ``created_by``, payload and diagnostics."""

from __future__ import annotations

from typing import Any

import pytest
from aioresponses import aioresponses
from freezegun.api import FrozenDateTimeFactory
from homeassistant.auth.const import GROUP_ID_ADMIN, GROUP_ID_USER
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from custom_components.magister.coach_text import DEFAULT_GUIDELINES
from custom_components.magister.const import (
    CONF_COACH,
    CONF_WEIGHTS,
    DOMAIN,
    GUIDELINES_MAX,
)
from custom_components.magister.diagnostics import async_get_config_entry_diagnostics

from .ha_helpers import NOW, FakeMagister, make_entry
from .test_coach import coach_options, make_user, setup_coach
from .test_homework import TODO_ID, uid

PROEFWERK = 100084


@pytest.fixture(autouse=True)
async def frozen_now(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> FrozenDateTimeFactory:
    """Friday 13 November 2026."""
    await hass.config.async_set_time_zone("Europe/Amsterdam")
    freezer.move_to(NOW)
    return freezer


async def open_coach(hass: HomeAssistant, entry: Any, child: str | None = None) -> Any:
    """The coach form of the options flow (choosing ``child`` when asked)."""
    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"next_step_id": "coach"}
    )
    if child is not None:
        assert result["step_id"] == "coach"
        result = await hass.config_entries.options.async_configure(
            result["flow_id"], {"child": child}
        )
    assert result["step_id"] == "coach_settings"
    return result


async def test_enable_link_users_and_edit_guidelines(
    hass: HomeAssistant, mocked: aioresponses
) -> None:
    """Saving applies at once (no reload) and stores per child."""
    student = await make_user(hass, "Leerling")
    admin = await hass.auth.async_create_user("Beheer", group_ids=[GROUP_ID_ADMIN])
    await hass.auth.async_create_system_user("Systeem")
    inactive = await hass.auth.async_create_user("Weg", group_ids=[GROUP_ID_USER])
    await hass.auth.async_update_user(inactive, is_active=False)
    entry = await setup_coach(hass, mocked, {CONF_WEIGHTS: {"1001": {"types": {}}}})
    runtime = entry.runtime_data

    result = await open_coach(hass, entry)
    keys = {str(k): k for k in result["data_schema"].schema}
    assert keys["enabled"].description["suggested_value"] is False
    assert keys["guidelines"].description["suggested_value"] == DEFAULT_GUIDELINES
    offered = {
        o["label"]
        for o in result["data_schema"].schema[keys["users"]].config["options"]
    }
    assert "Leerling" in offered
    assert "Systeem" not in offered
    assert "Weg" not in offered
    assert admin.name in offered

    result = await _save(
        hass,
        result,
        {"enabled": True, "users": [student.id], "guidelines": "  Wees kort.  "},
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()
    assert entry.runtime_data is runtime  # no reload
    assert entry.options[CONF_COACH] == {
        "1001": {
            "enabled": True,
            "users": [student.id],
            "guidelines": "Wees kort.",
        }
    }
    assert entry.options[CONF_WEIGHTS] == {"1001": {"types": {}}}

    # Edit again: the stored text is suggested; the default text is not stored.
    result = await open_coach(hass, entry)
    keys = {str(k): k for k in result["data_schema"].schema}
    assert keys["guidelines"].description["suggested_value"] == "Wees kort."
    assert keys["users"].description["suggested_value"] == [student.id]
    await _save(
        hass,
        result,
        {"enabled": True, "users": [student.id], "guidelines": DEFAULT_GUIDELINES},
    )
    assert "guidelines" not in entry.options[CONF_COACH]["1001"]


async def _save(hass: HomeAssistant, result: Any, data: dict[str, Any]) -> Any:
    return await hass.config_entries.options.async_configure(result["flow_id"], data)


async def test_reset_and_empty_guidelines_and_turn_off(
    hass: HomeAssistant, mocked: aioresponses
) -> None:
    """Empty or reset means the default; fully off removes the setting."""
    student = await make_user(hass)
    entry = await setup_coach(
        hass,
        mocked,
        coach_options(
            **{"1001": {"enabled": True, "users": [student.id], "guidelines": "Eigen."}}
        ),
    )
    result = await open_coach(hass, entry)
    await _save(
        hass,
        result,
        {
            "enabled": True,
            "users": [student.id],
            "guidelines": "Eigen.",
            "reset_guidelines": True,
        },
    )
    assert entry.options[CONF_COACH]["1001"] == {"enabled": True, "users": [student.id]}
    result = await open_coach(hass, entry)
    await _save(hass, result, {"enabled": False, "users": [], "guidelines": ""})
    assert CONF_COACH not in entry.options


async def test_guidelines_too_long_and_unknown_users(
    hass: HomeAssistant, mocked: aioresponses
) -> None:
    """Too long text is an error; users that do not exist are dropped."""
    student = await make_user(hass)
    entry = await setup_coach(hass, mocked, {})
    result = await open_coach(hass, entry)
    result = await _save(
        hass,
        result,
        {
            "enabled": True,
            "users": [student.id],
            "guidelines": "x" * (GUIDELINES_MAX + 1),
        },
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"guidelines": "guidelines_too_long"}
    result = await _save(
        hass, result, {"enabled": True, "users": [student.id], "guidelines": "x" * 50}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert entry.options[CONF_COACH]["1001"]["users"] == [student.id]


async def test_two_children_choose_one(
    hass: HomeAssistant, mocked: aioresponses
) -> None:
    """With several children the flow asks for the child first."""
    student = await make_user(hass)
    entry = await setup_coach(hass, mocked, {}, two=True)
    result = await open_coach(hass, entry, child="1002")
    assert result["description_placeholders"]["child"] == "Bram B"
    await _save(hass, result, {"enabled": True, "users": [student.id]})
    assert list(entry.options[CONF_COACH]) == ["1002"]
    result = await open_coach(hass, entry, child="1001")
    assert result["description_placeholders"]["child"] == "Anna A"
    await _save(hass, result, {"enabled": True, "users": [student.id]})
    assert set(entry.options[CONF_COACH]) == {"1001", "1002"}


async def test_diagnostics_count_only(
    hass: HomeAssistant, mocked: aioresponses
) -> None:
    """Counts of enabled children and linked users, no names, ids or text."""
    a, b = await make_user(hass, "Anna"), await make_user(hass, "Bram")
    entry = await setup_coach(
        hass,
        mocked,
        coach_options(
            **{
                "1001": {
                    "enabled": True,
                    "users": [a.id, b.id],
                    "guidelines": "Geheim.",
                },
                "1002": {"enabled": True, "users": [a.id]},
            }
        ),
        two=True,
    )
    data = await async_get_config_entry_diagnostics(hass, entry)
    assert data["coach"] == {"enabled_children": 2, "linked_users": 2}
    text = str(data)
    assert "Geheim" not in text
    assert a.id not in text
    assert CONF_COACH not in data["entry"]["options"]


async def test_created_by_in_payload_and_store(
    hass: HomeAssistant, mocked: aioresponses, hass_storage: dict[str, Any]
) -> None:
    """Subtasks of the card or service are ``user``; stored ones without it too."""
    entry = make_entry()
    key = f"{DOMAIN}.homework.{entry.entry_id}"
    hass_storage[key] = {
        "version": 1,
        "minor_version": 4,
        "key": key,
        "data": {
            "items": {
                uid(PROEFWERK): {
                    "progress": 0,
                    "last_partial": 0,
                    "updated": "",
                    "labels": [],
                    "subtasks": [
                        {
                            "id": "old",
                            "title": "Oud",
                            "planned": "2026-11-16",
                            "progress": 0,
                            "last_partial": 0,
                            "completed_on": None,
                        },
                        {
                            "id": "ai",
                            "title": "Van AI",
                            "planned": "2026-11-16",
                            "progress": 0,
                            "last_partial": 0,
                            "completed_on": None,
                            "created_by": "ai",
                        },
                        {
                            "id": "bad",
                            "title": "Vreemd",
                            "planned": "2026-11-16",
                            "progress": 0,
                            "last_partial": 0,
                            "completed_on": None,
                            "created_by": "robot",
                        },
                    ],
                }
            }
        },
    }
    FakeMagister(mocked)
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    entity = hass.data["todo"].get_entity(TODO_ID)
    subtasks = next(i for i in entity.payload()["items"] if i["uid"] == uid(PROEFWERK))[
        "subtasks"
    ]
    assert {s["title"]: s["created_by"] for s in subtasks} == {
        "Oud": "user",
        "Van AI": "ai",
        "Vreemd": "user",
    }
    # A service call (the card, automations) creates a "user" subtask.
    await hass.services.async_call(
        DOMAIN,
        "add_homework_subtask",
        {"entity_id": TODO_ID, "item": uid(PROEFWERK), "title": "Nieuw"},
        blocking=True,
    )
    assert await hass.config_entries.async_unload(entry.entry_id)
    saved = hass_storage[key]
    assert (saved["version"], saved["minor_version"]) == (1, 5)
    stored = {
        s["title"]: s["created_by"]
        for s in saved["data"]["items"][uid(PROEFWERK)]["subtasks"]
    }
    assert stored == {"Oud": "user", "Van AI": "ai", "Vreemd": "user", "Nieuw": "user"}


async def test_diagnostics_users_none(
    hass: HomeAssistant, mocked: aioresponses
) -> None:
    """A stored ``users: null`` does not break the diagnostics."""
    entry = await setup_coach(
        hass, mocked, coach_options(**{"1001": {"enabled": True, "users": None}})
    )
    data = await async_get_config_entry_diagnostics(hass, entry)
    assert data["coach"] == {"enabled_children": 1, "linked_users": 0}
