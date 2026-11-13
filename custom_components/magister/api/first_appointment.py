"""Find the first appointment of a day (pure logic, no Home Assistant imports)."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date, tzinfo

from .mapping import CANCELLED_STATUSES
from .models import Appointment


@dataclass(frozen=True, slots=True)
class FirstAppointment:
    """Result of :func:`find_first_appointment`.

    ``appointment`` is ``None`` when nothing qualifies on that day; ``skipped``
    counts the timed items before it (or all of the day) that were cancelled or
    excluded.
    """

    appointment: Appointment | None
    skipped: int


def normalize_subject(subject: str) -> str:
    """Key used to compare subjects: trimmed and case-insensitive."""
    return subject.strip().casefold()


def find_first_appointment(
    appointments: Iterable[Appointment],
    day: date,
    excluded: Iterable[str],
    tz: tzinfo,
) -> FirstAppointment:
    """Return the first timed, not cancelled, not excluded item on local ``day``.

    ``appointments`` are considered in start order (ties by id). All-day items are
    never counted. Subject matching is exact (not substring) and case-insensitive.
    """
    excluded_keys = {normalize_subject(item) for item in excluded}
    candidates = sorted(
        (
            item
            for item in appointments
            if not item.all_day and item.start.astimezone(tz).date() == day
        ),
        key=lambda item: (item.start, item.id),
    )
    skipped = 0
    for item in candidates:
        if (
            item.status in CANCELLED_STATUSES
            or normalize_subject(item.subject) in excluded_keys
        ):
            skipped += 1
            continue
        return FirstAppointment(item, skipped)
    return FirstAppointment(None, skipped)
