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
    LABEL_KINDS,
    NOTE_MAX,
    PERIOD_NEXT_WEEK,
    PERIODS,
    HomeworkItem,
    LabelOption,
    ManualLabel,
    PeriodSummary,
    Weights,
    default_label_options,
    effective_weights,
    extract_homework,
    homework_periods,
    item_uid,
    items_in_period,
    magister_info_type,
    next_week_fits,
    parse_label_options,
    skipped_days,
    summarize,
    uid_child_id,
)
from .api.mapping import CANCELLED_STATUSES, LOCAL_TZ
from .api.models import Appointment
from .const import CONF_HOST, CONF_LABELS, CONF_WEIGHTS, DOMAIN
from .coordinator import fetch_window

if TYPE_CHECKING:
    from .coordinator import MagisterConfigEntry, MagisterCoordinator

STORE_VERSION: Final = 1
STORE_MINOR_VERSION: Final = 2
SAVE_DELAY: Final = 5.0
PRUNE_AFTER: Final = timedelta(days=14)

# Progress entry keys.
PROGRESS: Final = "progress"
LAST_PARTIAL: Final = "last_partial"
UPDATED: Final = "updated"
GONE: Final = "gone"
LABELS: Final = "labels"

# Errors of the label commands; the WebSocket API uses them as error codes and the
# services as ``homework_<code>`` exception translation keys.
ERR_APPOINTMENT_NOT_FOUND: Final = "appointment_not_found"
ERR_LABEL_NOT_FOUND: Final = "label_not_found"
ERR_LABEL_EXISTS: Final = "label_exists"
ERR_LABEL_NOT_ON_APPOINTMENT: Final = "label_not_on_appointment"
ERR_INVALID_DATE: Final = "invalid_date"

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


def new_label_id() -> str:
    """A new stable id for a label option."""
    return uuid.uuid4().hex[:8]


class _HomeworkStore(Store[dict[str, Any]]):
    """The progress store, with its migration from earlier schema versions."""

    async def _async_migrate_func(
        self, old_major_version: int, old_minor_version: int, old_data: dict[str, Any]
    ) -> dict[str, Any]:
        """1.1 (progress only) to 1.2 (adds ``labels`` to every item).

        The major version stays 1 so that an older release can still read the file.
        """
        if old_major_version == 1 and old_minor_version < 2:
            items = old_data.get("items")
            return {
                "items": {
                    uid: {LABELS: [], **entry}
                    for uid, entry in (items if isinstance(items, dict) else {}).items()
                    if isinstance(entry, dict)
                }
            }
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
            manual = self._manual_labels()
            self._items = {
                child: extract_homework(appointments, self._host, child, manual)
                for child, appointments in data.items()
            }
        return self._items.get(child_id, [])

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

    def manual_label_names(self, child_id: int, appointment_id: int) -> list[str]:
        """Names of the manual labels of an appointment (for the calendar title)."""
        item = self.find_item(child_id, self.uid_of(child_id, appointment_id))
        return [label.name for label in item.manual_labels] if item else []

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
        """Whether an appointment in the current data still has this manual label."""
        present = {self.uid_of(child_id, a.id) for a in self._appointments(child_id)}
        return any(
            stored["id"] == label_id
            for uid, entry in self._progress.items()
            if uid in present
            for stored in entry[LABELS]
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
            kept = [s for s in entry[LABELS] if s["id"] != label_id]
            if len(kept) != len(entry[LABELS]):
                entry[LABELS] = kept
                self._drop_if_empty(uid)
                changed = True
        if changed:
            self._labels_changed()

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
        self._items_source = None
        self._changed()
        for listener in list(self._label_listeners):
            listener()

    def _drop_if_empty(self, uid: str) -> None:
        entry = self._progress.get(uid)
        if (
            entry is not None
            and not entry[LABELS]
            and entry[PROGRESS] == 0
            and entry[LAST_PARTIAL] == 0
        ):
            del self._progress[uid]

    def find_item(self, child_id: int, uid: str) -> HomeworkItem | None:
        """The item of ``child_id`` with ``uid``, ``None`` when unknown."""
        return next((i for i in self.items(child_id) if i.uid == uid), None)

    # -- periods ------------------------------------------------------------

    def period_fits(self, period: str) -> bool:
        """Whether a period lies within the fetch window (only next week can not)."""
        return period != PERIOD_NEXT_WEEK or next_week_fits(
            self._coordinator.weeks_ahead
        )

    def period(self, child_id: int, period: str, today: date) -> PeriodData:
        """Items, weights and weighted progress of a child for a period."""
        first, end = homework_periods(today)[period]
        items = items_in_period(
            self.items(child_id), (first, end), skipped_days(period, today)
        )
        weights = self.weights(child_id)
        return PeriodData(
            first, end, items, weights, summarize(items, self.progress, weights)
        )

    def due_open_count(self, child_id: int, today: date) -> int:
        """Open items due today or later (the number shown for the to-do list)."""
        return sum(
            1
            for item in self.items(child_id)
            if item.due_date >= today and self.progress(item.uid) < 100
        )

    # -- progress -----------------------------------------------------------

    def progress(self, uid: str) -> int:
        """Progress of an item in percent (0 when untouched)."""
        return int(self._progress.get(uid, {}).get(PROGRESS, 0))

    def last_partial(self, uid: str) -> int:
        """The last progress below 100 (restored when an item is reopened)."""
        return int(self._progress.get(uid, {}).get(LAST_PARTIAL, 0))

    def completed_at(self, uid: str) -> datetime | None:
        """When an item reached 100 %, ``None`` otherwise."""
        entry = self._progress.get(uid)
        if entry is None or entry[PROGRESS] < 100:
            return None
        return dt_util.parse_datetime(str(entry.get(UPDATED) or ""))

    @callback
    def set_progress(self, uid: str, progress: int) -> None:
        """Set the progress (0-100) of an item and tell the listeners."""
        progress = _clamp(progress)
        entry = self._progress.get(uid)
        previous = entry[PROGRESS] if entry else 0
        last_partial = entry[LAST_PARTIAL] if entry else 0
        if progress == previous:
            return
        if progress < 100:
            last_partial = progress
        elif previous < 100:
            last_partial = previous
        labels = entry[LABELS] if entry else []
        self._progress[uid] = {
            PROGRESS: progress,
            LAST_PARTIAL: last_partial,
            UPDATED: dt_util.utcnow().isoformat(),
            LABELS: labels,
        }
        self._drop_if_empty(uid)
        self._changed()

    @callback
    def reopen(self, uid: str) -> None:
        """Untick an item: restore the last progress below 100."""
        if self.progress(uid) >= 100:
            self.set_progress(uid, self.last_partial(uid))

    @callback
    def async_prune(self) -> None:
        """Drop progress and labels of appointments gone for more than 14 days."""
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
        self._items_source = None
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
            "manual_labels": {
                kind: sum(
                    1 for i in items for label in i.manual_labels if label.kind == kind
                )
                for kind in LABEL_KINDS
            },
            "weights": {
                "types_set": len(weights.types),
                "labels_set": len(weights.labels),
                "subjects_set": len(weights.subjects),
            },
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
    }


def item_to_dict(manager: HomeworkManager, item: HomeworkItem) -> Payload:
    """The WebSocket form of an item."""
    local = item.start.astimezone(LOCAL_TZ)
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
        "is_test": item.is_test,
        "text": item.text,
        "cancelled": item.cancelled,
        "has_attachments": item.has_attachments,
        "progress": manager.progress(item.uid),
        "completed": manager.progress(item.uid) >= 100,
        "last_partial": manager.last_partial(item.uid),
    }


def progress_payload(
    manager: HomeworkManager, child_id: int, *, available: bool
) -> Payload:
    """The values of the progress sensors; ``None`` where a sensor is unavailable."""
    today = dt_util.now(LOCAL_TZ).date()
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
