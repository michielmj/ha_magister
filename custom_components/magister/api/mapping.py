"""Map a Magister appointment to calendar fields (HLD section 7).

Pure functions without Home Assistant imports. Texts are Dutch constants because the
event data itself comes from Magister in Dutch.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from html.parser import HTMLParser
from typing import Final
from zoneinfo import ZoneInfo

from .models import Appointment

LOCAL_TZ: Final = ZoneInfo("Europe/Amsterdam")

CANCELLED_STATUSES: Final = frozenset({4, 5})
CHANGED_STATUSES: Final = {9: "Verplaatst", 10: "Verplaatst"}

CANCELLED_PREFIX: Final = "[Vervallen]"
INFO_TYPE_PREFIXES: Final = {
    1: "[Huiswerk]",
    2: "[Proefwerk]",
    3: "[Tentamen]",
    4: "[SO]",
    5: "[MO]",
    6: "[Informatie]",
}
CANCELLED_LINE: Final = "Vervallen"
ATTACHMENTS_LINE: Final = "Bijlagen in Magister"
EN_DASH: Final = "\u2013"
DEFAULT_SUBJECT: Final = "Afspraak"

_BLOCK_TAGS: Final = frozenset(
    {"p", "div", "ul", "ol", "table", "tr", "h1", "h2", "h3", "h4", "h5", "h6"}
)
_SKIP_TAGS: Final = frozenset({"script", "style"})
_SPACES_RE = re.compile(r"[ \t\r\f\v]+")
_BLANK_RUN_RE = re.compile(r"\n{3,}")


class _TextExtractor(HTMLParser):
    """Collects the visible text of an HTML fragment, keeping line structure."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self._skip = 0
        self._at_line_start = True

    def _add(self, text: str) -> None:
        self.parts.append(text)
        self._at_line_start = text.endswith("\n")

    def _line_break(self) -> None:
        """Start a new line unless one has just been started."""
        if not self._at_line_start:
            self._add("\n")

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in _SKIP_TAGS:
            self._skip += 1
        elif tag == "br":
            self._add("\n")
        elif tag == "li":
            self._line_break()
            self._add("- ")
        elif tag in _BLOCK_TAGS:
            self._line_break()

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.handle_starttag(tag, attrs)
        self.handle_endtag(tag)

    def handle_endtag(self, tag: str) -> None:
        if tag in _SKIP_TAGS:
            self._skip = max(self._skip - 1, 0)
        elif tag in _BLOCK_TAGS or tag == "li":
            self._line_break()

    def handle_data(self, data: str) -> None:
        if data and not self._skip:
            self._add(data)


def html_to_text(value: str) -> str:
    """Convert the HTML of ``Inhoud`` to plain text (lists, line breaks, entities)."""
    if not value:
        return ""
    extractor = _TextExtractor()
    extractor.feed(value)
    extractor.close()
    text = "".join(extractor.parts).replace("\xa0", " ")
    lines = [_SPACES_RE.sub(" ", line).strip() for line in text.split("\n")]
    return _BLANK_RUN_RE.sub("\n\n", "\n".join(lines)).strip()


@dataclass(frozen=True, slots=True)
class CalendarFields:
    """Calendar-ready fields of one appointment.

    For all-day items ``start`` and ``end`` are dates (``end`` exclusive), otherwise
    timezone-aware datetimes.
    """

    uid: str
    summary: str
    description: str
    location: str
    start: datetime | date
    end: datetime | date
    all_day: bool


def build_summary(
    appointment: Appointment,
    manual_labels: Sequence[str] = (),
    magister_label: str | None = None,
) -> str:
    """Title: ``[Vervallen]``, the Magister label, manual labels, then the subject.

    ``magister_label`` overrides the Magister label text: ``""`` shows none and
    ``"Proefwerk\u2192Huiswerk"`` a replacement; ``None`` keeps the original.
    """
    parts: list[str] = []
    if appointment.status in CANCELLED_STATUSES:
        parts.append(CANCELLED_PREFIX)
    if magister_label is not None:
        if magister_label:
            parts.append(f"[{magister_label}]")
    elif appointment.info_type is not None and (
        label := INFO_TYPE_PREFIXES.get(appointment.info_type)
    ):
        parts.append(label)
    parts.extend(f"[{name}]" for name in manual_labels)
    parts.append(appointment.subject or DEFAULT_SUBJECT)
    return " ".join(parts)


def lesson_hours(appointment: Appointment) -> str | None:
    """Return ``Lesuur 3`` / a range for lesson items, else ``None``."""
    first, last = appointment.period_start, appointment.period_end
    if first is None:
        return None
    if last is None or last <= first:
        return f"Lesuur {first}"
    return f"Lesuur {first}{EN_DASH}{last}"


def _status_line(appointment: Appointment) -> str | None:
    if appointment.status in CANCELLED_STATUSES:
        return CANCELLED_LINE
    if appointment.status is not None:
        return CHANGED_STATUSES.get(appointment.status)
    return None


def build_description(appointment: Appointment) -> str:
    """Plain-text description (lesson hours, status, details, content)."""
    header = [
        line
        for line in (
            lesson_hours(appointment),
            _status_line(appointment),
            appointment.description,
        )
        if line
    ]
    if appointment.teachers:
        label = "Docenten" if len(appointment.teachers) > 1 else "Docent"
        header.append(f"{label}: {', '.join(appointment.teachers)}")
    sections = ["\n".join(header)] if header else []
    if content := html_to_text(appointment.content):
        sections.append(content)
    if appointment.has_attachments:
        sections.append(ATTACHMENTS_LINE)
    return "\n\n".join(sections)


def _all_day_dates(appointment: Appointment) -> tuple[date, date]:
    """Local start date and exclusive end date of an all-day item."""
    start = appointment.start.astimezone(LOCAL_TZ)
    end = appointment.end.astimezone(LOCAL_TZ)
    end_date = end.date() if end.time() == time.min else end.date() + timedelta(days=1)
    if end_date <= start.date():
        end_date = start.date() + timedelta(days=1)
    return start.date(), end_date


def map_appointment(
    appointment: Appointment,
    host: str,
    manual_labels: Sequence[str] = (),
    magister_label: str | None = None,
) -> CalendarFields:
    """Return the calendar fields for an appointment of school ``host``."""
    start: datetime | date
    end: datetime | date
    if appointment.all_day:
        start, end = _all_day_dates(appointment)
    else:
        start, end = appointment.start, appointment.end
        if end <= start:
            end = start + timedelta(minutes=1)
    return CalendarFields(
        uid=f"magister-{appointment.id}@{host}",
        summary=build_summary(appointment, manual_labels, magister_label),
        description=build_description(appointment),
        location=appointment.location,
        start=start,
        end=end,
        all_day=appointment.all_day,
    )
