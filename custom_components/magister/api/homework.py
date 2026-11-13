"""Homework planner logic (pure, no Home Assistant imports).

A homework item is a Magister appointment with InfoType 1-5 (homework, test, exam,
written quiz, oral quiz). This module extracts the items, computes the periods
(tomorrow, this week, next week in Europe/Amsterdam) and the weighted progress.
"""

from __future__ import annotations

import math
from collections.abc import Callable, Iterable, Mapping
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
TEST_INFO_TYPES: Final = frozenset({2, 3, 4, 5})

PERIOD_TOMORROW: Final = "tomorrow"
PERIOD_WEEK: Final = "week"
PERIOD_NEXT_WEEK: Final = "next_week"
PERIODS: Final = (PERIOD_TOMORROW, PERIOD_WEEK, PERIOD_NEXT_WEEK)

WEIGHT_MIN: Final = 0.0
WEIGHT_MAX: Final = 10.0
DEFAULT_WEIGHT: Final = 1.0

PROGRESS_STEPS: Final = (0, 25, 50, 75, 100)


@dataclass(frozen=True, slots=True)
class HomeworkItem:
    """One homework or test item of a child."""

    uid: str
    appointment_id: int
    start: datetime
    due_date: date
    all_day: bool
    subject: str
    info_type: int
    label: str
    text: str
    cancelled: bool
    lesson_hour: int | None
    has_attachments: bool

    @property
    def is_test(self) -> bool:
        """Whether this is a test (InfoType 2-5) rather than plain homework."""
        return self.info_type in TEST_INFO_TYPES


def item_uid(host: str, child_id: int, appointment_id: int) -> str:
    """Stable key of an item: ``<host>:<childId>:<appointmentId>``."""
    return f"{host}:{child_id}:{appointment_id}"


def extract_homework(
    appointments: Iterable[Appointment], host: str, child_id: int
) -> list[HomeworkItem]:
    """Homework items of a child, ordered by due time, lesson hour and id."""
    items: list[HomeworkItem] = []
    for appointment in appointments:
        info_type = appointment.info_type
        if info_type is None or info_type not in HOMEWORK_TYPES:
            continue
        items.append(
            HomeworkItem(
                uid=item_uid(host, child_id, appointment.id),
                appointment_id=appointment.id,
                start=appointment.start,
                due_date=appointment.start.astimezone(LOCAL_TZ).date(),
                all_day=appointment.all_day,
                subject=appointment.subject,
                info_type=info_type,
                label=HOMEWORK_TYPES[info_type][1],
                text=html_to_text(appointment.content),
                cancelled=appointment.status in CANCELLED_STATUSES,
                lesson_hour=appointment.period_start,
                has_attachments=appointment.has_attachments,
            )
        )
    items.sort(key=lambda i: (i.start, i.lesson_hour or 0, i.uid))
    return items


def homework_periods(today: date) -> dict[str, tuple[date, date]]:
    """Periods as ``(first day, day after the last)`` for the local date ``today``.

    Tomorrow is ``today + 1``; this week is Monday to Sunday of the current week
    (days already past included); next week is the following Monday to Sunday.
    """
    monday = today - timedelta(days=today.weekday())
    tomorrow = today + timedelta(days=1)
    return {
        PERIOD_TOMORROW: (tomorrow, tomorrow + timedelta(days=1)),
        PERIOD_WEEK: (monday, monday + timedelta(days=7)),
        PERIOD_NEXT_WEEK: (monday + timedelta(days=7), monday + timedelta(days=14)),
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
    """Weights of one child, per type and per subject (default 1).

    ``types`` is keyed by the names in ``TYPE_KEYS``; ``subjects`` by the subject
    as it was stored. Subject matching is exact and case-insensitive.
    """

    types: Mapping[str, float] = field(default_factory=dict)
    subjects: Mapping[str, float] = field(default_factory=dict)

    @classmethod
    def from_options(cls, raw: Any) -> Weights:
        """Parse the stored form ``{"types": {...}, "subjects": {...}}`` leniently."""
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
        return cls(types, subjects)

    def type_weight(self, info_type: int) -> float:
        """Weight of an InfoType."""
        key = HOMEWORK_TYPES[info_type][0]
        return self.types.get(key, DEFAULT_WEIGHT)

    def subject_weight(self, subject: str) -> float:
        """Weight of a subject (case-insensitive)."""
        wanted = subject.casefold()
        for name, weight in self.subjects.items():
            if name.casefold() == wanted:
                return weight
        return DEFAULT_WEIGHT

    def item_weight(self, item: HomeworkItem) -> float:
        """``type_weight x subject_weight`` of an item."""
        return self.type_weight(item.info_type) * self.subject_weight(item.subject)


@dataclass(frozen=True, slots=True)
class PeriodSummary:
    """Progress statistics of the items due in one period."""

    value: float
    items: int
    completed: int
    open: int
    tests: int


def items_in_period(
    items: Iterable[HomeworkItem], period: tuple[date, date]
) -> list[HomeworkItem]:
    """Items due on a day in ``[first, end)``."""
    first, end = period
    return [item for item in items if first <= item.due_date < end]


def summarize(
    items: Iterable[HomeworkItem],
    progress: Callable[[str], int],
    weights: Weights,
) -> PeriodSummary:
    """Weighted average progress: sum(w x p) / sum(w), 100 when nothing counts."""
    count = completed = tests = 0
    weighted = total_weight = 0.0
    for item in items:
        count += 1
        done = progress(item.uid)
        completed += done >= 100
        tests += item.is_test
        weight = weights.item_weight(item)
        weighted += weight * done
        total_weight += weight
    average = weighted / total_weight if total_weight > 0 else 100.0
    return PeriodSummary(
        value=round(average, 1),
        items=count,
        completed=completed,
        open=count - completed,
        tests=tests,
    )


def effective_weights(
    items: Iterable[HomeworkItem], weights: Weights
) -> dict[str, dict[str, float]]:
    """The weights in use for ``items``: all types and the subjects present."""
    subjects: dict[str, float] = {}
    seen: set[str] = set()
    for item in items:
        if item.subject.casefold() not in seen:
            seen.add(item.subject.casefold())
            subjects[item.subject] = weights.subject_weight(item.subject)
    return {
        "types": {key: weights.types.get(key, DEFAULT_WEIGHT) for key in TYPE_KEYS},
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
