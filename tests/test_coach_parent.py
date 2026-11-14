"""M11: parent role, daily maximum, estimated time, overview, prompt, logbook."""

from __future__ import annotations

import json
import logging
from typing import Any

import pytest
from aioresponses import aioresponses
from freezegun.api import FrozenDateTimeFactory
from homeassistant.core import HomeAssistant
from homeassistant.helpers import llm
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_capture_events,
)

from custom_components.magister.coach import (
    CoachChild,
    async_accessible_children,
    parent_guidelines_of,
    parent_users,
    role_of,
    student_users,
)
from custom_components.magister.coach_text import (
    DEFAULT_GUIDELINES,
    DEFAULT_PARENT_GUIDELINES,
)
from custom_components.magister.const import CONF_PARENT_GUIDELINES, CONF_WEIGHTS

from .ha_helpers import NOW, FakeMagister, make_entry
from .test_coach import (
    COACH_API_ID,
    HOMEWORK,
    PROEFWERK,
    call,
    coach_options,
    fails,
    llm_context,
    make_user,
    ok,
    setup_coach,
)

THREE = [
    {"Id": 1001, "Roepnaam": "Anna", "Achternaam": "", "Tussenvoegsel": ""},
    {"Id": 1002, "Roepnaam": "Bram", "Achternaam": "", "Tussenvoegsel": ""},
    {"Id": 1003, "Roepnaam": "Cato", "Achternaam": "", "Tussenvoegsel": ""},
]


@pytest.fixture(autouse=True)
async def frozen_now(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> FrozenDateTimeFactory:
    """Friday 13 November 2026."""
    await hass.config.async_set_time_zone("Europe/Amsterdam")
    freezer.move_to(NOW)
    return freezer


@pytest.fixture
def logbook(hass: HomeAssistant) -> list[Any]:
    """The logbook entries that are written."""
    return async_capture_events(hass, "logbook_entry")


class Family:
    """Three children; a parent for A and B, a student for A, and an outsider."""

    entry: MockConfigEntry
    parent: Any
    student: Any
    other: Any


@pytest.fixture
async def family(hass: HomeAssistant, mocked: aioresponses) -> Family:
    """Parent: A (1001) and B (1002); student: A; C (1003) belongs to somebody else."""
    result = Family()
    result.parent = await make_user(hass, "Ouder")
    result.student = await make_user(hass, "Leerling")
    result.other = await make_user(hass, "Ander")
    fake = FakeMagister(mocked, children=THREE)
    # Child C has its own subject, so a leak would show.
    fake.appointments[1003] = json.loads(
        json.dumps(fake.appointments[1003]).replace("wiskunde", "geheimvak")
    )
    options = coach_options(
        **{
            "1001": {
                "enabled": True,
                "students": [result.student.id],
                "parents": [result.parent.id],
            },
            "1002": {"enabled": True, "parents": [result.parent.id]},
            "1003": {"enabled": True, "students": [result.other.id]},
        }
    )
    result.entry = make_entry(
        children=[(1001, "Anna A"), (1002, "Bram B"), (1003, "Cato C")],
        options=options,
    )
    result.entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(result.entry.entry_id)
    await hass.async_block_till_done()
    return result


def with_weights(family: Family, hass: HomeAssistant, weights: dict[str, Any]) -> None:
    """Set the weights (and the daily maximum) of the entry, without a reload."""
    hass.config_entries.async_update_entry(
        family.entry, options={**family.entry.options, CONF_WEIGHTS: weights}
    )


# -- roles --------------------------------------------------------------------------


async def test_roles_in_list_children(hass: HomeAssistant, family: Family) -> None:
    """Each child shows the caller's role and the daily maximum (default 90)."""
    data = await ok(hass, family.parent.id, "list_children")
    assert data["children"] == [
        {"id": "1001", "name": "Anna", "role": "parent", "daily_max_minutes": 90},
        {"id": "1002", "name": "Bram", "role": "parent", "daily_max_minutes": 90},
    ]
    data = await ok(hass, family.student.id, "list_children")
    assert data["children"] == [
        {"id": "1001", "name": "Anna", "role": "student", "daily_max_minutes": 90}
    ]
    with_weights(family, hass, {"1001": {"daily_max_minutes": 135}})
    data = await ok(hass, family.parent.id, "list_children")
    assert [c["daily_max_minutes"] for c in data["children"]] == [135, 90]


async def test_users_key_of_1_6_0_is_read_as_students(
    hass: HomeAssistant, mocked: aioresponses
) -> None:
    """`users` counts as `students` while `students` is missing; then it is ignored."""
    old, new, parent = [await make_user(hass, n) for n in ("Oud", "Nieuw", "Ouder")]
    entry = await setup_coach(
        hass,
        mocked,
        coach_options(**{"1001": {"enabled": True, "users": [old.id]}}),
    )
    settings = entry.options["coach"]["1001"]
    assert student_users(settings) == [old.id]
    assert parent_users(settings) == []
    assert role_of(settings, old.id) == "student"
    assert role_of(settings, None) is None
    assert role_of(settings, new.id) is None
    children = (await ok(hass, old.id, "list_children"))["children"]
    assert [c["role"] for c in children] == ["student"]
    # With `students` present the legacy key is no longer read.
    hass.config_entries.async_update_entry(
        entry,
        options=coach_options(
            **{
                "1001": {
                    "enabled": True,
                    "users": [old.id],
                    "students": [new.id],
                    "parents": [parent.id],
                }
            }
        ),
    )
    assert (await ok(hass, old.id, "list_children"))["children"] == []
    assert [
        c["role"] for c in (await ok(hass, new.id, "list_children"))["children"]
    ] == ["student"]
    assert [
        c["role"] for c in (await ok(hass, parent.id, "list_children"))["children"]
    ] == ["parent"]


async def test_garbage_in_user_lists_is_ignored(
    hass: HomeAssistant, mocked: aioresponses
) -> None:
    """Non-text entries and non-lists do not link anybody."""
    user = await make_user(hass)
    entry = await setup_coach(
        hass,
        mocked,
        coach_options(
            **{
                "1001": {
                    "enabled": True,
                    "students": [1, None, user.id],
                    "parents": "x",
                }
            }
        ),
    )
    assert student_users(entry.options["coach"]["1001"]) == [user.id]
    assert parent_users(entry.options["coach"]["1001"]) == []
    assert not async_accessible_children(hass, "someone-else")


async def test_user_in_both_lists_gets_the_parent_role(
    hass: HomeAssistant, mocked: aioresponses
) -> None:
    """The flow refuses it; hand-edited data gets the role with fewer rights."""
    user = await make_user(hass)
    await setup_coach(
        hass,
        mocked,
        coach_options(
            **{
                "1001": {
                    "enabled": True,
                    "students": [user.id],
                    "parents": [user.id],
                }
            }
        ),
    )
    (child,) = (await ok(hass, user.id, "list_children"))["children"]
    assert child["role"] == "parent"
    assert (
        await fails(hass, user.id, "set_progress", id=HOMEWORK, progress=50)
        == "not_allowed_for_role"
    )


# -- security -----------------------------------------------------------------------


async def test_parent_cannot_reach_a_third_child(
    hass: HomeAssistant, family: Family
) -> None:
    """A parent of A and B gets nothing of C, however C is asked for."""
    parent = family.parent.id
    for reference in ("1003", "Cato", "cato", "1003-abcdef12", "3"):
        for tool, args in (
            ("get_schedule", {"start": "2026-11-16", "end": "2026-11-16"}),
            ("list_homework", {}),
            ("get_progress", {}),
            ("list_label_options", {}),
            ("add_subtask", {"item": HOMEWORK, "title": "x"}),
            ("set_progress", {"id": HOMEWORK, "progress": 50}),
            ("add_label", {"appointment": HOMEWORK, "label": "Huiswerk"}),
            ("set_label_override", {"appointment": HOMEWORK, "mode": "disable"}),
        ):
            code = await fails(hass, parent, tool, child=reference, **args)
            assert code == "child_not_found", (reference, tool)
    # Nothing was written for C.
    manager = family.entry.runtime_data.homework
    assert not any(item.subtasks for item in manager.items(1003))
    assert manager.progress(f"school.magister.net:1003:{HOMEWORK}") == 0
    # Without `child` a parent of two children must choose one of her own.
    assert await fails(hass, parent, "list_homework") == "child_required"

    # The overview and everything else holds nothing of C.
    texts = []
    overview = await call(
        hass, parent, "get_overview", start="2026-11-16", end="2026-11-22"
    )
    texts.append(json.dumps(overview.data))
    for tool in ("list_children",):
        texts.append(json.dumps((await call(hass, parent, tool)).data))
    for child in ("1001", "1002"):
        texts.append(
            json.dumps((await call(hass, parent, "list_homework", child=child)).data)
        )
    api = await llm.async_get_api(hass, COACH_API_ID, llm_context(parent))
    texts.append(api.api_prompt)
    for text in texts:
        assert "geheimvak" not in text
        assert "Cato" not in text
        assert "1003" not in text


async def test_student_of_a_sees_nothing_of_b(
    hass: HomeAssistant, family: Family
) -> None:
    """The student of A: one child in the overview and in every other output."""
    student = family.student.id
    data = await ok(hass, student, "get_overview", start="2026-11-16", end="2026-11-22")
    assert [c["child"] for c in data["children"]] == ["1001"]
    assert "Bram" not in json.dumps(data)
    assert (
        await fails(hass, student, "list_homework", child="1002") == "child_not_found"
    )
    assert (
        await fails(
            hass, student, "add_subtask", child="Bram", item=HOMEWORK, title="x"
        )
        == "child_not_found"
    )
    api = await llm.async_get_api(hass, COACH_API_ID, llm_context(student))
    assert "Bram" not in api.api_prompt
    assert "Parent guidelines" not in api.api_prompt
    # The student of C only sees C; a stranger gets not_linked everywhere.
    other = await ok(
        hass, family.other.id, "get_overview", start="2026-11-16", end="2026-11-16"
    )
    assert [c["child"] for c in other["children"]] == ["1003"]
    stranger = await make_user(hass, "Vreemd")
    assert (
        await fails(
            hass, stranger.id, "get_overview", start="2026-11-16", end="2026-11-16"
        )
        == "not_linked"
    )


async def test_overview_without_user_or_inactive_user(
    hass: HomeAssistant, family: Family
) -> None:
    """No user, an unknown user and a deactivated user get `not_linked`."""
    args = {"start": "2026-11-16", "end": "2026-11-16"}
    result = await call(hass, None, "get_overview", **args)
    assert result.data["error"] == "not_linked"
    await hass.auth.async_update_user(family.student, is_active=False)
    result = await call(hass, family.student.id, "get_overview", **args)
    assert result.data["error"] == "not_linked"


# -- get_overview -------------------------------------------------------------------


async def test_overview_contents(hass: HomeAssistant, family: Family) -> None:
    """Per child and day: tests, assignments, open items, planned minutes, maximum."""
    parent = family.parent.id
    with_weights(family, hass, {"1001": {"daily_max_minutes": 60}})
    # Two subtasks on the test day (Thursday 19 Nov), 45 and 30 minutes.
    for title, minutes in (("woordjes", 45), ("grammatica", 30)):
        await ok(
            hass,
            parent,
            "add_subtask",
            child="1001",
            item=PROEFWERK,
            title=title,
            date="2026-11-19",
            minutes=minutes,
        )
    # A subtask without minutes counts as 0; one on another day counts there.
    await ok(
        hass,
        parent,
        "add_subtask",
        child="1001",
        item=PROEFWERK,
        title="los",
        date="2026-11-18",
    )
    await ok(
        hass,
        parent,
        "add_subtask",
        child="1001",
        item=HOMEWORK,
        title="rekenen",
        date="2026-11-14",
        minutes=15,
    )
    data = await ok(hass, parent, "get_overview", start="2026-11-14", end="2026-11-20")
    assert data["today"] == "2026-11-13"
    assert [c["child"] for c in data["children"]] == ["1001", "1002"]
    anna, bram = data["children"]
    assert (anna["name"], anna["role"], anna["daily_max_minutes"]) == (
        "Anna",
        "parent",
        60,
    )
    assert bram["daily_max_minutes"] == 90
    days = {d["date"]: d for d in anna["days"]}
    assert list(days) == [f"2026-11-{n}" for n in range(14, 21)]
    assert days["2026-11-14"]["weekday"] == "Saturday"
    assert days["2026-11-14"]["planned_minutes"] == 15
    assert days["2026-11-18"]["planned_minutes"] == 0
    thursday = days["2026-11-19"]
    assert thursday["planned_minutes"] == 75
    assert thursday["daily_max_minutes"] == 60
    assert thursday["over_daily_max"] is True
    assert days["2026-11-14"]["over_daily_max"] is False
    (test,) = [t for t in thursday["tests"] if t["id"] == PROEFWERK]
    assert test["subject"] == "Duitse taal"
    assert test["label"] == "Proefwerk"
    assert test["subtasks"] == 3
    assert test["completed"] is False
    assert thursday["open_items"] >= 1
    monday = days["2026-11-16"]
    assert HOMEWORK in {a["id"] for a in monday["assignments"]}
    assert all(
        t["id"] not in {a["id"] for a in monday["assignments"]} for t in monday["tests"]
    )
    # Bram has no subtasks: nothing planned, nothing over.
    assert all(d["planned_minutes"] == 0 for d in bram["days"])
    # The same ids and no hosts, uids or teacher data.
    text = json.dumps(data)
    for forbidden in ("magister.net", "Docent", "uid", "school.", "Anna A"):
        assert forbidden not in text, forbidden


async def test_overview_counts_done_subtasks_and_skips_disabled(
    hass: HomeAssistant, family: Family
) -> None:
    """A done subtask counts on the day it was done; a disabled item is left out."""
    student = family.student.id
    added = await ok(
        hass,
        student,
        "add_subtask",
        item=PROEFWERK,
        title="a",
        date="2026-11-19",
        minutes=20,
    )
    sub = added["item"]["subtasks"][0]["id"]
    data = await ok(hass, student, "get_overview", start="2026-11-13", end="2026-11-19")
    days = {d["date"]: d for d in data["children"][0]["days"]}
    assert days["2026-11-19"]["planned_minutes"] == 20
    assert days["2026-11-13"]["planned_minutes"] == 0
    await ok(hass, student, "set_progress", id=sub, progress=100)
    data = await ok(hass, student, "get_overview", start="2026-11-13", end="2026-11-19")
    days = {d["date"]: d for d in data["children"][0]["days"]}
    assert days["2026-11-13"]["planned_minutes"] == 20
    assert days["2026-11-19"]["planned_minutes"] == 0
    thursday = days["2026-11-19"]
    assert any(t["id"] == PROEFWERK and t["completed"] for t in thursday["tests"])
    assert (
        thursday["open_items"]
        == len(thursday["assignments"]) + len(thursday["tests"]) - 1
    )
    await ok(hass, student, "set_label_override", appointment=PROEFWERK, mode="disable")
    data = await ok(hass, student, "get_overview", start="2026-11-19", end="2026-11-19")
    (day,) = data["children"][0]["days"]
    assert PROEFWERK not in {i["id"] for i in day["tests"] + day["assignments"]}


async def test_overview_range_rules(hass: HomeAssistant, family: Family) -> None:
    """At most 31 days, end not before start, dates written YYYY-MM-DD."""
    parent = family.parent.id
    data = await ok(hass, parent, "get_overview", start="2026-11-01", end="2026-12-01")
    assert len(data["children"][0]["days"]) == 31
    for start, end in (
        ("2026-11-01", "2026-12-02"),
        ("2026-11-05", "2026-11-04"),
        ("13-11-2026", "2026-11-14"),
        ("2026-11-13", "morgen"),
    ):
        assert (
            await fails(hass, parent, "get_overview", start=start, end=end)
            == "invalid_format"
        )
    one = await ok(hass, parent, "get_overview", start="2026-11-13", end="2026-11-13")
    assert len(one["children"][0]["days"]) == 1
    assert await fails(hass, parent, "get_overview", start="2026-11-13") == (
        "invalid_format"
    )


# -- estimated time and created_by --------------------------------------------------


async def test_parent_subtasks_are_marked_and_logged(
    hass: HomeAssistant, family: Family, logbook: list[Any]
) -> None:
    """Parent: `created_by` parent, "Ouder via AI"; student: ai, "AI-coach"."""
    parent, student = family.parent.id, family.student.id
    data = await ok(
        hass,
        parent,
        "add_subtask",
        child="1001",
        item=PROEFWERK,
        title="H4 woordjes",
        date="2026-11-16",
        minutes=30,
    )
    sub = data["item"]["subtasks"][0]
    assert (sub["created_by"], sub["minutes"]) == ("parent", 30)
    other = await ok(
        hass, student, "add_subtask", item=PROEFWERK, title="Eigen", minutes=15
    )
    assert [s["created_by"] for s in other["item"]["subtasks"]] == ["parent", "ai"]
    # The parent's second child gets its own parent marker.
    second = await ok(
        hass, parent, "add_subtask", child="1002", item=PROEFWERK, title="Bram"
    )
    assert second["item"]["subtasks"][0]["created_by"] == "parent"
    assert second["item"]["subtasks"][0]["minutes"] is None

    updated = await ok(
        hass, parent, "update_subtask", child="1001", subtask=sub["id"], minutes=45
    )
    assert updated["item"]["subtasks"][0]["minutes"] == 45
    assert updated["item"]["subtasks"][0]["created_by"] == "parent"
    cleared = await ok(
        hass, parent, "update_subtask", child="1001", subtask=sub["id"], minutes=None
    )
    assert cleared["item"]["subtasks"][0]["minutes"] is None
    # A no-op update (the same value) is not logged.
    count = len(logbook)
    await ok(
        hass, parent, "update_subtask", child="1001", subtask=sub["id"], minutes=None
    )
    assert len(logbook) == count
    await ok(hass, parent, "delete_subtask", child="1001", subtask=sub["id"])

    messages = [e.data["message"] for e in logbook]
    assert (
        messages[0]
        == "Ouder via AI: deelstap 'H4 woordjes' toegevoegd aan Proefwerk Duitse taal"
    )
    assert (
        messages[1] == "AI-coach: deelstap 'Eigen' toegevoegd aan Proefwerk Duitse taal"
    )
    assert messages[2].startswith("Ouder via AI: deelstap 'Bram' toegevoegd")
    assert (
        messages[3]
        == "Ouder via AI: deelstap 'H4 woordjes' gewijzigd bij Proefwerk Duitse taal"
    )
    assert messages[4].startswith("Ouder via AI: deelstap 'H4 woordjes' gewijzigd")
    assert messages[5].startswith("Ouder via AI: deelstap 'H4 woordjes' verwijderd")
    assert len(messages) == 6
    assert all(e.data["name"] == "Magister" for e in logbook)


async def test_minutes_validation_in_the_tools(
    hass: HomeAssistant, family: Family, logbook: list[Any]
) -> None:
    """A bad value is `invalid_minutes` (nothing stored, nothing logged)."""
    student = family.student.id
    for bad in (0, 4, 7, 245, -5, True):
        assert (
            await fails(
                hass, student, "add_subtask", item=PROEFWERK, title="x", minutes=bad
            )
            == "invalid_minutes"
        ), bad
    for bad in (5, 240):
        await ok(hass, student, "add_subtask", item=PROEFWERK, title="y", minutes=bad)
    # Not an integer at all: the schema refuses it.
    for bad in ("30", 12.5, [5]):
        assert (
            await fails(
                hass, student, "add_subtask", item=PROEFWERK, title="x", minutes=bad
            )
            == "invalid_format"
        ), bad
    listed = await ok(
        hass, student, "list_homework", start="2026-11-19", end="2026-11-19"
    )
    item = next(i for i in listed["items"] if i["id"] == PROEFWERK)
    assert [s["minutes"] for s in item["subtasks"]] == [5, 240]
    sub = item["subtasks"][0]["id"]
    logged = len(logbook)
    assert (
        await fails(hass, student, "update_subtask", subtask=sub, minutes=6)
        == "invalid_minutes"
    )
    assert len(logbook) == logged
    # Minutes alone is a valid update; an update without anything is not.
    await ok(hass, student, "update_subtask", subtask=sub, minutes=90)
    assert await fails(hass, student, "update_subtask", subtask=sub) == "invalid_format"


# -- set_progress -------------------------------------------------------------------


async def test_set_progress_is_refused_for_parents(
    hass: HomeAssistant, family: Family, logbook: list[Any]
) -> None:
    """`not_allowed_for_role`: nothing written, nothing logged, also for subtasks."""
    parent, student = family.parent.id, family.student.id
    added = await ok(
        hass, parent, "add_subtask", child="1001", item=PROEFWERK, title="s", minutes=20
    )
    sub = added["item"]["subtasks"][0]["id"]
    logged = len(logbook)
    manager = family.entry.runtime_data.homework
    uid = f"school.magister.net:1001:{HOMEWORK}"
    for target in (HOMEWORK, sub):
        result = await call(
            hass, parent, "set_progress", child="1001", id=target, progress=100
        )
        assert result.error
        assert result.data["error"] == "not_allowed_for_role"
        assert "student" in result.data["message"]
    # Also with an invalid id or value: the role check comes first and writes nothing.
    assert (
        await fails(hass, parent, "set_progress", child="1002", id="x", progress=500)
        == "not_allowed_for_role"
    )
    assert manager.progress(uid) == 0
    sub_item = manager.find_subtask(f"school.magister.net:1001:{sub}")
    assert sub_item is not None and sub_item.progress == 0
    assert len(logbook) == logged
    # The parent still reads the progress.
    progress = await ok(hass, parent, "get_progress", child="1001")
    assert "next_day" in progress["progress"]
    # The student of the same child can, and it is logged as before.
    await ok(hass, student, "set_progress", id=sub, progress=50)
    assert logbook[-1].data["message"].startswith("AI-coach: voortgang van deelstap")
    tool = next(t for t in llm_tools(hass) if t.name == "set_progress")
    assert "not_allowed_for_role" in tool.description
    assert "parent" in tool.description


def llm_tools(hass: HomeAssistant) -> list[llm.Tool]:
    """The tools of the API."""
    from custom_components.magister.coach import coach_tools

    return coach_tools()


async def test_other_parent_writes_are_logged_as_parent(
    hass: HomeAssistant, family: Family, logbook: list[Any]
) -> None:
    """Label writes of a parent carry the same prefix."""
    parent = family.parent.id
    await ok(
        hass,
        parent,
        "set_label_override",
        child="1001",
        appointment=PROEFWERK,
        mode="disable",
    )
    assert logbook[-1].data["message"].startswith("Ouder via AI: Magister-label van")


# -- prompt -------------------------------------------------------------------------


async def test_prompt_per_role(hass: HomeAssistant, family: Family) -> None:
    """Role, daily maximum and the matching guidelines for each child."""
    with_weights(family, hass, {"1002": {"daily_max_minutes": 150}})
    hass.config_entries.async_update_entry(
        family.entry,
        options={**family.entry.options, CONF_PARENT_GUIDELINES: "  Kort en bondig.  "},
    )
    api = await llm.async_get_api(hass, COACH_API_ID, llm_context(family.parent.id))
    prompt = api.api_prompt
    assert "Anna (id 1001), Bram (id 1002)" in prompt
    assert "Always pass `child`" in prompt
    assert "You are the parent (role Ouder) of Anna (id 1001)" in prompt
    assert "You are the parent (role Ouder) of Bram (id 1002)" in prompt
    assert "Daily maximum: 90 study minutes per school day." in prompt
    assert "Daily maximum: 150 study minutes per school day." in prompt
    assert "Parent guidelines for Anna (id 1001):\nKort en bondig." in prompt
    assert "Parent guidelines for Bram (id 1002):\nKort en bondig." in prompt
    assert "get_overview" in prompt
    assert "within the child's daily maximum" in prompt
    assert "cannot set progress" in prompt
    assert DEFAULT_GUIDELINES not in prompt
    assert "Coaching guidelines for" not in prompt
    # The student of A gets the student text, never the parent's.
    api = await llm.async_get_api(hass, COACH_API_ID, llm_context(family.student.id))
    prompt = api.api_prompt
    assert "You coach the student (role Leerling) Anna (id 1001)." in prompt
    assert "Daily maximum: 90 study minutes per school day." in prompt
    assert "Coaching guidelines for Anna (id 1001):\n" + DEFAULT_GUIDELINES in prompt
    assert "Kort en bondig." not in prompt
    assert "Parent guidelines" not in prompt
    assert "get_overview" in prompt


async def test_default_parent_guidelines_verbatim(
    hass: HomeAssistant, family: Family
) -> None:
    """Empty means the default text of the milestone, in the prompt."""
    assert parent_guidelines_of(family.entry) == DEFAULT_PARENT_GUIDELINES
    api = await llm.async_get_api(hass, COACH_API_ID, llm_context(family.parent.id))
    assert DEFAULT_PARENT_GUIDELINES in api.api_prompt
    assert DEFAULT_PARENT_GUIDELINES.startswith(
        "Je helpt een ouder om voor een kind een haalbare studieplanning te maken."
    )
    for fragment in (
        "deelstappen van 15–45 minuten, elk met een geschatte tijd",  # noqa: RUF001
        "Houd je aan het dagmaximum van het kind",
        "Voortgang geeft het kind zelf aan; jij past die niet aan.",
        "Spreek Nederlands, tenzij de ouder een andere taal gebruikt.",
    ):
        assert fragment in DEFAULT_PARENT_GUIDELINES
    # A blank or non-text option is the default as well.
    for value in ("", "   ", 5, None):
        hass.config_entries.async_update_entry(
            family.entry,
            options={**family.entry.options, CONF_PARENT_GUIDELINES: value},
        )
        assert parent_guidelines_of(family.entry) == DEFAULT_PARENT_GUIDELINES


async def test_child_type_has_role_defaults() -> None:
    """A child made without a role is a student with the default maximum."""
    assert CoachChild.__dataclass_fields__["role"].default == "student"
    assert CoachChild.__dataclass_fields__["daily_max"].default == 90


async def test_unexpected_error_in_overview_is_generic(
    hass: HomeAssistant,
    family: Family,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A bug in the new tool gives `internal_error`, without details."""

    def boom(*args: Any, **kwargs: Any) -> Any:
        raise RuntimeError("secret detail geheimvak")

    monkeypatch.setattr("custom_components.magister.coach._overview_of", boom)
    caplog.set_level(logging.ERROR)
    result = await call(
        hass, family.parent.id, "get_overview", start="2026-11-16", end="2026-11-16"
    )
    assert result.data["error"] == "internal_error"
    assert "secret" not in json.dumps(result.data)
    assert "secret" not in caplog.text
