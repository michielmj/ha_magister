"""The study timer of a child (milestone M15).

A student starts a timer on a subtask that has an estimated time. The timer lives in the
homework store of the config entry (key ``timer``), per child, so it keeps running when
the card or the app is closed and survives a restart. When it runs out the student gets
a push notification on the companion app(s) that the administrator chose for the child
(never a parent), a persistent notification in Home Assistant and the event
``magister_study_timer_finished``.

States: ``running`` (``ends_at``), ``paused`` (``remaining`` seconds) and ``finished``;
a stopped timer is removed. The module has no knowledge of who may act: the rights are
checked by the manager (the same rule as answering a proposal, see ``roles``).
"""

from __future__ import annotations

import hmac
import logging
import secrets
from collections.abc import Callable, Coroutine
from datetime import datetime, timedelta
from functools import partial
from typing import TYPE_CHECKING, Any, Final

import probatio
from homeassistant.components import persistent_notification
from homeassistant.core import CALLBACK_TYPE, Event, HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.event import async_track_point_in_time
from homeassistant.util import dt as dt_util

from .api.homework import split_subtask_uid, uid_child_id
from .const import CONF_STUDY_TIMER, DOMAIN
from .context import ContextError

if TYPE_CHECKING:
    from .homework import HomeworkManager, Payload

_LOGGER = logging.getLogger(__name__)

STORE_KEY: Final = "timer"
STORE_TIMERS: Final = "timers"
STORE_SETTINGS: Final = "settings"

STATE_RUNNING: Final = "running"
STATE_PAUSED: Final = "paused"
STATE_FINISHED: Final = "finished"
STATES: Final = (STATE_RUNNING, STATE_PAUSED, STATE_FINISHED)

ACTION_START: Final = "start"
ACTION_PAUSE: Final = "pause"
ACTION_RESUME: Final = "resume"
ACTION_STOP: Final = "stop"
ACTION_EXTEND: Final = "extend"
ACTION_DONE: Final = "done"
ACTIONS: Final = (
    ACTION_START,
    ACTION_PAUSE,
    ACTION_RESUME,
    ACTION_STOP,
    ACTION_EXTEND,
    ACTION_DONE,
)

PROGRESS_STEPS: Final = (0, 25, 50, 75, 100)
PREWARN_MAX: Final = 15
EXTRA_MAX: Final = 30

# Where an action came from (decides the logbook text of ``done``).
SOURCE_API: Final = "api"
SOURCE_NOTIFICATION: Final = "notification"

ERR_TIMER_RUNNING: Final = "timer_running"
ERR_NO_MINUTES: Final = "no_minutes"
ERR_NO_TIMER: Final = "no_timer"
ERR_TIMER_STATE: Final = "timer_wrong_state"
ERR_EXTRA_NOT_SET: Final = "extra_not_set"
ERR_NOT_FINISHED: Final = "timer_not_finished"
ERR_NOT_ALLOWED: Final = "not_allowed_for_role"
ERR_SUBTASK_NOT_FOUND: Final = "subtask_not_found"
ERR_NOTHING_TO_UPDATE: Final = "nothing_to_update"

NOT_ALLOWED_MESSAGE: Final = (
    "Only the student controls the study timer. A parent (or an administrator) may "
    "only do so when the child has no active student user."
)

EVENT_FINISHED: Final = "magister_study_timer_finished"
EVENT_NOTIFICATION_ACTION: Final = "mobile_app_notification_action"
NOTIFY_DOMAIN: Final = "notify"
NOTIFY_PREFIX: Final = "mobile_app_"

# The texts are Dutch constants: they are sent from background tasks without a user
# language, and neither the notify services nor persistent notifications translate.
NOTIFICATION_TITLE: Final = "Studietimer"
TEXT_PREWARN: Final = "Nog {n} minuten: {what}"
TEXT_PREWARN_ONE: Final = "Nog 1 minuut: {what}"
TEXT_END: Final = "Tijd is om: {what}"
BUTTON_DONE: Final = "Klaar"
BUTTON_EXTEND: Final = "+{n} min"
BUTTON_STOP: Final = "Nog niet"

ACTION_PREFIX: Final = "MAGISTER_TIMER"
_SEPARATOR: Final = "|"
VERBS: Final = (ACTION_DONE, ACTION_EXTEND, ACTION_STOP)


class TimerError(ContextError):
    """A timer command that cannot be carried out (``code`` names the reason)."""


def timer_minutes(maximum: int) -> Callable[[Any], int | None]:
    """A validator: ``None`` (off) or a whole number from 1 to ``maximum``."""

    def validate(value: Any) -> int | None:
        if value is None:
            return None
        if isinstance(value, bool) or not isinstance(value, int):
            raise probatio.Invalid("must be a whole number of minutes or null")
        if not 1 <= value <= maximum:
            raise probatio.Invalid(f"must be between 1 and {maximum}")
        return value

    return validate


prewarn_value: Final = timer_minutes(PREWARN_MAX)
extra_value: Final = timer_minutes(EXTRA_MAX)


def progress_step(value: Any) -> int:
    """Validate the progress of a stop: 0, 25, 50, 75 or 100."""
    if isinstance(value, bool) or not isinstance(value, int):
        raise probatio.Invalid("progress must be 0, 25, 50, 75 or 100")
    if value not in PROGRESS_STEPS:
        raise probatio.Invalid("progress must be 0, 25, 50, 75 or 100")
    return value


def notify_services(hass: HomeAssistant) -> list[str]:
    """The names of the companion-app notify services (``mobile_app_*``)."""
    return sorted(
        name
        for name in hass.services.async_services_for_domain(NOTIFY_DOMAIN)
        if name.startswith(NOTIFY_PREFIX)
    )


def _valid(value: Any, maximum: int) -> int | None:
    try:
        return timer_minutes(maximum)(value)
    except probatio.Invalid:
        return None


def _what(title: str, subject: str | None) -> str:
    return f"{title} ({subject})" if subject else title


def _child_key(key: Any) -> int | None:
    try:
        return int(key)
    except TypeError, ValueError:
        return None


def _clean_timer(raw: Any) -> dict[str, Any] | None:
    """A stored timer, leniently; ``None`` when it is not usable."""
    if not isinstance(raw, dict):
        return None
    state, uid, nonce = raw.get("state"), raw.get("subtask"), raw.get("nonce")
    minutes = raw.get("minutes")
    if (
        state not in STATES
        or not isinstance(uid, str)
        or split_subtask_uid(uid) is None
        or not isinstance(nonce, str)
        or not nonce
        or isinstance(minutes, bool)
        or not isinstance(minutes, int)
        or minutes < 1
    ):
        return None
    clean: dict[str, Any] = {
        "subtask": uid,
        "state": state,
        "minutes": minutes,
        "nonce": nonce,
        "started_at": str(raw.get("started_at") or ""),
        "prewarned": raw.get("prewarned") is True,
    }
    if state == STATE_PAUSED:
        remaining = raw.get("remaining")
        if isinstance(remaining, bool) or not isinstance(remaining, int):
            return None
        clean["remaining"] = max(remaining, 0)
        return clean
    if dt_util.parse_datetime(str(raw.get("ends_at"))) is None:
        return None
    clean["ends_at"] = str(raw["ends_at"])
    return clean


class TimerEngine:
    """The timers and the student settings of all children of one config entry."""

    def __init__(self, manager: HomeworkManager, changed: Callable[[], None]) -> None:
        """Create the engine (``changed`` saves the store and tells the listeners)."""
        self._manager = manager
        self._changed = changed
        self._timers: dict[int, dict[str, Any]] = {}
        self._settings: dict[int, dict[str, int | None]] = {}
        self._cancel: dict[int, list[CALLBACK_TYPE]] = {}

    # -- storage -------------------------------------------------------------------

    def load(self, raw: Any) -> None:
        """Read the stored timers and settings (leniently)."""
        if not isinstance(raw, dict):
            return
        timers = raw.get(STORE_TIMERS)
        for key, stored in (timers if isinstance(timers, dict) else {}).items():
            if (child := _child_key(key)) is not None and (
                timer := _clean_timer(stored)
            ):
                self._timers[child] = timer
        settings = raw.get(STORE_SETTINGS)
        for key, stored in (settings if isinstance(settings, dict) else {}).items():
            if (child := _child_key(key)) is None or not isinstance(stored, dict):
                continue
            clean = {
                "prewarn_minutes": _valid(stored.get("prewarn_minutes"), PREWARN_MAX),
                "extra_minutes": _valid(stored.get("extra_minutes"), EXTRA_MAX),
            }
            if any(v is not None for v in clean.values()):
                self._settings[child] = clean

    def to_stored(self) -> dict[str, Any]:
        """The form kept in the store (empty when there is nothing)."""
        data: dict[str, Any] = {}
        if self._timers:
            data[STORE_TIMERS] = {str(c): dict(t) for c, t in self._timers.items()}
        if self._settings:
            data[STORE_SETTINGS] = {str(c): dict(s) for c, s in self._settings.items()}
        return data

    def drop_children(self, kept: list[int]) -> None:
        """Forget the timers and settings of children that were unselected."""
        for child in [c for c in {*self._timers, *self._settings} if c not in kept]:
            self._clear(child, log=None)
            self._settings.pop(child, None)

    # -- reading ---------------------------------------------------------------------

    def timer(self, child: int) -> dict[str, Any] | None:
        """The stored timer of a child (a copy), ``None`` when there is none."""
        stored = self._timers.get(child)
        return dict(stored) if stored else None

    def settings(self, child: int) -> dict[str, int | None]:
        """The student settings of a child (``None`` is off)."""
        stored = self._settings.get(child, {})
        return {
            "prewarn_minutes": stored.get("prewarn_minutes"),
            "extra_minutes": stored.get("extra_minutes"),
        }

    def _names(self, child: int, timer: dict[str, Any]) -> tuple[str, str]:
        sub = self._manager.find_subtask(timer["subtask"])
        ref = split_subtask_uid(timer["subtask"])
        item = self._manager.find_item(child, ref[0]) if ref else None
        return (sub.title if sub else ""), (
            item.subject if item and item.subject else ""
        )

    def payload(self, child: int) -> Payload | None:
        """The timer in the WebSocket form; ``None`` without a (usable) timer."""
        timer = self._timers.get(child)
        ref = split_subtask_uid(timer["subtask"]) if timer else None
        if timer is None or ref is None:
            return None
        sub = self._manager.find_subtask(timer["subtask"])
        item = self._manager.find_item(child, ref[0])
        if sub is None or item is None:
            return None
        result: Payload = {
            "subtask": timer["subtask"],
            "title": sub.title,
            "subject": item.subject,
            "due": item.due_date.isoformat(),
            "label": item.label,
            "state": timer["state"],
            "minutes": timer["minutes"],
            "started_at": timer["started_at"],
        }
        if timer["state"] == STATE_PAUSED:
            result["remaining"] = timer["remaining"]
        else:
            result["ends_at"] = timer["ends_at"]
        return result

    def statistics(self) -> dict[str, Any]:
        """Counts only."""
        return {
            "timers": {
                state: sum(1 for t in self._timers.values() if t["state"] == state)
                for state in STATES
            },
            "children_with_settings": len(self._settings),
            "prewarn_set": sum(
                1 for s in self._settings.values() if s["prewarn_minutes"]
            ),
            "extra_set": sum(1 for s in self._settings.values() if s["extra_minutes"]),
        }

    # -- start-up and shutdown -----------------------------------------------------

    @callback
    def async_restore(self) -> None:
        """Take the stored timers up again after a start (a missed end is finished)."""
        now = dt_util.utcnow()
        for child in list(self._timers):
            timer = self._timers[child]
            if self._manager.find_subtask(timer["subtask"]) is None:
                self._clear(child, log=None)
            elif timer["state"] == STATE_FINISHED:
                self._persistent(child, timer)
            elif timer["state"] == STATE_RUNNING:
                ends = dt_util.parse_datetime(timer["ends_at"])
                assert ends is not None
                if ends <= now:
                    self._finish(child)
                else:
                    self._schedule(child)

    @callback
    def async_unload(self) -> None:
        """Cancel every scheduled callback (the timers stay in the store)."""
        for child in list(self._cancel):
            self._unschedule(child)

    @callback
    def validate(self) -> None:
        """Stop the timers whose subtask is gone (or hidden)."""
        for child, timer in list(self._timers.items()):
            if self._manager.find_subtask(timer["subtask"]) is None:
                self._clear(child, log=None)

    # -- scheduling ------------------------------------------------------------------

    def _unschedule(self, child: int) -> None:
        for cancel in self._cancel.pop(child, []):
            cancel()

    def _schedule(self, child: int) -> None:
        self._unschedule(child)
        timer = self._timers.get(child)
        if timer is None or timer["state"] != STATE_RUNNING:
            return
        hass = self._manager.hass
        ends = dt_util.parse_datetime(timer["ends_at"])
        assert ends is not None
        nonce = timer["nonce"]
        cancels = [
            async_track_point_in_time(hass, partial(self._on_end, child, nonce), ends)
        ]
        prewarn = self.settings(child)["prewarn_minutes"]
        if prewarn and not timer["prewarned"]:
            at = ends - timedelta(minutes=prewarn)
            if at > dt_util.utcnow():
                cancels.append(
                    async_track_point_in_time(
                        hass, partial(self._on_prewarn, child, nonce), at
                    )
                )
            else:
                # The timer is shorter than the pre-warning (or it has passed).
                timer["prewarned"] = True
        self._cancel[child] = cancels

    def _current(self, child: int, nonce: str) -> dict[str, Any] | None:
        timer = self._timers.get(child)
        if timer and timer["state"] == STATE_RUNNING and timer["nonce"] == nonce:
            return timer
        return None

    @callback
    def _on_end(self, child: int, nonce: str, _now: datetime) -> None:
        if self._current(child, nonce) is not None:
            self._finish(child)

    @callback
    def _on_prewarn(self, child: int, nonce: str, _now: datetime) -> None:
        timer = self._current(child, nonce)
        prewarn = self.settings(child)["prewarn_minutes"]
        if timer is None or timer["prewarned"] or not prewarn:
            return
        timer["prewarned"] = True
        self._changed()
        title, subject = self._names(child, timer)
        text = (TEXT_PREWARN_ONE if prewarn == 1 else TEXT_PREWARN).format(
            n=prewarn, what=_what(title, subject)
        )
        self._notify(child, timer, text, done=False, extra=None, stop=False)

    @callback
    def _finish(self, child: int) -> None:
        timer = self._timers[child]
        self._unschedule(child)
        timer["state"] = STATE_FINISHED
        timer["prewarned"] = True
        self._changed()
        title, subject = self._names(child, timer)
        self._manager.log_entry(child, f"Studietimer afgelopen ({title})")
        self._manager.hass.bus.async_fire(
            EVENT_FINISHED, {"child": child, "subtask": timer["subtask"]}
        )
        self._persistent(child, timer)
        self._notify(
            child,
            timer,
            TEXT_END.format(what=_what(title, subject)),
            done=True,
            extra=self.settings(child)["extra_minutes"],
            stop=True,
        )

    # -- notifications -----------------------------------------------------------

    def _persistent_id(self, child: int) -> str:
        return f"{DOMAIN}_study_timer_{self._manager.entry_id}_{child}"

    def _persistent(self, child: int, timer: dict[str, Any]) -> None:
        title, subject = self._names(child, timer)
        persistent_notification.async_create(
            self._manager.hass,
            TEXT_END.format(what=_what(title, subject)),
            NOTIFICATION_TITLE,
            self._persistent_id(child),
        )

    def _targets(self, child: int) -> list[str]:
        stored = self._manager.entry_options.get(CONF_STUDY_TIMER)
        raw = stored.get(str(child)) if isinstance(stored, dict) else None
        return [t for t in raw if isinstance(t, str)] if isinstance(raw, list) else []

    def action_id(self, verb: str, child: int, timer: dict[str, Any]) -> str:
        """The id of a button: verb, entry, child, subtask (no school) and nonce."""
        rest = timer["subtask"].split(":", 2)[2]
        return _SEPARATOR.join(
            (
                ACTION_PREFIX,
                verb,
                self._manager.entry_id,
                str(child),
                rest,
                timer["nonce"],
            )
        )

    def _notify(
        self,
        child: int,
        timer: dict[str, Any],
        message: str,
        *,
        done: bool,
        extra: int | None,
        stop: bool,
    ) -> None:
        """Send a message to the targets of the child (nobody else)."""
        actions: list[dict[str, str]] = []
        if done:
            actions.append(
                {
                    "action": self.action_id(ACTION_DONE, child, timer),
                    "title": BUTTON_DONE,
                }
            )
        if extra:
            actions.append(
                {
                    "action": self.action_id(ACTION_EXTEND, child, timer),
                    "title": BUTTON_EXTEND.format(n=extra),
                }
            )
        if stop:
            actions.append(
                {
                    "action": self.action_id(ACTION_STOP, child, timer),
                    "title": BUTTON_STOP,
                }
            )
        data: dict[str, Any] = {
            "tag": self.tag(child),
            "ttl": 0,
            "priority": "high",
            "push": {"interruption-level": "time-sensitive"},
        }
        if actions:
            data["actions"] = actions
        self._send(
            child, {"message": message, "title": NOTIFICATION_TITLE, "data": data}
        )

    def tag(self, child: int) -> str:
        """The notification tag of a child: a new message replaces the old one."""
        return f"{DOMAIN}_study_timer_{child}"

    def _send(self, child: int, service_data: dict[str, Any]) -> None:
        if targets := self._targets(child):
            self._manager.create_task(self._async_send(targets, service_data))

    async def _async_send(
        self, targets: list[str], service_data: dict[str, Any]
    ) -> None:
        hass = self._manager.hass
        for target in targets:
            if not hass.services.has_service(NOTIFY_DOMAIN, target):
                _LOGGER.debug("Notify service %s is not available", target)
                continue
            try:
                await hass.services.async_call(
                    NOTIFY_DOMAIN, target, service_data, blocking=True
                )
            except HomeAssistantError as err:
                _LOGGER.warning(
                    "Could not send the study timer notification (%s)",
                    type(err).__name__,
                )

    def _clear_notifications(self, child: int) -> None:
        persistent_notification.async_dismiss(
            self._manager.hass, self._persistent_id(child)
        )
        self._send(
            child, {"message": "clear_notification", "data": {"tag": self.tag(child)}}
        )

    # -- the actions -----------------------------------------------------------------

    def _clear(self, child: int, *, log: str | None) -> dict[str, Any] | None:
        """Remove the timer of a child (and its notifications); log when asked."""
        timer = self._timers.pop(child, None)
        self._unschedule(child)
        if timer is None:
            return None
        if log:
            title, _ = self._names(child, timer)
            self._manager.log_entry(child, f"{log} ({title})")
        self._clear_notifications(child)
        self._changed()
        return timer

    def stop_for_subtask(self, uid: str) -> None:
        """Stop the timer on this subtask (it was deleted or completed)."""
        for child, timer in list(self._timers.items()):
            if timer["subtask"] == uid:
                self._clear(child, log="Studietimer gestopt")

    def set_settings(
        self, child: int, prewarn: Any, extra: Any, *, given: tuple[bool, bool]
    ) -> dict[str, int | None]:
        """Change the student settings (only the values that were given)."""
        if not any(given):
            raise TimerError(ERR_NOTHING_TO_UPDATE)
        current = self.settings(child)
        if given[0]:
            current["prewarn_minutes"] = prewarn
        if given[1]:
            current["extra_minutes"] = extra
        if any(v is not None for v in current.values()):
            self._settings[child] = current
        else:
            self._settings.pop(child, None)
        self._schedule(child)
        self._changed()
        return self.settings(child)

    def perform(
        self,
        child: int,
        action: str,
        *,
        subtask: str | None = None,
        replace: bool = False,
        progress: int | None = None,
        source: str = SOURCE_API,
    ) -> None:
        """Carry out an action (the rights are checked by the caller)."""
        if action == ACTION_START:
            self._start(child, subtask, replace)
            return
        timer = self._timers.get(child)
        if timer is None:
            raise TimerError(ERR_NO_TIMER)
        handler = {
            ACTION_PAUSE: self._pause,
            ACTION_RESUME: self._resume,
            ACTION_EXTEND: self._extend,
        }.get(action)
        if handler is not None:
            handler(child, timer)
        elif action == ACTION_STOP:
            self._stop(child, progress)
        else:
            self._done(child, source)

    def _start(self, child: int, subtask: str | None, replace: bool) -> None:
        ref = split_subtask_uid(subtask or "")
        sub = self._manager.find_subtask(subtask or "") if ref else None
        if sub is None or ref is None or uid_child_id(ref[0]) != child:
            raise TimerError(ERR_SUBTASK_NOT_FOUND)
        if sub.minutes is None:
            raise TimerError(ERR_NO_MINUTES)
        assert subtask is not None
        existing = self._timers.get(child)
        if existing and existing["state"] != STATE_FINISHED and not replace:
            raise TimerError(ERR_TIMER_RUNNING)
        self._clear(child, log="Studietimer gestopt" if existing else None)
        now = dt_util.utcnow()
        self._timers[child] = {
            "subtask": subtask,
            "state": STATE_RUNNING,
            "minutes": sub.minutes,
            "started_at": now.isoformat(),
            "ends_at": (now + timedelta(minutes=sub.minutes)).isoformat(),
            "nonce": secrets.token_hex(8),
            "prewarned": False,
        }
        self._schedule(child)
        self._changed()
        self._manager.log_entry(child, f"Studietimer gestart ({sub.title})")

    def _pause(self, child: int, timer: dict[str, Any]) -> None:
        if timer["state"] != STATE_RUNNING:
            raise TimerError(ERR_TIMER_STATE)
        ends = dt_util.parse_datetime(timer["ends_at"])
        assert ends is not None
        remaining = max(round((ends - dt_util.utcnow()).total_seconds()), 1)
        self._unschedule(child)
        timer["state"] = STATE_PAUSED
        timer["remaining"] = remaining
        del timer["ends_at"]
        self._changed()
        self._manager.log_entry(
            child, f"Studietimer gepauzeerd ({self._names(child, timer)[0]})"
        )

    def _resume(self, child: int, timer: dict[str, Any]) -> None:
        if timer["state"] != STATE_PAUSED:
            raise TimerError(ERR_TIMER_STATE)
        timer["state"] = STATE_RUNNING
        timer["ends_at"] = (
            dt_util.utcnow() + timedelta(seconds=timer.pop("remaining"))
        ).isoformat()
        self._schedule(child)
        self._changed()
        self._manager.log_entry(
            child, f"Studietimer hervat ({self._names(child, timer)[0]})"
        )

    def _extend(self, child: int, timer: dict[str, Any]) -> None:
        """Run a finished timer again for the extra minutes (can be repeated)."""
        if timer["state"] != STATE_FINISHED:
            raise TimerError(ERR_NOT_FINISHED)
        extra = self.settings(child)["extra_minutes"]
        if not extra:
            raise TimerError(ERR_EXTRA_NOT_SET)
        persistent_notification.async_dismiss(
            self._manager.hass, self._persistent_id(child)
        )
        timer["prewarned"] = True  # the pre-warning does not repeat
        timer["state"] = STATE_RUNNING
        timer["ends_at"] = (dt_util.utcnow() + timedelta(minutes=extra)).isoformat()
        timer["minutes"] = extra
        self._schedule(child)
        self._changed()
        self._manager.log_entry(
            child,
            f"Studietimer verlengd met {extra} min ({self._names(child, timer)[0]})",
        )

    def _stop(self, child: int, progress: int | None) -> None:
        timer = self._clear(child, log="Studietimer gestopt")
        assert timer is not None
        if progress is not None:
            title, _ = self._names(child, timer)
            self._manager.set_progress(timer["subtask"], progress)
            self._manager.log_entry(
                child, f"voortgang {progress}% bij stoppen ({title})"
            )

    def _done(self, child: int, source: str) -> None:
        timer = self._clear(child, log=None)
        assert timer is not None
        title, _ = self._names(child, timer)
        self._manager.set_progress(timer["subtask"], 100)
        how = "melding" if source == SOURCE_NOTIFICATION else "studietimer"
        self._manager.log_entry(child, f"deelstap afgerond via {how} ({title})")

    # -- the buttons of a notification -------------------------------------------------

    def parse_action(self, event: Event) -> tuple[str, int, str, str] | None:
        """``(verb, child, subtask uid, nonce)`` of a button of this entry, else None.

        Anything that is not a well-formed id of this entry and an existing timer with
        the same nonce (compared in constant time) is ignored: stale buttons do nothing.
        """
        action = event.data.get("action")
        if not isinstance(action, str):
            return None
        parts = action.split(_SEPARATOR)
        if len(parts) != 6 or parts[0] != ACTION_PREFIX:
            return None
        _, verb, entry_id, child_text, rest, nonce = parts
        child = _child_key(child_text)
        if verb not in VERBS or entry_id != self._manager.entry_id or child is None:
            return None
        timer = self._timers.get(child)
        uid = f"{self._manager.host}:{child}:{rest}"
        if (
            timer is None
            or timer["subtask"] != uid
            or not hmac.compare_digest(timer["nonce"].encode(), nonce.encode())
        ):
            return None
        return verb, child, uid, nonce


def action_coroutine(
    engine: TimerEngine, manager: HomeworkManager
) -> Callable[[Event], Coroutine[Any, Any, None]]:
    """The listener of ``mobile_app_notification_action`` for one entry."""

    async def handle(event: Event) -> None:
        parsed = engine.parse_action(event)
        if parsed is None:
            return
        verb, child, _, _ = parsed
        # The user behind the app is known for a real button press: check the rights.
        # Without a user in the event context the nonce and the configured target
        # (the only place the nonce was sent to) are the proof.
        if user_id := event.context.user_id:
            user = await manager.hass.auth.async_get_user(user_id)
            if (
                user is None
                or await manager.acting_mode(child, user_id, user.is_admin) is None
            ):
                _LOGGER.debug(
                    "A study timer button of a user without rights is ignored"
                )
                return
        try:
            engine.perform(child, verb, source=SOURCE_NOTIFICATION)
        except TimerError as err:
            _LOGGER.debug("A study timer button was not carried out: %s", err.code)

    return handle
