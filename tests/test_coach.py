"""AI homework coach: LLM API, tools, access control, logbook, prompt."""

from __future__ import annotations

import dataclasses
import json
import logging
import re
from types import MappingProxyType
from typing import Any

import probatio
import pytest
from aioresponses import aioresponses
from freezegun.api import FrozenDateTimeFactory
from homeassistant.auth.const import GROUP_ID_USER
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import Context, HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import llm
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_capture_events,
)

from custom_components.magister.coach import (
    COACH_API_ID,
    COACH_API_NAME,
    CoachError,
    async_accessible_children,
    coach_tools,
    pick_child,
)
from custom_components.magister.coach_text import DEFAULT_GUIDELINES
from custom_components.magister.const import (
    CONF_COACH,
    DOMAIN,
)
from custom_components.magister.todo import MagisterHomeworkTodo

from .api.helpers import RETURN_URL
from .ha_helpers import NOW, FakeMagister, make_entry

HOMEWORK = "100065"  # wiskunde, Monday 16 Nov, Huiswerk
PROEFWERK = "100084"  # Duitse taal, Thursday 19 Nov, Proefwerk
TWO_CHILDREN = [
    {"Id": 1001, "Roepnaam": "Anna", "Achternaam": "", "Tussenvoegsel": ""},
    {"Id": 1002, "Roepnaam": "Bram", "Achternaam": "", "Tussenvoegsel": ""},
]


@pytest.fixture(autouse=True)
async def frozen_now(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> FrozenDateTimeFactory:
    """Friday 13 November 2026, 10:30 in Amsterdam."""
    await hass.config.async_set_time_zone("Europe/Amsterdam")
    freezer.move_to(NOW)
    return freezer


async def make_user(hass: HomeAssistant, name: str = "Leerling") -> Any:
    """A non-admin Home Assistant user."""
    return await hass.auth.async_create_user(name, group_ids=[GROUP_ID_USER])


def coach_options(**per_child: dict[str, Any]) -> dict[str, Any]:
    """The ``coach`` option for children ``{"1001": {...}}``."""
    return {CONF_COACH: dict(per_child)}


async def setup_coach(
    hass: HomeAssistant,
    mocked: aioresponses,
    options: dict[str, Any],
    *,
    two: bool = False,
) -> MockConfigEntry:
    """Set up an entry (one or two children) with coach options."""
    if two:
        FakeMagister(mocked, children=TWO_CHILDREN)
        entry = make_entry(
            children=[(1001, "Anna A"), (1002, "Bram B")], options=options
        )
    else:
        FakeMagister(mocked)
        entry = make_entry(options=options)
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


def llm_context(user_id: str | None) -> llm.LLMContext:
    """The context an MCP request gives the tools."""
    return llm.LLMContext(
        platform="mcp_server",
        context=Context(user_id=user_id),
        language="*",
        assistant="conversation",
        device_id=None,
    )


async def call(
    hass: HomeAssistant, user_id: str | None, tool: str, **args: Any
) -> llm.ToolResult:
    """Call a tool the way the MCP server does."""
    api = await llm.async_get_api(hass, COACH_API_ID, llm_context(user_id))
    return await api.async_call_tool(llm.ToolInput(tool_name=tool, tool_args=args))


async def ok(hass: HomeAssistant, user_id: str, tool: str, **args: Any) -> Any:
    """A tool call that must succeed: its data."""
    result = await call(hass, user_id, tool, **args)
    assert not result.error, result.data
    return result.data


async def fails(hass: HomeAssistant, user_id: str, tool: str, **args: Any) -> str:
    """A tool call that must fail: the error code."""
    result = await call(hass, user_id, tool, **args)
    assert result.error, result.data
    return str(result.data["error"])


@pytest.fixture
async def student(hass: HomeAssistant, mocked: aioresponses) -> Any:
    """One child, coach on, linked to a student user."""
    user = await make_user(hass)
    entry = await setup_coach(
        hass, mocked, coach_options(**{"1001": {"enabled": True, "users": [user.id]}})
    )
    user.entry = entry
    return user


@pytest.fixture
def logbook(hass: HomeAssistant) -> list[Any]:
    """The logbook entries that are written."""
    return async_capture_events(hass, "logbook_entry")


# -- registration -----------------------------------------------------------------


async def test_api_registered_once_and_unregistered(
    hass: HomeAssistant, mocked: aioresponses
) -> None:
    """One API per instance, shared by entries, removed with the last entry."""
    steps = [
        {"action": "username"},
        {"action": "password"},
        {"redirectURL": RETURN_URL},
    ]
    FakeMagister(mocked, children=TWO_CHILDREN, challenges=[*steps, *steps])
    first = make_entry(children=[(1001, "Anna A")], unique_id="school.magister.net:1")
    second = make_entry(children=[(1002, "Bram B")], unique_id="school.magister.net:2")
    first.add_to_hass(hass)
    assert await hass.config_entries.async_setup(first.entry_id)
    api = next(a for a in llm.async_get_apis(hass) if a.id == COACH_API_ID)
    assert api.name == COACH_API_NAME == "Magister huiswerkcoach"
    second.add_to_hass(hass)
    assert await hass.config_entries.async_setup(second.entry_id)
    await hass.async_block_till_done()
    assert [a.id for a in llm.async_get_apis(hass)].count(COACH_API_ID) == 1
    assert await hass.config_entries.async_unload(first.entry_id)
    assert COACH_API_ID in [a.id for a in llm.async_get_apis(hass)]
    assert await hass.config_entries.async_unload(second.entry_id)
    assert COACH_API_ID not in [a.id for a in llm.async_get_apis(hass)]


async def test_tool_annotations_and_schemas(student: Any, hass: HomeAssistant) -> None:
    """Read tools are read-only; deletes are destructive; all closed-world."""
    tools = {t.name: t for t in coach_tools()}
    assert set(tools) == {
        "list_children",
        "get_schedule",
        "get_overview",
        "list_homework",
        "get_progress",
        "list_label_options",
        "add_subtask",
        "update_subtask",
        "delete_subtask",
        "set_progress",
        "add_label",
        "remove_label",
        "set_label_override",
        "list_context",
        "add_context",
        "update_context",
        "delete_context",
        "clear_context",
        "list_proposals",
        "propose_daily_max",
        "respond_to_proposal",
    }
    for name in tools.values():
        assert name.description
        assert name.annotations.open_world is False
    read = {"list_children", "get_schedule", "get_overview", "list_homework"}
    read.add("get_progress")
    read.add("list_label_options")
    read.add("list_context")
    read.add("list_proposals")
    for name, tool in tools.items():
        assert tool.annotations.read_only is (name in read)
        if name in read:
            assert tool.annotations.destructive is False
    assert tools["delete_subtask"].annotations.destructive
    assert tools["remove_label"].annotations.destructive
    assert not tools["add_subtask"].annotations.idempotent
    assert tools["set_progress"].annotations.idempotent


async def test_minutes_schema_is_integer_or_null(hass: HomeAssistant) -> None:
    """MCP shows ``minutes`` as integer or null; the shared check decides at runtime."""
    tools = {t.name: t for t in coach_tools()}
    for name in ("add_subtask", "update_subtask"):
        # As the MCP server of Home Assistant converts it.
        schema = probatio.to_openapi(tools[name].parameters, openapi_version="3.1.0")
        minutes = dict(schema["properties"]["minutes"])
        minutes.pop("description")
        assert minutes == {"anyOf": [{"type": "integer"}, {"type": "null"}]}, name
        assert "minutes" not in schema.get("required", [])


async def test_overdue_days_schema_is_integer(hass: HomeAssistant) -> None:
    """MCP shows ``overdue_days`` as an integer; the shared check decides the range."""
    tools = {t.name: t for t in coach_tools()}
    schema = probatio.to_openapi(
        tools["list_homework"].parameters, openapi_version="3.1.0"
    )
    assert schema["properties"]["overdue_days"]["type"] == "integer"
    assert "overdue_days" not in schema.get("required", [])


# -- access -----------------------------------------------------------------------


async def test_unlinked_and_anonymous_get_nothing(
    hass: HomeAssistant, student: Any
) -> None:
    """A user that is not linked (or no user) sees nothing, with a hint."""
    other = await make_user(hass, "Anders")
    for user_id in (other.id, None, "does-not-exist"):
        data = await ok(hass, user_id, "list_children")  # type: ignore[arg-type]
        assert data["children"] == []
        assert "AI-coach" in data["message"]
        for tool in ("list_homework", "get_progress", "list_label_options"):
            result = await call(hass, user_id, tool)
            assert result.error
            assert result.data["error"] == "not_linked"
        assert (
            await call(
                hass, user_id, "get_schedule", start="2026-11-13", end="2026-11-14"
            )
        ).data["error"] == "not_linked"
        assert (
            await call(hass, user_id, "add_subtask", item=PROEFWERK, title="x")
        ).data["error"] == "not_linked"
    manager = student.entry.runtime_data.homework
    assert not any(item.subtasks for item in manager.items(1001))


async def test_disabled_coach_and_inactive_user_have_no_access(
    hass: HomeAssistant, mocked: aioresponses
) -> None:
    """Coach off, or an inactive or system user: no access."""
    await make_user(hass, "Eigenaar")  # the first user is the owner
    user = await make_user(hass)
    entry = await setup_coach(
        hass,
        mocked,
        coach_options(**{"1001": {"enabled": False, "users": [user.id]}}),
    )
    # Linked, but the coach is off: a clearer error, which names no child.
    assert await fails(hass, user.id, "list_homework") == "coach_not_enabled"
    # Changing the options applies at once, without a reload.
    runtime = entry.runtime_data
    hass.config_entries.async_update_entry(
        entry,
        options=coach_options(**{"1001": {"enabled": True, "users": [user.id]}}),
    )
    await hass.async_block_till_done()
    assert entry.runtime_data is runtime
    assert (await ok(hass, user.id, "list_children"))["children"] == [
        {
            "id": "1001",
            "name": "Kind",
            "role": "student",
            "daily_max_minutes": 90,
            "daily_max_weekdays": [90] * 7,
        }
    ]
    await hass.auth.async_update_user(user, is_active=False)
    assert (await ok(hass, user.id, "list_children"))["children"] == []
    await hass.auth.async_update_user(user, is_active=True)
    hass.config_entries.async_update_entry(
        entry,
        options=coach_options(**{"1001": {"enabled": True, "users": []}}),
    )
    assert await fails(hass, user.id, "get_progress") == "not_linked"
    # An inactive user is not told anything about the linking.
    hass.config_entries.async_update_entry(
        entry,
        options=coach_options(**{"1001": {"enabled": False, "users": [user.id]}}),
    )
    await hass.auth.async_update_user(user, is_active=False)
    assert await fails(hass, user.id, "get_progress") == "not_linked"


async def test_not_enabled_only_for_loaded_active_users(
    hass: HomeAssistant, mocked: aioresponses
) -> None:
    """Not loaded entry, system user, inactive user: `not_linked`, nothing announced."""
    unloaded = await make_user(hass, "Ontladen")
    other = await make_user(hass, "Ander")
    system = await hass.auth.async_create_system_user("Systeem")
    inactive = await make_user(hass, "Inactief")
    await setup_coach(
        hass,
        mocked,
        coach_options(
            **{
                "1001": {
                    "enabled": False,
                    "users": [system.id, inactive.id],
                    "parents": [other.id],
                }
            }
        ),
    )
    # A second entry that is not loaded, with a disabled child linked to `unloaded`.
    idle = make_entry(
        children=[(2001, "Cas C")],
        unique_id="idle",
        options=coach_options(**{"2001": {"enabled": False, "users": [unloaded.id]}}),
    )
    idle.add_to_hass(hass)
    assert idle.state is not ConfigEntryState.LOADED
    # Linked to a disabled child: announced while active and loaded.
    assert await fails(hass, inactive.id, "get_progress") == "coach_not_enabled"
    # An inactive user's prompt does not say "not enabled".
    await hass.auth.async_update_user(inactive, is_active=False)
    api = await llm.async_get_api(hass, COACH_API_ID, llm_context(inactive.id))
    assert "not enabled" not in api.api_prompt
    assert await fails(hass, inactive.id, "get_progress") == "not_linked"
    # A system user is never told anything about the linking.
    assert await fails(hass, system.id, "get_progress") == "not_linked"
    # An entry that is not loaded does not count.
    assert await fails(hass, unloaded.id, "get_progress") == "not_linked"


async def test_user_of_child_a_cannot_touch_child_b(
    hass: HomeAssistant, mocked: aioresponses, logbook: list[Any]
) -> None:
    """Linked to Anna only: Bram's data can neither be read nor written."""
    anna, bram = await make_user(hass, "Anna"), await make_user(hass, "Bram")
    await setup_coach(
        hass,
        mocked,
        coach_options(
            **{
                "1001": {"enabled": True, "users": [anna.id]},
                "1002": {"enabled": True, "users": [bram.id]},
            }
        ),
        two=True,
    )
    children = (await ok(hass, anna.id, "list_children"))["children"]
    assert children == [
        {
            "id": "1001",
            "name": "Anna",
            "role": "student",
            "daily_max_minutes": 90,
            "daily_max_weekdays": [90] * 7,
        }
    ]
    # The only child is implied; Bram's id (or name) is refused like an unknown one.
    for wrong in ("1002", "Bram", "9999", 1002):
        for tool, args in (
            ("list_homework", {}),
            ("get_progress", {}),
            ("list_label_options", {}),
            ("get_schedule", {"start": "2026-11-13", "end": "2026-11-13"}),
            ("add_subtask", {"item": PROEFWERK, "title": "x"}),
            ("set_progress", {"id": HOMEWORK, "progress": 50}),
            ("add_label", {"appointment": HOMEWORK, "label": "default_test"}),
        ):
            assert await fails(hass, anna.id, tool, child=wrong, **args) == (
                "child_not_found"
            )
    assert logbook == []
    manager = next(
        iter(hass.config_entries.async_entries(DOMAIN))
    ).runtime_data.homework
    assert not any(
        item.subtasks for child in (1001, 1002) for item in manager.items(child)
    )
    # Bram's own user sees Bram.
    assert (await ok(hass, bram.id, "list_children"))["children"] == [
        {
            "id": "1002",
            "name": "Bram",
            "role": "student",
            "daily_max_minutes": 90,
            "daily_max_weekdays": [90] * 7,
        }
    ]


async def test_parent_with_two_children_must_pass_child(
    hass: HomeAssistant, mocked: aioresponses
) -> None:
    """A user linked to both children has to say which one."""
    parent = await make_user(hass, "Ouder")
    await setup_coach(
        hass,
        mocked,
        coach_options(
            **{
                "1001": {"enabled": True, "users": [parent.id]},
                "1002": {"enabled": True, "users": [parent.id]},
            }
        ),
        two=True,
    )
    children = (await ok(hass, parent.id, "list_children"))["children"]
    assert {c["name"] for c in children} == {"Anna", "Bram"}
    result = await call(hass, parent.id, "get_progress")
    assert result.data["error"] == "child_required"
    assert "1001" in result.data["message"]
    data = await ok(hass, parent.id, "get_progress", child="1002")
    assert data["child"] == "1002"
    # A child can also be named by first name (among the accessible ones).
    assert (await ok(hass, parent.id, "get_progress", child="anna"))["child"] == "1001"
    assert await fails(hass, parent.id, "get_progress", child=" ") == "child_required"


async def test_invalid_input_is_a_structured_error(
    hass: HomeAssistant, student: Any
) -> None:
    """Bad arguments return ``invalid_format`` instead of raising."""
    for tool, args in (
        ("add_subtask", {"item": PROEFWERK}),
        ("add_subtask", {"item": PROEFWERK, "title": "x", "date": "no"}),
        ("add_subtask", {"item": PROEFWERK, "title": " "}),
        ("add_subtask", {"item": "other.host:1002:5", "title": "x"}),
        ("add_subtask", {"item": PROEFWERK, "title": "x" * 101}),
        ("update_subtask", {"subtask": f"{PROEFWERK}:sub:ab", "title": " "}),
        ("set_progress", {"id": HOMEWORK, "progress": 101}),
        ("set_progress", {"id": HOMEWORK, "progress": True}),
        ("set_progress", {"id": HOMEWORK, "progress": 10, "extra": 1}),
        ("add_label", {"appointment": "../x", "label": "a"}),
        (
            "add_label",
            {"appointment": HOMEWORK, "label": "default_test", "note": "n" * 201},
        ),
        ("set_label_override", {"appointment": HOMEWORK, "mode": "bogus"}),
        ("get_schedule", {"start": "2026-11-13", "end": "2026-11-01"}),
        ("get_schedule", {"start": "2026-11-01", "end": "2026-12-31"}),
        ("get_schedule", {"start": "x", "end": "2026-12-31"}),
        ("list_homework", {"start": "x"}),
    ):
        assert await fails(hass, student.id, tool, **args) == "invalid_format", (
            tool,
            args,
        )


# -- read tools -------------------------------------------------------------------


async def test_read_tools(hass: HomeAssistant, student: Any) -> None:
    """Schedule, homework, progress and labels, for the linked child."""
    data = await ok(
        hass, student.id, "get_schedule", start="2026-11-19", end="2026-11-19"
    )
    assert data["child"] == "1001"
    lessons = {a["id"]: a for a in data["appointments"]}
    test = lessons[PROEFWERK]
    assert test["date"] == "2026-11-19"
    assert test["subject"] == "Duitse taal"
    assert test["location"] == "123"
    assert test["start"] == "11:05"
    assert test["magister_label"] == "Proefwerk"
    assert test["cancelled"] is False
    assert set(test) == {
        "id",
        "date",
        "start",
        "end",
        "all_day",
        "lesson_hour",
        "subject",
        "location",
        "cancelled",
        "info_type",
        "magister_label",
        "manual_labels",
        "override",
    }
    # Outside the fetched window: only the part inside is returned.
    far = await ok(
        hass, student.id, "get_schedule", start="2027-06-01", end="2027-06-02"
    )
    assert far["appointments"] == []
    assert far["available_from"] < far["available_until"]

    homework = await ok(
        hass, student.id, "list_homework", start="2026-11-16", end="2026-11-20"
    )
    assert homework["today"] == "2026-11-13"
    ids = {i["id"] for i in homework["items"]}
    assert {HOMEWORK, PROEFWERK} <= ids
    item = next(i for i in homework["items"] if i["id"] == PROEFWERK)
    assert item["label"] == "Proefwerk"
    assert item["is_test"] is True
    assert item["subtasks"] == []
    assert "uid" not in item
    assert all(
        d["date"] >= "2026-11-16" and d["date"] <= "2026-11-20"
        for d in homework["items"]
    )
    default = await ok(hass, student.id, "list_homework")
    assert any(i["date"] < "2026-11-13" for i in default["items"])  # overdue

    progress = await ok(hass, student.id, "get_progress")
    assert set(progress["progress"]) == {"next_day", "week", "next_week"}
    assert progress["progress"]["week"]["items"] > 0

    labels = await ok(hass, student.id, "list_label_options")
    assert [lb["name"] for lb in labels["labels"]][:2] == ["Huiswerk", "Proefwerk"]


async def test_include_completed(hass: HomeAssistant, student: Any) -> None:
    """Completed items only show up when asked for."""
    await ok(hass, student.id, "set_progress", id=HOMEWORK, progress=100)
    open_items = await ok(hass, student.id, "list_homework", start="2026-11-16")
    assert HOMEWORK not in {i["id"] for i in open_items["items"]}
    everything = await ok(
        hass, student.id, "list_homework", start="2026-11-16", include_completed=True
    )
    done = next(i for i in everything["items"] if i["id"] == HOMEWORK)
    assert done["completed"] is True


async def test_overdue_items(hass: HomeAssistant, student: Any) -> None:
    """Open overdue items are listed by default; completed ones and a start date not."""
    default = await ok(hass, student.id, "list_homework")
    overdue = [i for i in default["items"] if i["date"] < "2026-11-13"]
    assert overdue
    assert all(not i["completed"] for i in overdue)
    plain = await ok(hass, student.id, "list_homework", include_overdue=False)
    assert all(i["date"] >= "2026-11-13" for i in plain["items"])
    assert len(plain["items"]) == len(default["items"]) - len(overdue)
    ranged = await ok(hass, student.id, "list_homework", start="2026-11-13")
    assert [i["id"] for i in ranged["items"]] == [i["id"] for i in plain["items"]]
    # Completing an overdue item takes it off the default list.
    first = overdue[0]["id"]
    await ok(hass, student.id, "set_progress", id=first, progress=100)
    again = await ok(hass, student.id, "list_homework")
    assert first not in {i["id"] for i in again["items"]}
    # An `end` before today still bounds the overdue items.
    bounded = await ok(hass, student.id, "list_homework", end="2026-11-05")
    assert all(i["date"] <= "2026-11-05" for i in bounded["items"])


async def test_overdue_window(hass: HomeAssistant, student: Any) -> None:
    """Default 7 days back (today 13 Nov: from 6 Nov), `overdue_days` widens it."""

    async def dates(**args: Any) -> list[str]:
        data = await ok(hass, student.id, "list_homework", **args)
        return [i["date"] for i in data["items"] if i["date"] < "2026-11-13"]

    default = await dates()
    assert default
    assert min(default) == "2026-11-06"
    assert await dates(overdue_days=7) == default
    assert min(await dates(overdue_days=1)) == "2026-11-12"
    assert set(await dates(overdue_days=1)) == {"2026-11-12"}
    assert min(await dates(overdue_days=35)) < "2026-11-06"
    assert len(await dates(overdue_days=35)) > len(default)
    # Switched off, or a start date: no overdue part.
    assert await dates(include_overdue=False) == []
    assert await dates(overdue_days=35, include_overdue=False) == []
    assert await dates(start="2026-11-13", overdue_days=35) == []


async def test_overdue_minimum_uses_the_local_date(
    hass: HomeAssistant, student: Any, freezer: FrozenDateTimeFactory
) -> None:
    """23:30 UTC on 12 Nov is 13 Nov in Amsterdam: overdue starts 7 days before that."""
    freezer.move_to("2026-11-12T23:30:00+00:00")
    data = await ok(hass, student.id, "list_homework")
    dates = [i["date"] for i in data["items"] if i["date"] < "2026-11-13"]
    assert min(dates) == "2026-11-06"


@pytest.mark.parametrize("value", [0, 36, -1, 7.5, "7", True, None])
async def test_overdue_days_invalid(
    hass: HomeAssistant, student: Any, value: Any
) -> None:
    """Outside 1 to 35, or not a whole number: invalid_format."""
    assert (
        await fails(hass, student.id, "list_homework", overdue_days=value)
        == "invalid_format"
    )


async def test_cancelled_items_are_not_overdue(
    hass: HomeAssistant, student: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A cancelled lesson is never overdue, but listed inside a requested window."""
    manager = student.entry.runtime_data.homework
    real = type(manager).items
    target = "100057"  # 12 Nov, overdue

    def items(self: Any, child_id: int) -> Any:
        return [
            dataclasses.replace(i, cancelled=True)
            if i.appointment_id == int(target)
            else i
            for i in real(self, child_id)
        ]

    monkeypatch.setattr(type(manager), "items", items)
    default = await ok(hass, student.id, "list_homework")
    assert target not in {i["id"] for i in default["items"]}
    wide = await ok(hass, student.id, "list_homework", overdue_days=35)
    assert target not in {i["id"] for i in wide["items"]}
    window = await ok(
        hass, student.id, "list_homework", start="2026-11-12", end="2026-11-12"
    )
    item = next(i for i in window["items"] if i["id"] == target)
    assert item["cancelled"] is True


async def test_coach_not_enabled_vs_not_linked(
    hass: HomeAssistant, mocked: aioresponses
) -> None:
    """Linked only to disabled children: `coach_not_enabled`; no names anywhere."""
    off = await make_user(hass, "Uit")
    mixed = await make_user(hass, "Gemengd")
    stranger = await make_user(hass, "Vreemde")
    await setup_coach(
        hass,
        mocked,
        coach_options(
            **{
                "1001": {"enabled": False, "users": [off.id], "parents": [mixed.id]},
                "1002": {"enabled": True, "users": [mixed.id]},
            }
        ),
        two=True,
    )
    calls: list[tuple[str, dict[str, Any]]] = [
        ("get_schedule", {"start": "2026-11-13", "end": "2026-11-14"}),
        ("get_overview", {"start": "2026-11-13", "end": "2026-11-14"}),
        ("list_homework", {}),
        ("get_progress", {}),
        ("list_label_options", {}),
        ("add_subtask", {"item": PROEFWERK, "title": "x"}),
        ("update_subtask", {"subtask": f"{PROEFWERK}:sub:1", "title": "x"}),
        ("delete_subtask", {"subtask": f"{PROEFWERK}:sub:1"}),
        ("set_progress", {"id": PROEFWERK, "progress": 50}),
        ("add_label", {"appointment": PROEFWERK, "label": "SO"}),
        ("remove_label", {"appointment": PROEFWERK, "label": "SO"}),
        ("set_label_override", {"appointment": PROEFWERK, "mode": "clear"}),
    ]
    for user, code in ((off, "coach_not_enabled"), (stranger, "not_linked")):
        for tool, args in calls:
            result = await call(hass, user.id, tool, **args)
            assert result.error, tool
            assert result.data["error"] == code, tool
            assert "Anna" not in result.data["message"]
            assert "Bram" not in result.data["message"]
        listed = await ok(hass, user.id, "list_children")
        assert listed["children"] == []
        assert ("Settings per child" in listed["message"]) is (
            code == "coach_not_enabled"
        )
        api = await llm.async_get_api(hass, COACH_API_ID, llm_context(user.id))
        assert ("coach is not enabled" in api.api_prompt) is (
            code == "coach_not_enabled"
        )
        assert "Anna" not in api.api_prompt
        assert "Bram" not in api.api_prompt
    # Linked to one enabled child as well: that child works, nothing is announced.
    data = await ok(hass, mixed.id, "list_children")
    assert [c["id"] for c in data["children"]] == ["1002"]
    api = await llm.async_get_api(hass, COACH_API_ID, llm_context(mixed.id))
    assert "not enabled" not in api.api_prompt


# -- write tools ------------------------------------------------------------------


async def test_subtask_lifecycle_is_logged(
    hass: HomeAssistant, student: Any, logbook: list[Any]
) -> None:
    """Add, update, progress and delete a subtask: marked as AI, logged in Dutch."""
    data = await ok(
        hass,
        student.id,
        "add_subtask",
        item=PROEFWERK,
        title="H4 woordjes",
        date="2026-11-16",
    )
    sub = data["item"]["subtasks"][0]
    assert sub["created_by"] == "ai"
    assert sub["id"].startswith(f"{PROEFWERK}:sub:")
    assert sub["planned"] == "2026-11-16"
    assert data["item"]["derived"] is True
    assert "uid" not in sub

    data = await ok(
        hass,
        student.id,
        "update_subtask",
        subtask=sub["id"],
        title="H4 + H5",
        date="2026-11-17",
    )
    assert data["item"]["subtasks"][0]["title"] == "H4 + H5"
    await ok(hass, student.id, "update_subtask", subtask=sub["id"], date="2026-11-18")
    assert (
        await fails(hass, student.id, "update_subtask", subtask=sub["id"])
        == "invalid_format"
    )

    # The item's progress is derived: only the subtask can be set.
    assert (
        await fails(hass, student.id, "set_progress", id=PROEFWERK, progress=50)
        == "item_has_subtasks"
    )
    progress = await ok(hass, student.id, "set_progress", id=sub["id"], progress=100)
    assert progress["progress"] == 100
    assert progress["completed"] is True
    assert progress["item"]["progress"] == 100

    gone = await ok(hass, student.id, "delete_subtask", subtask=sub["id"])
    assert gone["item"]["subtasks"] == []

    messages = [e.data["message"] for e in logbook]
    assert messages == [
        "AI-coach: deelstap 'H4 woordjes' toegevoegd aan Proefwerk Duitse taal",
        "AI-coach: deelstap 'H4 + H5' gewijzigd bij Proefwerk Duitse taal",
        "AI-coach: deelstap 'H4 + H5' gewijzigd bij Proefwerk Duitse taal",
        "AI-coach: voortgang van deelstap 'H4 + H5' (Proefwerk Duitse taal) "
        "op 100% gezet",
        "AI-coach: deelstap 'H4 + H5' verwijderd bij Proefwerk Duitse taal",
    ]
    for event in logbook:
        assert event.data["domain"] == DOMAIN
        assert event.data["entity_id"] == "todo.kind_school_homework"
        assert event.data["name"] == "Magister"
        assert event.context.user_id == student.id


async def test_subtask_errors_use_the_contract_codes(
    hass: HomeAssistant, student: Any, logbook: list[Any]
) -> None:
    """The errors are those of the WebSocket API; nothing is logged."""
    assert (
        await fails(hass, student.id, "add_subtask", item="999", title="x")
        == "item_not_found"
    )
    assert (
        await fails(
            hass,
            student.id,
            "add_subtask",
            item=PROEFWERK,
            title="x",
            date="2026-12-31",
        )
        == "invalid_date"
    )
    assert (
        await fails(hass, student.id, "delete_subtask", subtask=f"{PROEFWERK}:sub:nope")
        == "subtask_not_found"
    )
    assert (
        await fails(hass, student.id, "update_subtask", subtask="nope", title="x")
        == "invalid_format"
    )
    assert (
        await fails(hass, student.id, "update_subtask", subtask=PROEFWERK, title="x")
        == "subtask_not_found"
    )
    for _ in range(20):
        await ok(hass, student.id, "add_subtask", item=PROEFWERK, title="x")
    assert (
        await fails(hass, student.id, "add_subtask", item=PROEFWERK, title="x")
        == "too_many_subtasks"
    )
    assert (
        await fails(hass, student.id, "set_progress", id="999", progress=10)
        == "item_not_found"
    )
    assert len(logbook) == 20


async def test_set_progress_of_an_item(
    hass: HomeAssistant, student: Any, logbook: list[Any]
) -> None:
    """An item without subtasks gets its own progress."""
    data = await ok(hass, student.id, "set_progress", id=HOMEWORK, progress=50)
    assert data["progress"] == 50
    assert data["completed"] is False
    assert logbook[0].data["message"] == (
        "AI-coach: voortgang van Huiswerk wiskunde op 50% gezet"
    )


async def test_labels_and_overrides(
    hass: HomeAssistant, student: Any, logbook: list[Any]
) -> None:
    """Manual labels (by id or name) and Magister label overrides."""
    data = await ok(
        hass,
        student.id,
        "add_label",
        appointment=HOMEWORK,
        label="proefwerk",
        note=" H3 + H4 ",
    )
    labels = data["item"]["manual_labels"]
    assert [(lb["name"], lb["note"]) for lb in labels] == [("Proefwerk", "H3 + H4")]
    assert (
        await fails(
            hass, student.id, "add_label", appointment=HOMEWORK, label="proefwerk"
        )
        == "label_exists"
    )
    assert (
        await fails(hass, student.id, "add_label", appointment=HOMEWORK, label="zzz")
        == "label_not_found"
    )
    assert (
        await fails(hass, student.id, "add_label", appointment="999", label="proefwerk")
        == "appointment_not_found"
    )
    removed = await ok(
        hass, student.id, "remove_label", appointment=HOMEWORK, label="Proefwerk"
    )
    assert removed["item"]["manual_labels"] == []
    assert (
        await fails(
            hass, student.id, "remove_label", appointment=HOMEWORK, label="Proefwerk"
        )
        == "label_not_on_appointment"
    )

    replaced = await ok(
        hass,
        student.id,
        "set_label_override",
        appointment=HOMEWORK,
        mode="replace",
        label="Proefwerk",
    )
    assert replaced["item"]["override"]["mode"] == "replace"
    assert replaced["item"]["is_test"] is True
    assert (
        await fails(
            hass, student.id, "set_label_override", appointment=HOMEWORK, mode="replace"
        )
        == "invalid_format"
    )
    disabled = await ok(
        hass, student.id, "set_label_override", appointment=HOMEWORK, mode="disable"
    )
    assert disabled["item"]["disabled"] is True
    assert (
        await fails(hass, student.id, "add_subtask", item=HOMEWORK, title="x")
        == "item_disabled"
    )
    assert (
        await fails(hass, student.id, "set_progress", id=HOMEWORK, progress=10)
        == "item_disabled"
    )
    cleared = await ok(
        hass, student.id, "set_label_override", appointment=HOMEWORK, mode="clear"
    )
    assert cleared["item"]["override"] is None
    assert [e.data["message"] for e in logbook] == [
        "AI-coach: label 'Proefwerk' toegevoegd aan Huiswerk wiskunde",
        "AI-coach: label 'Proefwerk' verwijderd van Huiswerk wiskunde",
        "AI-coach: Magister-label van Huiswerk wiskunde vervangen door 'Proefwerk'",
        "AI-coach: Magister-label van Huiswerk wiskunde uitgeschakeld",
        "AI-coach: Magister-label van Huiswerk wiskunde hersteld",
    ]


async def test_missing_entity_is_an_error(hass: HomeAssistant, student: Any) -> None:
    """Without the to-do entity there is nothing to write to."""
    from homeassistant.helpers import entity_registry as er

    registry = er.async_get(hass)
    registry.async_remove("todo.kind_school_homework")
    await hass.async_block_till_done()
    assert await fails(hass, student.id, "add_subtask", item=PROEFWERK, title="x") == (
        "not_found"
    )


# -- privacy ----------------------------------------------------------------------


async def test_no_teacher_or_school_data_in_any_output(
    hass: HomeAssistant, student: Any
) -> None:
    """No teacher names or codes, no school host, no full names, in all tools."""
    appointments = json.loads(
        (
            __import__("pathlib").Path(__file__).parent
            / "fixtures"
            / "school_a"
            / "appointments.json"
        ).read_text()
    )["Items"]
    teachers = {
        value
        for a in appointments
        for t in a.get("Docenten") or []
        for value in (t.get("Naam"), t.get("Docentcode"))
        if value
    }
    assert teachers
    outputs = [
        await ok(hass, student.id, "list_children"),
        await ok(
            hass, student.id, "get_schedule", start="2026-11-02", end="2026-11-30"
        ),
        await ok(
            hass,
            student.id,
            "list_homework",
            start="2026-11-01",
            include_completed=True,
        ),
        await ok(hass, student.id, "get_progress"),
        await ok(hass, student.id, "list_label_options"),
        await ok(hass, student.id, "add_subtask", item=PROEFWERK, title="x"),
        await ok(
            hass, student.id, "get_overview", start="2026-11-02", end="2026-11-30"
        ),
    ]
    api = await llm.async_get_api(hass, COACH_API_ID, llm_context(student.id))
    text = json.dumps(outputs, ensure_ascii=False) + api.api_prompt
    for teacher in teachers:
        assert not re.search(rf"\b{re.escape(teacher)}\b", text), teacher
    assert "magister.net" not in text
    assert "Kind A" not in text
    assert "Docent" not in text


async def test_children_of_other_users_are_not_in_the_prompt(
    hass: HomeAssistant, mocked: aioresponses
) -> None:
    """The prompt names only the user's own children."""
    anna, bram = await make_user(hass, "Anna"), await make_user(hass, "Bram")
    await setup_coach(
        hass,
        mocked,
        coach_options(
            **{
                "1001": {
                    "enabled": True,
                    "users": [anna.id],
                    "guidelines": "Alleen Anna.",
                },
                "1002": {"enabled": True, "users": [bram.id]},
            }
        ),
        two=True,
    )
    api = await llm.async_get_api(hass, COACH_API_ID, llm_context(anna.id))
    assert "Anna" in api.api_prompt
    assert "Bram" not in api.api_prompt
    assert "1002" not in api.api_prompt
    assert "Alleen Anna." in api.api_prompt
    assert DEFAULT_GUIDELINES not in api.api_prompt


async def test_shared_default_guidelines_do_not_name_other_users_children(
    hass: HomeAssistant, mocked: aioresponses
) -> None:
    """Two users, both children on the default text: each prompt names only its own."""
    anna, bram = await make_user(hass, "Anna"), await make_user(hass, "Bram")
    both = await make_user(hass, "Beide")
    await setup_coach(
        hass,
        mocked,
        coach_options(
            **{
                "1001": {"enabled": True, "users": [anna.id, both.id]},
                "1002": {"enabled": True, "users": [bram.id, both.id]},
            }
        ),
        two=True,
    )
    api = await llm.async_get_api(hass, COACH_API_ID, llm_context(anna.id))
    assert f"Coaching guidelines (for Anna (id 1001)):\n{DEFAULT_GUIDELINES}" in (
        api.api_prompt
    )
    assert "Bram" not in api.api_prompt
    assert "1002" not in api.api_prompt
    api = await llm.async_get_api(hass, COACH_API_ID, llm_context(both.id))
    title = "Coaching guidelines (for Anna (id 1001), Bram (id 1002)):"
    assert f"{title}\n{DEFAULT_GUIDELINES}" in api.api_prompt
    assert api.api_prompt.count(DEFAULT_GUIDELINES) == 1


# -- prompt -----------------------------------------------------------------------


async def test_prompt_contents(hass: HomeAssistant, student: Any) -> None:
    """Date, time zone, planner rules and the default guidelines (verbatim)."""
    api = await llm.async_get_api(hass, COACH_API_ID, llm_context(student.id))
    prompt = api.api_prompt
    assert "Today is 2026-11-13 (Friday)" in prompt
    assert "Europe/Amsterdam" in prompt
    for rule in ("derived progress", "next_day", "item_has_subtasks"):
        assert rule in prompt, rule
    assert "moves forward day by day" in prompt
    assert "Always refer to a child by its id" in prompt
    assert "Kind (id 1001)" in prompt
    assert DEFAULT_GUIDELINES in prompt
    assert DEFAULT_GUIDELINES.startswith(
        "Je bent een huiswerkcoach voor een middelbare"
    )
    assert "15\u201345 minuten" in prompt
    assert "Always pass `child`" not in prompt
    assert len(api.tools) == 21


async def test_prompt_for_unlinked_user(hass: HomeAssistant, student: Any) -> None:
    """An unlinked user gets the rules and a pointer, and no guidelines."""
    other = await make_user(hass, "Anders")
    api = await llm.async_get_api(hass, COACH_API_ID, llm_context(other.id))
    assert "not linked" in api.api_prompt
    assert DEFAULT_GUIDELINES not in api.api_prompt
    assert "Kind" not in api.api_prompt


async def test_custom_guidelines_and_two_children(
    hass: HomeAssistant, mocked: aioresponses
) -> None:
    """Each child's own guidelines; several children ask for `child`."""
    parent = await make_user(hass, "Ouder")
    await setup_coach(
        hass,
        mocked,
        coach_options(
            **{
                "1001": {"enabled": True, "users": [parent.id], "guidelines": "Kort."},
                "1002": {"enabled": True, "users": [parent.id]},
            }
        ),
        two=True,
    )
    api = await llm.async_get_api(hass, COACH_API_ID, llm_context(parent.id))
    assert "Coaching guidelines (for Anna (id 1001)):\nKort." in api.api_prompt
    assert (
        f"Coaching guidelines (for Bram (id 1002)):\n{DEFAULT_GUIDELINES}"
        in api.api_prompt
    )
    assert "Always pass `child`" in api.api_prompt


async def test_unknown_tool_raises(hass: HomeAssistant, student: Any) -> None:
    """The LLM helper rejects a tool that does not exist."""
    with pytest.raises(HomeAssistantError):
        await call(hass, student.id, "format_disk")


async def test_removing_the_last_label_leaves_the_planner(
    hass: HomeAssistant, student: Any
) -> None:
    """The item is ``null`` when its last label is gone."""
    lesson = "100067"  # no Magister label
    added = await ok(
        hass, student.id, "add_label", appointment=lesson, label="Huiswerk"
    )
    assert added["item"]["manual_labels"]
    removed = await ok(
        hass, student.id, "remove_label", appointment=lesson, label="Huiswerk"
    )
    assert removed["item"] is None


async def test_unloaded_entry_gives_no_access(
    hass: HomeAssistant, student: Any
) -> None:
    """While the entry is not loaded, nobody has access."""
    assert (await ok(hass, student.id, "list_children"))["children"]
    assert await hass.config_entries.async_unload(student.entry.entry_id)
    assert async_accessible_children(hass, student.id) == []
    with pytest.raises(HomeAssistantError):  # the API is gone with the last entry
        await call(hass, student.id, "list_children")


# -- fix round --------------------------------------------------------------------


def _rewrite_entry_data(
    entry: MockConfigEntry, *, host: str | None = None, child_id: int | None = None
) -> None:
    """Change the stored host or child id of a set-up entry, without a reload."""
    data = dict(entry.data)
    if host is not None:
        data["host"] = host
    if child_id is not None:
        data["children"] = [{**data["children"][0], "id": child_id}]
    object.__setattr__(entry, "data", MappingProxyType(data))


async def test_colliding_child_ids_across_schools_get_distinct_ids(
    hass: HomeAssistant, mocked: aioresponses
) -> None:
    """The same child id at two schools: tagged ids, never an ambiguous reference."""
    parent = await make_user(hass, "Ouder")
    steps = [
        {"action": "username"},
        {"action": "password"},
        {"redirectURL": RETURN_URL},
    ]
    FakeMagister(mocked, children=TWO_CHILDREN, challenges=[*steps, *steps])
    options = coach_options(
        **{
            "1001": {"enabled": True, "users": [parent.id]},
            "1002": {"enabled": True, "users": [parent.id]},
        }
    )
    first = make_entry(
        children=[(1001, "Anna A")], unique_id="school.magister.net:1", options=options
    )
    second = make_entry(
        children=[(1002, "Bram B")], unique_id="school.magister.net:2", options=options
    )
    for entry in (first, second):
        entry.add_to_hass(hass)
        assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert [c.id for c in async_accessible_children(hass, parent.id)] == [
        "1001",
        "1002",
    ]
    _rewrite_entry_data(second, host="other.example.org", child_id=1001)
    children = async_accessible_children(hass, parent.id)
    ids = [c.id for c in children]
    assert len(set(ids)) == 2
    assert all(re.fullmatch(r"1001-[0-9a-f]{8}", i) for i in ids)
    assert not any("example" in i or "magister" in i for i in ids)
    assert ids == [c.id for c in async_accessible_children(hass, parent.id)]
    listed = (await ok(hass, parent.id, "list_children"))["children"]
    assert [c["id"] for c in listed] == ids
    # The second tagged id routes to the second entry, the first to the first.
    for tagged, entry in zip(ids, (first, second), strict=True):
        assert pick_child(children, tagged).entry is entry
    # A bare id is ambiguous now (the name is too); the tagged id picks one child.
    assert await fails(hass, parent.id, "get_progress", child="1001") == (
        "child_not_found"
    )
    assert await fails(hass, parent.id, "get_progress") == "child_required"
    # A name shared by two of the user's own children asks for the id instead.
    twins = [dataclasses.replace(c, name="Twin") for c in children]
    with pytest.raises(CoachError) as ambiguous:
        pick_child(twins, "twin")
    assert ambiguous.value.code == "child_required"
    assert "use the id" in ambiguous.value.message
    assert all(c.id in ambiguous.value.message for c in twins)
    # A name that matches none of them stays unknown (no probing).
    with pytest.raises(CoachError) as unknown:
        pick_child(twins, "Other")
    assert unknown.value.code == "child_not_found"
    data = await ok(hass, parent.id, "get_progress", child=ids[0])
    assert data["child"] == ids[0]
    api = await llm.async_get_api(hass, COACH_API_ID, llm_context(parent.id))
    assert all(i in api.api_prompt for i in ids)
    assert "other.example.org" not in api.api_prompt


async def test_same_child_under_two_entries_is_listed_once(
    hass: HomeAssistant, mocked: aioresponses
) -> None:
    """Legacy: one child in two entries of the same school is one coachable child."""
    parent = await make_user(hass, "Ouder")
    steps = [
        {"action": "username"},
        {"action": "password"},
        {"redirectURL": RETURN_URL},
    ]
    FakeMagister(mocked, children=TWO_CHILDREN, challenges=[*steps, *steps])
    options = coach_options(**{"1001": {"enabled": True, "users": [parent.id]}})
    first = make_entry(
        children=[(1001, "Anna A")], unique_id="school.magister.net:1", options=options
    )
    second = make_entry(
        children=[(1002, "Bram B")], unique_id="school.magister.net:2", options=options
    )
    for entry in (first, second):
        entry.add_to_hass(hass)
        assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    _rewrite_entry_data(second, child_id=1001)
    children = async_accessible_children(hass, parent.id)
    assert [(c.id, c.entry.entry_id) for c in children] == [("1001", first.entry_id)]


async def test_entity_must_belong_to_the_childs_entry(
    hass: HomeAssistant, student: Any
) -> None:
    """An entity of the same unique id under another config entry is refused."""
    from homeassistant.helpers import entity_registry as er

    registry = er.async_get(hass)
    other = MockConfigEntry(domain=DOMAIN, title="x")
    other.add_to_hass(hass)
    entry = registry.async_get("todo.kind_school_homework")
    assert entry is not None and entry.config_entry_id == student.entry.entry_id
    # A todo entity of this unique id is found, but it belongs to a foreign entry.
    object.__setattr__(entry, "config_entry_id", other.entry_id)
    assert await fails(hass, student.id, "add_subtask", item=PROEFWERK, title="x") == (
        "not_found"
    )


async def test_system_user_has_no_access(
    hass: HomeAssistant, mocked: aioresponses
) -> None:
    """A system-generated user that is linked still gets nothing."""
    system = await hass.auth.async_create_system_user("Systeem")
    await setup_coach(
        hass, mocked, coach_options(**{"1001": {"enabled": True, "users": [system.id]}})
    )
    assert await fails(hass, system.id, "list_homework") == "not_linked"
    assert (await ok(hass, system.id, "list_children"))["children"] == []


async def test_writes_to_another_child_are_refused_for_every_tool(
    hass: HomeAssistant, mocked: aioresponses, logbook: list[Any]
) -> None:
    """Anna's user can use no write tool on Bram, nor reach Bram's subtasks."""
    anna, bram = await make_user(hass, "Anna"), await make_user(hass, "Bram")
    await setup_coach(
        hass,
        mocked,
        coach_options(
            **{
                "1001": {"enabled": True, "users": [anna.id]},
                "1002": {"enabled": True, "users": [bram.id]},
            }
        ),
        two=True,
    )
    sub = (await ok(hass, bram.id, "add_subtask", item=PROEFWERK, title="Van Bram"))[
        "item"
    ]["subtasks"][0]["id"]
    await ok(hass, bram.id, "add_label", appointment=HOMEWORK, label="Proefwerk")
    logged = len(logbook)
    writes: list[tuple[str, dict[str, Any]]] = [
        ("add_subtask", {"item": PROEFWERK, "title": "x"}),
        ("update_subtask", {"subtask": sub, "title": "y"}),
        ("delete_subtask", {"subtask": sub}),
        ("set_progress", {"id": sub, "progress": 50}),
        ("set_progress", {"id": HOMEWORK, "progress": 50}),
        ("add_label", {"appointment": HOMEWORK, "label": "default_test"}),
        ("remove_label", {"appointment": HOMEWORK, "label": "Proefwerk"}),
        ("set_label_override", {"appointment": HOMEWORK, "mode": "disable"}),
        ("set_label_override", {"appointment": HOMEWORK, "mode": "clear"}),
    ]
    for tool, args in writes:
        for wrong in ("1002", "Bram", 1002):
            assert await fails(hass, anna.id, tool, child=wrong, **args) == (
                "child_not_found"
            ), (tool, wrong)
        if "subtask" in args or (tool == "set_progress" and ":sub:" in args["id"]):
            # Without `child` the id is read as Anna's: Bram's subtask does not exist.
            assert await fails(hass, anna.id, tool, **args) in (
                "subtask_not_found",
                "item_not_found",
            ), tool
    assert len(logbook) == logged
    bram_manager = next(
        iter(hass.config_entries.async_entries(DOMAIN))
    ).runtime_data.homework
    titles = [s.title for i in bram_manager.items(1002) for s in i.subtasks]
    assert titles == ["Van Bram"]
    assert not any(item.subtasks for item in bram_manager.items(1001))
    assert [lb.name for i in bram_manager.items(1002) for lb in i.manual_labels] == [
        "Proefwerk"
    ]
    assert bram_manager.progress(f"school.magister.net:1002:{HOMEWORK}") == 0


async def test_noop_writes_are_not_logged(
    hass: HomeAssistant, student: Any, logbook: list[Any]
) -> None:
    """Nothing changed, nothing in the logbook; real changes still are."""
    await ok(hass, student.id, "set_progress", id=HOMEWORK, progress=50)
    assert len(logbook) == 1
    again = await ok(hass, student.id, "set_progress", id=HOMEWORK, progress=50)
    assert again["progress"] == 50
    assert len(logbook) == 1
    await ok(hass, student.id, "set_progress", id=HOMEWORK, progress=0)
    assert len(logbook) == 2

    await ok(hass, student.id, "set_label_override", appointment=HOMEWORK, mode="clear")
    assert len(logbook) == 2  # there was no override
    await ok(
        hass, student.id, "set_label_override", appointment=HOMEWORK, mode="disable"
    )
    await ok(
        hass, student.id, "set_label_override", appointment=HOMEWORK, mode="disable"
    )
    assert len(logbook) == 3
    await ok(hass, student.id, "set_label_override", appointment=HOMEWORK, mode="clear")
    assert len(logbook) == 4

    sub = (
        await ok(
            hass,
            student.id,
            "add_subtask",
            item=PROEFWERK,
            title="Woordjes",
            date="2026-11-16",
        )
    )["item"]["subtasks"][0]["id"]
    assert len(logbook) == 5
    await ok(hass, student.id, "update_subtask", subtask=sub, title="Woordjes")
    await ok(hass, student.id, "update_subtask", subtask=sub, date="2026-11-16")
    await ok(
        hass,
        student.id,
        "update_subtask",
        subtask=sub,
        title="Woordjes",
        date="2026-11-16",
    )
    assert len(logbook) == 5
    await ok(hass, student.id, "update_subtask", subtask=sub, title="Hoofdstuk 1")
    assert len(logbook) == 6
    await ok(hass, student.id, "set_progress", id=sub, progress=25)
    await ok(hass, student.id, "set_progress", id=sub, progress=25)
    assert len(logbook) == 7


async def test_unexpected_errors_are_generic(
    hass: HomeAssistant,
    student: Any,
    caplog: pytest.LogCaptureFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A bug inside a tool never leaks its message (uids, hosts) to the client."""

    def boom(*_: Any, **__: Any) -> None:
        raise RuntimeError("secret school.magister.net:1001:100065 detail")

    monkeypatch.setattr(MagisterHomeworkTodo, "add_subtask", boom)
    caplog.set_level(logging.INFO)
    result = await call(hass, student.id, "add_subtask", item=PROEFWERK, title="x")
    assert result.error
    assert result.data["error"] == "internal_error"
    assert "magister.net" not in json.dumps(result.data)
    assert "secret" not in json.dumps(result.data)
    assert "add_subtask" in caplog.text
    assert "magister.net" not in caplog.text


async def test_ids_with_a_trailing_newline_are_rejected(
    hass: HomeAssistant, student: Any
) -> None:
    """``fullmatch``: ``100065\\n`` is not an id."""
    for tool, args in (
        ("add_subtask", {"item": f"{PROEFWERK}\n", "title": "x"}),
        ("set_progress", {"id": f"{HOMEWORK}\n", "progress": 10}),
        ("update_subtask", {"subtask": f"{PROEFWERK}:sub:ab\n", "title": "x"}),
        ("add_label", {"appointment": f"{HOMEWORK}\n", "label": "proefwerk"}),
        ("set_label_override", {"appointment": f"{HOMEWORK}\n", "mode": "clear"}),
    ):
        assert await fails(hass, student.id, tool, **args) == "invalid_format", tool


async def test_full_names_are_never_used(
    hass: HomeAssistant, mocked: aioresponses
) -> None:
    """A short name that fell back to the full name becomes ``Kind <n>``."""
    user = await make_user(hass)
    FakeMagister(mocked, children=TWO_CHILDREN)
    entry = make_entry(
        children=[(1001, "Anna Jansen"), (1002, "Bram B")],
        options=coach_options(
            **{
                "1001": {"enabled": True, "users": [user.id]},
                "1002": {"enabled": True, "users": [user.id]},
            }
        ),
    )
    data = {**entry.data}
    data["children"] = [
        {"id": 1001, "name": "Anna Jansen", "short_name": "Anna Jansen"},
        {"id": 1002, "name": "Bram B", "short_name": "Bram"},
    ]
    entry = MockConfigEntry(
        domain=DOMAIN,
        title=entry.title,
        unique_id=entry.unique_id,
        data=data,
        options=dict(entry.options),
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    children = (await ok(hass, user.id, "list_children"))["children"]
    assert [c["name"] for c in children] == ["Kind 1", "Bram"]
    api = await llm.async_get_api(hass, COACH_API_ID, llm_context(user.id))
    assert "Anna" not in api.api_prompt
    assert "Jansen" not in api.api_prompt
    assert "Kind 1 (id 1001)" in api.api_prompt


async def test_no_leaks_in_errors_and_logbook(
    hass: HomeAssistant, student: Any, logbook: list[Any]
) -> None:
    """Error texts and logbook messages hold no host, uid or teacher data either."""
    await ok(hass, student.id, "add_subtask", item=PROEFWERK, title="x")
    await ok(hass, student.id, "set_progress", id=HOMEWORK, progress=50)
    await ok(hass, student.id, "add_label", appointment=HOMEWORK, label="proefwerk")
    await ok(
        hass, student.id, "set_label_override", appointment=HOMEWORK, mode="disable"
    )
    results = [
        await call(hass, student.id, tool, **args)
        for tool, args in (
            ("add_subtask", {"item": "999", "title": "x"}),
            ("add_subtask", {"item": "other.host:1002:5", "title": "x"}),
            ("update_subtask", {"subtask": f"{PROEFWERK}:sub:nope", "title": "x"}),
            ("delete_subtask", {"subtask": f"{PROEFWERK}:sub:nope"}),
            ("set_progress", {"id": "999", "progress": 10}),
            ("set_progress", {"id": PROEFWERK, "progress": 10}),
            ("add_label", {"appointment": "999", "label": "proefwerk"}),
            ("remove_label", {"appointment": HOMEWORK, "label": "zzz"}),
            ("get_schedule", {"start": "x", "end": "y"}),
            ("get_progress", {"child": "9999"}),
        )
    ]
    assert all(r.error for r in results), [r.data for r in results if not r.error]
    text = json.dumps([r.data for r in results]) + json.dumps(
        [e.data for e in logbook], default=str
    )
    assert logbook
    for forbidden in ("magister.net", "school.magister", "1001:", "Docent"):
        assert forbidden not in text, forbidden
    assert not re.search(r"\w+\.\w+:\d+:\d+", text)


async def test_short_name_equal_to_a_single_word_full_name_is_not_used(
    hass: HomeAssistant, mocked: aioresponses
) -> None:
    """A one-word short name equal to the full name falls back to ``Kind <n>``."""
    user = await make_user(hass)
    FakeMagister(mocked)
    entry = make_entry(
        options=coach_options(**{"1001": {"enabled": True, "users": [user.id]}})
    )
    data = {**entry.data}
    data["children"] = [{"id": 1001, "name": "Anna", "short_name": "Anna"}]
    entry = MockConfigEntry(
        domain=DOMAIN,
        title=entry.title,
        unique_id=entry.unique_id,
        data=data,
        options=dict(entry.options),
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    children = (await ok(hass, user.id, "list_children"))["children"]
    assert children == [
        {
            "id": "1001",
            "name": "Kind 1",
            "role": "student",
            "daily_max_minutes": 90,
            "daily_max_weekdays": [90] * 7,
        }
    ]


async def test_kind_number_counts_within_the_users_children(
    hass: HomeAssistant, mocked: aioresponses
) -> None:
    """A user linked to the second child only still sees ``Kind 1``."""
    parent = await make_user(hass, "Ouder")
    only_second = await make_user(hass, "Tweede")
    FakeMagister(mocked, children=TWO_CHILDREN)
    entry = make_entry(
        children=[(1001, "Anna A"), (1002, "Bram B")],
        options=coach_options(
            **{
                "1001": {"enabled": True, "users": [parent.id]},
                "1002": {"enabled": True, "users": [parent.id, only_second.id]},
            }
        ),
    )
    data = {**entry.data}
    data["children"] = [
        {"id": 1001, "name": "Anna A", "short_name": "Anna A"},
        {"id": 1002, "name": "Bram B", "short_name": "Bram B"},
    ]
    entry = MockConfigEntry(
        domain=DOMAIN,
        title=entry.title,
        unique_id=entry.unique_id,
        data=data,
        options=dict(entry.options),
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    names = [
        c["name"] for c in (await ok(hass, parent.id, "list_children"))["children"]
    ]
    assert names == ["Kind 1", "Kind 2"]
    assert (await ok(hass, only_second.id, "list_children"))["children"] == [
        {
            "id": "1002",
            "name": "Kind 1",
            "role": "student",
            "daily_max_minutes": 90,
            "daily_max_weekdays": [90] * 7,
        }
    ]


async def test_override_noop_detection_uses_the_stored_entry(
    hass: HomeAssistant, mocked: aioresponses, logbook: list[Any]
) -> None:
    """Clearing a stuck override and replacing a dangling one are real changes."""
    user = await make_user(hass)
    fake = FakeMagister(mocked)
    entry = make_entry(
        options=coach_options(**{"1001": {"enabled": True, "users": [user.id]}})
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    manager = entry.runtime_data.homework
    uid = f"school.magister.net:1001:{HOMEWORK}"

    # disable over a stored replace whose label option no longer exists
    await ok(
        hass,
        user.id,
        "set_label_override",
        appointment=HOMEWORK,
        mode="replace",
        label="Proefwerk",
    )
    manager._progress[uid]["override"]["label"] = "gone"
    manager._labels_changed()
    assert manager.find_item(1001, uid).override is None  # type: ignore[union-attr]
    before = len(logbook)
    await ok(hass, user.id, "set_label_override", appointment=HOMEWORK, mode="disable")
    assert len(logbook) == before + 1
    assert manager.stored_override(uid) == {"mode": "disable"}

    # clear on an appointment that lost its Magister label, override still stored
    for appointment in fake.appointments[1001]:
        if str(appointment["Id"]) == HOMEWORK:
            appointment["InfoType"] = 0
    await entry.runtime_data.coordinator.async_refresh()
    await hass.async_block_till_done()
    assert manager.find_item(1001, uid) is None
    before = len(logbook)
    await ok(hass, user.id, "set_label_override", appointment=HOMEWORK, mode="clear")
    assert len(logbook) == before + 1
    assert manager.stored_override(uid) is None
    await ok(hass, user.id, "set_label_override", appointment=HOMEWORK, mode="clear")
    assert len(logbook) == before + 1  # now there is really nothing to clear


async def test_disabled_overdue_item_is_not_listed(
    hass: HomeAssistant, student: Any
) -> None:
    """A disabled item that is overdue stays out of the default list."""
    default = await ok(hass, student.id, "list_homework")
    overdue = [i for i in default["items"] if i["date"] < "2026-11-13"]
    assert overdue
    target = overdue[0]["id"]
    await ok(hass, student.id, "set_label_override", appointment=target, mode="disable")
    again = await ok(hass, student.id, "list_homework")
    assert target not in {i["id"] for i in again["items"]}
    shown = await ok(hass, student.id, "list_homework", include_completed=True)
    assert target not in {i["id"] for i in shown["items"] if i["date"] < "2026-11-13"}
