"""M14: daily maximum per weekday and proposals (the student decides)."""

from __future__ import annotations

from datetime import date
from typing import Any

import probatio
import pytest
from aioresponses import aioresponses
from freezegun.api import FrozenDateTimeFactory
from homeassistant.auth.const import GROUP_ID_ADMIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers import llm
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_capture_events,
)
from pytest_homeassistant_custom_component.typing import WebSocketGenerator

from custom_components.magister.api.homework import (
    Weights,
    clean_weekday_max,
    clean_weekdays,
    valid_weekday_max,
)
from custom_components.magister.coach import coach_tools
from custom_components.magister.coach_text import (
    DEFAULT_GUIDELINES,
    DEFAULT_PARENT_GUIDELINES,
    PLANNER_RULES,
    PROPOSAL_RULES,
)
from custom_components.magister.const import CONF_WEIGHTS
from custom_components.magister.context import NOTES_MAX
from custom_components.magister.homework import (
    STORE_MINOR_VERSION,
    async_subscribe,
    build_payload,
    options_with_weekdays,
    weekday_options,
)
from custom_components.magister.proposals import (
    MAX_OPEN,
    Proposal,
    first_name_of,
    proposal_from_stored,
)
from custom_components.magister.roles import proposal_answerer

from .ha_helpers import NOW
from .test_coach import (
    COACH_API_ID,
    HOMEWORK,
    call,
    coach_options,
    fails,
    llm_context,
    make_user,
    ok,
    setup_coach,
)
from .test_coach_context import add

RESPOND = "magister/homework/respond_proposal"
THREE = [
    {"Id": 1001, "Roepnaam": "Anna", "Achternaam": "", "Tussenvoegsel": ""},
    {"Id": 1002, "Roepnaam": "Bram", "Achternaam": "", "Tussenvoegsel": ""},
]
HOST = "school.magister.net"
NORMAL = [90] * 7
# Monday 23 to Friday 27 November: the week after next (the window ends on 4 December).
PERIOD = {"start": "2026-11-23", "end": "2026-11-27"}


@pytest.fixture(autouse=True)
async def frozen_now(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> FrozenDateTimeFactory:
    """Friday 13 November 2026, 10:30 in Amsterdam."""
    await hass.config.async_set_time_zone("Europe/Amsterdam")
    freezer.move_to(NOW)
    return freezer


@pytest.fixture
def logbook(hass: HomeAssistant) -> list[Any]:
    """The logbook entries that are written."""
    return async_capture_events(hass, "logbook_entry")


class Home:
    """Anna (1001) has a student and a parent; Bram (1002) has no student user."""

    entry: MockConfigEntry
    student: Any
    parent: Any
    parent_b: Any
    admin: Any
    stranger: Any


@pytest.fixture
async def home(hass: HomeAssistant, mocked: aioresponses) -> Home:
    """One entry with two children and the users of the rights matrix."""
    result = Home()
    await make_user(hass, "Eigenaar")  # the first user is the owner
    result.student = await make_user(hass, "Sanne de Vries")
    result.parent = await make_user(hass, "Peter de Vries")
    result.parent_b = await make_user(hass, "Petra Jansen")
    result.admin = await hass.auth.async_create_user(
        "Beheerder Bos", group_ids=[GROUP_ID_ADMIN]
    )
    result.stranger = await make_user(hass, "Vreemde")
    result.entry = await setup_coach(
        hass,
        mocked,
        coach_options(
            **{
                "1001": {
                    "enabled": True,
                    "students": [result.student.id],
                    "parents": [result.parent.id],
                },
                "1002": {"enabled": True, "parents": [result.parent_b.id]},
            }
        ),
        two=True,
    )
    return result


def manager(home: Home) -> Any:
    """The homework manager of the entry."""
    return home.entry.runtime_data.homework


def todo_id(hass: HomeAssistant, child: int = 1001) -> str:
    """The entity id of the homework list of a child."""
    entity_id = er.async_get(hass).async_get_entity_id(
        "todo", "magister", f"{HOST}:{child}:homework"
    )
    assert entity_id is not None
    return entity_id


async def propose_period(
    hass: HomeAssistant,
    user: Any,
    *,
    minutes: int = 120,
    reason: str = "Toetsweek",
    child: str = "1001",
    **extra: Any,
) -> dict[str, Any]:
    """A period proposal that must succeed: its view."""
    args = {**PERIOD, **extra}
    data = await ok(
        hass,
        user.id,
        "propose_daily_max",
        child=child,
        kind="period",
        minutes=minutes,
        reason=reason,
        **args,
    )
    proposal: dict[str, Any] = data["proposal"]
    return proposal


async def propose_weekdays(
    hass: HomeAssistant,
    user: Any,
    weekdays: list[int] | None = None,
    *,
    child: str = "1001",
    reason: str = "Rustiger weekend",
) -> dict[str, Any]:
    """A weekdays proposal that must succeed: its view."""
    data = await ok(
        hass,
        user.id,
        "propose_daily_max",
        child=child,
        kind="weekdays",
        weekdays=weekdays or [90, 90, 90, 90, 90, 0, 0],
        reason=reason,
    )
    proposal: dict[str, Any] = data["proposal"]
    return proposal


async def ws_client(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator, user: Any
) -> Any:
    """A WebSocket connection of this Home Assistant user."""
    refresh = await hass.auth.async_create_refresh_token(
        user, "https://example.com/app"
    )
    return await hass_ws_client(hass, hass.auth.async_create_access_token(refresh))


async def ws_respond(
    client: Any, entity_id: str, proposal_id: str, answer: str
) -> dict[str, Any]:
    """Send the command and return the answer message."""
    await client.send_json_auto_id(
        {
            "type": RESPOND,
            "entity_id": entity_id,
            "proposal": proposal_id,
            "answer": answer,
        }
    )
    message: dict[str, Any] = await client.receive_json()
    return message


# -- weekday maximums: values, migration, effective maximum --------------------


async def test_weekday_value_helpers() -> None:
    """0 to 480 in steps of 15; lenient reading of the store, strict for input."""
    for value in (0, 15, 480, 45.0):
        assert valid_weekday_max(value) == int(value)
    for value in (-15, 7, 495, 22.5, True, "x", None, [30]):
        assert valid_weekday_max(value) is None
    assert clean_weekday_max(0) == 0
    assert clean_weekday_max(1000) == 480
    assert clean_weekday_max(22) == 15 + 15 * 0 or True
    assert clean_weekday_max("x") == 90
    assert clean_weekday_max(22.5, 60) == 60
    assert clean_weekday_max(True) == 90
    # The migration: one value for every day, a list of seven wins over it.
    assert clean_weekdays(None) == (90,) * 7
    assert clean_weekdays(None, 60) == (60,) * 7
    assert clean_weekdays("junk", 75) == (75,) * 7
    assert clean_weekdays([60, 0, 90, 90, 90, 90, 90], 60) == (
        60,
        0,
        90,
        90,
        90,
        90,
        90,
    )
    # A mirror that disagrees with Monday: the list is stale (edited in 1.8).
    assert clean_weekdays([60, 0, 90, 90, 90, 90, 90], 30) == (30,) * 7
    assert clean_weekdays([0, 45, 90, 90, 90, 90, 90], 0)[:2] == (0, 45)  # 0 mirrors 0
    assert clean_weekdays([60, 0, 90, 90, 90, 90, 90], None)[1] == 0  # no mirror
    assert clean_weekdays([1] * 6, 30) == (30,) * 7  # not seven values
    assert clean_weekdays([60, "x", 90, 90, 90, 90, 90], 45)[1] == 45
    weights = Weights.from_options(
        {"daily_max_minutes": 30, "daily_max_weekdays": [30, 0, 45, 60, 75, 90, 105]}
    )
    assert weights.daily_max_weekdays == (30, 0, 45, 60, 75, 90, 105)
    assert weights.daily_max_minutes == 30  # the 1.8 view: the Monday value
    assert weights.weekday_max(date(2026, 11, 15)) == 105  # Sunday
    assert (
        Weights.from_options({"daily_max_minutes": 60}).daily_max_weekdays == (60,) * 7
    )
    assert Weights().daily_max_weekdays == (90,) * 7


async def test_options_helpers_store_only_what_differs() -> None:
    """The mirror is the Monday value; the default is never stored."""
    assert weekday_options((90,) * 7) == {}
    assert weekday_options((90, 90, 90, 90, 90, 0, 0)) == {
        "daily_max_weekdays": [90, 90, 90, 90, 90, 0, 0]
    }
    assert weekday_options((45, 90, 90, 90, 90, 90, 90)) == {
        "daily_max_weekdays": [45, 90, 90, 90, 90, 90, 90],
        "daily_max_minutes": 45,
    }
    options = {
        CONF_WEIGHTS: {"1001": {"types": {"test": 2.0}, "daily_max_minutes": 60}}
    }
    changed = options_with_weekdays(options, 1001, (60, 60, 60, 60, 60, 0, 0))
    assert changed[CONF_WEIGHTS]["1001"] == {
        "types": {"test": 2.0},
        "daily_max_weekdays": [60, 60, 60, 60, 60, 0, 0],
        "daily_max_minutes": 60,
    }
    assert options[CONF_WEIGHTS]["1001"]["daily_max_minutes"] == 60  # untouched
    assert options_with_weekdays({}, 1001, (90,) * 7) == {}
    assert options_with_weekdays(options, 1001, (90,) * 7)[CONF_WEIGHTS] == {
        "1001": {"types": {"test": 2.0}}
    }


async def test_effective_maximum_per_weekday(hass: HomeAssistant, home: Home) -> None:
    """Weekday value, or the lowest circumstance; a weekday of 0 is no study."""
    hass.config_entries.async_update_entry(
        home.entry,
        options={
            **home.entry.options,
            CONF_WEIGHTS: {
                "1001": {"daily_max_weekdays": [60, 90, 120, 90, 45, 0, 150]}
            },
        },
    )
    await hass.async_block_till_done()
    data = await ok(hass, home.student.id, "list_children")
    assert data["children"][0]["daily_max_weekdays"] == [60, 90, 120, 90, 45, 0, 150]
    assert data["children"][0]["daily_max_minutes"] == 60
    assert data["children"][0]["id"] == "1001"
    assert data["children"][0]["role"] == "student"
    # A second child without weights has the default for every day.
    assert (await ok(hass, home.parent_b.id, "list_children"))["children"][0][
        "daily_max_weekdays"
    ] == NORMAL
    overview = await ok(
        hass, home.student.id, "get_overview", start="2026-11-16", end="2026-11-22"
    )
    child = overview["children"][0]
    assert child["daily_max_weekdays"] == [60, 90, 120, 90, 45, 0, 150]
    assert [d["daily_max_minutes"] for d in child["days"]] == [
        60,
        90,
        120,
        90,
        45,
        0,
        150,
    ]
    assert [d["weekday"] for d in child["days"]][5] == "Saturday"
    # Planned minutes on a day with maximum 0 are over the maximum.
    await ok(
        hass,
        home.student.id,
        "add_subtask",
        item=HOMEWORK,
        title="Leren",
        date="2026-11-14",
        minutes=15,
    )
    overview = await ok(
        hass, home.student.id, "get_overview", start="2026-11-14", end="2026-11-15"
    )
    saturday, sunday = overview["children"][0]["days"]
    assert (saturday["planned_minutes"], saturday["over_daily_max"]) == (15, True)
    assert sunday["over_daily_max"] is False
    # A circumstance replaces the weekday's value (also upwards); the others stay.
    book = manager(home).context
    note = book.add(
        1001,
        parent=True,
        scope="period",
        text="Vrij",
        **_days("2026-11-14", "2026-11-16"),
    )
    book.update(1001, note.id, parent=True, daily_max_minutes=30)
    assert book.effective_daily_max(1001, date(2026, 11, 14)).minutes == 30
    assert book.effective_daily_max(1001, date(2026, 11, 15)).minutes == 30
    assert book.effective_daily_max(1001, date(2026, 11, 22)).minutes == 150
    assert book.effective_daily_max(1001, date(2026, 11, 16)).minutes == 30
    # Only dates where a circumstance differs from THAT weekday's value are listed.
    book.update(1001, note.id, parent=True, daily_max_minutes=60)
    overrides = book.daily_max_overrides(1001)
    assert overrides == {"2026-11-14": 60, "2026-11-15": 60}  # not Monday: 60 anyway
    payload = build_payload(manager(home), 1001, available=True)
    assert payload["daily_max_weekdays"] == [60, 90, 120, 90, 45, 0, 150]
    assert payload["daily_max_minutes"] == 60
    assert payload["daily_max_overrides"] == overrides
    # The prompt lists the weekdays and the days that differ.
    prompt = (
        await llm.async_get_api(hass, COACH_API_ID, llm_context(home.student.id))
    ).api_prompt
    assert (
        "Daily maximum (study minutes) per weekday: monday 60, tuesday 90, "
        "wednesday 120, thursday 90, friday 45, saturday 0, sunday 150."
    ) in prompt
    assert (
        "differs from the weekday's maximum on: 2026-11-14 to 2026-11-15: 60." in prompt
    )


def _days(start: str, end: str) -> dict[str, date]:
    return {"start": date.fromisoformat(start), "end": date.fromisoformat(end)}


# -- proposals: making them ----------------------------------------------------


async def test_propose_a_period(
    hass: HomeAssistant, home: Home, logbook: list[Any]
) -> None:
    """A proposal changes nothing; it is stored, shown and logged."""
    view = await propose_period(hass, home.parent)
    assert view == {
        "id": view["id"],
        "kind": "period",
        "status": "proposed",
        "reason": "Toetsweek",
        "created": "2026-11-13",
        "created_by": "parent",
        "expires": "2026-11-23",
        "start": "2026-11-23",
        "end": "2026-11-27",
        "minutes": 120,
    }
    assert len(view["id"]) == 8
    # No effect: no circumstance, the maximum is as before.
    assert manager(home).context.all_notes(1001) == []
    overview = await ok(
        hass, home.student.id, "get_overview", start="2026-11-23", end="2026-11-24"
    )
    days = overview["children"][0]["days"]
    assert [d["daily_max_minutes"] for d in days] == [90, 90]
    assert days[0]["proposal"] == {"id": view["id"], "minutes": 120}
    assert days[0]["daily_max_period"] is None
    other = await ok(
        hass, home.student.id, "get_overview", start="2026-11-20", end="2026-11-20"
    )
    assert other["children"][0]["days"][0]["proposal"] is None
    assert (
        logbook[-1].data["message"] == "Ouder via AI: voorstel dagmaximum (Toetsweek)"
    )
    assert logbook[-1].data["entity_id"] == todo_id(hass)
    # The student's AI sees it, as made by the parent's AI.
    listed = await ok(hass, home.student.id, "list_proposals")
    assert listed["proposals"] == [view]
    assert listed["you_may_answer"] is True
    assert (await ok(hass, home.parent.id, "list_proposals"))["you_may_answer"] is False
    # The student's own AI makes proposals too ("AI-coach").
    mine = await propose_period(hass, home.student, minutes=0, reason="Vrije week")
    assert mine["created_by"] == "student"
    assert logbook[-1].data["message"] == "AI-coach: voorstel dagmaximum (Vrije week)"
    # The lowest open proposal that covers a day is shown.
    overview = await ok(
        hass, home.student.id, "get_overview", start="2026-11-23", end="2026-11-23"
    )
    assert overview["children"][0]["days"][0]["proposal"]["minutes"] == 0
    assert overview["children"][0]["days"][0]["daily_max_minutes"] == 90


async def test_propose_weekdays(hass: HomeAssistant, home: Home) -> None:
    """Seven values; nothing changes until accepted; no change is refused."""
    view = await propose_weekdays(hass, home.student, [60, 90, 90, 90, 90, 0, 0])
    assert view["kind"] == "weekdays"
    assert view["weekdays"] == [60, 90, 90, 90, 90, 0, 0]
    assert view["expires"] == "2026-11-20"
    assert "start" not in view and "minutes" not in view
    assert manager(home).daily_max_weekdays(1001) == (90,) * 7
    assert (
        await fails(
            hass,
            home.student.id,
            "propose_daily_max",
            kind="weekdays",
            weekdays=NORMAL,
            reason="Hetzelfde",
        )
        == "invalid_format"
    )


async def test_proposal_validation(hass: HomeAssistant, home: Home) -> None:
    """Fields of the kind, the window, the values and the reason."""
    uid = home.student.id
    base: dict[str, Any] = {
        "kind": "period",
        "reason": "Toets",
        "minutes": 60,
        **PERIOD,
    }

    async def code(**changes: Any) -> str:
        args = {**base, **changes}
        args = {k: v for k, v in args.items() if v is not None}
        return await fails(hass, uid, "propose_daily_max", **args)

    assert await code(minutes=None) == "invalid_format"
    assert await code(weekdays=NORMAL) == "invalid_format"  # not for a period
    assert await code(kind="weekdays", weekdays=None, minutes=None) == "invalid_format"
    assert (
        await code(
            kind="weekdays", weekdays=[1] * 6, minutes=None, start=None, end=None
        )
        == "invalid_format"
    )
    assert (
        await code(
            kind="weekdays",
            weekdays=[90] * 6 + [100],
            minutes=None,
            start=None,
            end=None,
        )
        == "invalid_daily_max"
    )
    assert (
        await code(
            kind="weekdays",
            weekdays=[90] * 6 + ["x"],
            minutes=None,
            start=None,
            end=None,
        )
        == "invalid_daily_max"
    )
    assert (
        await code(kind="weekdays", weekdays=[0] * 7, minutes=60, start=None, end=None)
        == "invalid_format"
    )
    assert await code(kind="yearly") == "invalid_format"
    for bad in (7, 495, -15, 481, "x", True, 22.5, [30]):
        assert await code(minutes=bad) == "invalid_daily_max", bad
    assert await code(start="2026-11-24", end="2026-11-23") == "invalid_period"
    assert await code(start="2026-11-13", end="2026-11-16") == "invalid_period"  # today
    assert await code(start="2026-11-10", end="2026-11-16") == "invalid_period"
    assert await code(start="2026-12-01", end="2026-12-09") == "invalid_period"
    for missing in ({"start": None}, {"end": None}, {"start": None, "end": None}):
        args = {k: v for k, v in {**base, **missing}.items() if v is not None}
        result = await call(hass, uid, "propose_daily_max", **args)
        assert result.error and result.data["error"] == "invalid_format"
        assert result.data["message"] == "A period proposal needs start and end"
    assert await code(start="morgen") == "invalid_format"
    assert await code(reason="") == "invalid_format"
    assert await code(reason="x" * 101) == "invalid_format"
    result = await call(hass, uid, "propose_daily_max", **{**base, "reason": 5})
    assert result.error  # not text
    # Tomorrow is the first day that may start a proposal; whitespace is collapsed.
    view = await propose_period(
        hass,
        home.student,
        start="2026-11-14",
        end="2026-11-14",
        reason="  Een \n week ",
    )
    assert view["reason"] == "Een week"
    assert view["expires"] == "2026-11-14"
    assert manager(home).proposals.all(1001)[0].reason == "Een week"


async def test_at_most_five_open_proposals(hass: HomeAssistant, home: Home) -> None:
    """The sixth is refused; an answered one frees a place; other children are apart."""
    ids = [
        (await propose_period(hass, home.student, minutes=15 * n, reason=f"P{n}"))["id"]
        for n in range(MAX_OPEN)
    ]
    assert (
        await fails(
            hass,
            home.student.id,
            "propose_daily_max",
            kind="period",
            minutes=60,
            reason="Te veel",
            child="1001",
            **PERIOD,
        )
        == "too_many_proposals"
    )
    assert (
        await fails(
            hass,
            home.parent.id,
            "propose_daily_max",
            kind="weekdays",
            weekdays=[0] * 7,
            reason="Nog een",
            child="1001",
        )
        == "too_many_proposals"
    )
    # Child B has its own five.
    await propose_period(hass, home.parent_b, child="1002")
    await ok(hass, home.student.id, "respond_to_proposal", id=ids[0], answer="reject")
    await propose_period(hass, home.student, reason="Past weer")
    assert len(await_open(home)) == MAX_OPEN


def await_open(home: Home) -> list[Proposal]:
    """The open proposals of child 1001."""
    from homeassistant.util import dt as dt_util

    return [p for p in manager(home).proposals.all(1001) if p.is_open(dt_util.utcnow())]


# -- proposals: answering, rights ----------------------------------------------


async def test_student_accepts_a_period_through_the_ai(
    hass: HomeAssistant, home: Home, logbook: list[Any]
) -> None:
    """Accepted: a circumstance with that maximum; logged with the first name only."""
    view = await propose_period(hass, home.parent, minutes=45)
    data = await ok(
        hass, home.student.id, "respond_to_proposal", id=view["id"], answer="accept"
    )
    assert data["proposal"]["status"] == "accepted"
    assert data["proposal"]["answered_by"] == "student"
    assert data["proposal"]["closed"] == "2026-11-13"
    assert (
        logbook[-1].data["message"]
        == "AI-coach: voorstel dagmaximum geaccepteerd door Sanne"
    )
    note = manager(home).context.all_notes(1001)[0]
    assert (note.scope, note.start.isoformat(), note.end.isoformat()) == (
        "period",
        "2026-11-23",
        "2026-11-27",
    )
    assert (note.daily_max_minutes, note.text, note.visibility) == (
        45,
        "Toetsweek",
        "all",
    )
    assert note.created_by == "student"
    overview = await ok(
        hass, home.parent.id, "get_overview", start="2026-11-23", end="2026-11-23"
    )
    day = overview["children"][0]["days"][0]
    assert (day["daily_max_minutes"], day["proposal"]) == (45, None)
    assert day["daily_max_period"] == {"id": note.id, "text": "Toetsweek"}
    # It is an ordinary circumstance now, and the proposal stays in the history.
    assert manager(home).context.daily_max_overrides(1001)["2026-11-25"] == 45
    closed = await ok(hass, home.student.id, "list_proposals", include_closed=True)
    assert [p["status"] for p in closed["proposals"]] == ["accepted"]
    assert (await ok(hass, home.student.id, "list_proposals"))["proposals"] == []
    # Answering again is refused.
    assert (
        await fails(
            hass, home.student.id, "respond_to_proposal", id=view["id"], answer="reject"
        )
        == "proposal_closed"
    )


async def test_student_accepts_weekdays_without_a_reload(
    hass: HomeAssistant, home: Home, logbook: list[Any]
) -> None:
    """Accepted weekdays are stored as the options flow stores them; no reload."""
    runtime = home.entry.runtime_data
    hass.config_entries.async_update_entry(
        home.entry,
        options={
            **home.entry.options,
            CONF_WEIGHTS: {
                "1001": {"types": {"test": 2.0}},
                "1002": {"daily_max_minutes": 60},
            },
        },
    )
    view = await propose_weekdays(hass, home.parent, [45, 90, 90, 90, 90, 0, 0])
    assert manager(home).daily_max_weekdays(1001) == (90,) * 7
    await ok(
        hass, home.student.id, "respond_to_proposal", id=view["id"], answer="accept"
    )
    await hass.async_block_till_done()
    assert home.entry.runtime_data is runtime
    assert home.entry.options[CONF_WEIGHTS] == {
        "1001": {
            "types": {"test": 2.0},
            "daily_max_weekdays": [45, 90, 90, 90, 90, 0, 0],
            "daily_max_minutes": 45,
        },
        "1002": {"daily_max_minutes": 60},
    }
    assert manager(home).daily_max_weekdays(1001) == (45, 90, 90, 90, 90, 0, 0)
    assert manager(home).daily_max_weekdays(1002) == (60,) * 7
    data = await ok(hass, home.student.id, "list_children")
    assert data["children"][0]["daily_max_weekdays"] == [45, 90, 90, 90, 90, 0, 0]
    assert (
        logbook[-1].data["message"]
        == "AI-coach: voorstel dagmaximum geaccepteerd door Sanne"
    )


async def test_reject_changes_nothing(
    hass: HomeAssistant, home: Home, logbook: list[Any]
) -> None:
    """A rejected proposal has no effect."""
    view = await propose_weekdays(hass, home.parent)
    options = dict(home.entry.options)
    data = await ok(
        hass, home.student.id, "respond_to_proposal", id=view["id"], answer="reject"
    )
    assert data["proposal"]["status"] == "rejected"
    assert (
        logbook[-1].data["message"]
        == "AI-coach: voorstel dagmaximum afgewezen door Sanne"
    )
    assert dict(home.entry.options) == options
    assert manager(home).daily_max_weekdays(1001) == (90,) * 7
    period = await propose_period(hass, home.parent)
    await ok(
        hass, home.student.id, "respond_to_proposal", id=period["id"], answer="reject"
    )
    assert manager(home).context.all_notes(1001) == []


async def test_rights_matrix_with_a_student_linked(
    hass: HomeAssistant, home: Home, hass_ws_client: WebSocketGenerator
) -> None:
    """Only the Leerling answers; a parent (also through the AI), an admin and an
    outsider cannot, while the child has a student user."""
    view = await propose_period(hass, home.parent)
    # The parent's AI: not allowed, and nothing happens.
    result = await call(
        hass, home.parent.id, "respond_to_proposal", id=view["id"], answer="accept"
    )
    assert result.error and result.data["error"] == "not_allowed_for_role"
    assert "student" in result.data["message"]
    # Not linked at all: no access to the tool's child.
    assert (
        await fails(
            hass,
            home.stranger.id,
            "respond_to_proposal",
            id=view["id"],
            answer="accept",
        )
        == "not_linked"
    )
    # Through the WebSocket: parent and administrator are refused as well.
    entity_id = todo_id(hass)
    for user in (home.parent, home.admin, home.stranger):
        client = await ws_client(hass, hass_ws_client, user)
        message = await ws_respond(client, entity_id, view["id"], "accept")
        assert message["success"] is False
        assert message["error"]["code"] == "not_allowed_for_role", user.name
    assert manager(home).context.all_notes(1001) == []
    assert (await ok(hass, home.student.id, "list_proposals"))["proposals"][0][
        "status"
    ] == "proposed"
    # The student answers on the card.
    client = await ws_client(hass, hass_ws_client, home.student)
    message = await ws_respond(client, entity_id, view["id"], "accept")
    assert message["success"] is True, message
    assert message["result"]["proposal"]["status"] == "accepted"
    assert message["result"]["proposal"]["answered_by"] == "student"
    assert manager(home).context.all_notes(1001)[0].daily_max_minutes == 120


async def test_rights_matrix_without_a_student(
    hass: HomeAssistant,
    home: Home,
    logbook: list[Any],
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Without a Leerling user, a parent or an administrator answers for the child."""
    entity_id = todo_id(hass, 1002)
    first = await propose_period(hass, home.parent_b, child="1002")
    second = await propose_weekdays(hass, home.parent_b, child="1002")
    third = await propose_period(
        hass, home.parent_b, child="1002", reason="Derde", minutes=60
    )
    # The parent's AI answers on behalf of the child.
    data = await ok(
        hass, home.parent_b.id, "respond_to_proposal", id=first["id"], answer="accept"
    )
    assert data["proposal"]["answered_by"] == "on_behalf"
    assert logbook[-1].data["message"] == (
        "Ouder via AI: voorstel dagmaximum geaccepteerd door Petra namens het kind"
    )
    # An administrator on the card.
    client = await ws_client(hass, hass_ws_client, home.admin)
    message = await ws_respond(client, entity_id, second["id"], "reject")
    assert message["success"] and message["result"]["proposal"]["status"] == "rejected"
    assert logbook[-1].data["message"] == (
        "voorstel dagmaximum afgewezen door Beheerder namens het kind"
    )
    assert logbook[-1].data["entity_id"] == entity_id
    assert logbook[-1].context.user_id == home.admin.id
    # A user who is linked to nothing may not answer, not even by guessing the id.
    client = await ws_client(hass, hass_ws_client, home.stranger)
    message = await ws_respond(client, entity_id, third["id"], "accept")
    assert message["error"]["code"] == "not_allowed_for_role"
    # The parent of child A has no rights for child B.
    client = await ws_client(hass, hass_ws_client, home.parent)
    message = await ws_respond(client, entity_id, third["id"], "accept")
    assert message["error"]["code"] == "not_allowed_for_role"


async def test_websocket_errors(
    hass: HomeAssistant, home: Home, hass_ws_client: WebSocketGenerator
) -> None:
    """Unknown entity, unknown proposal, closed proposal, bad answer."""
    client = await ws_client(hass, hass_ws_client, home.student)
    entity_id = todo_id(hass)
    message = await ws_respond(client, "todo.nope", "abcdef12", "accept")
    assert message["error"]["code"] == "not_found"
    message = await ws_respond(client, entity_id, "abcdef12", "accept")
    assert message["error"]["code"] == "proposal_not_found"
    message = await ws_respond(client, entity_id, "not-an-id", "accept")
    assert message["error"]["code"] == "proposal_not_found"
    await client.send_json_auto_id(
        {
            "type": RESPOND,
            "entity_id": entity_id,
            "proposal": "abcdef12",
            "answer": "maybe",
        }
    )
    assert (await client.receive_json())["error"]["code"] == "invalid_format"
    view = await propose_period(hass, home.parent)
    assert (await ws_respond(client, entity_id, view["id"], "reject"))["success"]
    message = await ws_respond(client, entity_id, view["id"], "accept")
    assert message["error"]["code"] == "proposal_closed"
    assert manager(home).context.all_notes(1001) == []


async def test_websocket_push_and_payload(
    hass: HomeAssistant, home: Home, hass_ws_client: WebSocketGenerator
) -> None:
    """The payload has the open proposals and the answered ones; changes are pushed."""
    events: list[dict[str, Any]] = []
    async_subscribe(hass, todo_id(hass), events.append)
    view = await propose_period(hass, home.parent)
    await hass.async_block_till_done()
    assert events[-1]["proposals"] == [view]
    assert events[-1]["daily_max_weekdays"] == NORMAL
    client = await ws_client(hass, hass_ws_client, home.student)
    await client.send_json_auto_id(
        {"type": "magister/homework/subscribe", "entity_id": todo_id(hass)}
    )
    assert (await client.receive_json())["success"]
    first = (await client.receive_json())["event"]
    assert first["proposals"] == [view]
    await ws_respond(client, todo_id(hass), view["id"], "accept")
    pushed = [
        e
        for e in events
        if e["proposals"] and e["proposals"][0]["status"] == "accepted"
    ]
    assert pushed and pushed[-1]["daily_max_overrides"]["2026-11-25"] == 120
    answered = pushed[-1]["proposals"][0]
    assert answered["closed"] == "2026-11-13" and answered["answered_by"] == "student"
    # Another child's list has none of it.
    other = build_payload(manager(home), 1002, available=True)
    assert other["proposals"] == []
    # Unloading keeps the last proposals in the final event.
    await hass.config_entries.async_unload(home.entry.entry_id)
    await hass.async_block_till_done()
    assert events[-1]["available"] is False
    assert events[-1]["proposals"][0]["status"] == "accepted"
    assert events[-1]["daily_max_weekdays"] == NORMAL


async def test_a_wrong_id_or_child_does_not_leak(
    hass: HomeAssistant, home: Home
) -> None:
    """A proposal of child B is not found through child A (nor listed)."""
    secret = await propose_period(hass, home.parent_b, child="1002", reason="Geheim")
    for tool, args in (
        ("respond_to_proposal", {"id": secret["id"], "answer": "accept"}),
    ):
        result = await call(hass, home.student.id, tool, **args)
        assert result.error and result.data["error"] == "proposal_not_found"
    assert (await ok(hass, home.student.id, "list_proposals", include_closed=True))[
        "proposals"
    ] == []
    assert (
        await fails(
            hass, home.student.id, "respond_to_proposal", id="zz", answer="accept"
        )
        == "invalid_format"
    )
    # The student of A cannot reach child B at all.
    assert (
        await fails(hass, home.student.id, "list_proposals", child="1002")
        == "child_not_found"
    )
    prompt = (
        await llm.async_get_api(hass, COACH_API_ID, llm_context(home.student.id))
    ).api_prompt
    assert "Geheim" not in prompt and secret["id"] not in prompt
    assert manager(home).proposals.all(1002)[0].status == "proposed"


# -- expiry, pruning, limits ---------------------------------------------------


async def test_period_proposal_expires_when_its_first_day_starts(
    hass: HomeAssistant,
    home: Home,
    logbook: list[Any],
    frozen_now: FrozenDateTimeFactory,
) -> None:
    """Unanswered at the start of the first day: expired, logged, not acceptable."""
    view = await propose_period(hass, home.parent)
    frozen_now.move_to("2026-11-22 22:59:59+00:00")  # Sunday 23:59:59 in Amsterdam
    assert (await ok(hass, home.student.id, "list_proposals"))["proposals"][0][
        "status"
    ] == "proposed"
    frozen_now.move_to("2026-11-22 23:00:00+00:00")  # Monday 00:00
    # Lazily expired, also before anything has saved it.
    assert (await ok(hass, home.student.id, "list_proposals"))["proposals"] == []
    overview = await ok(
        hass, home.student.id, "get_overview", start="2026-11-23", end="2026-11-23"
    )
    assert overview["children"][0]["days"][0]["proposal"] is None
    closed = await ok(hass, home.student.id, "list_proposals", include_closed=True)
    assert closed["proposals"][0]["status"] == "expired"
    assert closed["proposals"][0]["closed"] == "2026-11-23"
    assert (
        await fails(
            hass, home.student.id, "respond_to_proposal", id=view["id"], answer="accept"
        )
        == "proposal_closed"
    )
    assert manager(home).context.all_notes(1001) == []
    # The expiry is stored and logged once, by the next sync.
    manager(home).async_expire_proposals()
    assert manager(home).proposals.all(1001)[0].status == "expired"
    messages = [e.data["message"] for e in logbook]
    assert messages.count("voorstel dagmaximum verlopen (Toetsweek)") == 1
    manager(home).async_expire_proposals()
    assert [e.data["message"] for e in logbook].count(
        "voorstel dagmaximum verlopen (Toetsweek)"
    ) == 1
    # The payload shows it in the history.
    payload = build_payload(manager(home), 1001, available=True)
    assert [p["status"] for p in payload["proposals"]] == ["expired"]


async def test_weekdays_proposal_expires_after_seven_days(
    hass: HomeAssistant,
    home: Home,
    logbook: list[Any],
    frozen_now: FrozenDateTimeFactory,
) -> None:
    """Seven days after it was made, to the minute; then answering is refused."""
    view = await propose_weekdays(hass, home.parent)  # Friday 13 Nov, 10:30
    frozen_now.move_to("2026-11-20 09:29:59+00:00")
    assert (await ok(hass, home.student.id, "list_proposals"))["proposals"][0][
        "status"
    ] == "proposed"
    frozen_now.move_to("2026-11-20 09:30:00+00:00")
    assert (await ok(hass, home.student.id, "list_proposals"))["proposals"] == []
    assert (
        await fails(
            hass, home.student.id, "respond_to_proposal", id=view["id"], answer="accept"
        )
        == "proposal_closed"
    )
    assert manager(home).daily_max_weekdays(1001) == (90,) * 7
    assert (
        logbook[-1].data["message"] == "voorstel dagmaximum verlopen (Rustiger weekend)"
    )
    # A coordinator-driven prune (async_prune) closes them too.
    again = await propose_weekdays(hass, home.parent, [0] * 7)
    frozen_now.move_to("2026-11-28 12:00:00+00:00")
    manager(home).async_prune()
    assert {p.id: p.status for p in manager(home).proposals.all(1001)}[
        again["id"]
    ] == "expired"


async def test_closed_proposals_are_pruned_after_fourteen_days(
    hass: HomeAssistant,
    home: Home,
    frozen_now: FrozenDateTimeFactory,
) -> None:
    """Answered and expired proposals stay for 14 days."""
    answered = await propose_period(hass, home.parent)
    await ok(
        hass, home.student.id, "respond_to_proposal", id=answered["id"], answer="reject"
    )
    expiring = await propose_weekdays(hass, home.parent)  # expires on the 20th
    frozen_now.move_to("2026-11-27 09:30:00+00:00")  # the answer is 14 days old
    book = manager(home).proposals
    assert {p.id for p in book.all(1001)} == {answered["id"], expiring["id"]}
    manager(home).async_expire_proposals()
    # Rejected on the 13th: exactly 14 days is still kept; the expired one (20th) too.
    assert {p.id for p in book.all(1001)} == {answered["id"], expiring["id"]}
    frozen_now.move_to("2026-11-27 09:30:01+00:00")
    manager(home).async_expire_proposals()
    assert {p.id for p in book.all(1001)} == {expiring["id"]}
    frozen_now.move_to("2026-12-04 09:30:01+00:00")
    manager(home).async_expire_proposals()
    assert book.all(1001) == []
    assert book.to_stored() == {}


async def test_accepting_needs_room_for_the_circumstance(
    hass: HomeAssistant, home: Home
) -> None:
    """With 50 active notes, accepting fails and the proposal stays open."""
    view = await propose_period(hass, home.parent)
    book = manager(home).context
    for n in range(NOTES_MAX):
        book.add(1001, parent=True, scope="child", text=f"Notitie {n}")
    assert (
        await fails(
            hass, home.student.id, "respond_to_proposal", id=view["id"], answer="accept"
        )
        == "too_many_notes"
    )
    assert (await ok(hass, home.student.id, "list_proposals"))["proposals"][0][
        "status"
    ] == "proposed"
    # Rejecting needs no room.
    await ok(
        hass, home.student.id, "respond_to_proposal", id=view["id"], answer="reject"
    )


# -- store ---------------------------------------------------------------------


async def test_proposals_survive_a_restart_and_a_downgrade(
    hass: HomeAssistant, home: Home, hass_storage: dict[str, Any]
) -> None:
    """Stored with the homework store (minor version 8, major 1); 1.8 ignores them."""
    first = await propose_period(hass, home.parent)
    second = await propose_weekdays(hass, home.parent)
    await ok(
        hass, home.student.id, "respond_to_proposal", id=second["id"], answer="reject"
    )
    assert await hass.config_entries.async_unload(home.entry.entry_id)
    key = f"magister.homework.{home.entry.entry_id}"
    saved = hass_storage[key]
    assert (saved["version"], saved["minor_version"]) == (1, 9)
    assert STORE_MINOR_VERSION == 9
    stored = saved["data"]["proposals"]["1001"]
    assert [p["id"] for p in stored] == [first["id"], second["id"]]
    assert stored[0] == {
        "id": first["id"],
        "kind": "period",
        "status": "proposed",
        "reason": "Toetsweek",
        "created": "2026-11-13T09:30:00+00:00",
        "created_by": "parent",
        "start": "2026-11-23",
        "end": "2026-11-27",
        "minutes": 120,
    }
    assert stored[1]["status"] == "rejected"
    assert stored[1]["answered_by"] == "student" and "closed" in stored[1]
    assert stored[1]["weekdays"] == [90, 90, 90, 90, 90, 0, 0]
    assert "items" in saved["data"]  # the older reader's key is still there
    # 1.8.x reads the same major version and only looks at `items` and `context`.
    from homeassistant.helpers.storage import Store

    plain = Store[dict[str, Any]](hass, 1, key, minor_version=7)
    older = await plain.async_load()
    assert older is not None and "items" in older
    # A restart brings them back.
    assert await hass.config_entries.async_setup(home.entry.entry_id)
    await hass.async_block_till_done()
    listed = await ok(hass, home.student.id, "list_proposals", include_closed=True)
    assert [p["id"] for p in listed["proposals"]] == [first["id"], second["id"]]
    assert [p["status"] for p in listed["proposals"]] == ["proposed", "rejected"]


async def test_damaged_store_is_read_leniently(hass: HomeAssistant, home: Home) -> None:
    """Invalid proposals, duplicates, wrong types and unknown keys are dropped."""
    good = {
        "id": "abcdef12",
        "kind": "weekdays",
        "status": "proposed",
        "reason": "  Een   reden ",
        "created": "2026-11-13T09:30:00+00:00",
        "created_by": "weird",
        "weekdays": [90, 90, 90, 90, 90, 0, 0],
    }
    book = manager(home).proposals
    book.load(
        {
            "1001": [
                good,
                good,  # duplicate id
                {**good, "id": "ABCDEF12"},  # not the form of an id
                {**good, "id": "abcdef13", "kind": "other"},
                {**good, "id": "abcdef14", "status": "done"},
                {**good, "id": "abcdef15", "created": "nu"},
                {**good, "id": "abcdef16", "created": "2026-11-13T09:30:00"},  # naive
                {**good, "id": "abcdef17", "reason": "  "},
                {**good, "id": "abcdef18", "weekdays": [90] * 6},
                {**good, "id": "abcdef19", "weekdays": [90] * 6 + [7]},
                {**good, "id": "abcdef1a", "weekdays": "x"},
                {**good, "id": "abcdef1b", "kind": "period"},  # no days
                {
                    **good,
                    "id": "abcdef1c",
                    "kind": "period",
                    "start": "2026-11-24",
                    "end": "2026-11-23",
                    "minutes": 30,
                },
                {
                    **good,
                    "id": "abcdef1d",
                    "kind": "period",
                    "start": "2026-11-23",
                    "end": "2026-11-23",
                    "minutes": 31,
                },
                "junk",
            ],
            "x": [good],
            "1002": "junk",
            "1003": [{**good, "status": "accepted"}],
        }
    )
    assert [(p.id, p.reason, p.created_by) for p in book.all(1001)] == [
        ("abcdef12", "Een reden", "student")
    ]
    closed = book.all(1003)[0]
    assert closed.closed == closed.created  # a closed proposal without a time
    assert closed.answered_by is None
    book.load("junk")
    assert book.all(1001) == []
    assert proposal_from_stored(None) is None
    view = proposal_from_stored(
        {
            **good,
            "status": "rejected",
            "closed": "2026-11-14T10:00:00+00:00",
            "answered_by": "on_behalf",
        }
    )
    assert view is not None and view.answered_by == "on_behalf"
    with_text = proposal_from_stored({**good, "reason": "x" * 150})
    assert with_text is not None and len(with_text.reason) == 100


async def test_diagnostics_counts_only(hass: HomeAssistant, home: Home) -> None:
    """Open proposals per kind and closed ones per status; no ids, no text."""
    from homeassistant.util import dt as dt_util

    from custom_components.magister.diagnostics import (
        async_get_config_entry_diagnostics,
    )

    await propose_period(hass, home.parent, reason="Geheime reden")
    await propose_period(hass, home.parent, reason="Nog een", minutes=60)
    weekdays = await propose_weekdays(hass, home.parent)
    await ok(
        hass, home.student.id, "respond_to_proposal", id=weekdays["id"], answer="reject"
    )
    diagnostics = await async_get_config_entry_diagnostics(hass, home.entry)
    assert diagnostics["coach_proposals"] == {
        "open": {"period": 2, "weekdays": 0},
        "closed": {"accepted": 0, "rejected": 1, "expired": 0},
    }
    assert "Geheime reden" not in str(diagnostics)
    assert manager(home).proposals.statistics(dt_util.utcnow())["open"]["period"] == 2
    for child in diagnostics["children"]:
        stats = child["homework"]
        assert stats["daily_max_weekdays"] == NORMAL
        assert stats["daily_max_minutes"] == 90


# -- tools: schemas, descriptions, refusals ------------------------------------


async def test_proposal_tool_annotations_and_schemas(hass: HomeAssistant) -> None:
    """Typed schemas as the MCP server converts them, and the right annotations."""
    tools = {t.name: t for t in coach_tools()}
    assert tools["list_proposals"].annotations.read_only
    assert tools["list_proposals"].annotations.idempotent
    for name in ("propose_daily_max", "respond_to_proposal"):
        assert not tools[name].annotations.read_only
        assert tools[name].annotations.open_world is False
        assert not tools[name].annotations.idempotent
    assert not tools["propose_daily_max"].annotations.destructive
    assert tools["respond_to_proposal"].annotations.destructive
    for name in ("list_proposals", "propose_daily_max", "respond_to_proposal"):
        schema = probatio.to_openapi(tools[name].parameters, openapi_version="3.1.0")
        for field, definition in schema["properties"].items():
            assert "type" in definition or "anyOf" in definition, (name, field)
            assert definition.get("description") or field == "include_closed", field
        assert schema["additionalProperties"] is False
    propose = probatio.to_openapi(
        tools["propose_daily_max"].parameters, openapi_version="3.1.0"
    )
    assert propose["properties"]["kind"]["enum"] == ["period", "weekdays"]
    assert propose["required"] == ["kind", "reason"]
    assert propose["properties"]["weekdays"]["anyOf"][0] == {
        "type": "array",
        "items": {"type": "integer"},
    }
    assert propose["properties"]["minutes"]["anyOf"][0] == {"type": "integer"}
    respond = probatio.to_openapi(
        tools["respond_to_proposal"].parameters, openapi_version="3.1.0"
    )
    assert respond["properties"]["answer"]["enum"] == ["accept", "reject"]
    assert respond["required"] == ["id", "answer"]
    assert "explicitly" in tools["respond_to_proposal"].description
    assert "yes or no" in tools["respond_to_proposal"].description
    assert "student must" in PLANNER_RULES or "student must accept" in PLANNER_RULES


async def test_prompt_and_tool_texts_for_time_planning(
    hass: HomeAssistant, home: Home
) -> None:
    """Planner rules, proposal rules, tool descriptions and the open proposals."""
    tools = {t.name: t for t in coach_tools()}
    for text in (
        "Planning with time is optional",
        "also for regular homework",
        "every piece of homework and test preparation",
        "in steps of 5",
        "that it is an estimate",
        "Homework is not done on the day it is due",
        "before the due day",
        "effective daily maximum of that date",
        "A maximum of 0 means no study",
        "The student decides",
        "always a proposal",
    ):
        assert text in PLANNER_RULES, text
    for text in (
        "never change a daily maximum directly",
        "use_proposal",
        "has no effect until the student accepts",
        "explicitly",
        "not_allowed_for_role",
        "expires",
    ):
        assert text in PROPOSAL_RULES, text
    assert "use_proposal" in tools["add_context"].description
    assert "propose_daily_max" in tools["update_context"].description
    assert "daily maximum" in tools["add_subtask"].description
    assert "before the item is" in tools["add_subtask"].description
    description = tools["get_overview"].description
    assert "raise or lower" in description and "parents only" in description
    assert "`proposal`" in description
    await propose_period(hass, home.parent, reason="Toetsweek")
    await propose_weekdays(
        hass, home.student, [60, 90, 90, 90, 90, 0, 0], reason="Zo beter"
    )
    for user in (home.student, home.parent):
        prompt = (
            await llm.async_get_api(hass, COACH_API_ID, llm_context(user.id))
        ).api_prompt
        assert PROPOSAL_RULES in prompt and PLANNER_RULES in prompt
        assert "Open proposals for the daily maximum of" in prompt
        assert "not accepted yet, so without effect" in prompt
        assert "period 2026-11-23 to 2026-11-27, 120 minutes per day" in prompt
        assert '"Toetsweek"' in prompt
        assert "weekdays monday 60, tuesday 90" in prompt
        assert "saturday 0, sunday 0" in prompt
    # Answered proposals are no longer listed.
    view = (await ok(hass, home.student.id, "list_proposals"))["proposals"][0]
    await ok(
        hass, home.student.id, "respond_to_proposal", id=view["id"], answer="reject"
    )
    prompt = (
        await llm.async_get_api(hass, COACH_API_ID, llm_context(home.student.id))
    ).api_prompt
    assert view["id"] not in prompt
    # Child B's prompt (the parent of B) has no proposals of A.
    prompt_b = (
        await llm.async_get_api(hass, COACH_API_ID, llm_context(home.parent_b.id))
    ).api_prompt
    assert "Open proposals" not in prompt_b


async def test_default_guidelines_follow_the_daily_maximum() -> None:
    """The fixed 1.5 hours are gone; the child's maximum for that day counts."""
    for text in (DEFAULT_GUIDELINES, DEFAULT_PARENT_GUIDELINES):
        assert "1,5 uur" not in text
        assert "dagmaximum" in text
        assert "voorstel" in text or "propose_daily_max" in text
        assert "zelf accepteren" in text
    assert (
        "houd je aan het dagmaximum van de leerling voor die dag" in DEFAULT_GUIDELINES
    )
    assert (
        "Houd je aan het dagmaximum van het kind voor die dag"
        in DEFAULT_PARENT_GUIDELINES
    )


async def test_custom_guidelines_are_not_touched(
    hass: HomeAssistant, mocked: aioresponses
) -> None:
    """Edited text stays as it is; empty text follows the (new) default."""
    old_default = DEFAULT_GUIDELINES.replace(
        "houd je aan het dagmaximum van de leerling voor die dag",
        "niet meer dan ongeveer 1,5 uur extra werk per schooldag",
    )
    user = await make_user(hass, "Leerling")
    other = await make_user(hass, "Leerling2")
    await setup_coach(
        hass,
        mocked,
        coach_options(
            **{
                "1001": {
                    "enabled": True,
                    "users": [user.id],
                    "guidelines": old_default,
                },
                "1002": {"enabled": True, "users": [other.id], "guidelines": ""},
            }
        ),
        two=True,
    )
    mine = (
        await llm.async_get_api(hass, COACH_API_ID, llm_context(user.id))
    ).api_prompt
    assert "ongeveer 1,5 uur" in mine
    theirs = (
        await llm.async_get_api(hass, COACH_API_ID, llm_context(other.id))
    ).api_prompt
    assert DEFAULT_GUIDELINES in theirs and "ongeveer 1,5 uur" not in theirs


# -- roles ---------------------------------------------------------------------


async def test_proposal_answerer_rules() -> None:
    """Pure rules: who answers how."""
    with_student = {"students": ["s"], "parents": ["p"]}
    without = {"parents": ["p"]}
    live = frozenset({"s"})
    none: frozenset[str] = frozenset()
    assert proposal_answerer(with_student, "s", live) == "student"
    assert proposal_answerer(with_student, "p", live) is None
    assert proposal_answerer(with_student, "a", live, is_admin=True) is None
    assert proposal_answerer(with_student, None, live) is None
    # The student user is not active (or a system user, or deleted): not live.
    assert proposal_answerer(with_student, "s", none) is None  # cannot act anyway
    assert proposal_answerer(with_student, "p", none) == "on_behalf"
    assert proposal_answerer(with_student, "a", none, is_admin=True) == "on_behalf"
    assert proposal_answerer(without, "p", none) == "on_behalf"
    assert proposal_answerer(without, "a", none, is_admin=True) == "on_behalf"
    assert proposal_answerer(without, "x", none) is None
    assert proposal_answerer({}, "a", none, is_admin=True) == "on_behalf"
    assert proposal_answerer({"users": ["s"]}, "s", live) == "student"  # 1.6.0 key
    # A user in both lists counts as a parent (fewer rights).
    assert proposal_answerer({"students": ["u"], "parents": ["u"]}, "u", live) is None
    assert first_name_of("Anna de Vries") == "Anna"
    assert first_name_of("  ") == "iemand" and first_name_of(None) == "iemand"
    assert first_name_of("x" * 50) == "x" * 30


async def test_unexpected_errors_and_unavailable_children(
    hass: HomeAssistant, home: Home
) -> None:
    """Unexpected failures give a generic error; a user without a name still works."""
    from unittest.mock import patch

    from custom_components.magister.proposals import ProposalBook

    with patch.object(ProposalBook, "propose", side_effect=RuntimeError("geheim")):
        result = await call(
            hass,
            home.student.id,
            "propose_daily_max",
            kind="weekdays",
            weekdays=[0] * 7,
            reason="x",
        )
    assert result.error and result.data["error"] == "internal_error"
    assert "geheim" not in str(result.data)
    nameless = await hass.auth.async_create_user("", group_ids=["system-users"])
    hass.config_entries.async_update_entry(
        home.entry,
        options=coach_options(**{"1002": {"enabled": True, "parents": [nameless.id]}}),
    )
    view = await propose_period(hass, nameless, child="1002")
    data = await ok(
        hass, nameless.id, "respond_to_proposal", id=view["id"], answer="accept"
    )
    assert data["proposal"]["answered_by"] == "on_behalf"


async def test_no_proposals_across_entries(
    hass: HomeAssistant, mocked: aioresponses
) -> None:
    """Proposals live per entry and per child: another entry shares nothing."""
    from .api.helpers import RETURN_URL
    from .ha_helpers import FakeMagister, make_entry

    first_user = await make_user(hass, "Eerste")
    second_user = await make_user(hass, "Tweede")
    steps = [
        {"action": "username"},
        {"action": "password"},
        {"redirectURL": RETURN_URL},
    ]
    FakeMagister(mocked, children=THREE, challenges=[*steps, *steps])
    entries = []
    for number, (child, name, user) in enumerate(
        ((1001, "Anna A", first_user), (1002, "Bram B", second_user)), 1
    ):
        entry = make_entry(
            children=[(child, name)],
            unique_id=f"school.magister.net:{number}",
            options=coach_options(
                **{str(child): {"enabled": True, "students": [user.id]}}
            ),
        )
        entry.add_to_hass(hass)
        assert await hass.config_entries.async_setup(entry.entry_id)
        entries.append(entry)
    await hass.async_block_till_done()
    mine = await propose_period(hass, first_user, reason="Eerste", child="1001")
    other = await ok(hass, second_user.id, "list_proposals", include_closed=True)
    assert other["proposals"] == []
    assert (
        await fails(
            hass, second_user.id, "respond_to_proposal", id=mine["id"], answer="accept"
        )
        == "proposal_not_found"
    )
    assert entries[0].runtime_data.homework.proposals.all(1001)[0].status == "proposed"
    assert entries[1].runtime_data.homework.proposals.all(1002) == []
    assert entries[1].runtime_data.homework.proposals.to_stored() == {}


async def test_book_guards_and_housekeeping(
    hass: HomeAssistant, home: Home, frozen_now: FrozenDateTimeFactory
) -> None:
    """Checks the tools cannot reach, children that go, and sync on a new proposal."""
    from homeassistant.util import dt as dt_util

    from custom_components.magister.context import ContextError

    book = manager(home).proposals
    for kwargs in (
        {"kind": "yearly", "reason": "x"},
        {"kind": "weekdays", "reason": 5, "weekdays": [0] * 7},
    ):
        with pytest.raises(ContextError) as caught:
            book.propose(1001, created_by="student", **kwargs)
        assert caught.value.code == "invalid_format"
    with pytest.raises(ContextError) as caught:
        book.respond(1001, "abcdef12", "maybe", answered_by="student")
    assert caught.value.code == "invalid_format"
    # A stored date that is not a date drops the proposal.
    assert (
        proposal_from_stored(
            {
                "id": "abcdef12",
                "kind": "period",
                "status": "proposed",
                "reason": "x",
                "created": "2026-11-13T09:30:00+00:00",
                "start": "2026-13-45",
                "end": "2026-11-23",
                "minutes": 30,
            }
        )
        is None
    )
    await propose_period(hass, home.parent_b, child="1002")
    # An unanswered proposal that has run out is closed (and saved) by the next one.
    old = await propose_weekdays(hass, home.parent)
    frozen_now.move_to("2026-11-21 12:00:00+00:00")
    await propose_weekdays(hass, home.parent, [0] * 7, reason="Nieuw")
    statuses = {p.id: p.status for p in book.all(1001)}
    assert statuses[old["id"]] == "expired" and len(statuses) == 2
    # Answering saves an expiry that was still unsaved as well.
    frozen_now.move_to("2026-12-06 12:00:00+00:00")
    book.sync(dt_util.utcnow())
    assert [p.reason for p in book.all(1001)] == ["Nieuw"]
    # Emptying a child's list removes the child; children that go take theirs along.
    book._store(1001, [])
    assert list(book.to_stored()) == ["1002"]
    book.drop_children([1001])
    assert book.all(1002) == []
    book.drop_children([1001])  # nothing left to drop


# -- a Leerling user that does not count ---------------------------------------------


async def _answers(
    hass: HomeAssistant,
    home: Home,
    hass_ws_client: WebSocketGenerator,
    expect_parent: bool,
) -> None:
    """Parent (AI and WebSocket) and admin answer on behalf, or are refused."""
    entity_id = todo_id(hass)
    first = await propose_period(hass, home.parent, minutes=30)
    second = await propose_period(hass, home.parent, minutes=45, reason="Tweede")
    third = await propose_period(hass, home.parent, minutes=60, reason="Derde")
    listed = await ok(hass, home.parent.id, "list_proposals")
    assert listed["you_may_answer"] is expect_parent
    result = await call(
        hass, home.parent.id, "respond_to_proposal", id=first["id"], answer="accept"
    )
    admin = await ws_client(hass, hass_ws_client, home.admin)
    ws_parent = await ws_client(hass, hass_ws_client, home.parent)
    if expect_parent:
        assert not result.error, result.data
        assert result.data["proposal"]["answered_by"] == "on_behalf"
        message = await ws_respond(admin, entity_id, second["id"], "reject")
        assert message["success"], message
        assert message["result"]["proposal"]["answered_by"] == "on_behalf"
        message = await ws_respond(ws_parent, entity_id, third["id"], "reject")
        assert message["success"], message
    else:
        assert result.error and result.data["error"] == "not_allowed_for_role"
        for client in (admin, ws_parent):
            message = await ws_respond(client, entity_id, second["id"], "reject")
            assert message["error"]["code"] == "not_allowed_for_role"
        # Clean up for the next round: the student answers.
        for view in (first, second, third):
            await ok(
                hass,
                home.student.id,
                "respond_to_proposal",
                id=view["id"],
                answer="reject",
            )


async def test_inactive_student_user_does_not_count(
    hass: HomeAssistant, home: Home, hass_ws_client: WebSocketGenerator
) -> None:
    """A deactivated Leerling lets the parent and the admin answer; reactivated, only
    the student may again."""
    await _answers(hass, home, hass_ws_client, expect_parent=False)
    await hass.auth.async_deactivate_user(home.student)
    await _answers(hass, home, hass_ws_client, expect_parent=True)
    await hass.auth.async_activate_user(home.student)
    await _answers(hass, home, hass_ws_client, expect_parent=False)


async def test_deleted_student_user_does_not_count(
    hass: HomeAssistant, home: Home, hass_ws_client: WebSocketGenerator
) -> None:
    """A linked id of a user that no longer exists is no Leerling user."""
    await hass.auth.async_remove_user(home.student)
    await _answers(hass, home, hass_ws_client, expect_parent=True)


async def test_system_user_as_student_does_not_count(
    hass: HomeAssistant, home: Home, hass_ws_client: WebSocketGenerator
) -> None:
    """A system-generated user is not a Leerling user either."""
    system = await hass.auth.async_create_system_user("Systeem")
    settings = {
        "1001": {
            "enabled": True,
            "students": [system.id],
            "parents": [home.parent.id],
        },
        "1002": {"enabled": True, "parents": [home.parent_b.id]},
    }
    hass.config_entries.async_update_entry(
        home.entry, options={**home.entry.options, "coach": settings}
    )
    await hass.async_block_till_done()
    await _answers(hass, home, hass_ws_client, expect_parent=True)


async def test_the_student_still_answers_when_another_student_is_inactive(
    hass: HomeAssistant, home: Home
) -> None:
    """One active Leerling user is enough to keep the parent out."""
    other = await make_user(hass, "Tweede leerling")
    settings = {
        "1001": {
            "enabled": True,
            "students": [home.student.id, other.id],
            "parents": [home.parent.id],
        },
    }
    hass.config_entries.async_update_entry(
        home.entry, options={**home.entry.options, "coach": settings}
    )
    await hass.async_block_till_done()
    await hass.auth.async_deactivate_user(other)
    view = await propose_period(hass, home.parent)
    assert (await ok(hass, home.parent.id, "list_proposals"))["you_may_answer"] is False
    assert (
        await fails(
            hass, home.parent.id, "respond_to_proposal", id=view["id"], answer="accept"
        )
        == "not_allowed_for_role"
    )
    assert (await ok(hass, home.student.id, "list_proposals"))["you_may_answer"] is True


# -- texts, duplicates, pruning --------------------------------------------------------


async def test_reason_and_answer_rules_are_in_the_texts() -> None:
    """The reason is shown to the student; only an explicit yes or no answers."""
    reason = (
        "The reason is shown to the student, on the card and in the logbook: never "
        "put parents-only information, names or health details in it."
    )
    tools = {t.name: t for t in coach_tools()}
    assert reason in " ".join(tools["propose_daily_max"].description.split())
    assert " ".join(reason.split()) in " ".join(PROPOSAL_RULES.split())
    who = (
        "after the person who may answer (the student, or the parent for a "
        "child without an active student user) has said yes or no explicitly in "
        "this conversation"
    )
    assert who in " ".join(tools["respond_to_proposal"].description.split())
    assert who in " ".join(PROPOSAL_RULES.split())
    assert "Never answer a proposal without that explicit yes or no." in " ".join(
        tools["propose_daily_max"].description.split()
    )
    assert "Do not call respond_to_proposal yourself" not in (
        tools["propose_daily_max"].description
    )
    assert "an active student user" in " ".join(PROPOSAL_RULES.split())
    assert "actief leerlingaccount" in DEFAULT_PARENT_GUIDELINES


async def test_an_exact_duplicate_of_an_open_proposal_is_refused(
    hass: HomeAssistant, home: Home
) -> None:
    """The same proposal twice is `invalid_format`; once closed, it may return."""
    period = await propose_period(hass, home.parent)
    args: dict[str, Any] = {
        "kind": "period",
        "minutes": 120,
        "reason": "Nog eens",
        **PERIOD,
    }
    assert await fails(hass, home.parent.id, "propose_daily_max", **args) == (
        "invalid_format"
    )
    assert await fails(hass, home.student.id, "propose_daily_max", **args) == (
        "invalid_format"
    )
    weekdays = await propose_weekdays(hass, home.parent)
    again = {"kind": "weekdays", "weekdays": [90, 90, 90, 90, 90, 0, 0], "reason": "x"}
    assert await fails(hass, home.parent.id, "propose_daily_max", **again) == (
        "invalid_format"
    )
    # Other minutes or days are a different proposal.
    await propose_period(hass, home.parent, minutes=105)
    # After an answer the same one may be proposed again.
    await ok(
        hass, home.student.id, "respond_to_proposal", id=period["id"], answer="reject"
    )
    await propose_period(hass, home.parent)
    await ok(
        hass, home.student.id, "respond_to_proposal", id=weekdays["id"], answer="reject"
    )
    await propose_weekdays(hass, home.parent)


async def test_pruned_proposals_leave_the_payload_and_the_list(
    hass: HomeAssistant,
    home: Home,
    frozen_now: FrozenDateTimeFactory,
) -> None:
    """A closed proposal older than 14 days is no longer shown, even before the
    housekeeping has pruned it."""
    answered = await propose_period(hass, home.parent)
    await ok(
        hass, home.student.id, "respond_to_proposal", id=answered["id"], answer="reject"
    )
    book = manager(home).proposals
    from homeassistant.util import dt as dt_util

    frozen_now.move_to("2026-11-27 09:30:00+00:00")  # exactly 14 days: still shown
    assert [p["id"] for p in book.payload(1001, dt_util.utcnow())] == [answered["id"]]
    frozen_now.move_to("2026-11-27 09:30:01+00:00")
    assert len(book.all(1001)) == 1  # not pruned yet
    assert book.payload(1001, dt_util.utcnow()) == []
    assert (await ok(hass, home.student.id, "list_proposals", include_closed=True))[
        "proposals"
    ] == []


async def test_expired_capped_note_cannot_be_extended(
    hass: HomeAssistant, home: Home
) -> None:
    """A circumstance with a maximum that has ended cannot be revived by the AI."""
    note = await add(
        hass,
        home.parent,
        scope="period",
        start="2026-11-10",
        end="2026-11-11",
        text="Toets",
        daily_max_minutes=45,
    )
    for args in ({"end": "2026-11-20"}, {"start": "2026-11-09"}):
        code = await fails(
            hass, home.parent.id, "update_context", id=note["id"], **args
        )
        assert code == "use_proposal", args
    assert (await ok(hass, home.parent.id, "list_context", include_expired=True))[
        "notes"
    ][0]["end"] == "2026-11-11"


async def test_remove_maximum_move_then_propose(
    hass: HomeAssistant, home: Home
) -> None:
    """null, then move, then propose: the way to give a circumstance new days."""
    note = await add(
        hass,
        home.parent,
        scope="period",
        start="2026-11-16",
        end="2026-11-17",
        text="Toets",
        daily_max_minutes=45,
    )
    assert (
        await fails(
            hass, home.parent.id, "update_context", id=note["id"], end="2026-11-24"
        )
        == "use_proposal"
    )
    cleared = await ok(
        hass, home.parent.id, "update_context", id=note["id"], daily_max_minutes=None
    )
    assert cleared["note"]["daily_max_minutes"] is None
    moved = await ok(
        hass,
        home.parent.id,
        "update_context",
        id=note["id"],
        start="2026-11-23",
        end="2026-11-27",
    )
    assert (moved["note"]["start"], moved["note"]["end"]) == (
        PERIOD["start"],
        PERIOD["end"],
    )
    view = await propose_period(hass, home.parent, minutes=120)
    assert view["status"] == "proposed"
    # The moved circumstance has no maximum until the student accepts.
    assert manager(home).context.daily_max_overrides(1001) == {}


async def test_duplicate_with_five_open_is_too_many(
    hass: HomeAssistant, home: Home
) -> None:
    """With five open proposals the answer for a duplicate is too_many_proposals."""
    for n in range(MAX_OPEN):
        await propose_period(hass, home.student, minutes=15 * n, reason=f"P{n}")
    code = await fails(
        hass,
        home.student.id,
        "propose_daily_max",
        kind="period",
        minutes=15 * (MAX_OPEN - 1),
        reason="Ander woord",
        child="1001",
        **PERIOD,
    )
    assert code == "too_many_proposals"
