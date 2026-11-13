"""Tests against anonymized real responses of a school (tests/fixtures/school_a)."""

from __future__ import annotations

import json
from collections import Counter
from datetime import UTC
from pathlib import Path
from typing import Any

import pytest

from custom_components.magister.api.models import (
    Account,
    Appointment,
    AppointmentType,
    InfoType,
    Person,
    parse_timestamp,
)

FIXTURES = Path(__file__).parent.parent / "fixtures" / "school_a"


def load(name: str) -> dict[str, Any]:
    """Load a fixture."""
    data: dict[str, Any] = json.loads((FIXTURES / name).read_text(encoding="utf-8"))
    return data


@pytest.fixture(scope="module")
def all_items() -> list[dict[str, Any]]:
    """Raw items without status filter."""
    items: list[dict[str, Any]] = load("appointments.json")["Items"]
    return items


def test_seven_digit_fraction_timestamps() -> None:
    """The real format (7 fractional digits plus Z) parses to UTC-aware values."""
    parsed = parse_timestamp("2026-11-02T08:15:00.0000000Z")
    assert parsed.isoformat() == "2026-11-02T08:15:00+00:00"
    assert parsed.tzinfo is UTC


def test_all_appointments_parse(all_items: list[dict[str, Any]]) -> None:
    """All 140 real items parse into UTC-aware appointments."""
    assert len(all_items) == 140
    appointments = [Appointment.from_json(item) for item in all_items]
    assert all(a.start.tzinfo is not None and a.end > a.start for a in appointments)
    assert Counter(a.type_enum for a in appointments) == Counter(
        {AppointmentType.LESSON: 136, AppointmentType.KWT: 4}
    )
    homework = [a for a in appointments if a.info_type_enum is InfoType.HOMEWORK]
    assert len(homework) == 47
    assert all(a.subject for a in appointments if a.type == 13)


def test_status_filter_hides_exactly_the_cancelled_lessons(
    all_items: list[dict[str, Any]],
) -> None:
    """status=1 drops exactly the 10 Status 5 items."""
    filtered = load("appointments-status1.json")["Items"]
    assert len(filtered) == 130
    filtered_ids = {i["Id"] for i in filtered}
    extra = [i for i in all_items if i["Id"] not in filtered_ids]
    assert len(extra) == 10
    assert {i["Status"] for i in extra} == {5}
    assert {i["Status"] for i in filtered} == {1, 3, 7}


def test_observed_codes_match_the_data(all_items: list[dict[str, Any]]) -> None:
    """The recorded code counts agree with the fixture."""
    observed = load("observed-codes.json")["Kind A"]["without_status_filter"]
    for key in ("Status", "InfoType", "Type"):
        counted = Counter(str(i[key]) for i in all_items)
        assert dict(counted) == observed[key]


def test_account_and_children() -> None:
    """The anonymized parent account and its child parse."""
    account = Account.from_json(load("account.json"))
    assert account.is_parent
    children = [Person.from_json(c) for c in load("children.json")["Items"]]
    assert [c.name for c in children] == ["Kind A"]
    assert children[0].id != account.person.id
