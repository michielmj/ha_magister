"""Data models and parsing for the Magister data API."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import IntEnum
from typing import Any

from .errors import MagisterApiError

_TS_RE = re.compile(r"^(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})(?:\.\d+)?(?:Z|\+00:00)?$")

PARENT_GROUP = "Ouder"


class InfoType(IntEnum):
    """Appointment ``InfoType`` codes (community-reported, see docs/reference)."""

    NONE = 0
    HOMEWORK = 1
    TEST = 2
    EXAM = 3
    WRITTEN_QUIZ = 4
    ORAL_QUIZ = 5
    INFORMATION = 6
    NOTE = 7


class AppointmentType(IntEnum):
    """Appointment ``Type`` codes (community-reported, see docs/reference)."""

    PERSONAL = 1
    GENERAL = 2
    SCHOOLWIDE = 3
    INTERNSHIP = 4
    INTAKE = 5
    FREE = 6
    KWT = 7
    LESSON = 13
    PLANNING = 16


def _enum_or_none[E: IntEnum](cls: type[E], value: int | None) -> E | None:
    """Return the enum member for ``value`` or ``None`` when unknown."""
    if value is None:
        return None
    try:
        return cls(value)
    except ValueError:
        return None


def parse_timestamp(value: str) -> datetime:
    """Parse a Magister UTC timestamp (any number of fractional digits)."""
    match = _TS_RE.match(value) if isinstance(value, str) else None
    if match is None:
        raise MagisterApiError("Unexpected timestamp format in response")
    return datetime.strptime(match.group(1), "%Y-%m-%dT%H:%M:%S").replace(tzinfo=UTC)


def _opt_int(value: Any) -> int | None:
    """Return ``value`` as int, or ``None`` when it is not an int."""
    if isinstance(value, bool) or not isinstance(value, int):
        return None
    return value


def _names(items: Any, key: str = "Naam") -> tuple[str, ...]:
    """Collect non-empty ``key`` strings from a list of dicts."""
    if not isinstance(items, list):
        return ()
    return tuple(
        str(item[key]) for item in items if isinstance(item, dict) and item.get(key)
    )


@dataclass(frozen=True, slots=True)
class Person:
    """A person: the account holder or a child."""

    id: int
    first_name: str
    infix: str
    last_name: str
    initials: str

    @property
    def name(self) -> str:
        """Display name: call name (or initials), infix and last name."""
        parts = [self.first_name or self.initials, self.infix, self.last_name]
        return " ".join(part for part in parts if part) or f"person {self.id}"

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> Person:
        """Parse a ``Persoon`` / child item."""
        try:
            person_id = int(data["Id"])
        except (KeyError, TypeError, ValueError) as err:
            raise MagisterApiError("Person without a valid Id in response") from err
        return cls(
            id=person_id,
            first_name=str(data.get("Roepnaam") or ""),
            infix=str(data.get("Tussenvoegsel") or ""),
            last_name=str(data.get("Achternaam") or ""),
            initials=str(data.get("Voorletters") or ""),
        )


@dataclass(frozen=True, slots=True)
class Account:
    """The logged-in account: a person plus its groups (e.g. ``Ouder``)."""

    person: Person
    groups: tuple[str, ...]

    @property
    def is_parent(self) -> bool:
        """Whether this is a parent account (agenda belongs to the children)."""
        return PARENT_GROUP in self.groups

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> Account:
        """Parse the ``/api/account`` response."""
        persoon = data.get("Persoon")
        if not isinstance(persoon, dict):
            raise MagisterApiError("Account response has no Persoon")
        return cls(person=Person.from_json(persoon), groups=_names(data.get("Groep")))


@dataclass(frozen=True, slots=True)
class Appointment:
    """An agenda item (lesson, homework, test, personal or school event)."""

    id: int
    start: datetime
    end: datetime
    all_day: bool
    description: str
    subjects: tuple[str, ...]
    location: str
    classrooms: tuple[str, ...]
    teachers: tuple[str, ...]
    period_start: int | None
    period_end: int | None
    content: str
    status: int | None
    info_type: int | None
    type: int | None
    afgerond: bool
    has_attachments: bool = False

    @property
    def subject(self) -> str:
        """Subject names joined with a comma.

        Some schools leave ``Vakken`` empty; then the subject is the first
        `` - `` segment of ``Omschrijving`` (e.g. ``wisB - K4wisB_1 - D1 - ...``).
        """
        if self.subjects:
            return ", ".join(self.subjects)
        return self.description.split(" - ", 1)[0].strip()

    @property
    def info_type_enum(self) -> InfoType | None:
        """``info_type`` as enum, ``None`` when unknown."""
        return _enum_or_none(InfoType, self.info_type)

    @property
    def type_enum(self) -> AppointmentType | None:
        """``type`` as enum, ``None`` when unknown."""
        return _enum_or_none(AppointmentType, self.type)

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> Appointment:
        """Parse one item of the ``afspraken`` response."""
        try:
            appointment_id = int(data["Id"])
            start = parse_timestamp(data["Start"])
            end = parse_timestamp(data["Einde"])
        except (KeyError, TypeError, ValueError) as err:
            raise MagisterApiError(
                "Appointment with missing fields in response"
            ) from err
        classrooms = _names(data.get("Lokalen"))
        return cls(
            id=appointment_id,
            start=start,
            end=end,
            all_day=bool(data.get("DuurtHeleDag")),
            description=str(data.get("Omschrijving") or ""),
            subjects=_names(data.get("Vakken")),
            location=str(data.get("Lokatie") or ", ".join(classrooms)),
            classrooms=classrooms,
            teachers=_names(data.get("Docenten")),
            period_start=_opt_int(data.get("LesuurVan")),
            period_end=_opt_int(data.get("LesuurTotMet")),
            content=str(data.get("Inhoud") or ""),
            status=_opt_int(data.get("Status")),
            info_type=_opt_int(data.get("InfoType")),
            type=_opt_int(data.get("Type")),
            afgerond=bool(data.get("Afgerond")),
            has_attachments=bool(data.get("HeeftBijlagen")),
        )
