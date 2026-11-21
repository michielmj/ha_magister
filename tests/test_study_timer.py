"""M15 phase A: the study timer (engine, rights, settings, notifications, API)."""

from __future__ import annotations

from datetime import timedelta
from typing import Any

import probatio
import pytest
from aioresponses import aioresponses
from freezegun.api import FrozenDateTimeFactory
from homeassistant.auth.const import GROUP_ID_ADMIN
from homeassistant.components import persistent_notification
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import Context, HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_capture_events,
    async_fire_time_changed,
    async_mock_service,
)
from pytest_homeassistant_custom_component.typing import WebSocketGenerator

from custom_components.magister.api.homework import subtask_uid
from custom_components.magister.const import CONF_STUDY_TIMER
from custom_components.magister.diagnostics import async_get_config_entry_diagnostics
from custom_components.magister.homework import async_subscribe
from custom_components.magister.timer import (
    ACTION_PREFIX,
    TimerEngine,
    notify_services,
    progress_step,
)

from .ha_helpers import NOW
from .test_coach import HOMEWORK, PROEFWERK, coach_options, make_user, ok, setup_coach
from .test_coach import fails as coach_fails

HOST = "school.magister.net"
TIMER = "magister/homework/timer"
SETTINGS = "magister/homework/timer_settings"
TARGET = "mobile_app_iphone_x"
OTHER = "mobile_app_other_phone"
EVENT_ACTION = "mobile_app_notification_action"


@pytest.fixture(autouse=True)
async def frozen_now(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> FrozenDateTimeFactory:
    """Friday 13 November 2026, 10:30 in Amsterdam."""
    await hass.config.async_set_time_zone("Europe/Amsterdam")
    freezer.move_to(NOW)
    return freezer


class Home:
    """Anna (1001): student + parent + target; Bram (1002): a parent, no student."""

    entry: MockConfigEntry
    student: Any
    parent: Any
    parent_b: Any
    admin: Any
    stranger: Any
    notify: list[Any]
    other: list[Any]


@pytest.fixture
async def home(hass: HomeAssistant, mocked: aioresponses) -> Home:
    """Two children with the users of the rights matrix and a notify target."""
    result = Home()
    await make_user(hass, "Eigenaar")
    result.student = await make_user(hass, "Sanne de Vries")
    result.parent = await make_user(hass, "Peter de Vries")
    result.parent_b = await make_user(hass, "Petra Jansen")
    result.admin = await hass.auth.async_create_user(
        "Beheerder Bos", group_ids=[GROUP_ID_ADMIN]
    )
    result.stranger = await make_user(hass, "Vreemde")
    result.notify = async_mock_service(hass, "notify", TARGET)
    result.other = async_mock_service(hass, "notify", OTHER)
    options = {
        **coach_options(
            **{
                "1001": {
                    "enabled": True,
                    "students": [result.student.id],
                    "parents": [result.parent.id],
                },
                "1002": {"enabled": True, "parents": [result.parent_b.id]},
            }
        ),
        CONF_STUDY_TIMER: {"1001": [TARGET]},
    }
    result.entry = await setup_coach(hass, mocked, options, two=True)
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


def make_sub(
    home: Home,
    minutes: int | None = 30,
    *,
    child: int = 1001,
    appointment: str = HOMEWORK,
    title: str = "Opgave 3",
) -> str:
    """A subtask (with an estimated time) and its uid."""
    mgr = manager(home)
    item = mgr.add_subtask(
        child, f"{HOST}:{child}:{appointment}", title, None, minutes=minutes
    )
    return subtask_uid(item.uid, item.subtasks[-1].id)


async def client_of(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator, user: Any
) -> Any:
    """A WebSocket connection of this user."""
    refresh = await hass.auth.async_create_refresh_token(
        user, "https://example.com/app"
    )
    return await hass_ws_client(hass, hass.auth.async_create_access_token(refresh))


async def send(client: Any, command: str, entity_id: str, **fields: Any) -> Any:
    """Send a command and return the answer message."""
    await client.send_json_auto_id({"type": command, "entity_id": entity_id, **fields})
    return await client.receive_json()


async def timer(client: Any, entity_id: str, action: str, **fields: Any) -> Any:
    """A timer command."""
    return await send(client, TIMER, entity_id, action=action, **fields)


async def tick(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, **delta: float
) -> None:
    """Let time pass and fire what is due."""
    freezer.tick(timedelta(**delta))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()


def notifications(hass: HomeAssistant) -> dict[str, Any]:
    """The persistent notifications."""
    return dict(persistent_notification._async_get_or_create_notifications(hass))


@pytest.fixture
def logbook(hass: HomeAssistant) -> list[Any]:
    """The logbook entries that are written."""
    return async_capture_events(hass, "logbook_entry")


def messages(logbook: list[Any]) -> list[str]:
    """The logbook messages."""
    return [e.data["message"] for e in logbook]


async def act(home: Home, action: str, **fields: Any) -> None:
    """A timer action of the student."""
    await manager(home).async_timer_action(
        1001, action, user_id=home.student.id, **fields
    )


async def set_settings(home: Home, *, prewarn: Any = None, extra: Any = None) -> None:
    """Set the settings of Anna as the student would."""
    await manager(home).async_set_timer_settings(
        1001, user_id=home.student.id, prewarn=prewarn, extra=extra
    )


# -- the lifecycle ---------------------------------------------------------------


async def test_lifecycle(
    hass: HomeAssistant,
    home: Home,
    hass_ws_client: WebSocketGenerator,
    freezer: FrozenDateTimeFactory,
    logbook: list[Any],
) -> None:
    """Start, pause, resume, run out, extend, done; stop with progress."""
    sub = make_sub(home)
    await set_settings(home, extra=5)
    client = await client_of(hass, hass_ws_client, home.student)
    entity_id = todo_id(hass)
    finished = async_capture_events(hass, "magister_study_timer_finished")

    start = await timer(client, entity_id, "start", subtask=sub)
    assert start["success"]
    state = start["result"]["timer"]
    assert state["state"] == "running" and state["minutes"] == 30
    assert state["ends_at"] == "2026-11-13T10:00:00+00:00"
    assert state["started_at"] == "2026-11-13T09:30:00+00:00"
    assert state["subtask"] == sub and state["title"] == "Opgave 3"
    assert state["subject"] and state["due"] == "2026-11-16" and "label" in state
    assert "nonce" not in state and "remaining" not in state

    await tick(hass, freezer, minutes=10)
    paused = (await timer(client, entity_id, "pause"))["result"]["timer"]
    assert paused["state"] == "paused" and paused["remaining"] == 20 * 60
    assert "ends_at" not in paused
    # Paused time does not run.
    await tick(hass, freezer, minutes=60)
    assert not finished
    resumed = (await timer(client, entity_id, "resume"))["result"]["timer"]
    assert resumed["ends_at"] == "2026-11-13T11:00:00+00:00"

    assert (await timer(client, entity_id, "extend"))["error"]["code"] == (
        "timer_not_finished"
    )
    await tick(hass, freezer, minutes=20)
    assert [e.data for e in finished] == [{"child": 1001, "subtask": sub}]
    assert manager(home).timers.timer(1001)["state"] == "finished"
    # Extend: it runs again for the extra minutes, and can be repeated.
    again = (await timer(client, entity_id, "extend"))["result"]["timer"]
    assert again["state"] == "running" and again["minutes"] == 5
    await tick(hass, freezer, minutes=5)
    assert len(finished) == 2
    assert (await timer(client, entity_id, "extend"))["success"]
    done = await timer(client, entity_id, "done")
    assert done["success"] and done["result"]["timer"] is None
    assert manager(home).progress(sub) == 100

    # Stop with progress: sets the progress and stops in one call.
    sub2 = make_sub(home, 15, title="Opgave 4")
    assert (await timer(client, entity_id, "start", subtask=sub2))["success"]
    stop = await timer(client, entity_id, "stop", progress=50)
    assert stop["success"] and stop["result"]["timer"] is None
    assert manager(home).progress(sub2) == 50
    assert manager(home).timers.timer(1001) is None
    # Stop without progress leaves the progress as it is.
    assert (await timer(client, entity_id, "start", subtask=sub2))["success"]
    assert (await timer(client, entity_id, "stop"))["success"]
    assert manager(home).progress(sub2) == 50

    log = messages(logbook)
    for text in (
        "Studietimer gestart (Opgave 3)",
        "Studietimer gepauzeerd (Opgave 3)",
        "Studietimer hervat (Opgave 3)",
        "Studietimer afgelopen (Opgave 3)",
        "Studietimer verlengd met 5 min (Opgave 3)",
        "deelstap afgerond via studietimer (Opgave 3)",
        "Studietimer gestopt (Opgave 4)",
        "voortgang 50% bij stoppen (Opgave 4)",
    ):
        assert text in log


async def test_errors(
    hass: HomeAssistant, home: Home, hass_ws_client: WebSocketGenerator
) -> None:
    """The error codes of the timer commands."""
    sub = make_sub(home)
    no_minutes = make_sub(home, None, title="Zonder tijd")
    other_child = make_sub(home, 30, child=1002)
    client = await client_of(hass, hass_ws_client, home.student)
    entity_id = todo_id(hass)

    async def code(action: str, **fields: Any) -> str:
        answer = await timer(client, entity_id, action, **fields)
        assert not answer["success"]
        return str(answer["error"]["code"])

    for action in ("pause", "resume", "stop", "extend", "done"):
        assert await code(action) == "no_timer"
    assert await code("start") == "invalid_format"  # no subtask
    assert await code("start", subtask="nonsense") == "subtask_not_found"
    assert await code("start", subtask=other_child) == "subtask_not_found"
    assert await code("start", subtask=no_minutes) == "no_minutes"
    assert await code("start", subtask=sub, progress=33) == "invalid_format"
    assert await code("bogus") == "invalid_format"

    assert (await timer(client, entity_id, "start", subtask=sub))["success"]
    assert await code("start", subtask=sub) == "timer_running"
    assert await code("resume") == "timer_wrong_state"
    assert await code("extend") == "timer_not_finished"
    assert (await timer(client, entity_id, "pause"))["success"]
    assert await code("pause") == "timer_wrong_state"
    assert await code("extend") == "timer_not_finished"
    assert await code("start", subtask=sub) == "timer_running"  # paused counts
    # replace: stops the old one and starts the new one.
    sub2 = make_sub(home, 15, title="Opgave 4")
    replaced = await timer(client, entity_id, "start", subtask=sub2, replace=True)
    assert replaced["result"]["timer"]["subtask"] == sub2
    # Extend on a finished timer needs extra minutes.
    manager(home).timers._timers[1001]["state"] = "finished"
    assert await code("extend") == "extra_not_set"


async def test_start_replaces_a_finished_timer_without_replace(
    hass: HomeAssistant,
    home: Home,
    hass_ws_client: WebSocketGenerator,
    freezer: FrozenDateTimeFactory,
) -> None:
    """A timer that ran out is not "running": the next start needs no replace."""
    sub, sub2 = make_sub(home, 5), make_sub(home, 10, title="Opgave 4")
    client = await client_of(hass, hass_ws_client, home.student)
    await timer(client, todo_id(hass), "start", subtask=sub)
    await tick(hass, freezer, minutes=5)
    assert notifications(hass)
    answer = await timer(client, todo_id(hass), "start", subtask=sub2)
    assert answer["result"]["timer"]["subtask"] == sub2
    assert not notifications(hass)


# -- the pre-warning ---------------------------------------------------------------


async def test_prewarning(
    hass: HomeAssistant,
    home: Home,
    hass_ws_client: WebSocketGenerator,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Sent x minutes before the end, without buttons; skipped for a short timer."""
    sub = make_sub(home, 10)
    await set_settings(home, prewarn=2, extra=5)
    client = await client_of(hass, hass_ws_client, home.student)
    await timer(client, todo_id(hass), "start", subtask=sub)
    await tick(hass, freezer, minutes=7)
    assert home.notify == []
    # A pause before the pre-warning moves it with the end.
    await timer(client, todo_id(hass), "pause")
    await tick(hass, freezer, minutes=30)
    await timer(client, todo_id(hass), "resume")
    await tick(hass, freezer, minutes=1)  # 2 minutes left: the pre-warning is due
    assert len(home.notify) == 1
    call = home.notify[0]
    assert call.data["message"] == "Nog 2 minuten: Opgave 3 (" + _subject(home) + ")"
    data = call.data["data"]
    assert "actions" not in data  # the pre-warning has no buttons
    assert data["tag"] == "magister_study_timer_1001"
    assert data["push"] == {"interruption-level": "time-sensitive"}
    assert home.other == []
    # The end, an extension and the end again: the pre-warning does not repeat.
    await tick(hass, freezer, minutes=2)
    assert "Tijd is om" in home.notify[1].data["message"]
    await manager(home).async_timer_action(1001, "extend", user_id=home.student.id)
    await tick(hass, freezer, minutes=5)
    assert [c.data["message"].split(":")[0] for c in home.notify] == [
        "Nog 2 minuten",
        "Tijd is om",
        "Tijd is om",
    ]


def _subject(home: Home) -> str:
    return str(manager(home).timers.payload(1001)["subject"])


async def test_prewarning_skipped_when_the_timer_is_shorter(
    hass: HomeAssistant,
    home: Home,
    freezer: FrozenDateTimeFactory,
) -> None:
    """A short timer never warns; one minute reads as singular."""
    sub = make_sub(home, 5)
    await set_settings(home, prewarn=10)
    await act(home, "start", subtask=sub)
    await tick(hass, freezer, minutes=2)
    assert home.notify == []
    await tick(hass, freezer, minutes=3)
    assert [c.data["message"].split(":")[0] for c in home.notify] == ["Tijd is om"]
    await act(home, "stop")
    # With one minute the text is singular.
    await set_settings(home, prewarn=1)
    await act(home, "start", subtask=sub)
    await tick(hass, freezer, minutes=4)
    assert home.notify[-1].data["message"].startswith("Nog 1 minuut: ")
    # Changing the setting while it runs moves the pre-warning; off cancels it.
    await act(home, "stop")
    await set_settings(home, prewarn=3)
    await act(home, "start", subtask=sub)
    await set_settings(home, prewarn=4)
    await tick(hass, freezer, minutes=1, seconds=1)
    assert home.notify[-1].data["message"].startswith("Nog 4 minuten: ")
    count = len(home.notify)
    await set_settings(home, prewarn=None)
    await tick(hass, freezer, minutes=5)
    assert [c.data["message"].split(":")[0] for c in home.notify[count:]] == [
        "Tijd is om"
    ]


# -- notifications -----------------------------------------------------------------


async def test_end_notification_payload(
    hass: HomeAssistant,
    home: Home,
    hass_ws_client: WebSocketGenerator,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Text, buttons, tag, interruption level; persistent notification; targets."""
    sub = make_sub(home, 5)
    await set_settings(home, extra=10)
    client = await client_of(hass, hass_ws_client, home.student)
    await timer(client, todo_id(hass), "start", subtask=sub)
    nonce = manager(home).timers._timers[1001]["nonce"]
    await tick(hass, freezer, minutes=5)
    assert len(home.notify) == 1 and home.other == []
    call = home.notify[0]
    subject = _subject(home)
    assert call.data["message"] == f"Tijd is om: Opgave 3 ({subject})"
    data = call.data["data"]
    assert data["tag"] == "magister_study_timer_1001"
    assert data["push"] == {"interruption-level": "time-sensitive"}
    rest = sub.split(":", 2)[2]
    base = f"{ACTION_PREFIX}|%s|{home.entry.entry_id}|1001|{rest}|{nonce}"
    assert data["actions"] == [
        {"action": base % "done", "title": "Klaar"},
        {"action": base % "extend", "title": "+10 min"},
        {"action": base % "stop", "title": "Nog niet"},
    ]
    # No school name in the buttons, no teacher data in the texts.
    assert HOST not in str(call.data)
    shown = notifications(hass)
    assert len(shown) == 1
    assert next(iter(shown.values()))["message"] == call.data["message"]
    # Without extra minutes there is no +x button.
    await set_settings(home)
    await manager(home).async_set_timer_settings(
        1001, user_id=home.student.id, extra=None
    )
    await timer(client, todo_id(hass), "start", subtask=sub, replace=True)
    await tick(hass, freezer, minutes=5)
    titles = [a["title"] for a in home.notify[-1].data["data"]["actions"]]
    assert titles == ["Klaar", "Nog niet"]
    # Child 2 has no target: nobody is notified, but the timer finishes.
    sub_b = make_sub(home, 5, child=1002)
    count = len(home.notify)
    await manager(home).async_timer_action(
        1002, "start", user_id=home.parent_b.id, subtask=sub_b
    )
    await tick(hass, freezer, minutes=5)
    assert len(home.notify) == count and home.other == []
    assert len(notifications(hass)) == 2


async def test_targets_that_do_not_work_are_skipped(
    hass: HomeAssistant,
    home: Home,
    freezer: FrozenDateTimeFactory,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A missing or failing notify service never breaks the timer."""
    hass.config_entries.async_update_entry(
        home.entry,
        options={
            **home.entry.options,
            CONF_STUDY_TIMER: {"1001": ["mobile_app_gone", "mobile_app_bad", TARGET]},
        },
    )

    async def bad(call: Any) -> None:
        raise HomeAssistantError("boom")

    hass.services.async_register("notify", "mobile_app_bad", bad)
    sub = make_sub(home, 5)
    await manager(home).async_timer_action(
        1001, "start", user_id=home.student.id, subtask=sub
    )
    await tick(hass, freezer, minutes=5)
    assert len(home.notify) == 1  # the good one still got it
    assert "HomeAssistantError" in caplog.text
    assert manager(home).timers.timer(1001)["state"] == "finished"
    # A damaged option is ignored.
    hass.config_entries.async_update_entry(
        home.entry, options={**home.entry.options, CONF_STUDY_TIMER: {"1001": 5}}
    )
    assert manager(home).timers._targets(1001) == []


async def test_persistent_notification_is_dismissed(
    hass: HomeAssistant,
    home: Home,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Removed on restart, extend, stop and done; the phone notification is cleared."""
    mgr = manager(home)
    user = home.student.id
    await set_settings(home, extra=5)
    sub = make_sub(home, 5)

    async def act(action: str, **kw: Any) -> None:
        await mgr.async_timer_action(1001, action, user_id=user, **kw)

    for ending in ("start", "extend", "stop", "done"):
        await act("start", subtask=sub, replace=True)
        await tick(hass, freezer, minutes=5)
        assert len(notifications(hass)) == 1
        home.notify.clear()
        if ending == "start":
            await act("start", subtask=sub, replace=True)
        else:
            await act(ending)
        assert notifications(hass) == {}
        if ending in ("stop", "done"):
            assert home.notify[-1].data == {
                "message": "clear_notification",
                "data": {"tag": "magister_study_timer_1001"},
            }
        await act("stop") if mgr.timers.timer(1001) else None
        mgr.set_progress(sub, 0)


# -- the buttons -------------------------------------------------------------------


async def finished_buttons(
    hass: HomeAssistant, home: Home, freezer: FrozenDateTimeFactory
) -> tuple[str, dict[str, str]]:
    """Run a timer out and return its subtask and the button ids by verb."""
    await set_settings(home, extra=5)
    sub = make_sub(home, 5)
    await manager(home).async_timer_action(
        1001, "start", user_id=home.student.id, subtask=sub
    )
    await tick(hass, freezer, minutes=5)
    actions = home.notify[-1].data["data"]["actions"]
    return sub, {a["action"].split("|")[1]: a["action"] for a in actions}


def press(hass: HomeAssistant, action: Any, user_id: str | None = None) -> None:
    """The companion app reports a button press."""
    hass.bus.async_fire(
        EVENT_ACTION, {"action": action}, context=Context(user_id=user_id)
    )


async def test_buttons(
    hass: HomeAssistant,
    home: Home,
    freezer: FrozenDateTimeFactory,
    logbook: list[Any],
) -> None:
    """Klaar, +x min and Nog niet act on the timer."""
    sub, ids = await finished_buttons(hass, home, freezer)
    assert set(ids) == {"done", "extend", "stop"}
    press(hass, ids["extend"], home.student.id)
    await hass.async_block_till_done()
    assert manager(home).timers.timer(1001)["state"] == "running"
    await tick(hass, freezer, minutes=5)
    press(hass, ids["stop"], home.student.id)  # Nog niet: no progress change
    await hass.async_block_till_done()
    assert manager(home).timers.timer(1001) is None
    assert manager(home).progress(sub) == 0
    # A button of the stopped timer does nothing any more.
    press(hass, ids["done"], home.student.id)
    await hass.async_block_till_done()
    assert manager(home).progress(sub) == 0

    # Klaar, from a new timer on the same subtask: the old buttons are stale.
    await manager(home).async_timer_action(
        1001, "start", user_id=home.student.id, subtask=sub
    )
    press(hass, ids["done"], home.student.id)
    await hass.async_block_till_done()
    assert manager(home).timers.timer(1001)["state"] == "running"
    assert manager(home).progress(sub) == 0
    await tick(hass, freezer, minutes=5)
    fresh = {
        a["action"].split("|")[1]: a["action"]
        for a in home.notify[-1].data["data"]["actions"]
    }
    assert fresh["done"] != ids["done"]
    press(hass, fresh["done"], home.student.id)
    await hass.async_block_till_done()
    assert manager(home).progress(sub) == 100
    assert manager(home).timers.timer(1001) is None
    assert "deelstap afgerond via melding (Opgave 3)" in messages(logbook)


async def test_button_rights_and_garbage(
    hass: HomeAssistant, home: Home, freezer: FrozenDateTimeFactory
) -> None:
    """Rights of the user in the event; no user: nonce and target are the proof."""
    sub, ids = await finished_buttons(hass, home, freezer)
    done = ids["done"]
    for user_id in (home.parent.id, home.admin.id, home.stranger.id, "unknown"):
        press(hass, done, user_id)
    await hass.async_block_till_done()
    assert manager(home).timers.timer(1001) is not None
    # Garbage and ids of other entries, children, subtasks or nonces are ignored.
    prefix, verb, entry_id, child, rest, nonce = done.split("|")
    for bad in (
        None,
        5,
        "other",
        "MAGISTER_TIMER|done|x",
        f"{prefix}|bogus|{entry_id}|{child}|{rest}|{nonce}",
        f"{prefix}|{verb}|other|{child}|{rest}|{nonce}",
        f"{prefix}|{verb}|{entry_id}|x|{rest}|{nonce}",
        f"{prefix}|{verb}|{entry_id}|1002|{rest}|{nonce}",
        f"{prefix}|{verb}|{entry_id}|{child}|100065:sub:zzzz|{nonce}",
        f"{prefix}|{verb}|{entry_id}|{child}|{rest}|{'0' * 16}",
    ):
        press(hass, bad, home.student.id)
    await hass.async_block_till_done()
    assert manager(home).timers.timer(1001)["state"] == "finished"
    assert manager(home).progress(sub) == 0
    # No user in the event: the nonce is the proof.
    press(hass, done)
    await hass.async_block_till_done()
    assert manager(home).progress(sub) == 100
    # A button that cannot be carried out is ignored (extend without extra minutes).
    await set_settings(home)
    await manager(home).async_set_timer_settings(
        1001, user_id=home.student.id, extra=None
    )
    sub2 = make_sub(home, 5, title="Opgave 4")
    await manager(home).async_timer_action(
        1001, "start", user_id=home.student.id, subtask=sub2
    )
    await tick(hass, freezer, minutes=5)
    nonce2 = manager(home).timers._timers[1001]["nonce"]
    rest2 = sub2.split(":", 2)[2]
    press(hass, f"{prefix}|extend|{entry_id}|{child}|{rest2}|{nonce2}")
    await hass.async_block_till_done()
    assert manager(home).timers.timer(1001)["state"] == "finished"


async def test_parent_presses_for_a_child_without_student(
    hass: HomeAssistant, home: Home, freezer: FrozenDateTimeFactory
) -> None:
    """The phone of a parent works for a child that has no active student user."""
    hass.config_entries.async_update_entry(
        home.entry,
        options={**home.entry.options, CONF_STUDY_TIMER: {"1002": [TARGET]}},
    )
    sub = make_sub(home, 5, child=1002)
    await manager(home).async_timer_action(
        1002, "start", user_id=home.parent_b.id, subtask=sub
    )
    await tick(hass, freezer, minutes=5)
    done = home.notify[-1].data["data"]["actions"][0]["action"]
    press(hass, done, home.parent.id)  # a parent of another child
    await hass.async_block_till_done()
    assert manager(home).timers.timer(1002) is not None
    press(hass, done, home.parent_b.id)
    await hass.async_block_till_done()
    assert manager(home).timers.timer(1002) is None


# -- rights ------------------------------------------------------------------------


async def test_rights_matrix(
    hass: HomeAssistant, home: Home, hass_ws_client: WebSocketGenerator
) -> None:
    """The M14 answer rule, for the timer and for the settings."""
    sub_a, sub_b = make_sub(home), make_sub(home, 30, child=1002)

    async def allowed(user: Any, child: int, sub: str) -> bool:
        client = await client_of(hass, hass_ws_client, user)
        entity_id = todo_id(hass, child)
        answer = await timer(client, entity_id, "start", subtask=sub, replace=True)
        settings = await send(client, SETTINGS, entity_id, extra_minutes=5)
        assert answer["success"] is settings["success"]
        if not answer["success"]:
            assert answer["error"]["code"] == "not_allowed_for_role"
            assert settings["error"]["code"] == "not_allowed_for_role"
        await client.close()
        return bool(answer["success"])

    # Anna has an active student: only the student.
    assert await allowed(home.student, 1001, sub_a)
    for user in (home.parent, home.parent_b, home.admin, home.stranger):
        assert not await allowed(user, 1001, sub_a)
    # Bram has none: his parent and an administrator, nobody else.
    assert await allowed(home.parent_b, 1002, sub_b)
    assert await allowed(home.admin, 1002, sub_b)
    assert not await allowed(home.parent, 1002, sub_b)
    assert not await allowed(home.student, 1002, sub_b)
    assert not await allowed(home.stranger, 1002, sub_b)
    # A deactivated student does not count: the parent acts on the child's behalf.
    await hass.auth.async_deactivate_user(home.student)
    assert await allowed(home.parent, 1001, sub_a)
    assert await allowed(home.admin, 1001, sub_a)


async def test_unknown_entity_and_read_only(
    hass: HomeAssistant, home: Home, hass_ws_client: WebSocketGenerator
) -> None:
    """Unknown entity: not_found."""
    client = await client_of(hass, hass_ws_client, home.student)
    assert (await timer(client, "todo.nope", "pause"))["error"]["code"] == "not_found"
    assert (await send(client, SETTINGS, "todo.nope", extra_minutes=5))["error"][
        "code"
    ] == "not_found"


# -- settings ----------------------------------------------------------------------


async def test_settings(
    hass: HomeAssistant,
    home: Home,
    hass_ws_client: WebSocketGenerator,
    hass_storage: dict[str, Any],
) -> None:
    """Off or 1-15 and 1-30; stored; null switches off; nothing to update."""
    client = await client_of(hass, hass_ws_client, home.student)
    entity_id = todo_id(hass)
    answer = await send(
        client, SETTINGS, entity_id, prewarn_minutes=5, extra_minutes=30
    )
    assert answer["result"] == {
        "timer_settings": {"prewarn_minutes": 5, "extra_minutes": 30}
    }
    only = await send(client, SETTINGS, entity_id, prewarn_minutes=15)
    assert only["result"]["timer_settings"] == {
        "prewarn_minutes": 15,
        "extra_minutes": 30,
    }
    for field, value in (
        ("prewarn_minutes", 0),
        ("prewarn_minutes", 16),
        ("prewarn_minutes", True),
        ("prewarn_minutes", "5"),
        ("prewarn_minutes", 2.5),
        ("extra_minutes", 31),
        ("extra_minutes", 0),
    ):
        bad = await send(client, SETTINGS, entity_id, **{field: value})
        assert bad["error"]["code"] == "invalid_format", (field, value)
    empty = await send(client, SETTINGS, entity_id)
    assert empty["error"]["code"] == "invalid_format"
    off = await send(
        client, SETTINGS, entity_id, prewarn_minutes=None, extra_minutes=None
    )
    assert off["result"]["timer_settings"] == {
        "prewarn_minutes": None,
        "extra_minutes": None,
    }
    assert manager(home).timers.to_stored() == {}
    # They live in the homework store, per child.
    await send(client, SETTINGS, entity_id, extra_minutes=10)
    assert await hass.config_entries.async_unload(home.entry.entry_id)
    saved = hass_storage[f"magister.homework.{home.entry.entry_id}"]
    assert saved["data"]["timer"]["settings"] == {
        "1001": {"prewarn_minutes": None, "extra_minutes": 10}
    }


async def test_coach_tool_for_settings(hass: HomeAssistant, home: Home) -> None:
    """set_timer_settings: the student (and a parent without student); never timers."""
    data = await ok(
        hass,
        home.student.id,
        "set_timer_settings",
        prewarn_minutes=3,
        extra_minutes=None,
    )
    assert data["timer_settings"] == {"prewarn_minutes": 3, "extra_minutes": None}
    assert manager(home).timers.settings(1001)["prewarn_minutes"] == 3
    assert (
        await coach_fails(hass, home.student.id, "set_timer_settings")
        == "invalid_format"
    )
    assert (
        await coach_fails(hass, home.student.id, "set_timer_settings", extra_minutes=99)
        == "invalid_format"
    )
    # A parent may not while the child has an active student.
    assert (
        await coach_fails(
            hass, home.parent.id, "set_timer_settings", child="1001", extra_minutes=5
        )
        == "not_allowed_for_role"
    )
    assert manager(home).timers.settings(1001)["extra_minutes"] is None
    # A parent of a child without a student user may.
    done = await ok(hass, home.parent_b.id, "set_timer_settings", extra_minutes=5)
    assert done["timer_settings"]["extra_minutes"] == 5
    from custom_components.magister.coach import coach_tools

    assert not [
        t.name
        for t in coach_tools()
        if "timer" in t.name and t.name != "set_timer_settings"
    ]


async def test_coach_reads_show_the_timer(hass: HomeAssistant, home: Home) -> None:
    """list_homework and get_progress show the timer; no school host anywhere."""
    assert (await ok(hass, home.student.id, "get_progress"))["timer"] is None
    assert (await ok(hass, home.student.id, "list_homework"))["timer"] is None
    sub = make_sub(home, 20)
    await manager(home).async_timer_action(
        1001, "start", user_id=home.student.id, subtask=sub
    )
    for tool in ("get_progress", "list_homework"):
        data = await ok(hass, home.student.id, tool)
        view = data["timer"]
        assert view["state"] == "running" and view["title"] == "Opgave 3"
        assert view["minutes"] == 20 and view["ends_at"]
        assert HOST not in str(view) and "nonce" not in view
    parent = await ok(hass, home.parent.id, "get_progress")
    assert parent["timer"]["state"] == "running"


# -- the payload -------------------------------------------------------------------


async def test_payload_and_unavailable_event(
    hass: HomeAssistant, home: Home, hass_ws_client: WebSocketGenerator
) -> None:
    """``timer`` and ``timer_settings`` are pushed, also in the last event."""
    sub = make_sub(home, 25)
    client = await client_of(hass, hass_ws_client, home.student)
    entity_id = todo_id(hass)
    await client.send_json_auto_id(
        {"type": "magister/homework/subscribe", "entity_id": entity_id}
    )
    assert (await client.receive_json())["success"]
    first = (await client.receive_json())["event"]
    assert first["timer"] is None
    assert first["timer_settings"] == {"prewarn_minutes": None, "extra_minutes": None}
    await client.send_json_auto_id(
        {"type": TIMER, "entity_id": entity_id, "action": "start", "subtask": sub}
    )
    seen = [await client.receive_json(), await client.receive_json()]
    event = next(m["event"] for m in seen if m["type"] == "event")
    assert next(m for m in seen if m["type"] == "result")["success"]
    assert event["timer"]["subtask"] == sub and event["timer"]["state"] == "running"
    received: list[Any] = []
    async_subscribe(hass, entity_id, received.append)
    assert await hass.config_entries.async_unload(home.entry.entry_id)
    await hass.async_block_till_done()
    final = received[-1]
    assert final["available"] is False
    assert final["timer"]["subtask"] == sub
    assert final["timer_settings"] == {"prewarn_minutes": None, "extra_minutes": None}


# -- services ----------------------------------------------------------------------


async def test_services(
    hass: HomeAssistant, home: Home, freezer: FrozenDateTimeFactory
) -> None:
    """start_study_timer and stop_study_timer, with and without a user."""
    sub, sub2 = make_sub(home), make_sub(home, 10, title="Opgave 4")
    entity_id = todo_id(hass)

    async def call(service: str, user: Any = None, **data: Any) -> None:
        await hass.services.async_call(
            "magister",
            service,
            {"entity_id": entity_id, **data},
            blocking=True,
            context=Context(user_id=user.id) if user else None,
        )

    await call("start_study_timer", subtask=sub)  # an automation: no user
    assert manager(home).timers.timer(1001)["subtask"] == sub
    with pytest.raises(ServiceValidationError) as err:
        await call("start_study_timer", subtask=sub2)
    assert err.value.translation_key == "homework_timer_running"
    await call("start_study_timer", home.student, subtask=sub2, replace=True)
    with pytest.raises(ServiceValidationError) as err:
        await call("stop_study_timer", home.parent)
    assert err.value.translation_key == "homework_not_allowed_for_role"
    with pytest.raises(probatio.Invalid):
        await call("stop_study_timer", progress=30)
    await call("stop_study_timer", home.student, progress="75")
    assert manager(home).progress(sub2) == 75
    assert manager(home).timers.timer(1001) is None
    with pytest.raises(ServiceValidationError) as err:
        await call("stop_study_timer")
    assert err.value.translation_key == "homework_no_timer"
    # An admin user (not an automation) follows the same rule as everyone.
    with pytest.raises(ServiceValidationError):
        await call("start_study_timer", home.admin, subtask=sub)


# -- the subtask goes away ---------------------------------------------------------


async def test_subtask_changes(
    hass: HomeAssistant,
    home: Home,
    hass_ws_client: WebSocketGenerator,
    logbook: list[Any],
) -> None:
    """Deleting or completing stops the timer; changing the minutes does not."""
    client = await client_of(hass, hass_ws_client, home.student)
    entity_id = todo_id(hass)
    mgr = manager(home)
    sub = make_sub(home, 30)
    await timer(client, entity_id, "start", subtask=sub)
    changed = await send(
        client, "magister/homework/update_subtask", entity_id, subtask=sub, minutes=60
    )
    assert changed["success"]
    state = mgr.timers.timer(1001)
    assert state["minutes"] == 30 and state["state"] == "running"
    # Completing (100 %) stops it.
    mgr.set_progress(sub, 100)
    assert mgr.timers.timer(1001) is None
    mgr.set_progress(sub, 50)
    assert mgr.timers.timer(1001) is None
    # Deleting stops it.
    await timer(client, entity_id, "start", subtask=sub)
    mgr.set_progress(sub, 25)
    assert mgr.timers.timer(1001) is not None
    deleted = await send(
        client, "magister/homework/delete_subtask", entity_id, subtask=sub
    )
    assert deleted["success"] and mgr.timers.timer(1001) is None
    assert "Studietimer gestopt (Opgave 3)" in messages(logbook)
    # Disabling the item hides the subtask: the timer goes with it.
    sub2 = make_sub(home, 30, title="Opgave 4")
    await timer(client, entity_id, "start", subtask=sub2)
    override = await send(
        client,
        "magister/homework/set_override",
        entity_id,
        appointment=f"{HOST}:1001:{HOMEWORK}",
        mode="disable",
    )
    assert override["success"] and mgr.timers.timer(1001) is None
    assert mgr.timers.payload(1001) is None


async def test_coordinator_update_drops_a_timer_without_subtask(
    hass: HomeAssistant, home: Home
) -> None:
    """A timer of a subtask that is gone (e.g. its lesson left the window) stops."""
    sub = make_sub(home, 30)
    mgr = manager(home)
    await mgr.async_timer_action(1001, "start", user_id=home.student.id, subtask=sub)
    now = dt_util.utcnow()
    mgr.timers._on_end(1001, "stale", now)  # a stale callback does nothing
    mgr.timers._on_prewarn(1001, "stale", now)
    assert mgr.timers.timer(1001)["state"] == "running"
    mgr._progress.clear()
    mgr._invalidate()
    assert mgr.timers.payload(1001) is None  # hidden before it is validated
    mgr._handle_coordinator_update()
    assert mgr.timers.timer(1001) is None


# -- restart and unload ------------------------------------------------------------


async def restart(hass: HomeAssistant, home: Home) -> None:
    """Unload and set up the entry again."""
    assert await hass.config_entries.async_unload(home.entry.entry_id)
    assert await hass.config_entries.async_setup(home.entry.entry_id)
    await hass.async_block_till_done()


async def test_restore_running_timer(
    hass: HomeAssistant,
    home: Home,
    freezer: FrozenDateTimeFactory,
    hass_storage: dict[str, Any],
) -> None:
    """A running timer survives a restart and still ends and notifies."""
    sub = make_sub(home, 20)
    await set_settings(home, prewarn=2)
    await manager(home).async_timer_action(
        1001, "start", user_id=home.student.id, subtask=sub
    )
    await tick(hass, freezer, minutes=5)
    await restart(hass, home)
    assert manager(home).timers.timer(1001)["state"] == "running"
    await tick(hass, freezer, minutes=13)  # 2 minutes left
    assert home.notify[-1].data["message"].startswith("Nog 2 minuten")
    await tick(hass, freezer, minutes=2)
    assert home.notify[-1].data["message"].startswith("Tijd is om")
    # Stored in the homework store, minor version 9, major 1.
    await restart(hass, home)
    saved = hass_storage[f"magister.homework.{home.entry.entry_id}"]
    assert (saved["version"], saved["minor_version"]) == (1, 9)
    assert manager(home).timers.timer(1001)["state"] == "finished"
    assert len(notifications(hass)) == 1  # re-created, the phone is not told again


async def test_restore_with_the_end_in_the_past(
    hass: HomeAssistant, home: Home, freezer: FrozenDateTimeFactory
) -> None:
    """A timer that ended while Home Assistant was down finishes at once."""
    sub = make_sub(home, 10)
    await manager(home).async_timer_action(
        1001, "start", user_id=home.student.id, subtask=sub
    )
    finished = async_capture_events(hass, "magister_study_timer_finished")
    assert await hass.config_entries.async_unload(home.entry.entry_id)
    freezer.tick(timedelta(hours=3))
    assert await hass.config_entries.async_setup(home.entry.entry_id)
    await hass.async_block_till_done()
    assert manager(home).timers.timer(1001)["state"] == "finished"
    assert len(finished) == 1
    assert home.notify[-1].data["message"].startswith("Tijd is om")
    assert len(notifications(hass)) == 1


async def test_restore_paused_and_gone(
    hass: HomeAssistant, home: Home, freezer: FrozenDateTimeFactory
) -> None:
    """A paused timer stays paused; a timer of a deleted subtask is dropped."""
    sub, gone = make_sub(home, 10), make_sub(home, 10, child=1002)
    mgr = manager(home)
    await mgr.async_timer_action(1001, "start", user_id=home.student.id, subtask=sub)
    await tick(hass, freezer, minutes=4)
    await mgr.async_timer_action(1001, "pause", user_id=home.student.id)
    await mgr.async_timer_action(1002, "start", user_id=home.parent_b.id, subtask=gone)
    mgr.timers._timers[1002]["subtask"] = f"{HOST}:1002:{PROEFWERK}:sub:nope"
    await restart(hass, home)
    assert manager(home).timers.timer(1001)["remaining"] == 6 * 60
    assert manager(home).timers.timer(1002) is None
    await tick(hass, freezer, minutes=30)
    assert manager(home).timers.timer(1001)["state"] == "paused"


async def test_unload_cancels_the_callbacks(
    hass: HomeAssistant, home: Home, freezer: FrozenDateTimeFactory
) -> None:
    """After an unload nothing fires (the timer stays in the store)."""
    sub = make_sub(home, 10)
    await set_settings(home, prewarn=2)
    mgr = manager(home)
    await mgr.async_timer_action(1001, "start", user_id=home.student.id, subtask=sub)
    assert len(mgr.timers._cancel[1001]) == 2
    finished = async_capture_events(hass, "magister_study_timer_finished")
    assert await hass.config_entries.async_unload(home.entry.entry_id)
    assert home.entry.state is ConfigEntryState.NOT_LOADED
    assert mgr.timers._cancel == {}
    await tick(hass, freezer, minutes=20)
    assert not finished and home.notify == []
    # A button press after the unload is not handled either.
    press(hass, "MAGISTER_TIMER|done|x|1001|y|z")
    await hass.async_block_till_done()


async def test_damaged_store_and_children_that_left(home_engine: Any = None) -> None:
    """Lenient reading of the stored timers and settings."""


@pytest.fixture
def engine(home: Home) -> TimerEngine:
    """A fresh engine on the manager of the entry."""
    return TimerEngine(manager(home), lambda: None)


async def test_lenient_loading(home: Home, engine: TimerEngine) -> None:
    """Unusable timers and settings are dropped."""
    good = {
        "subtask": f"{HOST}:1001:{HOMEWORK}:sub:ab",
        "state": "paused",
        "minutes": 10,
        "remaining": 60,
        "nonce": "n",
    }
    running = {**good, "state": "running", "ends_at": "2026-11-13T10:00:00+00:00"}
    engine.load("junk")
    engine.load(
        {
            "timers": {
                "1001": running,
                "1002": good,
                "x": good,
                "1003": {**good, "state": "bogus"},
                "1004": {**good, "subtask": "nonsense"},
                "1005": {**good, "nonce": ""},
                "1006": {**good, "minutes": 0},
                "1007": {**good, "minutes": True},
                "1008": {**good, "remaining": "x"},
                "1009": {**running, "ends_at": "later"},
                "1010": 5,
            },
            "settings": {
                "1001": {"prewarn_minutes": 3, "extra_minutes": 99},
                "1002": {"prewarn_minutes": 0, "extra_minutes": "x"},
                "1003": "junk",
                "y": {"prewarn_minutes": 3},
            },
        }
    )
    assert sorted(engine._timers) == [1001, 1002]
    assert engine.settings(1001) == {"prewarn_minutes": 3, "extra_minutes": None}
    assert sorted(engine._settings) == [1001]
    engine.load({"timers": 5, "settings": 5})
    stats = engine.statistics()
    assert stats["timers"] == {"running": 1, "paused": 1, "finished": 0}
    engine.drop_children([1001])
    assert sorted(engine._timers) == [1001]
    assert progress_step(25) == 25
    for bad in (True, "25", 30):
        with pytest.raises(Exception):  # noqa: B017
            progress_step(bad)


# -- options flow ------------------------------------------------------------------


async def test_options_flow_notify_targets(hass: HomeAssistant, home: Home) -> None:
    """Choose the child, then the mobile_app notify services; no reload."""
    assert notify_services(hass) == [TARGET, OTHER]
    async_mock_service(hass, "notify", "send_message")  # not a companion app
    assert notify_services(hass) == [TARGET, OTHER]
    runtime = home.entry.runtime_data
    result = await hass.config_entries.options.async_init(home.entry.entry_id)
    assert "study_timer" in result["menu_options"]
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"next_step_id": "study_timer"}
    )
    assert result["type"] is FlowResultType.FORM and result["step_id"] == "study_timer"
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"child": "1002"}
    )
    assert result["step_id"] == "study_timer_targets"
    assert result["description_placeholders"]["child"]
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"targets": [OTHER]}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()
    assert home.entry.options[CONF_STUDY_TIMER] == {"1001": [TARGET], "1002": [OTHER]}
    assert home.entry.runtime_data is runtime  # no reload
    assert home.entry.state is ConfigEntryState.LOADED
    # Empty list removes the child; the last one removes the key.
    for child, left in (("1001", {"1002": [OTHER]}), ("1002", None)):
        result = await hass.config_entries.options.async_init(home.entry.entry_id)
        result = await hass.config_entries.options.async_configure(
            result["flow_id"], {"next_step_id": "study_timer"}
        )
        result = await hass.config_entries.options.async_configure(
            result["flow_id"], {"child": child}
        )
        result = await hass.config_entries.options.async_configure(
            result["flow_id"], {}
        )
        assert result["type"] is FlowResultType.CREATE_ENTRY
        assert home.entry.options.get(CONF_STUDY_TIMER) == left
    assert home.entry.runtime_data is runtime


async def test_options_flow_one_child_and_removed_service(
    hass: HomeAssistant, mocked: aioresponses
) -> None:
    """One child skips the choice; a chosen service that is gone can be removed."""
    entry = await setup_coach(
        hass, mocked, {CONF_STUDY_TIMER: {"1001": ["mobile_app_old"]}}
    )
    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"next_step_id": "study_timer"}
    )
    assert result["step_id"] == "study_timer_targets"
    selector = result["data_schema"].schema["targets"]
    assert [o["value"] for o in selector.config["options"]] == ["mobile_app_old"]
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"targets": []}
    )
    assert CONF_STUDY_TIMER not in entry.options


# -- diagnostics -------------------------------------------------------------------


async def test_diagnostics_counts_only(hass: HomeAssistant, home: Home) -> None:
    """Counts of timers, settings and targets; no service names."""
    sub = make_sub(home)
    await set_settings(home, prewarn=2, extra=5)
    await manager(home).async_timer_action(
        1001, "start", user_id=home.student.id, subtask=sub
    )
    data = await async_get_config_entry_diagnostics(hass, home.entry)
    assert data["study_timer"] == {
        "timers": {"running": 1, "paused": 0, "finished": 0},
        "children_with_settings": 1,
        "prewarn_set": 1,
        "extra_set": 1,
        "children_with_targets": 1,
        "targets": 1,
    }
    assert CONF_STUDY_TIMER not in data["entry"]["options"]
    assert TARGET not in str(data)
    assert data["children"][0]["homework"]["timer"] is True
