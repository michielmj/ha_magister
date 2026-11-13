"""Homework planner state: progress store, items per child and weights.

Progress lives in Home Assistant only (a ``Store`` per config entry); nothing is written
back to Magister. Changing progress or weights recomputes locally and never calls the
Magister API.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from datetime import date, datetime, timedelta
from typing import TYPE_CHECKING, Any, Final

import probatio
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util

from .api.homework import HomeworkItem, Weights, extract_homework
from .api.mapping import LOCAL_TZ
from .const import CONF_HOST, CONF_WEIGHTS, DOMAIN

if TYPE_CHECKING:
    from .coordinator import MagisterConfigEntry, MagisterCoordinator

STORE_VERSION: Final = 1
SAVE_DELAY: Final = 5.0
PRUNE_AFTER: Final = timedelta(days=14)

# Progress entry keys.
PROGRESS: Final = "progress"
LAST_PARTIAL: Final = "last_partial"
UPDATED: Final = "updated"
GONE: Final = "gone"

_SUBSCRIBERS: Final = f"{DOMAIN}_homework_subscribers"

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
        self._store: Store[dict[str, Any]] = Store(
            hass, STORE_VERSION, f"{DOMAIN}.homework.{entry.entry_id}"
        )
        self._progress: dict[str, dict[str, Any]] = {}
        self._listeners: list[CALLBACK_TYPE] = []
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
            self._items = {
                child: extract_homework(appointments, self._host, child)
                for child, appointments in data.items()
            }
        return self._items.get(child_id, [])

    def find_item(self, child_id: int, uid: str) -> HomeworkItem | None:
        """The item of ``child_id`` with ``uid``, ``None`` when unknown."""
        return next((i for i in self.items(child_id) if i.uid == uid), None)

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
        if progress == 0 and last_partial == 0:
            self._progress.pop(uid, None)
        else:
            self._progress[uid] = {
                PROGRESS: progress,
                LAST_PARTIAL: last_partial,
                UPDATED: dt_util.utcnow().isoformat(),
            }
        self._changed()

    @callback
    def reopen(self, uid: str) -> None:
        """Untick an item: restore the last progress below 100."""
        if self.progress(uid) >= 100:
            self.set_progress(uid, self.last_partial(uid))

    @callback
    def async_prune(self) -> None:
        """Drop progress of items that left the window more than 14 days ago."""
        data = self._coordinator.data
        if data is None:
            return
        present = {item.uid for child in data for item in self.items(child)}
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
    def async_weights_changed(self) -> None:
        """Weights changed in the options: recompute without a reload."""
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
                for t in sorted({i.info_type for i in items})
            },
            "cancelled": sum(1 for i in items if i.cancelled),
            "with_attachments": sum(1 for i in items if i.has_attachments),
            "progress": {
                "not_started": sum(1 for v in values if v == 0),
                "partial": sum(1 for v in values if 0 < v < 100),
                "done": sum(1 for v in values if v == 100),
                "average": round(sum(values) / len(values), 1) if values else None,
            },
            "weights": {
                "types_set": len(weights.types),
                "subjects_set": len(weights.subjects),
            },
        }

    @property
    def stored_entries(self) -> int:
        """Number of stored progress entries."""
        return len(self._progress)


async def async_remove_store(hass: HomeAssistant, entry_id: str) -> None:
    """Delete the progress store of a removed config entry."""
    await Store(hass, STORE_VERSION, f"{DOMAIN}.homework.{entry_id}").async_remove()


def _parse_date(value: Any) -> date | None:
    try:
        return date.fromisoformat(str(value))
    except ValueError:
        return None


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
        "is_test": item.is_test,
        "text": item.text,
        "cancelled": item.cancelled,
        "has_attachments": item.has_attachments,
        "progress": manager.progress(item.uid),
        "completed": manager.progress(item.uid) >= 100,
        "last_partial": manager.last_partial(item.uid),
    }


def build_payload(
    manager: HomeworkManager, child_id: int, *, available: bool
) -> Payload:
    """The full WebSocket payload for a child's to-do entity."""
    return {
        "available": available,
        "items": [item_to_dict(manager, i) for i in manager.items(child_id)],
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
        if not subscribers:
            _subscribers(hass).pop(entity_id, None)

    return remove


@callback
def async_publish(hass: HomeAssistant, entity_id: str, payload: Payload) -> None:
    """Send ``payload`` to the subscribers of a to-do entity id."""
    for subscriber in list(_subscribers(hass).get(entity_id, [])):
        subscriber(payload)
