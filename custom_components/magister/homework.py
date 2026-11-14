"""Homework planner state: progress store, items per child and weights.

Progress and manual labels live in Home Assistant only (a ``Store`` per config entry);
nothing is written back to Magister. Changing progress, labels or weights recomputes
locally and never calls the Magister API.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import TYPE_CHECKING, Any, Final

import probatio
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util

from .api.homework import (
    CREATED_BY,
    CREATED_BY_USER,
    LABEL_KINDS,
    MAX_SUBTASKS,
    MODE_DISABLE,
    MODE_REPLACE,
    NOTE_MAX,
    OVERRIDE_MODES,
    PERIOD_NEXT_WEEK,
    PERIODS,
    SUBTASK_TITLE_MAX,
    EffectiveState,
    Entry,
    HomeworkItem,
    LabelOption,
    ManualLabel,
    Override,
    PeriodSummary,
    Subtask,
    Weights,
    active_subtasks,
    default_label_options,
    derived_progress,
    effective_state,
    effective_weights,
    entries_in_period,
    extract_homework,
    homework_entries,
    homework_periods,
    item_uid,
    magister_info_type,
    magister_label_option,
    magister_label_text,
    next_week_fits,
    parse_label_options,
    skipped_days,
    split_subtask_uid,
    subtask_current_date,
    subtask_date_allowed,
    subtask_overdue,
    subtask_uid,
    summarize_entries,
    uid_child_id,
)
from .api.mapping import CANCELLED_STATUSES, LOCAL_TZ
from .api.models import Appointment
from .const import CONF_HOST, CONF_LABELS, CONF_WEIGHTS, DOMAIN
from .coordinator import fetch_window

if TYPE_CHECKING:
    from .coordinator import MagisterConfigEntry, MagisterCoordinator

STORE_VERSION: Final = 1
STORE_MINOR_VERSION: Final = 5
SAVE_DELAY: Final = 5.0
PRUNE_AFTER: Final = timedelta(days=14)

# Progress entry keys.
PROGRESS: Final = "progress"
LAST_PARTIAL: Final = "last_partial"
UPDATED: Final = "updated"
GONE: Final = "gone"
LABELS: Final = "labels"
OVERRIDE: Final = "override"
SUBTASKS: Final = "subtasks"

# Errors of the label commands; the WebSocket API uses them as error codes and the
# services as ``homework_<code>`` exception translation keys.
ERR_APPOINTMENT_NOT_FOUND: Final = "appointment_not_found"
ERR_LABEL_NOT_FOUND: Final = "label_not_found"
ERR_LABEL_EXISTS: Final = "label_exists"
ERR_LABEL_NOT_ON_APPOINTMENT: Final = "label_not_on_appointment"
ERR_INVALID_DATE: Final = "invalid_date"
# Errors of the subtask commands (same transport as the label errors).
ERR_ITEM_NOT_FOUND: Final = "item_not_found"
ERR_ITEM_DISABLED: Final = "item_disabled"
ERR_SUBTASK_NOT_FOUND: Final = "subtask_not_found"
ERR_TOO_MANY_SUBTASKS: Final = "too_many_subtasks"
ERR_NOTHING_TO_UPDATE: Final = "nothing_to_update"
ERR_NO_MAGISTER_LABEL: Final = "no_magister_label"
# Invalid input: the WebSocket API reports both as ``invalid_format``.
ERR_LABEL_REQUIRED: Final = "label_required"
ERR_LABEL_IS_ORIGINAL: Final = "label_is_original"

_SUBSCRIBERS: Final = f"{DOMAIN}_homework_subscribers"


@dataclass(frozen=True, slots=True)
class PeriodData:
    """One progress period of a child: the single source for sensors and payload."""

    first: date
    end: date
    items: list[HomeworkItem]
    weights: Weights
    summary: PeriodSummary

    @property
    def effective_weights(self) -> dict[str, Any]:
        """The weights in use for the items of the period."""
        return effective_weights(self.items, self.weights)


type Payload = dict[str, Any]
type Subscriber = Callable[[Payload], None]


def strict_progress(value: Any) -> int:
    """Validate a progress value: a real integer 0-100 (booleans are rejected)."""
    if isinstance(value, bool) or not isinstance(value, int):
        raise probatio.Invalid("progress must be an integer")
    if not 0 <= value <= 100:
        raise probatio.Invalid("progress must be between 0 and 100")
    return value


def service_progress(value: Any) -> int:
    """Like ``strict_progress`` but also accepts whole numbers as text or float."""
    if isinstance(value, bool):
        raise probatio.Invalid("progress must be an integer")
    try:
        number = float(value)
    except TypeError, ValueError:
        raise probatio.Invalid("progress must be an integer") from None
    if not number.is_integer():
        raise probatio.Invalid("progress must be an integer")
    return strict_progress(int(number))


class LabelError(Exception):
    """A label command that cannot be carried out (``code`` names the reason)."""

    def __init__(self, code: str) -> None:
        """Remember the error code."""
        super().__init__(code)
        self.code = code


def note_text(value: Any) -> str:
    """Validate a label note: text of at most 200 characters, trimmed."""
    if not isinstance(value, str):
        raise probatio.Invalid("note must be text")
    text = value.strip()
    if len(text) > NOTE_MAX:
        raise probatio.Invalid(f"note must be at most {NOTE_MAX} characters")
    return text


def subtask_title(value: Any) -> str:
    """Validate a subtask title: 1-100 characters, trimmed."""
    if not isinstance(value, str):
        raise probatio.Invalid("title must be text")
    text = value.strip()
    if not text:
        raise probatio.Invalid("title must not be empty")
    if len(text) > SUBTASK_TITLE_MAX:
        raise probatio.Invalid(f"title must be at most {SUBTASK_TITLE_MAX} characters")
    return text


def new_label_id() -> str:
    """A new stable id for a label option."""
    return uuid.uuid4().hex[:8]


class _HomeworkStore(Store[dict[str, Any]]):
    """The progress store, with its migration from earlier schema versions."""

    async def _async_migrate_func(
        self, old_major_version: int, old_minor_version: int, old_data: dict[str, Any]
    ) -> dict[str, Any]:
        """1.1 (progress only) to 1.2 (adds ``labels`` to every item).

        1.2 to 1.3 adds the optional ``override`` per item, 1.3 to 1.4 the optional
        ``subtasks`` list and 1.4 to 1.5 the optional ``created_by`` of a subtask
        (a missing value reads as ``"user"``): none of these needs a migration.
        The major version stays 1 so that an older release can still read the file.
        """
        if old_major_version == 1:
            if old_minor_version < 2:
                items = old_data.get("items")
                return {
                    "items": {
                        uid: {LABELS: [], **entry}
                        for uid, entry in (
                            items if isinstance(items, dict) else {}
                        ).items()
                        if isinstance(entry, dict)
                    }
                }
            return old_data
        raise NotImplementedError  # pragma: no cover


def _clamp(value: Any) -> int:
    """A progress value as int within 0-100."""
    try:
        return min(max(int(value), 0), 100)
    except TypeError, ValueError:
        return 0


class HomeworkManager:
    """Items, progress and weights of all children of one config entry."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: MagisterConfigEntry,
        coordinator: MagisterCoordinator,
    ) -> None:
        """Create the manager (call ``async_load`` before use)."""
        self.hass = hass
        self._entry = entry
        self._coordinator = coordinator
        self._host: str = entry.data[CONF_HOST]
        self._store = _HomeworkStore(
            hass,
            STORE_VERSION,
            f"{DOMAIN}.homework.{entry.entry_id}",
            minor_version=STORE_MINOR_VERSION,
        )
        self._progress: dict[str, dict[str, Any]] = {}
        self._listeners: list[CALLBACK_TYPE] = []
        self._label_listeners: list[CALLBACK_TYPE] = []
        self._items: dict[int, list[HomeworkItem]] = {}
        self._items_source: Mapping[int, Any] | None = None
        self._by_uid: dict[str, HomeworkItem] = {}
        self._effective: dict[str, EffectiveState] = {}
        self._dirty = False

    async def async_load(self) -> None:
        """Read the stored progress."""
        stored = await self._store.async_load()
        raw = stored.get("items") if isinstance(stored, dict) else None
        if isinstance(raw, dict):
            for uid, entry in raw.items():
                if not isinstance(entry, dict):
                    continue
                clean = {
                    PROGRESS: _clamp(entry.get(PROGRESS)),
                    LAST_PARTIAL: min(_clamp(entry.get(LAST_PARTIAL)), 99),
                    UPDATED: str(entry.get(UPDATED) or ""),
                }
                if isinstance(gone := entry.get(GONE), str):
                    clean[GONE] = gone
                clean[LABELS] = _clean_labels(entry.get(LABELS))
                if (override := _clean_override(entry.get(OVERRIDE))) is not None:
                    clean[OVERRIDE] = override
                if subtasks := _clean_subtasks(entry.get(SUBTASKS)):
                    clean[SUBTASKS] = subtasks
                self._progress[str(uid)] = clean
        self.async_prune()

    @callback
    def async_start(self) -> None:
        """Prune and notify on each coordinator update."""
        self._entry.async_on_unload(
            self._coordinator.async_add_listener(self._handle_coordinator_update)
        )

    async def async_flush(self) -> None:
        """Write unsaved progress now (the entry is being unloaded)."""
        if self._dirty:
            self._dirty = False
            await self._store.async_save(self._data())

    # -- items --------------------------------------------------------------

    def items(self, child_id: int) -> list[HomeworkItem]:
        """Homework items of a child in the fetch window (cached per refresh)."""
        data = self._coordinator.data or {}
        if self._items_source is not data:
            self._items_source = data
            self._effective = {}
            manual = self._manual_labels()
            overrides = self._overrides()
            subtasks = self._subtasks()
            self._items = {
                child: extract_homework(
                    appointments, self._host, child, manual, overrides, subtasks
                )
                for child, appointments in data.items()
            }
            self._by_uid = {i.uid: i for items in self._items.values() for i in items}
        return self._items.get(child_id, [])

    def _refresh(self) -> None:
        """Rebuild the item caches when the coordinator data changed."""
        self.items(0)

    def _invalidate(self) -> None:
        """Rebuild the items (and their effective state) on next use."""
        self._items_source = None

    def effective(self, item: HomeworkItem) -> EffectiveState:
        """The effective state of an item (labels, overrides and weights applied)."""
        self._refresh()
        state = self._effective.get(item.uid)
        if state is None:
            weights = self.weights(uid_child_id(item.uid) or 0)
            state = self._effective[item.uid] = effective_state(item, weights)
        return state

    def _overrides(self) -> dict[str, Override]:
        """Stored overrides by uid; a replacement whose option is gone is left out."""
        options: dict[int, dict[str, LabelOption]] = {}
        result: dict[str, Override] = {}
        for uid, entry in self._progress.items():
            stored = entry.get(OVERRIDE)
            if stored is None or (child := uid_child_id(uid)) is None:
                continue
            if stored["mode"] == MODE_DISABLE:
                result[uid] = Override(MODE_DISABLE)
                continue
            if child not in options:
                options[child] = {o.id: o for o in self.label_options(child)}
            if (option := options[child].get(stored["label"])) is not None:
                result[uid] = Override(MODE_REPLACE, option)
        return result

    def _subtasks(self) -> dict[str, tuple[Subtask, ...]]:
        """The stored subtasks by item uid."""
        return {
            uid: tuple(_subtask_from_stored(s) for s in entry[SUBTASKS])
            for uid, entry in self._progress.items()
            if entry.get(SUBTASKS)
        }

    def _manual_labels(self) -> dict[str, tuple[ManualLabel, ...]]:
        """The stored manual labels by item uid, resolved against the options."""
        options: dict[int, dict[str, LabelOption]] = {}
        result: dict[str, tuple[ManualLabel, ...]] = {}
        for uid, entry in self._progress.items():
            if not entry[LABELS] or (child := uid_child_id(uid)) is None:
                continue
            if child not in options:
                options[child] = {o.id: o for o in self.label_options(child)}
            labels = tuple(
                ManualLabel(
                    option.id,
                    option.name,
                    option.kind,
                    stored["note"],
                    stored["added"],
                )
                for stored in entry[LABELS]
                if (option := options[child].get(stored["id"])) is not None
            )
            if labels:
                result[uid] = labels
        return result

    def uid_of(self, child_id: int, appointment_id: int) -> str:
        """The item uid of an appointment of a child."""
        return item_uid(self._host, child_id, appointment_id)

    def title_labels(
        self, child_id: int, appointment_id: int
    ) -> tuple[list[str], str | None]:
        """Manual label names and the Magister label text for a calendar title.

        The text is ``None`` for the original label, ``""`` when it is disabled and
        ``Proefwerk->Huiswerk`` for a replacement.
        """
        item = self.find_item(child_id, self.uid_of(child_id, appointment_id))
        if item is None:
            return [], None
        return [label.name for label in item.manual_labels], magister_label_text(item)

    def find_appointment(self, child_id: int, uid: str) -> Appointment | None:
        """The appointment of ``child_id`` with item uid ``uid`` in the window."""
        return next(
            (
                a
                for a in self._appointments(child_id)
                if self.uid_of(child_id, a.id) == uid
            ),
            None,
        )

    def appointments_on(self, child_id: int, day: date) -> list[Appointment]:
        """The appointments of a child on a local date, in item order."""
        data = self._coordinator.data or {}
        found = [
            a
            for a in data.get(child_id, [])
            if a.start.astimezone(LOCAL_TZ).date() == day
        ]
        return sorted(
            found,
            key=lambda a: (a.start, a.period_start or 0, self.uid_of(child_id, a.id)),
        )

    def window_dates(self) -> tuple[date, date]:
        """The fetch window as ``(first day, day after the last)``."""
        start, end = fetch_window(
            dt_util.now(), self._coordinator.weeks_back, self._coordinator.weeks_ahead
        )
        return start.astimezone(LOCAL_TZ).date(), end.astimezone(LOCAL_TZ).date()

    # -- manual labels --------------------------------------------------------

    def label_options(self, child_id: int) -> list[LabelOption]:
        """The label options of a child (the five Magister names by default)."""
        stored = self._entry.options.get(CONF_LABELS)
        raw = stored.get(str(child_id)) if isinstance(stored, Mapping) else None
        parsed = parse_label_options(raw)
        return default_label_options() if parsed is None else parsed

    def label_in_use(self, child_id: int, label_id: str) -> bool:
        """Whether a present appointment has this manual label or replacement."""
        present = {self.uid_of(child_id, a.id) for a in self._appointments(child_id)}
        # An override only counts while its appointment has a Magister label.
        with_label = {
            self.uid_of(child_id, a.id)
            for a in self._appointments(child_id)
            if magister_info_type(a) is not None
        }
        return any(
            any(stored["id"] == label_id for stored in entry[LABELS])
            or (
                uid in with_label
                and (entry.get(OVERRIDE) or {}).get("label") == label_id
            )
            for uid, entry in self._progress.items()
            if uid in present
        )

    def _appointments(self, child_id: int) -> list[Appointment]:
        return list((self._coordinator.data or {}).get(child_id, []))

    @callback
    def drop_label_references(self, child_id: int, label_id: str) -> None:
        """Forget a deleted label on appointments that are no longer present."""
        changed = False
        for uid in list(self._progress):
            entry = self._progress[uid]
            if uid_child_id(uid) != child_id:
                continue
            touched = False
            kept = [s for s in entry[LABELS] if s["id"] != label_id]
            if len(kept) != len(entry[LABELS]):
                entry[LABELS] = kept
                touched = True
            if (entry.get(OVERRIDE) or {}).get("label") == label_id:
                del entry[OVERRIDE]
                touched = True
            if touched:
                self._drop_if_empty(uid)
                changed = True
        if changed:
            self._labels_changed()

    @callback
    def set_override(
        self, child_id: int, uid: str, override: Override | None
    ) -> HomeworkItem | None:
        """Replace, disable (or with ``None`` restore) the Magister label of an item.

        Restoring also removes a stored override of an appointment that lost its
        Magister label; the result is ``None`` when the appointment is then not in the
        planner. Replacing or disabling needs a Magister label.
        """
        appointment = self.find_appointment(child_id, uid)
        if appointment is None:
            raise LabelError(ERR_APPOINTMENT_NOT_FOUND)
        info_type = magister_info_type(appointment)
        stored: dict[str, str] | None = None
        if override is not None:
            if info_type is None:
                raise LabelError(ERR_NO_MAGISTER_LABEL)
            stored = {"mode": override.mode}
            if override.label is not None:
                if override.label.id == magister_label_option(info_type).id:
                    raise LabelError(ERR_LABEL_IS_ORIGINAL)
                stored["label"] = override.label.id
        entry = self._progress.get(uid)
        if (entry.get(OVERRIDE) if entry else None) != stored:
            if stored is None:
                assert entry is not None
                del entry[OVERRIDE]
                self._drop_if_empty(uid)
            else:
                if entry is None:
                    entry = self._progress[uid] = _blank_entry()
                entry[OVERRIDE] = stored
            self._labels_changed()
        return self.find_item(child_id, uid)

    def stored_override(self, uid: str) -> dict[str, str] | None:
        """A copy of the stored override entry of an item (``None`` when none)."""
        entry = self._progress.get(uid)
        stored = entry.get(OVERRIDE) if entry else None
        return dict(stored) if stored else None

    @callback
    def add_label(
        self, child_id: int, uid: str, label: LabelOption, note: str
    ) -> HomeworkItem:
        """Add a manual label to an appointment of the child."""
        if self.find_appointment(child_id, uid) is None:
            raise LabelError(ERR_APPOINTMENT_NOT_FOUND)
        entry = self._progress.get(uid)
        if entry is not None and any(s["id"] == label.id for s in entry[LABELS]):
            raise LabelError(ERR_LABEL_EXISTS)
        if entry is None:
            entry = self._progress[uid] = _blank_entry()
        entry[LABELS].append(
            {"id": label.id, "note": note, "added": dt_util.utcnow().isoformat()}
        )
        self._labels_changed()
        item = self.find_item(child_id, uid)
        assert item is not None
        return item

    @callback
    def remove_label(
        self, child_id: int, uid: str, label: LabelOption
    ) -> HomeworkItem | None:
        """Remove a manual label; ``None`` when the item left the planner."""
        if self.find_appointment(child_id, uid) is None:
            raise LabelError(ERR_APPOINTMENT_NOT_FOUND)
        entry = self._progress.get(uid)
        kept = [s for s in entry[LABELS] if s["id"] != label.id] if entry else []
        if entry is None or len(kept) == len(entry[LABELS]):
            raise LabelError(ERR_LABEL_NOT_ON_APPOINTMENT)
        entry[LABELS] = kept
        self._drop_if_empty(uid)
        self._labels_changed()
        return self.find_item(child_id, uid)

    def _labels_changed(self) -> None:
        self._invalidate()
        self._changed()
        for listener in list(self._label_listeners):
            listener()

    def _drop_if_empty(self, uid: str) -> None:
        entry = self._progress.get(uid)
        if (
            entry is not None
            and not entry[LABELS]
            and OVERRIDE not in entry
            and not entry.get(SUBTASKS)
            and entry[PROGRESS] == 0
            and entry[LAST_PARTIAL] == 0
        ):
            del self._progress[uid]

    def find_item(self, child_id: int, uid: str) -> HomeworkItem | None:
        """The item of ``child_id`` with ``uid``, ``None`` when unknown."""
        self.items(child_id)
        item = self._by_uid.get(uid)
        return item if item is not None and uid_child_id(uid) == child_id else None

    # -- periods ------------------------------------------------------------

    def period_fits(self, period: str) -> bool:
        """Whether a period lies within the fetch window (only next week can not)."""
        return period != PERIOD_NEXT_WEEK or next_week_fits(
            self._coordinator.weeks_ahead
        )

    def entries(self, child_id: int, today: date) -> list[Entry]:
        """The progress entries of a child: items without subtasks plus subtasks."""
        return homework_entries(
            self.items(child_id), self.progress, self.weights(child_id), today
        )

    def period(self, child_id: int, period: str, today: date) -> PeriodData:
        """Items, weights and weighted progress of a child for a period."""
        first, end = homework_periods(today)[period]
        skipped = skipped_days(period, today)
        entries = entries_in_period(
            self.entries(child_id, today), (first, end), skipped
        )
        counted = {entry.item_uid for entry in entries}
        items = [
            item
            for item in self.items(child_id)
            if item.uid in counted
            or (
                self.effective(item).disabled
                and first <= item.due_date < end
                and item.due_date not in skipped
            )
        ]
        return PeriodData(
            first,
            end,
            items,
            self.weights(child_id),
            summarize_entries(entries),
        )

    def due_open_count(self, child_id: int, today: date) -> int:
        """Open entries on today or later (the number shown for the to-do list).

        Entries are the items without subtasks and the subtasks (on their current date).
        """
        return sum(
            1
            for entry in self.entries(child_id, today)
            if entry.day >= today and entry.progress < 100
        )

    def is_completed(self, item: HomeworkItem) -> bool:
        """Completed: progress 100 (derived with subtasks), or the item is disabled."""
        return self.progress(item.uid) >= 100 or self.effective(item).disabled

    def active_subtasks(self, item: HomeworkItem) -> tuple[Subtask, ...]:
        """The subtasks of an item that count (none while it is disabled)."""
        return active_subtasks(item, self.effective(item))

    @staticmethod
    def today() -> date:
        """The local (Amsterdam) date."""
        return dt_util.now(LOCAL_TZ).date()

    # -- progress -----------------------------------------------------------

    def progress(self, uid: str) -> int:
        """Progress in percent (0 when untouched).

        Of a subtask uid: the subtask's progress. Of an item with active subtasks: the
        derived progress (their rounded mean).
        """
        if split_subtask_uid(uid) is not None:
            sub = self.find_subtask(uid)
            return sub.progress if sub else 0
        item = self._item_by_uid(uid)
        if item is not None and (subtasks := self.active_subtasks(item)):
            return derived_progress(subtasks)
        return int(self._progress.get(uid, {}).get(PROGRESS, 0))

    def last_partial(self, uid: str) -> int:
        """The last progress below 100 (restored when an item is reopened)."""
        if split_subtask_uid(uid) is not None:
            sub = self.find_subtask(uid)
            return sub.last_partial if sub else 0
        return int(self._progress.get(uid, {}).get(LAST_PARTIAL, 0))

    def completed_at(self, uid: str) -> datetime | None:
        """When an item reached 100 %, ``None`` otherwise (and for derived progress)."""
        entry = self._progress.get(uid)
        if entry is None or entry[PROGRESS] < 100 or self.has_subtasks(uid):
            return None
        return dt_util.parse_datetime(str(entry.get(UPDATED) or ""))

    def _item_by_uid(self, uid: str) -> HomeworkItem | None:
        self._refresh()
        return self._by_uid.get(uid)

    def has_subtasks(self, uid: str) -> bool:
        """Whether an item has active subtasks (its progress is then derived)."""
        item = self._item_by_uid(uid)
        return item is not None and bool(self.active_subtasks(item))

    def find_subtask(self, uid: str) -> Subtask | None:
        """The active subtask with a subtask uid, ``None`` when unknown or hidden."""
        if (ref := split_subtask_uid(uid)) is None:
            return None
        if (item := self._item_by_uid(ref[0])) is None:
            return None
        return next((s for s in self.active_subtasks(item) if s.id == ref[1]), None)

    @callback
    def set_progress(self, uid: str, progress: int) -> None:
        """Set the progress (0-100) of an item or subtask and tell the listeners."""
        progress = _clamp(progress)
        if (ref := split_subtask_uid(uid)) is not None:
            self._set_subtask_progress(ref, progress)
            return
        if self.has_subtasks(uid):
            return  # derived: the own progress is not used while it has subtasks
        entry = self._progress.get(uid)
        previous = entry[PROGRESS] if entry else 0
        last_partial = entry[LAST_PARTIAL] if entry else 0
        if progress == previous:
            return
        if progress < 100:
            last_partial = progress
        elif previous < 100:
            last_partial = previous
        updated = {
            **(entry or _blank_entry()),
            PROGRESS: progress,
            LAST_PARTIAL: last_partial,
            UPDATED: dt_util.utcnow().isoformat(),
        }
        self._progress[uid] = updated
        self._drop_if_empty(uid)
        self._changed()

    def _set_subtask_progress(self, ref: tuple[str, str], progress: int) -> None:
        stored = self._stored_subtask(*ref)
        if stored is None or progress == stored["progress"]:
            return
        previous = stored["progress"]
        if progress < 100:
            stored["last_partial"] = progress
            stored["completed_on"] = None
        else:
            if previous < 100:
                stored["last_partial"] = previous
            stored["completed_on"] = self.today().isoformat()
        stored["progress"] = progress
        self._invalidate()
        self._changed()

    def _stored_subtask(self, item_uid_: str, sub_id: str) -> dict[str, Any] | None:
        entry = self._progress.get(item_uid_)
        return next(
            (s for s in (entry or {}).get(SUBTASKS, []) if s["id"] == sub_id), None
        )

    @callback
    def reopen(self, uid: str) -> None:
        """Untick an item or subtask: restore the last progress below 100."""
        if self.progress(uid) >= 100:
            self.set_progress(uid, self.last_partial(uid))

    # -- subtasks -----------------------------------------------------------

    def _subtask_item(self, child_id: int, item_uid_: str) -> HomeworkItem:
        """The item subtasks can be changed on (not disabled)."""
        item = self.find_item(child_id, item_uid_)
        if item is None:
            raise LabelError(ERR_ITEM_NOT_FOUND)
        if self.effective(item).disabled:
            raise LabelError(ERR_ITEM_DISABLED)
        return item

    def _check_planned(self, item: HomeworkItem, planned: date) -> None:
        if not subtask_date_allowed(planned, item.due_date, self.today()):
            raise LabelError(ERR_INVALID_DATE)

    @callback
    def add_subtask(
        self,
        child_id: int,
        item_uid_: str,
        title: str,
        planned: date | None,
        created_by: str = CREATED_BY_USER,
    ) -> HomeworkItem:
        """Add a subtask (planned today by default) to an item; returns the item."""
        item = self._subtask_item(child_id, item_uid_)
        if len(item.subtasks) >= MAX_SUBTASKS:
            raise LabelError(ERR_TOO_MANY_SUBTASKS)
        planned = planned or self.today()
        self._check_planned(item, planned)
        entry = self._progress.get(item_uid_)
        if entry is None:
            entry = self._progress[item_uid_] = _blank_entry()
        entry.setdefault(SUBTASKS, []).append(
            {
                "id": new_label_id(),
                "title": title,
                "planned": planned.isoformat(),
                "progress": 0,
                "last_partial": 0,
                "completed_on": None,
                "created_by": created_by,
            }
        )
        return self._subtasks_changed(child_id, item_uid_)

    @callback
    def update_subtask(
        self,
        child_id: int,
        uid: str,
        title: str | None,
        planned: date | None,
    ) -> HomeworkItem:
        """Change the title and/or planned date of a subtask; returns the item."""
        if title is None and planned is None:
            raise LabelError(ERR_NOTHING_TO_UPDATE)
        item, stored = self._find_stored_subtask(child_id, uid)
        if planned is not None:
            self._check_planned(item, planned)
            stored["planned"] = planned.isoformat()
        if title is not None:
            stored["title"] = title
        return self._subtasks_changed(child_id, item.uid)

    @callback
    def delete_subtask(self, child_id: int, uid: str) -> HomeworkItem:
        """Delete a subtask; returns the item (its own progress applies without any)."""
        item, stored = self._find_stored_subtask(child_id, uid)
        entry = self._progress[item.uid]
        entry[SUBTASKS].remove(stored)
        if not entry[SUBTASKS]:
            del entry[SUBTASKS]
            self._drop_if_empty(item.uid)
        return self._subtasks_changed(child_id, item.uid)

    def _find_stored_subtask(
        self, child_id: int, uid: str
    ) -> tuple[HomeworkItem, dict[str, Any]]:
        ref = split_subtask_uid(uid)
        if ref is None:
            raise LabelError(ERR_SUBTASK_NOT_FOUND)
        item = self._subtask_item(child_id, ref[0])
        stored = self._stored_subtask(*ref)
        if stored is None:
            raise LabelError(ERR_SUBTASK_NOT_FOUND)
        return item, stored

    def _subtasks_changed(self, child_id: int, item_uid_: str) -> HomeworkItem:
        self._invalidate()
        self._changed()
        item = self.find_item(child_id, item_uid_)
        assert item is not None
        return item

    @callback
    def async_prune(self) -> None:
        """Drop progress, labels and overrides of appointments gone over 14 days."""
        data = self._coordinator.data
        if data is None:
            return
        present = {
            self.uid_of(child, appointment.id)
            for child, appointments in data.items()
            for appointment in appointments
        }
        today = dt_util.now(LOCAL_TZ).date()
        changed = False
        for uid in list(self._progress):
            entry = self._progress[uid]
            if uid in present:
                changed |= entry.pop(GONE, None) is not None
                continue
            gone = _parse_date(entry.get(GONE))
            if gone is None:
                entry[GONE] = today.isoformat()
                changed = True
            elif today - gone > PRUNE_AFTER:
                del self._progress[uid]
                changed = True
        if changed:
            self._schedule_save()

    # -- weights ------------------------------------------------------------

    def weights(self, child_id: int) -> Weights:
        """The weights of a child from the entry options."""
        stored = self._entry.options.get(CONF_WEIGHTS)
        if not isinstance(stored, Mapping):
            return Weights()
        return Weights.from_options(stored.get(str(child_id)))

    @callback
    def async_options_changed(self) -> None:
        """Weights or labels changed in the options: recompute without a reload."""
        self._invalidate()
        for listener in list(self._label_listeners):
            listener()
        for listener in list(self._listeners):
            listener()

    # -- listeners ----------------------------------------------------------

    @callback
    def async_add_listener(self, listener: CALLBACK_TYPE) -> CALLBACK_TYPE:
        """Call ``listener`` when progress or weights changed."""
        self._listeners.append(listener)

        @callback
        def remove() -> None:
            if listener in self._listeners:
                self._listeners.remove(listener)

        return remove

    @callback
    def async_add_label_listener(self, listener: CALLBACK_TYPE) -> CALLBACK_TYPE:
        """Call ``listener`` when labels or label options changed."""
        self._label_listeners.append(listener)

        @callback
        def remove() -> None:
            if listener in self._label_listeners:
                self._label_listeners.remove(listener)

        return remove

    @callback
    def _handle_coordinator_update(self) -> None:
        self.async_prune()

    def _changed(self) -> None:
        self._schedule_save()
        for listener in list(self._listeners):
            listener()

    # -- storage ------------------------------------------------------------

    def _data(self) -> dict[str, Any]:
        return {"items": {uid: dict(entry) for uid, entry in self._progress.items()}}

    @callback
    def _schedule_save(self) -> None:
        self._dirty = True
        self._store.async_delay_save(self._save_data, SAVE_DELAY)

    @callback
    def _save_data(self) -> dict[str, Any]:
        self._dirty = False
        return self._data()

    # -- diagnostics --------------------------------------------------------

    def statistics(self, child_id: int) -> dict[str, Any]:
        """Counts and progress statistics of a child (no names, no texts)."""
        items = self.items(child_id)
        values = [self.progress(item.uid) for item in items]
        weights = self.weights(child_id)
        return {
            "items": len(items),
            "by_info_type": {
                str(t): sum(1 for i in items if i.info_type == t)
                for t in sorted({i.info_type for i in items if i.info_type is not None})
            },
            "cancelled": sum(1 for i in items if i.cancelled),
            "with_attachments": sum(1 for i in items if i.has_attachments),
            "progress": {
                "not_started": sum(1 for v in values if v == 0),
                "partial": sum(1 for v in values if 0 < v < 100),
                "done": sum(1 for v in values if v == 100),
                "average": round(sum(values) / len(values), 1) if values else None,
            },
            "overrides": {
                mode: sum(1 for i in items if i.override and i.override.mode == mode)
                for mode in OVERRIDE_MODES
            },
            "manual_labels": {
                kind: sum(
                    1 for i in items for label in i.manual_labels if label.kind == kind
                )
                for kind in LABEL_KINDS
            },
            "subtasks": self._subtask_statistics(items),
            "weights": {
                "types_set": len(weights.types),
                "labels_set": len(weights.labels),
                "subjects_set": len(weights.subjects),
            },
        }

    def _subtask_statistics(self, items: list[HomeworkItem]) -> dict[str, int]:
        today = self.today()
        subtasks = [(item, sub) for item in items for sub in self.active_subtasks(item)]
        return {
            "items_with_subtasks": sum(
                1 for item in items if self.has_subtasks(item.uid)
            ),
            "total": len(subtasks),
            "done": sum(1 for _, sub in subtasks if sub.done),
            "overdue": sum(
                1
                for item, sub in subtasks
                if subtask_overdue(sub, item.due_date, today)
            ),
        }

    @property
    def stored_entries(self) -> int:
        """Number of stored progress entries."""
        return len(self._progress)


async def async_remove_store(hass: HomeAssistant, entry_id: str) -> None:
    """Delete the progress store of a removed config entry."""
    await _HomeworkStore(
        hass,
        STORE_VERSION,
        f"{DOMAIN}.homework.{entry_id}",
        minor_version=STORE_MINOR_VERSION,
    ).async_remove()


def _subtask_from_stored(stored: dict[str, Any]) -> Subtask:
    return Subtask(
        stored["id"],
        stored["title"],
        date.fromisoformat(stored["planned"]),
        stored["progress"],
        stored["last_partial"],
        date.fromisoformat(stored["completed_on"]) if stored["completed_on"] else None,
        stored.get("created_by") or CREATED_BY_USER,
    )


def _clean_subtasks(raw: Any) -> list[dict[str, Any]]:
    """Stored subtasks, leniently; unusable ones are dropped, at most 20 are kept."""
    subtasks: list[dict[str, Any]] = []
    if not isinstance(raw, list):
        return subtasks
    for stored in raw:
        if not isinstance(stored, dict):
            continue
        sub_id, title = stored.get("id"), stored.get("title")
        planned = _parse_date(stored.get("planned"))
        if not isinstance(sub_id, str) or not sub_id or planned is None:
            continue
        if any(s["id"] == sub_id for s in subtasks):
            continue
        if not isinstance(title, str) or not (
            title := title.strip()[:SUBTASK_TITLE_MAX]
        ):
            continue
        progress = _clamp(stored.get(PROGRESS))
        completed_on = (
            _parse_date(stored.get("completed_on")) if progress >= 100 else None
        )
        subtasks.append(
            {
                "id": sub_id,
                "title": title,
                "planned": planned.isoformat(),
                "progress": progress,
                "last_partial": min(_clamp(stored.get(LAST_PARTIAL)), 99),
                "completed_on": completed_on.isoformat() if completed_on else None,
                "created_by": created_by
                if (created_by := stored.get("created_by")) in CREATED_BY
                else CREATED_BY_USER,
            }
        )
        if len(subtasks) >= MAX_SUBTASKS:
            break
    return subtasks


def _blank_entry() -> dict[str, Any]:
    return {PROGRESS: 0, LAST_PARTIAL: 0, UPDATED: "", LABELS: []}


def _clean_labels(raw: Any) -> list[dict[str, str]]:
    """Stored manual labels, leniently: a list of ``{id, note, added}``."""
    labels: list[dict[str, str]] = []
    if not isinstance(raw, list):
        return labels
    for stored in raw:
        if isinstance(stored, dict) and isinstance(label_id := stored.get("id"), str):
            if any(label["id"] == label_id for label in labels):
                continue
            labels.append(
                {
                    "id": label_id,
                    "note": str(stored.get("note") or "")[:NOTE_MAX],
                    "added": str(stored.get("added") or ""),
                }
            )
    return labels


def _clean_override(raw: Any) -> dict[str, str] | None:
    """A stored override, leniently: a replace (with label id) or a disable."""
    if not isinstance(raw, dict):
        return None
    if raw.get("mode") == MODE_DISABLE:
        return {"mode": MODE_DISABLE}
    if raw.get("mode") == MODE_REPLACE and isinstance(label := raw.get("label"), str):
        return {"mode": MODE_REPLACE, "label": label} if label else None
    return None


def _parse_date(value: Any) -> date | None:
    try:
        return date.fromisoformat(str(value))
    except ValueError:
        return None


def manual_labels_to_list(item: HomeworkItem) -> list[Payload]:
    """The manual labels of an item in the WebSocket form."""
    return [
        {"id": label.id, "name": label.name, "kind": label.kind, "note": label.note}
        for label in item.manual_labels
    ]


def override_to_dict(item: HomeworkItem | None) -> Payload | None:
    """The override of an item in the WebSocket form (``None`` when there is none)."""
    override = item.override if item else None
    if override is None:
        return None
    if override.mode == MODE_REPLACE and override.label is not None:
        label = override.label
        return {
            "mode": MODE_REPLACE,
            "label": {"id": label.id, "name": label.name, "kind": label.kind},
        }
    return {"mode": MODE_DISABLE}


def appointment_to_dict(
    manager: HomeworkManager, child_id: int, appointment: Appointment
) -> Payload:
    """The WebSocket form of an appointment (for the add-label dialog)."""
    uid = manager.uid_of(child_id, appointment.id)
    item = manager.find_item(child_id, uid)
    return {
        "uid": uid,
        "start": appointment.start.astimezone(LOCAL_TZ).isoformat(),
        "end": appointment.end.astimezone(LOCAL_TZ).isoformat(),
        "all_day": appointment.all_day,
        "lesson_hour": appointment.period_start,
        "subject": appointment.subject,
        "cancelled": appointment.status in CANCELLED_STATUSES,
        "info_type": magister_info_type(appointment),
        "manual_labels": manual_labels_to_list(item) if item else [],
        "override": override_to_dict(item),
    }


def subtask_to_dict(item: HomeworkItem, sub: Subtask, today: date) -> Payload:
    """The WebSocket form of a subtask."""
    return {
        "uid": subtask_uid(item.uid, sub.id),
        "title": sub.title,
        "planned": sub.planned.isoformat(),
        "date": subtask_current_date(sub, item.due_date, today).isoformat(),
        "overdue": subtask_overdue(sub, item.due_date, today),
        "progress": sub.progress,
        "completed": sub.done,
        "last_partial": sub.last_partial,
        "created_by": sub.created_by,
    }


def item_to_dict(manager: HomeworkManager, item: HomeworkItem) -> Payload:
    """The WebSocket form of an item."""
    local = item.start.astimezone(LOCAL_TZ)
    state = manager.effective(item)
    today = manager.today()
    subtasks = manager.active_subtasks(item)
    return {
        "uid": item.uid,
        "due": item.due_date.isoformat() if item.all_day else local.isoformat(),
        "date": item.due_date.isoformat(),
        "all_day": item.all_day,
        "lesson_hour": item.lesson_hour,
        "subject": item.subject,
        "info_type": item.info_type,
        "label": item.label,
        "manual_labels": manual_labels_to_list(item),
        "override": override_to_dict(item),
        "disabled": state.disabled,
        "is_test": state.is_test,
        "text": item.text,
        "cancelled": item.cancelled,
        "has_attachments": item.has_attachments,
        "progress": manager.progress(item.uid),
        "completed": manager.is_completed(item),
        "last_partial": manager.last_partial(item.uid),
        "derived": bool(subtasks),
        "subtasks": [subtask_to_dict(item, sub, today) for sub in subtasks],
    }


def progress_payload(
    manager: HomeworkManager, child_id: int, *, available: bool
) -> Payload:
    """The values of the progress sensors; ``None`` where a sensor is unavailable."""
    today = manager.today()
    result: Payload = {}
    for period in PERIODS:
        if not available or not manager.period_fits(period):
            result[period] = None
            continue
        summary = manager.period(child_id, period, today).summary
        result[period] = {
            "value": summary.value,
            "items": summary.items,
            "completed": summary.completed,
        }
    return result


def build_payload(
    manager: HomeworkManager, child_id: int, *, available: bool
) -> Payload:
    """The full WebSocket payload for a child's to-do entity."""
    return {
        "available": available,
        "items": [item_to_dict(manager, i) for i in manager.items(child_id)],
        "labels": [
            {"id": o.id, "name": o.name, "kind": o.kind}
            for o in manager.label_options(child_id)
        ],
        "progress": progress_payload(manager, child_id, available=available),
    }


# -- WebSocket subscribers, kept per entity id so they survive entry reloads ----------


def _subscribers(hass: HomeAssistant) -> dict[str, list[Subscriber]]:
    data: dict[str, list[Subscriber]] = hass.data.setdefault(_SUBSCRIBERS, {})
    return data


@callback
def async_subscribe(
    hass: HomeAssistant, entity_id: str, subscriber: Subscriber
) -> CALLBACK_TYPE:
    """Receive the payloads pushed for a to-do entity id."""
    subscribers = _subscribers(hass).setdefault(entity_id, [])
    subscribers.append(subscriber)

    @callback
    def remove() -> None:
        if subscriber in subscribers:
            subscribers.remove(subscriber)
        if not subscribers and _subscribers(hass).get(entity_id) is subscribers:
            _subscribers(hass).pop(entity_id, None)

    return remove


@callback
def async_publish(hass: HomeAssistant, entity_id: str, payload: Payload) -> None:
    """Send ``payload`` to the subscribers of a to-do entity id."""
    for subscriber in list(_subscribers(hass).get(entity_id, [])):
        subscriber(payload)
