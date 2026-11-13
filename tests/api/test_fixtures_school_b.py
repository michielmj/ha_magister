"""Tests against anonymized real responses of school B (Vakken is always empty)."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

from custom_components.magister.api.models import (
    Account,
    Appointment,
    AppointmentType,
    Person,
)

FIXTURES = Path(__file__).parent.parent / "fixtures"


def load(school: str, name: str) -> dict[str, Any]:
    """Load a fixture."""
    path = FIXTURES / school / name
    data: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    return data


def test_school_b_parses_and_status_filter() -> None:
    """94 items parse; status=1 hides exactly the 5 Status 5 items."""
    items = load("school_b", "appointments.json")["Items"]
    filtered = load("school_b", "appointments-status1.json")["Items"]
    assert (len(items), len(filtered)) == (94, 89)
    parsed = [Appointment.from_json(i) for i in items]
    assert all(a.start.tzinfo is not None for a in parsed)
    kept = {i["Id"] for i in filtered}
    extra = [i for i in items if i["Id"] not in kept]
    assert len(extra) == 5
    assert {i["Status"] for i in extra} == {5}
    assert Counter(i["Status"] for i in items) == {7: 53, 1: 36, 5: 5}


def test_school_b_subject_comes_from_description() -> None:
    """Vakken is empty everywhere; subject = first Omschrijving segment."""
    items = load("school_b", "appointments.json")["Items"]
    parsed = [Appointment.from_json(i) for i in items]
    assert all(a.subjects == () for a in parsed)
    subjects = {a.subject for a in parsed}
    assert {"wisB", "SE NAT", "Schoolfotograaf", "Voorlichting PTA en PTD"} <= subjects
    assert all(subjects)


def test_school_b_types_and_multi_hour_items() -> None:
    """Type 2 items, multi-hour lessons and long group lists parse."""
    parsed = [
        Appointment.from_json(i) for i in load("school_b", "appointments.json")["Items"]
    ]
    general = [a for a in parsed if a.type_enum is AppointmentType.GENERAL]
    assert {a.subject for a in general} == {
        "Schoolfotograaf",
        "Voorlichting PTA en PTD",
    }
    multi = [a for a in parsed if a.period_start != a.period_end]
    assert multi
    assert any((a.period_start, a.period_end) == (4, 5) for a in multi)
    assert any("10 docenten - 10 groepen" in a.description for a in parsed)
    school_exams = [a for a in parsed if a.description.startswith("SE ")]
    assert school_exams
    assert {a.info_type for a in school_exams} == {0}


def test_school_b_cancellation_hint_in_text() -> None:
    """A Status 1 lesson can still say in its text that it is cancelled."""
    items = load("school_b", "appointments.json")["Items"]
    hints = [i for i in items if "gaat niet door" in (i["Inhoud"] or "")]
    assert hints
    assert all(i["Status"] == 1 for i in hints)


def test_school_b_account_children_and_codes() -> None:
    """Account, children and recorded counts agree with the data."""
    assert Account.from_json(load("school_b", "account.json")).is_parent
    kids = [Person.from_json(c) for c in load("school_b", "children.json")["Items"]]
    assert [k.name for k in kids] == ["Kind A"]
    items = load("school_b", "appointments.json")["Items"]
    observed = load("school_b", "observed-codes.json")["Kind A"][
        "without_status_filter"
    ]
    for key in ("Status", "InfoType", "Type"):
        assert dict(Counter(str(i[key]) for i in items)) == observed[key]


def test_school_a_subject_unchanged() -> None:
    """School A keeps using the Vakken names."""
    items = load("school_a", "appointments.json")["Items"]
    parsed = [Appointment.from_json(i) for i in items]
    assert {a.subject for a in parsed if a.type == 13} >= {"wiskunde", "natuurkunde"}


def test_school_b_attachment_flag_without_list() -> None:
    """HeeftBijlagen is true on 3 items while Bijlagen stays null."""
    items = load("school_b", "appointments.json")["Items"]
    flagged = [i["Id"] for i in items if i["HeeftBijlagen"]]
    assert flagged == [100002, 100015, 100032]
    assert all(i["Bijlagen"] is None for i in items)
    assert all(i["Opmerking"] is None and i["Aantekening"] is None for i in items)
