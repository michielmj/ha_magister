"""Context notes of the AI coach: books and tools in use, circumstances, agreements.

Notes live in the homework store of the config entry (key ``context``), per child.
There are four scopes: ``child``, ``subject``, ``item`` (an appointment) and ``period``
(a circumstance with a start and an end date, inside the sync window, optionally with
a daily study maximum for its days). A note is visible to everyone (``all``) or only to
parents (``parents``): a student's AI never receives the latter.

This module has no Home Assistant dependency beyond the service at the bottom; the
rights, the limits and the validation are the rules of milestone M13.
"""

from __future__ import annotations

import re
import uuid
from collections.abc import Callable, Iterable
from dataclasses import dataclass, replace
from datetime import date, timedelta
from typing import TYPE_CHECKING, Any, Final

import probatio
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import (
    HomeAssistant,
    ServiceCall,
    ServiceResponse,
    SupportsResponse,
    callback,
)
from homeassistant.exceptions import ServiceValidationError, Unauthorized
from homeassistant.helpers import config_validation as cv

from .api.homework import DAILY_MAX_MAX, DAILY_MAX_STEP
from .const import CHILD_ID, CHILD_NAME, CHILD_SHORT_NAME, CONF_CHILDREN, DOMAIN

if TYPE_CHECKING:
    from .homework import HomeworkManager

STORE_KEY: Final = "context"

SCOPE_CHILD: Final = "child"
SCOPE_SUBJECT: Final = "subject"
SCOPE_ITEM: Final = "item"
SCOPE_PERIOD: Final = "period"
SCOPES: Final = (SCOPE_CHILD, SCOPE_SUBJECT, SCOPE_ITEM, SCOPE_PERIOD)

VISIBILITY_ALL: Final = "all"
VISIBILITY_PARENTS: Final = "parents"
VISIBILITIES: Final = (VISIBILITY_ALL, VISIBILITY_PARENTS)

CREATED_BY_STUDENT: Final = "student"
CREATED_BY_PARENT: Final = "parent"

NOTE_ID: Final = re.compile(r"[0-9a-f]{8}")
TEXT_MAX: Final = 500
NOTES_MAX: Final = 50
PERIOD_MAX_MINUTES: Final = DAILY_MAX_MAX
PRUNE_ITEM_AFTER: Final = timedelta(days=14)

ERR_TEXT_TOO_LONG: Final = "text_too_long"
ERR_TOO_MANY_NOTES: Final = "too_many_notes"
ERR_UNKNOWN_SUBJECT: Final = "unknown_subject"
ERR_ITEM_NOT_FOUND: Final = "item_not_found"
ERR_INVALID_PERIOD: Final = "invalid_period"
ERR_INVALID_DAILY_MAX: Final = "invalid_daily_max"
ERR_CONTEXT_NOT_FOUND: Final = "context_not_found"
ERR_NOT_ALLOWED_FOR_ROLE: Final = "not_allowed_for_role"
ERR_INVALID_FORMAT: Final = "invalid_format"
ERR_USE_PROPOSAL: Final = "use_proposal"

SERVICE_CLEAR_COACH_CONTEXT: Final = "clear_coach_context"
ATTR_CONFIG_ENTRY_ID: Final = "config_entry_id"
ATTR_CHILD: Final = "child"
ATTR_SUBJECT: Final = "subject"

NOT_SET: Final[Any] = object()


class ContextError(Exception):
    """A context operation that fails with a code of the contract."""

    def __init__(self, code: str, message: str | None = None) -> None:
        """Remember the code and the explanation."""
        super().__init__(code)
        self.code = code
        self.message = message or code


@dataclass(frozen=True, slots=True)
class Note:
    """One context note of a child."""

    id: str
    scope: str
    text: str
    visibility: str
    created_by: str
    updated: str
    subject: str | None = None
    item: str | None = None
    start: date | None = None
    end: date | None = None
    daily_max_minutes: int | None = None
    # Item notes only: the day the appointment was first missing (pruned after 14 days).
    gone: date | None = None

    @property
    def is_period(self) -> bool:
        """Whether this is a circumstance."""
        return self.scope == SCOPE_PERIOD

    def expired(self, today: date) -> bool:
        """A circumstance whose end date lies before today."""
        return self.end is not None and self.end < today

    def visible_to(self, *, parent: bool) -> bool:
        """Whether the user of a role may see (and so change) the note."""
        return parent or self.visibility == VISIBILITY_ALL

    def stored(self) -> dict[str, Any]:
        """The form kept in the store."""
        data: dict[str, Any] = {
            "id": self.id,
            "scope": self.scope,
            "text": self.text,
            "visibility": self.visibility,
            "created_by": self.created_by,
            "updated": self.updated,
        }
        if self.subject is not None:
            data["subject"] = self.subject
        if self.item is not None:
            data["item"] = self.item
        if self.start is not None:
            data["start"] = self.start.isoformat()
        if self.end is not None:
            data["end"] = self.end.isoformat()
        if self.daily_max_minutes is not None:
            data["daily_max_minutes"] = self.daily_max_minutes
        if self.gone is not None:
            data["gone"] = self.gone.isoformat()
        return data

    def view(self, today: date, *, with_text: bool = True) -> dict[str, Any]:
        """The form the tools return (no internal fields)."""
        data: dict[str, Any] = {"id": self.id, "scope": self.scope}
        if self.subject is not None:
            data["subject"] = self.subject
        if self.item is not None:
            data["item"] = self.item
        if self.is_period:
            data["start"] = self.start.isoformat() if self.start else None
            data["end"] = self.end.isoformat() if self.end else None
            data["daily_max_minutes"] = self.daily_max_minutes
            data["expired"] = self.expired(today)
        data["visibility"] = self.visibility
        if with_text:
            data["text"] = self.text
        data["created_by"] = self.created_by
        data["updated"] = self.updated
        return data


# -- validation ---------------------------------------------------------------------


def clean_text(value: Any) -> str:
    """A note text: one line (whitespace collapsed), 1 to 500 characters."""
    if not isinstance(value, str):
        raise ContextError(ERR_INVALID_FORMAT, "`text` must be text")
    text = " ".join(value.split())
    if not text:
        raise ContextError(ERR_INVALID_FORMAT, "`text` must not be empty")
    if len(text) > TEXT_MAX:
        raise ContextError(
            ERR_TEXT_TOO_LONG, f"A note has at most {TEXT_MAX} characters"
        )
    return text


def check_daily_max(value: Any) -> int:
    """A period maximum: 0 to 480 minutes in steps of 15."""
    if isinstance(value, float) and value.is_integer():
        value = int(value)
    if (
        not isinstance(value, int)
        or isinstance(value, bool)
        or not 0 <= value <= PERIOD_MAX_MINUTES
        or value % DAILY_MAX_STEP
    ):
        raise ContextError(
            ERR_INVALID_DAILY_MAX,
            f"`daily_max_minutes` is 0 to {PERIOD_MAX_MINUTES} in steps of "
            f"{DAILY_MAX_STEP}",
        )
    return value


def _parse_date(value: Any) -> date | None:
    try:
        return date.fromisoformat(value) if isinstance(value, str) else None
    except ValueError:
        return None


def note_from_stored(raw: Any, today: date) -> Note | None:
    """A note from the store; ``None`` when it is not a valid note (it is dropped).

    A note whose id is not 8 lowercase hex characters (the form of the ids this module
    makes, and the only form the tools accept) is dropped, not given a new id: a new
    random id on every load would not be stable.
    """
    if not isinstance(raw, dict):
        return None
    note_id, scope, text = raw.get("id"), raw.get("scope"), raw.get("text")
    if (
        not isinstance(note_id, str)
        or not NOTE_ID.fullmatch(note_id)
        or scope not in SCOPES
        or not isinstance(text, str)
        or not text.strip()
    ):
        return None
    visibility = (
        raw["visibility"] if raw.get("visibility") in VISIBILITIES else VISIBILITY_ALL
    )
    created_by = (
        CREATED_BY_PARENT
        if raw.get("created_by") == CREATED_BY_PARENT
        else CREATED_BY_STUDENT
    )
    subject = raw.get("subject") if isinstance(raw.get("subject"), str) else None
    item = raw.get("item") if isinstance(raw.get("item"), str) else None
    start, end = _parse_date(raw.get("start")), _parse_date(raw.get("end"))
    if (scope == SCOPE_SUBJECT and not subject) or (
        scope == SCOPE_ITEM and not (item and item.isdigit() and item.isascii())
    ):
        return None
    if scope == SCOPE_PERIOD and (start is None or end is None or end < start):
        return None
    try:
        daily = (
            check_daily_max(raw["daily_max_minutes"]) if scope == SCOPE_PERIOD else None
        )
    except ContextError, KeyError:
        daily = None
    return Note(
        id=note_id,
        scope=scope,
        text=" ".join(text.split())[:TEXT_MAX],
        visibility=visibility,
        created_by=created_by,
        updated=str(raw.get("updated") or today.isoformat()),
        subject=subject if scope in (SCOPE_SUBJECT, SCOPE_ITEM) else None,
        item=item if scope == SCOPE_ITEM else None,
        start=start if scope == SCOPE_PERIOD else None,
        end=end if scope == SCOPE_PERIOD else None,
        daily_max_minutes=daily,
        gone=_parse_date(raw.get("gone")) if scope == SCOPE_ITEM else None,
    )


@dataclass(frozen=True, slots=True)
class EffectiveMax:
    """The daily maximum of one day and the circumstance that sets it (if any)."""

    minutes: int
    note: Note | None


class ContextBook:
    """The context notes of all children of one config entry."""

    def __init__(self, manager: HomeworkManager, on_change: Callable[[], None]) -> None:
        """Create the (empty) book; ``on_change`` saves and notifies."""
        self._manager = manager
        self._on_change = on_change
        self._notes: dict[int, list[Note]] = {}

    # -- storage ----------------------------------------------------------------

    def load(self, raw: Any, today: date) -> None:
        """Read the stored notes (anything invalid is dropped)."""
        self._notes = {}
        if not isinstance(raw, dict):
            return
        for key, notes in raw.items():
            if not isinstance(notes, list):
                continue
            try:
                child_id = int(key)
            except ValueError:
                continue
            seen: set[str] = set()
            clean: list[Note] = []
            for stored in notes:
                note = note_from_stored(stored, today)
                if note is not None and note.id not in seen:
                    seen.add(note.id)
                    clean.append(note)
            if clean:
                self._notes[child_id] = clean

    def to_stored(self) -> dict[str, list[dict[str, Any]]]:
        """The notes in the form of the store."""
        return {
            str(child_id): [note.stored() for note in notes]
            for child_id, notes in self._notes.items()
            if notes
        }

    def _store(self, child_id: int, notes: list[Note]) -> None:
        if notes:
            self._notes[child_id] = notes
        else:
            self._notes.pop(child_id, None)
        self._on_change()

    # -- reading ------------------------------------------------------------------

    def all_notes(self, child_id: int) -> list[Note]:
        """Every note of a child (for the code, not for a role)."""
        return list(self._notes.get(child_id, []))

    def visible(
        self,
        child_id: int,
        *,
        parent: bool,
        scope: str | None = None,
        subject: str | None = None,
        item: str | None = None,
    ) -> list[Note]:
        """The notes the role may see, optionally filtered, in a stable order."""
        wanted = subject.casefold() if subject else None
        found = [
            n
            for n in self._notes.get(child_id, [])
            if n.visible_to(parent=parent)
            and (scope is None or n.scope == scope)
            and (wanted is None or (n.subject or "").casefold() == wanted)
            and (item is None or n.item == item)
        ]
        order = {name: index for index, name in enumerate(SCOPES)}
        return sorted(
            found,
            key=lambda n: (order[n.scope], n.start or date.min, n.updated, n.id),
        )

    def for_item(
        self, child_id: int, item_id: str, subject: str, *, parent: bool
    ) -> list[Note]:
        """The notes of an item and of its subject that the role may see."""
        return [
            n
            for n in self.visible(child_id, parent=parent)
            if (n.scope == SCOPE_ITEM and n.item == item_id)
            or (
                n.scope == SCOPE_SUBJECT
                and subject != ""
                and (n.subject or "").casefold() == subject.casefold()
            )
        ]

    def active_count(self, child_id: int, today: date) -> int:
        """The notes that count towards the limit (circumstances not expired)."""
        return sum(1 for n in self._notes.get(child_id, []) if not n.expired(today))

    def subjects_with_notes(self, child_id: int) -> list[str]:
        """The subjects that have notes (subject and item notes), sorted."""
        found: dict[str, str] = {}
        for note in self._notes.get(child_id, []):
            if note.subject:
                found.setdefault(note.subject.casefold(), note.subject)
        return sorted(found.values(), key=str.casefold)

    def count(self, child_id: int, subject: str | None = None) -> int:
        """The notes of a child, or of one subject (subject and item notes)."""
        if subject is None:
            return len(self._notes.get(child_id, []))
        wanted = subject.casefold()
        return sum(
            1
            for n in self._notes.get(child_id, [])
            if (n.subject or "").casefold() == wanted
        )

    def statistics(self) -> dict[str, Any]:
        """Counts only: per scope, and how many notes are for parents only."""
        notes = [n for ns in self._notes.values() for n in ns]
        return {
            "notes": {s: sum(1 for n in notes if n.scope == s) for s in SCOPES},
            "parents_only": sum(1 for n in notes if n.visibility == VISIBILITY_PARENTS),
        }

    # -- the daily maximum ---------------------------------------------------------

    def effective_daily_max(
        self, child_id: int, day: date, *, parent: bool = True
    ) -> EffectiveMax:
        """The daily maximum of a day: the lowest circumstance, else the weekday's.

        The weekday value is that of the child for the weekday of ``day`` (since 1.9.0
        every weekday has its own). This is the one function the overview, the prompt
        and the card use. A circumstance applies to its days also after it has ended
        (past days). On a tie the circumstance that ``parent`` (the role) may see
        wins, so a student is not pointed at a parents-only period when a visible one
        explains the day.
        """
        candidates = [
            (
                note.daily_max_minutes,
                not note.visible_to(parent=parent),
                note.start,
                note.id,
                note,
            )
            for note in self._notes.get(child_id, [])
            if note.daily_max_minutes is not None
            and note.start is not None
            and note.end is not None
            and note.start <= day <= note.end
        ]
        normal = self._manager.weekday_max(child_id, day)
        if not candidates:
            return EffectiveMax(normal, None)
        minutes, _, _, _, note = min(candidates, key=lambda c: c[:4])
        if not note.visible_to(parent=parent) and minutes == normal:
            # A hidden period that changes nothing is not named to this role.
            return EffectiveMax(normal, None)
        return EffectiveMax(minutes, note)

    def daily_max_overrides(self, child_id: int) -> dict[str, int]:
        """The effective maximum of the days a period changes, in the sync window.

        Only days whose maximum differs from the normal value of that weekday.
        """
        if not any(
            n.daily_max_minutes is not None for n in self._notes.get(child_id, [])
        ):
            return {}
        first, after_last = self._manager.window_dates()
        result: dict[str, int] = {}
        day = first
        while day < after_last:
            effective = self.effective_daily_max(child_id, day)
            # A period that leaves the maximum as it is changes nothing to show.
            if (
                effective.note is not None
                and effective.minutes != self._manager.weekday_max(child_id, day)
            ):
                result[day.isoformat()] = effective.minutes
            day += timedelta(days=1)
        return result

    # -- checks that need the schedule -------------------------------------------------

    def window_subjects(self, child_id: int) -> dict[str, str]:
        """The subjects of the fetched window: ``{casefolded: name}``."""
        return {
            a.subject.casefold(): a.subject
            for a in self._manager.appointments(child_id)
            if a.subject
        }

    def resolve_subject(self, child_id: int, name: Any, *, parent: bool) -> str:
        """The subject of a child that matches ``name`` (case-insensitive)."""
        if not isinstance(name, str) or not name.strip():
            raise ContextError(ERR_INVALID_FORMAT, "`subject` must be a subject name")
        wanted = name.strip().casefold()
        known = self.window_subjects(child_id)
        for note in self.visible(child_id, parent=parent):
            if note.subject:
                known.setdefault(note.subject.casefold(), note.subject)
        if wanted not in known:
            raise ContextError(
                ERR_UNKNOWN_SUBJECT,
                "This child has no such subject; use a subject from get_schedule.",
            )
        return known[wanted]

    def check_period(self, start: date | None, end: date | None) -> tuple[date, date]:
        """A period inside the sync window with ``start`` <= ``end``."""
        first, after_last = self._manager.window_dates()
        last = after_last - timedelta(days=1)
        if start is None or end is None:
            raise ContextError(ERR_INVALID_PERIOD, "A circumstance needs start and end")
        if end < start or start < first or end > last:
            raise ContextError(
                ERR_INVALID_PERIOD,
                f"`start` <= `end`, both between {first.isoformat()} and "
                f"{last.isoformat()}",
            )
        return start, end

    def _check_period_change(
        self, note: Note, start: date | None, end: date | None
    ) -> tuple[date, date]:
        """The days after a change: only a given value is held to the window.

        A circumstance may have begun before the window (it moves along): a stored
        ``start`` is not checked again when only the end or the text changes.
        """
        first, after_last = self._manager.window_dates()
        last = after_last - timedelta(days=1)
        if start is not None and start < first:
            raise ContextError(
                ERR_INVALID_PERIOD,
                f"A new `start` is {first.isoformat()} or later; leave `start` out to "
                "keep the current first day.",
            )
        if end is not None and end > last:
            raise ContextError(
                ERR_INVALID_PERIOD,
                f"A new `end` is {last.isoformat()} or earlier.",
            )
        if end is not None and end < first:
            raise ContextError(
                ERR_INVALID_PERIOD,
                f"A new `end` is {first.isoformat()} or later.",
            )
        if start is not None and start > last:
            raise ContextError(
                ERR_INVALID_PERIOD,
                f"A new `start` is {last.isoformat()} or earlier.",
            )
        # A circumstance always has both days; the stored one stands for the other.
        new_start = start or note.start
        new_end = end or note.end
        assert new_start is not None and new_end is not None
        if new_end < new_start:
            if end is None:
                message = (
                    f"`start` must not be after the current last day "
                    f"({new_end.isoformat()}); give a later `end` as well."
                )
            elif start is None:
                message = (
                    f"`end` must not be before the current first day "
                    f"({new_start.isoformat()})."
                )
            else:
                message = "`start` must not be after `end`."
            raise ContextError(ERR_INVALID_PERIOD, message)
        return new_start, new_end

    # -- writing --------------------------------------------------------------------

    def _new_id(self, child_id: int) -> str:
        taken = {n.id for n in self._notes.get(child_id, [])}
        while (note_id := uuid.uuid4().hex[:8]) in taken:
            pass  # pragma: no cover
        return note_id

    def add(
        self,
        child_id: int,
        *,
        parent: bool,
        scope: str,
        text: Any,
        subject: Any = None,
        item: Any = None,
        start: date | None = None,
        end: date | None = None,
        daily_max_minutes: Any = None,
        visibility: str = VISIBILITY_ALL,
    ) -> Note:
        """Add a note; the rights, the fields of the scope and the limit are checked."""
        if scope not in SCOPES or visibility not in VISIBILITIES:
            raise ContextError(ERR_INVALID_FORMAT, "Unknown `scope` or `visibility`")
        if visibility == VISIBILITY_PARENTS and not parent:
            raise ContextError(
                ERR_NOT_ALLOWED_FOR_ROLE,
                "Only a parent can store a note that is for parents only.",
            )
        text = clean_text(text)
        given = {
            "subject": subject is not None,
            "item": item is not None,
            "start": start is not None,
            "end": end is not None,
            "daily_max_minutes": daily_max_minutes is not None,
        }
        allowed = {
            SCOPE_CHILD: set(),
            SCOPE_SUBJECT: {"subject"},
            SCOPE_ITEM: {"item"},
            SCOPE_PERIOD: {"start", "end", "daily_max_minutes"},
        }[scope]
        extra = [n for n, present in given.items() if present and n not in allowed]
        if extra:
            raise ContextError(
                ERR_INVALID_FORMAT,
                f"A {scope} note does not take: {', '.join(extra)}",
            )
        today = self._manager.today()
        resolved_subject: str | None = None
        item_id: str | None = None
        period: tuple[date, date] | None = None
        daily: int | None = None
        if scope == SCOPE_SUBJECT:
            resolved_subject = self.resolve_subject(child_id, subject, parent=parent)
        elif scope == SCOPE_ITEM:
            if not isinstance(item, str) or not (item.isdigit() and item.isascii()):
                raise ContextError(ERR_INVALID_FORMAT, "The id is not an item id")
            appointment = self._manager.find_appointment(
                child_id, self._manager.uid_of(child_id, int(item))
            )
            if appointment is None:
                raise ContextError(ERR_ITEM_NOT_FOUND, "Homework item not found")
            item_id = str(appointment.id)
            resolved_subject = appointment.subject or None
        elif scope == SCOPE_PERIOD:
            period = self.check_period(start, end)
            daily = (
                check_daily_max(daily_max_minutes)
                if daily_max_minutes is not None
                else None
            )
        counts = not (period and period[1] < today)
        if counts and self.active_count(child_id, today) >= NOTES_MAX:
            raise ContextError(
                ERR_TOO_MANY_NOTES,
                f"At most {NOTES_MAX} notes per child; delete a note first.",
            )
        note = Note(
            id=self._new_id(child_id),
            scope=scope,
            text=text,
            visibility=visibility,
            created_by=CREATED_BY_PARENT if parent else CREATED_BY_STUDENT,
            updated=today.isoformat(),
            subject=resolved_subject,
            item=item_id,
            start=period[0] if period else None,
            end=period[1] if period else None,
            daily_max_minutes=daily,
        )
        self._store(child_id, [*self._notes.get(child_id, []), note])
        return note

    def add_accepted_period(
        self,
        child_id: int,
        *,
        start: date,
        end: date,
        text: str,
        minutes: int,
        created_by: str,
    ) -> Note:
        """Add the circumstance of an accepted proposal (the limit still holds)."""
        today = self._manager.today()
        if self.active_count(child_id, today) >= NOTES_MAX:
            raise ContextError(
                ERR_TOO_MANY_NOTES,
                f"At most {NOTES_MAX} notes per child; delete a note first.",
            )
        note = Note(
            id=self._new_id(child_id),
            scope=SCOPE_PERIOD,
            text=clean_text(text),
            visibility=VISIBILITY_ALL,
            created_by=created_by,
            updated=today.isoformat(),
            start=start,
            end=end,
            daily_max_minutes=check_daily_max(minutes),
        )
        self._store(child_id, [*self._notes.get(child_id, []), note])
        return note

    def find(self, child_id: int, note_id: str, *, parent: bool) -> Note:
        """A note of this child that the role may see (else ``context_not_found``)."""
        for note in self._notes.get(child_id, []):
            if note.id == note_id and note.visible_to(parent=parent):
                return note
        raise ContextError(ERR_CONTEXT_NOT_FOUND, "No such note")

    def _check_change_allowed(self, note: Note, *, parent: bool) -> None:
        if not parent and note.created_by == CREATED_BY_PARENT:
            raise ContextError(
                ERR_NOT_ALLOWED_FOR_ROLE,
                "This note was made by a parent; only a parent can change it.",
            )

    def update(
        self,
        child_id: int,
        note_id: str,
        *,
        parent: bool,
        text: Any = NOT_SET,
        start: date | None = None,
        end: date | None = None,
        daily_max_minutes: Any = NOT_SET,
        visibility: str | None = None,
        protect_maximum: bool = False,
    ) -> tuple[Note, bool]:
        """Change a note; the second value says whether anything changed.

        With ``protect_maximum`` (the AI), a circumstance that keeps a daily maximum
        may not cover a day outside its current days: that is a proposal.
        """
        note = self.find(child_id, note_id, parent=parent)
        self._check_change_allowed(note, parent=parent)
        if visibility is not None and visibility not in VISIBILITIES:
            raise ContextError(ERR_INVALID_FORMAT, "Unknown `visibility`")
        if visibility == VISIBILITY_PARENTS and not parent:
            raise ContextError(
                ERR_NOT_ALLOWED_FOR_ROLE,
                "Only a parent can store a note that is for parents only.",
            )
        if (
            text is NOT_SET
            and start is None
            and end is None
            and daily_max_minutes is NOT_SET
            and visibility is None
        ):
            raise ContextError(ERR_INVALID_FORMAT, "Give at least one field to change")
        if not note.is_period and (
            start is not None or end is not None or daily_max_minutes is not NOT_SET
        ):
            raise ContextError(
                ERR_INVALID_FORMAT,
                "`start`, `end` and `daily_max_minutes` are for circumstances only",
            )
        changes: dict[str, Any] = {}
        if text is not NOT_SET:
            changes["text"] = clean_text(text)
        if visibility is not None:
            changes["visibility"] = visibility
        if note.is_period:
            if start is not None or end is not None:
                changes["start"], changes["end"] = self._check_period_change(
                    note, start, end
                )
            if daily_max_minutes is not NOT_SET:
                changes["daily_max_minutes"] = (
                    None
                    if daily_max_minutes is None
                    else check_daily_max(daily_max_minutes)
                )
        updated = replace(note, **changes)
        if updated == note:
            return note, False
        if (
            protect_maximum
            and updated.daily_max_minutes is not None
            and updated.visibility == VISIBILITY_PARENTS
            and note.visibility != VISIBILITY_PARENTS
        ):
            raise ContextError(
                ERR_INVALID_FORMAT,
                "A circumstance with a daily maximum stays visible to the student "
                "(`visibility` `all`): the student decides about their own time. "
                "Remove the maximum in the same call to make it parents-only.",
            )
        if protect_maximum and updated.daily_max_minutes is not None:
            assert updated.start and updated.end and note.start and note.end
            if updated.start < note.start or updated.end > note.end:
                raise ContextError(
                    ERR_USE_PROPOSAL,
                    "The AI cannot move or extend a circumstance that has a daily "
                    "maximum: the student decides. Make a proposal with "
                    "propose_daily_max, or shrink the days.",
                )
        today = self._manager.today()
        if (
            note.expired(today)
            and not updated.expired(today)
            and self.active_count(child_id, today) >= NOTES_MAX
        ):
            raise ContextError(
                ERR_TOO_MANY_NOTES,
                f"At most {NOTES_MAX} notes per child; delete a note first.",
            )
        # The last editor owns the note: a student cannot overwrite a parent's edit.
        updated = replace(
            updated,
            updated=today.isoformat(),
            created_by=CREATED_BY_PARENT if parent else note.created_by,
        )
        self._store(
            child_id,
            [updated if n.id == note.id else n for n in self._notes[child_id]],
        )
        return updated, True

    def delete(self, child_id: int, note_id: str, *, parent: bool) -> Note:
        """Delete one note (the same rights as changing it)."""
        note = self.find(child_id, note_id, parent=parent)
        self._check_change_allowed(note, parent=parent)
        self._store(child_id, [n for n in self._notes[child_id] if n.id != note.id])
        return note

    def clear(self, child_id: int, subject: str | None = None) -> int:
        """Delete all notes of a child, or of one subject; the number deleted."""
        doomed = {n.id for n in self.matching(child_id, subject)}
        if doomed:
            self._store(
                child_id, [n for n in self._notes[child_id] if n.id not in doomed]
            )
        return len(doomed)

    def matching(self, child_id: int, subject: str | None = None) -> list[Note]:
        """The notes ``clear`` deletes: all of the child, or those of one subject."""
        wanted = subject.casefold() if subject else None
        return [
            n
            for n in self._notes.get(child_id, [])
            if wanted is None or (n.subject or "").casefold() == wanted
        ]

    def drop_children(self, keep: Iterable[int]) -> None:
        """Forget the notes of children that are no longer part of the entry."""
        stay = set(keep)
        gone = [child_id for child_id in self._notes if child_id not in stay]
        for child_id in gone:
            del self._notes[child_id]
        if gone:
            self._on_change()

    def prune(
        self, today: date, window_start: date, present_items: set[str] | None
    ) -> bool:
        """Drop periods that ended before the window and notes of gone items.

        ``present_items`` are the uids of the appointments in the window (``None``
        when nothing was fetched yet: item notes stay). Item notes go 14 days after
        their appointment left the window, like the other planner data of the item.
        """
        changed = False
        for child_id, notes in list(self._notes.items()):
            kept: list[Note] = []
            for note in notes:
                if note.is_period and note.end is not None and note.end < window_start:
                    continue
                if note.scope == SCOPE_ITEM and present_items is not None:
                    uid = self._manager.uid_of(child_id, int(note.item or 0))
                    if uid in present_items:
                        note = replace(note, gone=None)
                    elif note.gone is None:
                        note = replace(note, gone=today)
                    elif today - note.gone > PRUNE_ITEM_AFTER:
                        continue
                kept.append(note)
            if kept != notes:
                changed = True
                if kept:
                    self._notes[child_id] = kept
                else:
                    del self._notes[child_id]
        return changed


# -- text for the AI --------------------------------------------------------------


def day_ranges(values: dict[date, int]) -> list[tuple[date, date, int]]:
    """Consecutive days with the same value as ``(first, last, value)``."""
    ranges: list[tuple[date, date, int]] = []
    for day in sorted(values):
        if ranges and ranges[-1][1] + timedelta(days=1) == day:
            first, _, value = ranges[-1]
            if value == values[day]:
                ranges[-1] = (first, day, value)
                continue
        ranges.append((day, day, values[day]))
    return ranges


# -- the service ---------------------------------------------------------------------


def _clear_service_schema() -> probatio.Schema:
    return probatio.Schema(
        {
            probatio.Required(ATTR_CONFIG_ENTRY_ID): cv.string,
            probatio.Required(ATTR_CHILD): cv.string,
            probatio.Optional(ATTR_SUBJECT): cv.string,
        }
    )


async def _async_clear_coach_context(call: ServiceCall) -> ServiceResponse:
    """Delete the context of a child (or one subject) and return the number deleted."""
    hass = call.hass
    if (user_id := call.context.user_id) is not None:
        user = await hass.auth.async_get_user(user_id)
        if user is None or not user.is_admin:
            raise Unauthorized(context=call.context)
    entry = hass.config_entries.async_get_entry(call.data[ATTR_CONFIG_ENTRY_ID])
    if (
        entry is None
        or entry.domain != DOMAIN
        or entry.state is not ConfigEntryState.LOADED
    ):
        raise ServiceValidationError(
            translation_domain=DOMAIN, translation_key="entry_not_loaded"
        )
    wanted = str(call.data[ATTR_CHILD]).strip().casefold()
    matches = {
        int(c[CHILD_ID])
        for c in entry.data[CONF_CHILDREN]
        if wanted
        in (
            str(c[CHILD_ID]),
            str(c[CHILD_NAME]).casefold(),
            str(c[CHILD_SHORT_NAME]).casefold(),
        )
    }
    if len(matches) > 1:
        raise ServiceValidationError(
            translation_domain=DOMAIN, translation_key="child_ambiguous"
        )
    if not matches:
        raise ServiceValidationError(
            translation_domain=DOMAIN, translation_key="child_not_found"
        )
    (child_id,) = matches
    book = entry.runtime_data.homework.context
    subject = (call.data.get(ATTR_SUBJECT) or "").strip() or None
    return {"deleted": book.clear(child_id, subject)}


@callback
def async_register_context_service(hass: HomeAssistant) -> None:
    """Register ``magister.clear_coach_context`` (at integration setup)."""
    hass.services.async_register(
        DOMAIN,
        SERVICE_CLEAR_COACH_CONTEXT,
        _async_clear_coach_context,
        schema=_clear_service_schema(),
        supports_response=SupportsResponse.OPTIONAL,
    )
