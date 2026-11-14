"""AI homework coach: LLM API, tools, access control, logbook, prompt."""

from __future__ import annotations

import json
import re
from typing import Any

import pytest
from aioresponses import aioresponses
from freezegun.api import FrozenDateTimeFactory
from homeassistant.auth.const import GROUP_ID_USER
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
    async_accessible_children,
    coach_tools,
)
from custom_components.magister.coach_text import DEFAULT_GUIDELINES
from custom_components.magister.const import (
    CONF_COACH,
    DOMAIN,
)

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
    }
    for name in tools.values():
        assert name.description
        assert name.annotations.open_world is False
    read = {"list_children", "get_schedule", "list_homework", "get_progress"}
    read.add("list_label_options")
    for name, tool in tools.items():
        assert tool.annotations.read_only is (name in read)
        if name in read:
            assert tool.annotations.destructive is False
    assert tools["delete_subtask"].annotations.destructive
    assert tools["remove_label"].annotations.destructive
    assert not tools["add_subtask"].annotations.idempotent
    assert tools["set_progress"].annotations.idempotent


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
    assert not hass.data.get("sentinel")


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
    assert await fails(hass, user.id, "list_homework") == "not_linked"
    # Changing the options applies at once, without a reload.
    runtime = entry.runtime_data
    hass.config_entries.async_update_entry(
        entry,
        options=coach_options(**{"1001": {"enabled": True, "users": [user.id]}}),
    )
    await hass.async_block_till_done()
    assert entry.runtime_data is runtime
    assert (await ok(hass, user.id, "list_children"))["children"] == [
        {"id": "1001", "name": "Kind"}
    ]
    await hass.auth.async_update_user(user, is_active=False)
    assert (await ok(hass, user.id, "list_children"))["children"] == []
    await hass.auth.async_update_user(user, is_active=True)
    hass.config_entries.async_update_entry(
        entry,
        options=coach_options(**{"1001": {"enabled": True, "users": []}}),
    )
    assert await fails(hass, user.id, "get_progress") == "not_linked"


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
    assert children == [{"id": "1001", "name": "Anna"}]
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
        {"id": "1002", "name": "Bram"}
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
    assert all(i["date"] >= "2026-11-13" for i in default["items"])

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


# -- prompt -----------------------------------------------------------------------


async def test_prompt_contents(hass: HomeAssistant, student: Any) -> None:
    """Date, time zone, planner rules and the default guidelines (verbatim)."""
    api = await llm.async_get_api(hass, COACH_API_ID, llm_context(student.id))
    prompt = api.api_prompt
    assert "Today is 2026-11-13 (Friday)" in prompt
    assert "Europe/Amsterdam" in prompt
    for rule in ("derived progress", "rolling", "next_day", "item_has_subtasks"):
        assert rule in prompt or rule == "rolling"
    assert "moves forward day by day" in prompt
    assert "Kind (id 1001)" in prompt
    assert DEFAULT_GUIDELINES in prompt
    assert DEFAULT_GUIDELINES.startswith(
        "Je bent een huiswerkcoach voor een middelbare"
    )
    assert "15\u201345 minuten" in prompt
    assert "Always pass `child`" not in prompt
    assert len(api.tools) == 12


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
    assert "Coaching guidelines for Anna (id 1001):\nKort." in api.api_prompt
    assert f"Coaching guidelines for Bram (id 1002):\n{DEFAULT_GUIDELINES}" in (
        api.api_prompt
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
