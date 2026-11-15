"""AI coach: options flow, stored ``created_by``, payload and diagnostics."""

from __future__ import annotations

from typing import Any

import pytest
from aioresponses import aioresponses
from freezegun.api import FrozenDateTimeFactory
from homeassistant.auth.const import GROUP_ID_ADMIN, GROUP_ID_USER
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType, InvalidData

from custom_components.magister.coach_text import (
    DEFAULT_GUIDELINES,
    DEFAULT_PARENT_GUIDELINES,
)
from custom_components.magister.const import (
    CONF_COACH,
    CONF_PARENT_GUIDELINES,
    CONF_WEIGHTS,
    DOMAIN,
    GUIDELINES_MAX,
)
from custom_components.magister.diagnostics import async_get_config_entry_diagnostics

from .ha_helpers import NOW, FakeMagister, make_entry
from .test_coach import coach_options, make_user, setup_coach
from .test_homework import TODO_ID, uid

PROEFWERK = 100084
NORMAL = {key: 1.0 for key in ("homework", "test", "exam", "written_quiz", "oral_quiz")}


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
    assert result["menu_options"] == ["coach_child", "coach_parent"]
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"next_step_id": "coach_child"}
    )
    if child is not None:
        assert result["step_id"] == "coach_child"
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
        for o in result["data_schema"].schema[keys["students"]].config["options"]
    }
    assert "Leerling" in offered
    assert "Systeem" not in offered
    assert "Weg" not in offered
    assert admin.name in offered

    result = await _save(
        hass,
        result,
        {"enabled": True, "students": [student.id], "guidelines": "  Wees kort.  "},
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()
    assert entry.runtime_data is runtime  # no reload
    assert entry.options[CONF_COACH] == {
        "1001": {
            "enabled": True,
            "students": [student.id],
            "parents": [],
            "users": [student.id],
            "guidelines": "Wees kort.",
        }
    }
    assert entry.options[CONF_WEIGHTS] == {"1001": {"types": {}}}

    # Edit again: the stored text is suggested; the default text is not stored.
    result = await open_coach(hass, entry)
    keys = {str(k): k for k in result["data_schema"].schema}
    assert keys["guidelines"].description["suggested_value"] == "Wees kort."
    assert keys["students"].description["suggested_value"] == [student.id]
    await _save(
        hass,
        result,
        {"enabled": True, "students": [student.id], "guidelines": DEFAULT_GUIDELINES},
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
            **{
                "1001": {
                    "enabled": True,
                    "students": [student.id],
                    "guidelines": "Eigen.",
                }
            }
        ),
    )
    result = await open_coach(hass, entry)
    await _save(
        hass,
        result,
        {
            "enabled": True,
            "students": [student.id],
            "guidelines": "Eigen.",
            "reset_guidelines": True,
        },
    )
    assert entry.options[CONF_COACH]["1001"] == {
        "enabled": True,
        "students": [student.id],
        "parents": [],
        "users": [student.id],
    }
    result = await open_coach(hass, entry)
    await _save(hass, result, {"enabled": False, "students": [], "guidelines": ""})
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
            "students": [student.id],
            "guidelines": "x" * (GUIDELINES_MAX + 1),
        },
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"guidelines": "guidelines_too_long"}
    result = await _save(
        hass,
        result,
        {"enabled": True, "students": [student.id], "guidelines": "x" * 50},
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert entry.options[CONF_COACH]["1001"]["students"] == [student.id]


async def test_two_children_choose_one(
    hass: HomeAssistant, mocked: aioresponses
) -> None:
    """With several children the flow asks for the child first."""
    student = await make_user(hass)
    entry = await setup_coach(hass, mocked, {}, two=True)
    result = await open_coach(hass, entry, child="1002")
    assert result["description_placeholders"]["child"] == "Bram B"
    await _save(hass, result, {"enabled": True, "students": [student.id]})
    assert list(entry.options[CONF_COACH]) == ["1002"]
    result = await open_coach(hass, entry, child="1001")
    assert result["description_placeholders"]["child"] == "Anna A"
    await _save(hass, result, {"enabled": True, "students": [student.id]})
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
    assert data["coach"] == {
        "enabled_children": 2,
        "student_users": 2,
        "parent_users": 0,
        "linked_users": 2,
    }
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
    assert (saved["version"], saved["minor_version"]) == (1, 6)
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
    assert data["coach"] == {
        "enabled_children": 1,
        "student_users": 0,
        "parent_users": 0,
        "linked_users": 0,
    }


# -- M11: roles, parent guidelines, daily maximum ----------------------------------


async def test_roles_are_saved_per_child_and_refused_when_in_both(
    hass: HomeAssistant, mocked: aioresponses
) -> None:
    """Students and parents are two lists; the same user in both is refused."""
    student, parent = await make_user(hass, "Leerling"), await make_user(hass, "Ouder")
    entry = await setup_coach(hass, mocked, {})
    result = await open_coach(hass, entry)
    schema = result["data_schema"].schema
    keys = {str(k): k for k in schema}
    assert {"enabled", "students", "parents", "guidelines", "reset_guidelines"} == set(
        keys
    )
    assert "users" not in keys
    labels = {o["label"] for o in schema[keys["parents"]].config["options"]}
    assert {"Leerling", "Ouder"} <= labels
    result = await _save(
        hass,
        result,
        {"enabled": True, "students": [student.id], "parents": [student.id]},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"parents": "user_in_both_roles"}
    assert CONF_COACH not in entry.options
    # The form keeps what was typed.
    keys = {str(k): k for k in result["data_schema"].schema}
    assert keys["parents"].description["suggested_value"] == [student.id]
    result = await _save(
        hass,
        result,
        {"enabled": True, "students": [student.id], "parents": [parent.id]},
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert entry.options[CONF_COACH]["1001"] == {
        "enabled": True,
        "students": [student.id],
        "parents": [parent.id],
        "users": [student.id],
    }
    # Only parents is enough to keep the setting; the 1.6.0 mirror then holds nobody.
    result = await open_coach(hass, entry)
    await _save(
        hass, result, {"enabled": False, "students": [], "parents": [parent.id]}
    )
    assert entry.options[CONF_COACH]["1001"]["parents"] == [parent.id]
    assert entry.options[CONF_COACH]["1001"]["users"] == []
    result = await open_coach(hass, entry)
    await _save(hass, result, {"enabled": False, "students": [], "parents": []})
    assert CONF_COACH not in entry.options


async def test_old_users_key_shows_as_students_and_is_replaced_on_save(
    hass: HomeAssistant, mocked: aioresponses
) -> None:
    """A 1.6.0 setting opens with its users as students; saving writes the new keys."""
    student = await make_user(hass)
    entry = await setup_coach(
        hass,
        mocked,
        coach_options(**{"1001": {"enabled": True, "users": [student.id]}}),
    )
    result = await open_coach(hass, entry)
    keys = {str(k): k for k in result["data_schema"].schema}
    assert keys["students"].description["suggested_value"] == [student.id]
    assert keys["parents"].description["suggested_value"] == []
    await _save(hass, result, {"enabled": True, "students": [student.id]})
    assert entry.options[CONF_COACH]["1001"] == {
        "enabled": True,
        "students": [student.id],
        "parents": [],
        "users": [student.id],
    }


async def test_parent_only_child_mirrors_no_users(
    hass: HomeAssistant, mocked: aioresponses
) -> None:
    """The 1.6.0 `users` mirror holds the students only (empty for parents only)."""
    parent = await make_user(hass, "Ouder")
    entry = await setup_coach(hass, mocked, {})
    result = await open_coach(hass, entry)
    await _save(hass, result, {"enabled": True, "students": [], "parents": [parent.id]})
    assert entry.options[CONF_COACH]["1001"] == {
        "enabled": True,
        "students": [],
        "parents": [parent.id],
        "users": [],
    }


async def _open_parent(hass: HomeAssistant, entry: Any) -> Any:
    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"next_step_id": "coach"}
    )
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"next_step_id": "coach_parent"}
    )
    assert result["step_id"] == "coach_parent"
    return result


async def test_parent_guidelines_flow(
    hass: HomeAssistant, mocked: aioresponses
) -> None:
    """One text per entry: default suggested; empty, default and reset clear it."""
    entry = await setup_coach(hass, mocked, {}, two=True)
    runtime = entry.runtime_data
    result = await _open_parent(hass, entry)
    keys = {str(k): k for k in result["data_schema"].schema}
    assert keys["parent_guidelines"].description["suggested_value"] == (
        DEFAULT_PARENT_GUIDELINES
    )
    assert result["description_placeholders"] == {"max": "4000"}
    result = await _save(hass, result, {"parent_guidelines": "  Kort en bondig.  "})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()
    assert entry.options[CONF_PARENT_GUIDELINES] == "Kort en bondig."
    assert entry.runtime_data is runtime  # no reload
    # Edit again: the stored text is suggested.
    result = await _open_parent(hass, entry)
    keys = {str(k): k for k in result["data_schema"].schema}
    assert keys["parent_guidelines"].description["suggested_value"] == (
        "Kort en bondig."
    )
    # Too long.
    result = await _save(
        hass, result, {"parent_guidelines": "x" * (GUIDELINES_MAX + 1)}
    )
    assert result["errors"] == {"parent_guidelines": "guidelines_too_long"}
    assert entry.options[CONF_PARENT_GUIDELINES] == "Kort en bondig."
    # Exactly the limit is fine.
    result = await _save(hass, result, {"parent_guidelines": "x" * GUIDELINES_MAX})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    # The default text, empty text and the reset all remove the stored text.
    for submitted in (
        {"parent_guidelines": DEFAULT_PARENT_GUIDELINES},
        {"parent_guidelines": "   "},
        {"parent_guidelines": "Eigen.", "reset_guidelines": True},
        {},
    ):
        result = await _open_parent(hass, entry)
        await _save(hass, result, {"parent_guidelines": "Eerst."})
        assert entry.options[CONF_PARENT_GUIDELINES] == "Eerst."
        result = await _open_parent(hass, entry)
        await _save(hass, result, submitted)
        assert CONF_PARENT_GUIDELINES not in entry.options
    assert entry.runtime_data is runtime


async def test_diagnostics_count_roles_and_leave_parent_text_out(
    hass: HomeAssistant, mocked: aioresponses
) -> None:
    """Counts per role only; the parent guidelines text is not in the options shown."""
    a, p = await make_user(hass, "Anna"), await make_user(hass, "Ouder Geheim")
    entry = await setup_coach(
        hass,
        mocked,
        {
            **coach_options(
                **{"1001": {"enabled": True, "students": [a.id], "parents": [p.id]}}
            ),
            CONF_PARENT_GUIDELINES: "Heel persoonlijke tekst.",
            CONF_WEIGHTS: {"1001": {"daily_max_minutes": 120}},
        },
    )
    data = await async_get_config_entry_diagnostics(hass, entry)
    assert data["coach"] == {
        "enabled_children": 1,
        "student_users": 1,
        "parent_users": 1,
        "linked_users": 2,
    }
    text = str(data)
    for secret in (a.id, p.id, "Geheim", "persoonlijke"):
        assert secret not in text
    assert CONF_PARENT_GUIDELINES not in data["entry"]["options"]
    (child,) = data["children"]
    assert child["homework"]["daily_max_minutes"] == 120


# -- daily maximum --------------------------------------------------------------------


async def _open_daily_max(hass: HomeAssistant, entry: Any, child: str | None) -> Any:
    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"next_step_id": "daily_max"}
    )
    if child is not None:
        assert result["step_id"] == "daily_max"
        result = await hass.config_entries.options.async_configure(
            result["flow_id"], {"child": child}
        )
    assert result["step_id"] == "daily_max_settings"
    return result


async def test_daily_max_flow(hass: HomeAssistant, mocked: aioresponses) -> None:
    """Own menu item: default 90, steps of 15, stored with the weights, no reload."""
    entry = await setup_coach(
        hass,
        mocked,
        {CONF_WEIGHTS: {"1002": {"types": {"test": 2.0}}}},
        two=True,
    )
    runtime = entry.runtime_data
    result = await _open_daily_max(hass, entry, "1001")
    keys = {str(k): k for k in result["data_schema"].schema}
    assert keys["daily_max_minutes"].description["suggested_value"] == 90
    config = result["data_schema"].schema[keys["daily_max_minutes"]].config
    assert (config["min"], config["max"], config["step"]) == (15, 480, 15)
    assert result["description_placeholders"] == {"child": "Anna A", "default": "90"}
    # Outside the range or not a step of 15: an error, nothing stored.
    for bad in (0, 14, 481, 495):  # the selector refuses these
        with pytest.raises(InvalidData):
            await _save(hass, result, {"daily_max_minutes": bad})
    for bad in (16, 100, 479, 100.5):  # in range but not a step of 15
        result = await _save(hass, result, {"daily_max_minutes": bad})
        assert result["type"] is FlowResultType.FORM, bad
        assert result["errors"] == {"daily_max_minutes": "invalid_daily_max"}, bad
    assert entry.options[CONF_WEIGHTS] == {"1002": {"types": {"test": 2.0}}}
    result = await _save(hass, result, {"daily_max_minutes": 135.0})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()
    assert entry.runtime_data is runtime  # no reload
    assert entry.options[CONF_WEIGHTS] == {
        "1001": {"daily_max_minutes": 135},
        "1002": {"types": {"test": 2.0}},
    }
    manager = runtime.homework
    assert (manager.daily_max(1001), manager.daily_max(1002)) == (135, 90)
    # The second child keeps its other weights when its maximum is set and reset.
    result = await _open_daily_max(hass, entry, "1002")
    await _save(hass, result, {"daily_max_minutes": 15})
    assert entry.options[CONF_WEIGHTS]["1002"] == {
        "types": {"test": 2.0},
        "daily_max_minutes": 15,
    }
    result = await _open_daily_max(hass, entry, "1002")
    keys = {str(k): k for k in result["data_schema"].schema}
    assert keys["daily_max_minutes"].description["suggested_value"] == 15
    await _save(hass, result, {"daily_max_minutes": 90})
    assert entry.options[CONF_WEIGHTS]["1002"] == {"types": {"test": 2.0}}
    # Back to the default for the only setting removes the entry (and the option).
    result = await _open_daily_max(hass, entry, "1001")
    await _save(hass, result, {"daily_max_minutes": 90})
    assert "1001" not in entry.options[CONF_WEIGHTS]
    assert entry.runtime_data is runtime


async def test_daily_max_single_child_and_removal_of_empty_weights(
    hass: HomeAssistant, mocked: aioresponses
) -> None:
    """One child skips the choice; the weights option disappears when empty."""
    entry = await setup_coach(hass, mocked, {})
    result = await _open_daily_max(hass, entry, None)
    await _save(hass, result, {"daily_max_minutes": 480})
    assert entry.options[CONF_WEIGHTS] == {"1001": {"daily_max_minutes": 480}}
    result = await _open_daily_max(hass, entry, None)
    await _save(hass, result, {"daily_max_minutes": 90})
    assert CONF_WEIGHTS not in entry.options


async def test_weights_flow_keeps_the_daily_max(
    hass: HomeAssistant, mocked: aioresponses
) -> None:
    """Saving the weights keeps the child's daily maximum, even at all-default."""
    entry = await setup_coach(
        hass, mocked, {CONF_WEIGHTS: {"1001": {"daily_max_minutes": 150}}}
    )
    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"next_step_id": "weights"}
    )
    assert result["step_id"] == "weights_types"
    result = await _save(hass, result, {**NORMAL, "test": 3.0})
    while result["type"] is FlowResultType.FORM:
        normal = {str(k): 1.0 for k in result["data_schema"].schema}
        result = await _save(hass, result, normal)
    stored = entry.options[CONF_WEIGHTS]["1001"]
    assert stored["daily_max_minutes"] == 150
    assert stored["types"] == {"test": 3.0}
    # All weights back to normal: only the daily maximum is left.
    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"next_step_id": "weights"}
    )
    result = await _save(hass, result, NORMAL)
    while result["type"] is FlowResultType.FORM:
        normal = {str(k): 1.0 for k in result["data_schema"].schema}
        result = await _save(hass, result, normal)
    assert entry.options[CONF_WEIGHTS] == {
        "1001": {"types": {}, "subjects": {}, "daily_max_minutes": 150}
    }
