"""Tests for model parsing."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pytest

from custom_components.magister.api.errors import MagisterApiError
from custom_components.magister.api.models import (
    Account,
    Appointment,
    AppointmentType,
    InfoType,
    Person,
    parse_timestamp,
)


def lesson(**overrides: Any) -> dict[str, Any]:
    """A typical lesson item."""
    item: dict[str, Any] = {
        "Id": 1001,
        "Start": "2026-11-09T07:30:00.0000000Z",
        "Einde": "2026-11-09T08:20:00.0000000Z",
        "DuurtHeleDag": False,
        "Omschrijving": "wi - 1.01",
        "Lokatie": "",
        "Lokalen": [{"Naam": "A101"}, {"Naam": ""}],
        "Vakken": [{"Naam": "Wiskunde"}],
        "Docenten": [{"Naam": "Docent 1"}],
        "LesuurVan": 1,
        "LesuurTotMet": 2,
        "Inhoud": "<p>Maak opgave 3</p>",
        "Status": 1,
        "InfoType": 2,
        "Type": 13,
        "Afgerond": True,
    }
    item.update(overrides)
    return item


def test_parse_timestamp() -> None:
    """Fractions of any length parse into UTC-aware datetimes."""
    expected = datetime(2026, 11, 9, 7, 30, tzinfo=UTC)
    assert parse_timestamp("2026-11-09T07:30:00.0000000Z") == expected
    assert parse_timestamp("2026-11-09T07:30:00Z") == expected
    assert parse_timestamp("2026-11-09T07:30:00+00:00") == expected
    with pytest.raises(MagisterApiError):
        parse_timestamp("yesterday")
    with pytest.raises(MagisterApiError):
        parse_timestamp(None)  # type: ignore[arg-type]


def test_appointment_lesson() -> None:
    """A lesson maps all fields."""
    appointment = Appointment.from_json(lesson())
    assert appointment.id == 1001
    assert appointment.start == datetime(2026, 11, 9, 7, 30, tzinfo=UTC)
    assert appointment.start.tzinfo is not None
    assert appointment.subject == "Wiskunde"
    assert appointment.location == "A101"
    assert appointment.classrooms == ("A101",)
    assert appointment.teachers == ("Docent 1",)
    assert (appointment.period_start, appointment.period_end) == (1, 2)
    assert appointment.content == "<p>Maak opgave 3</p>"
    assert appointment.info_type_enum is InfoType.TEST
    assert appointment.type_enum is AppointmentType.LESSON
    assert appointment.afgerond is True
    assert appointment.all_day is False


def test_appointment_all_day_and_defaults() -> None:
    """All-day items with mostly empty fields parse."""
    appointment = Appointment.from_json(
        {
            "Id": 5,
            "Start": "2026-11-10T00:00:00Z",
            "Einde": "2026-11-11T00:00:00Z",
            "DuurtHeleDag": True,
            "Lokatie": "Aula",
            "Vakken": None,
            "Lokalen": None,
        }
    )
    assert appointment.all_day is True
    assert appointment.location == "Aula"
    assert appointment.subjects == ()
    assert appointment.description == ""
    assert appointment.status is None
    assert appointment.info_type_enum is None
    assert appointment.afgerond is False


def test_appointment_unknown_codes_do_not_crash() -> None:
    """Unknown enum codes stay as ints; the enum helpers return None."""
    appointment = Appointment.from_json(lesson(Status=99, InfoType=77, Type=1234))
    assert appointment.status == 99
    assert appointment.info_type == 77
    assert appointment.info_type_enum is None
    assert appointment.type == 1234
    assert appointment.type_enum is None


def test_appointment_odd_value_types() -> None:
    """Non-int codes become None instead of raising."""
    appointment = Appointment.from_json(
        lesson(Status="x", InfoType=True, LesuurVan=None)
    )
    assert appointment.status is None
    assert appointment.info_type is None
    assert appointment.period_start is None


@pytest.mark.parametrize("missing", ["Id", "Start", "Einde"])
def test_appointment_missing_field(missing: str) -> None:
    """Missing required fields raise an API error."""
    data = lesson()
    del data[missing]
    with pytest.raises(MagisterApiError):
        Appointment.from_json(data)


def test_person_and_account() -> None:
    """Persons and accounts parse; names are assembled."""
    person = Person.from_json(
        {
            "Id": 7,
            "Roepnaam": "Kind",
            "Tussenvoegsel": "van",
            "Achternaam": "Test",
            "Voorletters": "K.",
        }
    )
    assert person.name == "Kind van Test"
    assert Person.from_json({"Id": 8, "Voorletters": "A.B."}).name == "A.B."
    assert Person.from_json({"Id": 9}).name == "person 9"

    account = Account.from_json(
        {"Persoon": {"Id": 7, "Roepnaam": "Ouder"}, "Groep": [{"Naam": "Ouder"}]}
    )
    assert account.is_parent
    student = Account.from_json({"Persoon": {"Id": 1}, "Groep": [{"Naam": "Leerling"}]})
    assert not student.is_parent
    assert Account.from_json({"Persoon": {"Id": 1}}).groups == ()


def test_person_and_account_errors() -> None:
    """Bad payloads raise API errors."""
    with pytest.raises(MagisterApiError):
        Person.from_json({"Roepnaam": "x"})
    with pytest.raises(MagisterApiError):
        Account.from_json({"Groep": []})
