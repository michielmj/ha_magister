"""Homework planner logic (pure, no Home Assistant imports).

A homework item is a Magister appointment with InfoType 1-5 (homework, test, exam,
written quiz, oral quiz) or with at least one manual label. This module extracts the
items, computes the periods (next school day, this week, next week in
Europe/Amsterdam) and the weighted progress.
"""

from __future__ import annotations

import math
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Any, Final

from .mapping import CANCELLED_STATUSES, LOCAL_TZ, html_to_text
from .models import Appointment

# InfoType -> (key used in the weights, label of the item).
HOMEWORK_TYPES: Final[dict[int, tuple[str, str]]] = {
    1: ("homework", "Huiswerk"),
    2: ("test", "Proefwerk"),
    3: ("exam", "Tentamen"),
    4: ("written_quiz", "SO"),
    5: ("oral_quiz", "MO"),
}
TYPE_KEYS: Final[tuple[str, ...]] = tuple(key for key, _ in HOMEWORK_TYPES.values())

PERIOD_NEXT_DAY: Final = "next_day"
PERIOD_WEEK: Final = "week"
PERIOD_NEXT_WEEK: Final = "next_week"
PERIODS: Final = (PERIOD_NEXT_DAY, PERIOD_WEEK, PERIOD_NEXT_WEEK)

# Manual label kinds and the stored note length.
KIND_HOMEWORK: Final = "homework"
KIND_TEST: Final = "test"
LABEL_KINDS: Final = (KIND_HOMEWORK, KIND_TEST)

# Overrides of the Magister label of an appointment (``clear`` only exists in commands).
MODE_REPLACE: Final = "replace"
MODE_DISABLE: Final = "disable"
MODE_CLEAR: Final = "clear"
OVERRIDE_MODES: Final = (MODE_REPLACE, MODE_DISABLE)
ARROW: Final = "\u2192"
NOTE_MAX: Final = 200
LABEL_NAME_MAX: Final = 40

WEIGHT_MIN: Final = 0.0
WEIGHT_MAX: Final = 10.0
DEFAULT_WEIGHT: Final = 1.0

PROGRESS_STEPS: Final = (0, 25, 50, 75, 100)

# Subtasks (since 1.5.0).
SUBTASK_TITLE_MAX: Final = 100
MAX_SUBTASKS: Final = 20
SUBTASK_SEPARATOR: Final = ":sub:"


# Who created a subtask: the user (card, service), the AI coach of a student (since
# 1.6.0) or the AI of a parent (since 1.7.0).
CREATED_BY_USER: Final = "user"
CREATED_BY_AI: Final = "ai"
CREATED_BY_PARENT: Final = "parent"
CREATED_BY: Final = (CREATED_BY_USER, CREATED_BY_AI, CREATED_BY_PARENT)

# Estimated time of a subtask in minutes (since 1.7.0): 5 to 240 in steps of 5.
MINUTES_MIN: Final = 5
MINUTES_MAX: Final = 240
MINUTES_STEP: Final = 5

# Study minutes per school day of a child (since 1.7.0): the daily maximum.
DAILY_MAX_DEFAULT: Final = 90
DAILY_MAX_MIN: Final = 15
DAILY_MAX_MAX: Final = 480
DAILY_MAX_STEP: Final = 15
# Since 1.9.0 the maximum is set per weekday (Monday to Sunday): 0 to 480 in steps of
# 15, where 0 means "no study planned that day".
WEEKDAY_MAX_MIN: Final = 0
WEEKDAYS: Final = 7


def valid_minutes(value: Any) -> int | None:
    """The estimated time of a subtask as int; ``None`` when it is not allowed.

    Booleans and non-integers are refused; a whole float (a number selector) is fine.
    """
    if isinstance(value, bool) or not isinstance(value, int | float):
        return None
    if isinstance(value, float) and not value.is_integer():
        return None
    minutes = int(value)
    if not MINUTES_MIN <= minutes <= MINUTES_MAX or minutes % MINUTES_STEP:
        return None
    return minutes


def clean_daily_max(value: Any) -> int:
    """A stored daily maximum, leniently: rounded to the step, clamped, else default."""
    if isinstance(value, bool) or not isinstance(value, int | float):
        return DAILY_MAX_DEFAULT
    if isinstance(value, float) and not value.is_integer():
        return DAILY_MAX_DEFAULT
    # Integer arithmetic: a huge value must not overflow (no float division).
    stepped = (int(value) + DAILY_MAX_STEP // 2) // DAILY_MAX_STEP * DAILY_MAX_STEP
    return min(max(stepped, DAILY_MAX_MIN), DAILY_MAX_MAX)


def clean_weekday_max(value: Any, default: int = DAILY_MAX_DEFAULT) -> int:
    """A stored maximum of one weekday: rounded to the step, 0 to 480, else default."""
    if isinstance(value, bool) or not isinstance(value, int | float):
        return default
    if isinstance(value, float) and not value.is_integer():
        return default
    stepped = (int(value) + DAILY_MAX_STEP // 2) // DAILY_MAX_STEP * DAILY_MAX_STEP
    return min(max(stepped, WEEKDAY_MAX_MIN), DAILY_MAX_MAX)


def valid_weekday_max(value: Any) -> int | None:
    """A weekday maximum as int; ``None`` when it is not 0 to 480 in steps of 15."""
    if isinstance(value, float) and value.is_integer():
        value = int(value)
    if (
        not isinstance(value, int)
        or isinstance(value, bool)
        or not WEEKDAY_MAX_MIN <= value <= DAILY_MAX_MAX
        or value % DAILY_MAX_STEP
    ):
        return None
    return value


def clean_weekdays(raw: Any, single: Any = None) -> tuple[int, ...]:
    """The seven weekday maximums from the options, leniently (Monday first).

    ``raw`` is the stored ``daily_max_weekdays`` (seven values). Without a usable
    list, the single ``daily_max_minutes`` of 1.7 and 1.8 (``single``) is the value of
    every day: that is the migration. The default is 90 for every day.
    """
    if isinstance(raw, list | tuple) and len(raw) == WEEKDAYS:
        fallback = clean_daily_max(single)
        return tuple(clean_weekday_max(v, fallback) for v in raw)
    return (clean_daily_max(single),) * WEEKDAYS


@dataclass(frozen=True, slots=True)
class Subtask:
    """A step of a homework item, planned on a day on or before the item's date.

    ``completed_on`` is the local date the subtask reached 100 (``None`` below 100).
    """

    id: str
    title: str
    planned: date
    progress: int = 0
    last_partial: int = 0
    completed_on: date | None = None
    created_by: str = "user"
    minutes: int | None = None

    @property
    def done(self) -> bool:
        """Whether the subtask is at 100 %."""
        return self.progress >= 100


@dataclass(frozen=True, slots=True)
class LabelOption:
    """A label a child can get manually: a stable id, a name and a kind."""

    id: str
    name: str
    kind: str


@dataclass(frozen=True, slots=True)
class Override:
    """An override of the Magister label: a replacement option or a disable.

    ``label`` is the resolved replacement option (``None`` for ``disable``).
    """

    mode: str
    label: LabelOption | None = None


@dataclass(frozen=True, slots=True)
class ManualLabel:
    """A manual label on an appointment, resolved against the label options."""

    id: str
    name: str
    kind: str
    note: str
    added: str


def magister_label_option(info_type: int) -> LabelOption:
    """The Magister label of an InfoType 1-5 as a (default) label option."""
    key, name = HOMEWORK_TYPES[info_type]
    return LabelOption(
        f"default_{key}", name, KIND_HOMEWORK if info_type == 1 else KIND_TEST
    )


def default_label_options() -> list[LabelOption]:
    """The five Magister names with their kinds (the default label options)."""
    return [magister_label_option(info_type) for info_type in HOMEWORK_TYPES]


def default_label_type_key(label_id: str) -> str | None:
    """The type key of a default label id (``default_<key>``), else ``None``."""
    key = label_id.removeprefix("default_")
    return key if key != label_id and key in TYPE_KEYS else None


def parse_label_options(raw: Any) -> list[LabelOption] | None:
    """Label options from stored options; ``None`` when not configured (default)."""
    if not isinstance(raw, list):
        return None
    options: list[LabelOption] = []
    seen: set[str] = set()
    for entry in raw:
        if not isinstance(entry, Mapping):
            continue
        label_id, name, kind = entry.get("id"), entry.get("name"), entry.get("kind")
        if not isinstance(label_id, str) or not label_id or label_id in seen:
            continue
        if not isinstance(name, str) or not name.strip():
            continue
        seen.add(label_id)
        options.append(
            LabelOption(
                label_id, name.strip(), kind if kind in LABEL_KINDS else KIND_HOMEWORK
            )
        )
    return options


def label_options_to_stored(options: Iterable[LabelOption]) -> list[dict[str, str]]:
    """The stored form of label options."""
    return [{"id": o.id, "name": o.name, "kind": o.kind} for o in options]


def find_label_option(
    options: Iterable[LabelOption], reference: str, *, by_name: bool = False
) -> LabelOption | None:
    """The option with id ``reference``; optionally also by name (case-insensitive)."""
    options = list(options)
    for option in options:
        if option.id == reference:
            return option
    if by_name:
        wanted = reference.strip().casefold()
        for option in options:
            if option.name.casefold() == wanted:
                return option
    return None


@dataclass(frozen=True, slots=True)
class HomeworkItem:
    """One homework or test item of a child."""

    uid: str
    appointment_id: int
    start: datetime
    due_date: date
    all_day: bool
    subject: str
    info_type: int | None
    label: str | None
    text: str
    cancelled: bool
    lesson_hour: int | None
    has_attachments: bool
    manual_labels: tuple[ManualLabel, ...] = ()
    override: Override | None = None
    subtasks: tuple[Subtask, ...] = ()


@dataclass(frozen=True, slots=True)
class EffectiveState:
    """What an item is after overrides: see ``effective_state``."""

    effective_label: LabelOption | None
    active_labels: tuple[LabelOption, ...]
    disabled: bool
    is_test: bool
    weight: float


def magister_label_text(item: HomeworkItem) -> str | None:
    """The Magister label as shown in titles, after an override.

    ``None`` when there is no override (show the original), ``""`` when the label is
    disabled (show nothing) and ``"Proefwerk\u2192Huiswerk"`` for a replacement.
    """
    if item.info_type is None or item.override is None:
        return None
    if item.override.mode == MODE_REPLACE and item.override.label is not None:
        return f"{HOMEWORK_TYPES[item.info_type][1]}{ARROW}{item.override.label.name}"
    return ""


def effective_state(item: HomeworkItem, weights: Weights) -> EffectiveState:
    """The single place that decides what an item is, with its overrides applied.

    * ``effective_label``: the original Magister label, the replacement option, or
      ``None`` (no Magister label, or it is disabled);
    * ``active_labels``: the effective label plus the manual labels;
    * ``disabled``: no active labels are left (the Magister label is disabled and there
      are no manual labels): the item counts as completed;
    * ``is_test``: any active label of the kind ``test``;
    * ``weight``: ``max(active label weights) x subject weight``, 0 when disabled.
      The default labels use the weight of their type.
    """
    effective: LabelOption | None = None
    if item.info_type is not None:
        override = item.override
        if override is None:
            effective = magister_label_option(item.info_type)
        elif override.mode == MODE_REPLACE and override.label is not None:
            effective = override.label
    active = tuple(
        ([effective] if effective is not None else [])
        + [LabelOption(m.id, m.name, m.kind) for m in item.manual_labels]
    )
    disabled = not active
    weight = (
        0.0
        if disabled
        else max(weights.label_weight(label.id) for label in active)
        * weights.subject_weight(item.subject)
    )
    return EffectiveState(
        effective_label=effective,
        active_labels=active,
        disabled=disabled,
        is_test=any(label.kind == KIND_TEST for label in active),
        weight=weight,
    )


def item_uid(host: str, child_id: int, appointment_id: int) -> str:
    """Stable key of an item: ``<host>:<childId>:<appointmentId>``."""
    return f"{host}:{child_id}:{appointment_id}"


def uid_child_id(uid: str) -> int | None:
    """The child id in an item uid, ``None`` when it is not one."""
    parts = uid.rsplit(":", 2)
    try:
        return int(parts[1]) if len(parts) == 3 else None
    except ValueError:
        return None


def magister_info_type(appointment: Appointment) -> int | None:
    """The Magister homework InfoType (1-5) of an appointment, else ``None``."""
    info_type = appointment.info_type
    return info_type if info_type in HOMEWORK_TYPES else None


def extract_homework(
    appointments: Iterable[Appointment],
    host: str,
    child_id: int,
    manual: Mapping[str, Sequence[ManualLabel]] | None = None,
    overrides: Mapping[str, Override] | None = None,
    subtasks: Mapping[str, Sequence[Subtask]] | None = None,
) -> list[HomeworkItem]:
    """Homework items of a child, ordered by due time, lesson hour and id.

    An item is an appointment with a Magister InfoType 1-5 or a manual label
    (``manual`` maps item uids to their labels). ``overrides`` (by uid) only apply to
    appointments that have a Magister label. ``subtasks`` (by uid) are the stored
    subtasks of the items.
    """
    items: list[HomeworkItem] = []
    for appointment in appointments:
        info_type = magister_info_type(appointment)
        uid = item_uid(host, child_id, appointment.id)
        labels = tuple((manual or {}).get(uid, ()))
        if info_type is None and not labels:
            continue
        items.append(
            HomeworkItem(
                uid=uid,
                appointment_id=appointment.id,
                start=appointment.start,
                due_date=appointment.start.astimezone(LOCAL_TZ).date(),
                all_day=appointment.all_day,
                subject=appointment.subject,
                info_type=info_type,
                label=HOMEWORK_TYPES[info_type][1] if info_type is not None else None,
                text=html_to_text(appointment.content),
                cancelled=appointment.status in CANCELLED_STATUSES,
                lesson_hour=appointment.period_start,
                has_attachments=appointment.has_attachments,
                manual_labels=labels,
                override=(overrides or {}).get(uid) if info_type is not None else None,
                subtasks=tuple((subtasks or {}).get(uid, ())),
            )
        )
    items.sort(key=lambda i: (i.start, i.lesson_hour or 0, i.uid))
    return items


def next_school_day(today: date) -> date:
    """The first school day (Monday-Friday) after ``today``."""
    weekday = today.weekday()
    return today + timedelta(days=1 if weekday < 4 else 7 - weekday)


def homework_periods(today: date) -> dict[str, tuple[date, date]]:
    """Periods as ``(first day, day after the last)`` for the local date ``today``.

    ``next_day`` runs from today up to and including the next school day (Monday for
    Friday, Saturday and Sunday). ``week`` is the Saturday on or before today through
    the following Friday (so on a Saturday it starts today); ``next_week`` is the
    Saturday-Friday week after that.
    """
    saturday = today - timedelta(days=(today.weekday() - 5) % 7)
    return {
        PERIOD_NEXT_DAY: (today, next_school_day(today) + timedelta(days=1)),
        PERIOD_WEEK: (saturday, saturday + timedelta(days=7)),
        PERIOD_NEXT_WEEK: (saturday + timedelta(days=7), saturday + timedelta(days=14)),
    }


def next_week_fits(weeks_ahead: int) -> bool:
    """Whether next week always lies within a fetch window of ``weeks_ahead``."""
    return weeks_ahead >= 2


def _clean_weight(value: Any) -> float | None:
    """A weight from stored options, or ``None`` when it is not usable."""
    if isinstance(value, bool) or not isinstance(value, int | float):
        return None
    if math.isnan(value) or math.isinf(value):
        return None
    return min(max(float(value), WEIGHT_MIN), WEIGHT_MAX)


@dataclass(frozen=True, slots=True)
class Weights:
    """Weights of one child, per type, per manual label id and per subject (default 1).

    ``types`` is keyed by the names in ``TYPE_KEYS``; ``labels`` by label option id;
    ``subjects`` by the subject as it was stored. Subject matching is exact and
    case-insensitive. ``daily_max_weekdays`` (since 1.9.0) is the study time per
    weekday, Monday first, stored with the weights of the child; before 1.9.0 one value
    (``daily_max_minutes``) held for every day and it is still stored as a mirror of
    the Monday value, for a downgrade.
    """

    types: Mapping[str, float] = field(default_factory=dict)
    subjects: Mapping[str, float] = field(default_factory=dict)
    labels: Mapping[str, float] = field(default_factory=dict)
    daily_max_weekdays: tuple[int, ...] = (DAILY_MAX_DEFAULT,) * WEEKDAYS

    @property
    def daily_max_minutes(self) -> int:
        """The Monday value: what 1.8 and older cards know as the daily maximum."""
        return self.daily_max_weekdays[0]

    def weekday_max(self, day: date) -> int:
        """The maximum of the weekday of ``day``."""
        return self.daily_max_weekdays[day.weekday()]

    @classmethod
    def from_options(cls, raw: Any) -> Weights:
        """Parse the stored form ``{"types", "labels", "subjects"}`` leniently."""
        if not isinstance(raw, Mapping):
            return cls()
        types: dict[str, float] = {}
        if isinstance(raw_types := raw.get("types"), Mapping):
            for key, value in raw_types.items():
                weight = _clean_weight(value)
                if key in TYPE_KEYS and weight is not None:
                    types[key] = weight
        subjects: dict[str, float] = {}
        if isinstance(raw_subjects := raw.get("subjects"), Mapping):
            for name, value in raw_subjects.items():
                weight = _clean_weight(value)
                if isinstance(name, str) and name.strip() and weight is not None:
                    subjects[name] = weight
        labels: dict[str, float] = {}
        if isinstance(raw_labels := raw.get("labels"), Mapping):
            for label_id, value in raw_labels.items():
                weight = _clean_weight(value)
                if isinstance(label_id, str) and label_id and weight is not None:
                    labels[label_id] = weight
        return cls(
            types,
            subjects,
            labels,
            clean_weekdays(raw.get("daily_max_weekdays"), raw.get("daily_max_minutes")),
        )

    def type_weight(self, info_type: int) -> float:
        """Weight of an InfoType."""
        key = HOMEWORK_TYPES[info_type][0]
        return self.types.get(key, DEFAULT_WEIGHT)

    def label_weight(self, label_id: str) -> float:
        """Weight of a manual label; the default labels use their type's weight."""
        if (key := default_label_type_key(label_id)) is not None:
            return self.types.get(key, DEFAULT_WEIGHT)
        return self.labels.get(label_id, DEFAULT_WEIGHT)

    def subject_weight(self, subject: str) -> float:
        """Weight of a subject (case-insensitive)."""
        wanted = subject.casefold()
        for name, weight in self.subjects.items():
            if name.casefold() == wanted:
                return weight
        return DEFAULT_WEIGHT


@dataclass(frozen=True, slots=True)
class PeriodSummary:
    """Progress statistics of the items due in one period."""

    value: float
    items: int
    completed: int
    open: int
    tests: int


def skipped_days(period: str, today: date) -> frozenset[date]:
    """Days inside a period's range that do not belong to it.

    Only ``next_day`` has them: the free days between today and the next school day
    (Saturday and Sunday on a Friday, Sunday on a Saturday).
    """
    if period != PERIOD_NEXT_DAY:
        return frozenset()
    last = next_school_day(today)
    return frozenset(today + timedelta(days=n) for n in range(1, (last - today).days))


def items_in_period(
    items: Iterable[HomeworkItem],
    period: tuple[date, date],
    skipped: frozenset[date] = frozenset(),
) -> list[HomeworkItem]:
    """Items due on a day in ``[first, end)`` that is not in ``skipped``."""
    first, end = period
    return [
        item
        for item in items
        if first <= item.due_date < end and item.due_date not in skipped
    ]


def subtask_uid(item_uid_: str, subtask_id: str) -> str:
    """The uid of a subtask: ``<item uid>:sub:<id>``."""
    return f"{item_uid_}{SUBTASK_SEPARATOR}{subtask_id}"


def split_subtask_uid(uid: str) -> tuple[str, str] | None:
    """``(item uid, subtask id)`` of a subtask uid, ``None`` when it is not one."""
    item, separator, sub_id = uid.rpartition(SUBTASK_SEPARATOR)
    return (item, sub_id) if separator and item and sub_id else None


def subtask_current_date(sub: Subtask, item_date: date, today: date) -> date:
    """The day a subtask is on, for the local date ``today``.

    Not done: ``min(max(planned, today), item date)``: it rolls forward day by day
    (weekends included) but never past the item. Done: the day it was completed,
    clamped to the item date; it no longer moves.
    """
    if sub.done:
        return min(sub.completed_on or sub.planned, item_date)
    return min(max(sub.planned, today), item_date)


def subtask_overdue(sub: Subtask, item_date: date, today: date) -> bool:
    """Not done while the item date has passed."""
    return not sub.done and item_date < today


def derived_progress(subtasks: Sequence[Subtask]) -> int:
    """The mean progress of the subtasks, rounded half up (0 without subtasks)."""
    count = len(subtasks)
    if not count:
        return 0
    return (2 * sum(sub.progress for sub in subtasks) + count) // (2 * count)


def subtask_date_allowed(planned: date, item_date: date, today: date) -> bool:
    """``today <= planned <= item date``, or exactly the item date when it is past."""
    if item_date < today:
        return planned == item_date
    return today <= planned <= item_date


def active_subtasks(item: HomeworkItem, state: EffectiveState) -> tuple[Subtask, ...]:
    """The subtasks that count: none while the item is disabled."""
    return () if state.disabled else item.subtasks


@dataclass(frozen=True, slots=True)
class Entry:
    """One thing that counts in the progress: an item or one of its subtasks."""

    uid: str
    item_uid: str
    day: date
    weight: float
    progress: int
    is_test: bool


def item_entries(
    item: HomeworkItem,
    state: EffectiveState,
    own_progress: int,
    today: date,
) -> list[Entry]:
    """The entries of an item: the single place that expands subtasks.

    * disabled: nothing;
    * no subtasks: the item itself, on its due date;
    * ``n`` subtasks: ``n`` entries of weight ``item weight / n``, each on its current
      date with its own progress (so the weights over all periods add up to the item's).
    """
    if state.disabled:
        return []
    subtasks = active_subtasks(item, state)
    if not subtasks:
        return [
            Entry(
                item.uid,
                item.uid,
                item.due_date,
                state.weight,
                own_progress,
                state.is_test,
            )
        ]
    weight = state.weight / len(subtasks)
    return [
        Entry(
            subtask_uid(item.uid, sub.id),
            item.uid,
            subtask_current_date(sub, item.due_date, today),
            weight,
            sub.progress,
            state.is_test,
        )
        for sub in subtasks
    ]


def homework_entries(
    items: Iterable[HomeworkItem],
    progress: Callable[[str], int],
    weights: Weights,
    today: date,
) -> list[Entry]:
    """The entries of all ``items`` (``progress`` gives the own progress of an item)."""
    entries: list[Entry] = []
    for item in items:
        state = effective_state(item, weights)
        entries.extend(item_entries(item, state, progress(item.uid), today))
    return entries


def entries_in_period(
    entries: Iterable[Entry],
    period: tuple[date, date],
    skipped: frozenset[date] = frozenset(),
) -> list[Entry]:
    """Entries on a day in ``[first, end)`` that is not in ``skipped``."""
    first, end = period
    return [e for e in entries if first <= e.day < end and e.day not in skipped]


def summarize_entries(entries: Iterable[Entry]) -> PeriodSummary:
    """Weighted average progress: sum(w x p) / sum(w), 100 when nothing counts."""
    count = completed = tests = 0
    weighted = total_weight = 0.0
    for entry in entries:
        count += 1
        completed += entry.progress >= 100
        tests += entry.is_test
        weighted += entry.weight * entry.progress
        total_weight += entry.weight
    average = weighted / total_weight if total_weight > 0 else 100.0
    return PeriodSummary(
        value=round(average, 1),
        items=count,
        completed=completed,
        open=count - completed,
        tests=tests,
    )


def summarize(
    items: Iterable[HomeworkItem],
    progress: Callable[[str], int],
    weights: Weights,
    today: date | None = None,
) -> PeriodSummary:
    """Weighted average progress of all entries of ``items`` (see ``item_entries``).

    Disabled items are ignored altogether (weight 0, not counted). ``today`` only
    matters for the periods of subtasks; it defaults to the local date.
    """
    day = today or datetime.now(LOCAL_TZ).date()
    return summarize_entries(homework_entries(items, progress, weights, day))


def effective_weights(
    items: Iterable[HomeworkItem], weights: Weights
) -> dict[str, dict[str, float]]:
    """The weights in use for ``items``: all types, the labels and subjects present."""
    subjects: dict[str, float] = {}
    labels: dict[str, float] = {}
    seen: set[str] = set()
    for item in items:
        used: list[LabelOption | ManualLabel] = list(item.manual_labels)
        if item.override and item.override.label:
            used.append(item.override.label)
        for label in used:
            labels[label.name] = weights.label_weight(label.id)
        if item.subject.casefold() not in seen:
            seen.add(item.subject.casefold())
            subjects[item.subject] = weights.subject_weight(item.subject)
    return {
        "types": {key: weights.types.get(key, DEFAULT_WEIGHT) for key in TYPE_KEYS},
        "labels": dict(sorted(labels.items(), key=lambda kv: kv[0].casefold())),
        "subjects": dict(sorted(subjects.items(), key=lambda kv: kv[0].casefold())),
    }


def merge_subject_weights(
    stored: Mapping[str, float], present: Mapping[str, float]
) -> dict[str, float]:
    """New subject weights: ``present`` replaces matching names, others are kept.

    Only values other than the default are stored. Matching is case-insensitive.
    """
    present_keys = {name.casefold() for name in present}
    merged = {
        name: weight
        for name, weight in stored.items()
        if name.casefold() not in present_keys
    }
    for name, weight in present.items():
        if weight != DEFAULT_WEIGHT:
            merged[name] = weight
    return merged


def subjects_of(items: Iterable[HomeworkItem]) -> list[str]:
    """Distinct subjects (case-insensitive), in alphabetical order."""
    seen: dict[str, str] = {}
    for item in items:
        if item.subject:
            seen.setdefault(item.subject.casefold(), item.subject)
    return sorted(seen.values(), key=str.casefold)
