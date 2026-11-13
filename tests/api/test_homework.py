"""Pure homework planner logic: extraction, periods, weights and averages."""

from __future__ import annotations

import json
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import pytest

from custom_components.magister.api import Appointment
from custom_components.magister.api.homework import (
    HomeworkItem,
    Weights,
    effective_weights,
    extract_homework,
    homework_periods,
    item_uid,
    items_in_period,
    merge_subject_weights,
    next_week_fits,
    subjects_of,
    summarize,
)

FIXTURES = Path(__file__).parent.parent / "fixtures"
HOST = "school.magister.net"


def appointment(**overrides: Any) -> Appointment:
    """A lesson with homework on Monday 16 Nov 2026, 09:00 Amsterdam."""
    data: dict[str, Any] = {
        "Id": 7,
        "Start": "2026-11-16T08:00:00.0000000Z",
        "Einde": "2026-11-16T08:45:00.0000000Z",
        "DuurtHeleDag": False,
        "Omschrijving": "wi - D3",
        "Vakken": [{"Naam": "wiskunde"}],
        "LesuurVan": 3,
        "LesuurTotMet": 3,
        "Inhoud": "<p>maken: <b>opg. 1</b></p><ul><li>a</li></ul>",
        "Status": 1,
        "InfoType": 1,
        "Type": 13,
        "HeeftBijlagen": True,
    }
    data.update(overrides)
    return Appointment.from_json(data)


def make_item(**overrides: Any) -> HomeworkItem:
    """A homework item built from ``appointment``."""
    (item,) = extract_homework([appointment(**overrides)], HOST, 1001)
    return item


def test_extract_item_fields() -> None:
    """All fields of an item are taken from the appointment."""
    item = make_item()
    assert item.uid == "school.magister.net:1001:7" == item_uid(HOST, 1001, 7)
    assert item.due_date == date(2026, 11, 16)
    assert item.subject == "wiskunde"
    assert item.label == "Huiswerk"
    assert item.text == "maken: opg. 1\n- a"
    assert item.lesson_hour == 3
    assert item.has_attachments
    assert not item.cancelled
    assert not item.is_test


@pytest.mark.parametrize(
    ("info_type", "label", "is_test"),
    [
        (1, "Huiswerk", False),
        (2, "Proefwerk", True),
        (3, "Tentamen", True),
        (4, "SO", True),
        (5, "MO", True),
    ],
)
def test_info_types_one_to_five(info_type: int, label: str, is_test: bool) -> None:
    """Homework and tests are items."""
    item = make_item(InfoType=info_type)
    assert (item.label, item.is_test) == (label, is_test)


@pytest.mark.parametrize("info_type", [None, 0, 6, 7, 99])
def test_other_info_types_are_not_items(info_type: int | None) -> None:
    """Information and everything else is not homework."""
    assert extract_homework([appointment(InfoType=info_type)], HOST, 1) == []


@pytest.mark.parametrize("status", [4, 5])
def test_cancelled_lessons_are_kept_and_marked(status: int) -> None:
    """Homework on a cancelled lesson is shown, marked cancelled."""
    assert make_item(Status=status).cancelled


def test_all_day_item_uses_local_date() -> None:
    """An all-day item starting at 23:00 UTC is due on the next local day."""
    item = make_item(Start="2026-11-15T23:00:00.0000000Z", DuurtHeleDag=True)
    assert item.due_date == date(2026, 11, 16)
    assert item.all_day


def test_subject_falls_back_to_description() -> None:
    """Schools without Vakken use the first part of the description."""
    item = make_item(Vakken=[], Omschrijving="wisB - K4wisB_1 - D1")
    assert item.subject == "wisB"


def test_items_are_sorted_by_time_hour_and_id() -> None:
    """Order: due time, lesson hour, appointment id."""
    items = extract_homework(
        [
            appointment(Id=3, Start="2026-11-17T08:00:00.0000000Z"),
            appointment(Id=2),
            appointment(Id=1),
        ],
        HOST,
        1,
    )
    assert [i.appointment_id for i in items] == [1, 2, 3]


@pytest.mark.parametrize(
    ("today", "tomorrow", "week", "next_week"),
    [
        # Friday
        (date(2026, 11, 13), (14, 15), (9, 16), (16, 23)),
        # Monday: this week includes today
        (date(2026, 11, 9), (10, 11), (9, 16), (16, 23)),
        # Sunday: tomorrow is next week's Monday
        (date(2026, 11, 15), (16, 17), (9, 16), (16, 23)),
    ],
)
def test_periods(
    today: date,
    tomorrow: tuple[int, int],
    week: tuple[int, int],
    next_week: tuple[int, int],
) -> None:
    """Tomorrow, Mon-Sun this week (past days included) and next week."""
    periods = homework_periods(today)
    for name, (first, end) in (
        ("tomorrow", tomorrow),
        ("week", week),
        ("next_week", next_week),
    ):
        assert periods[name] == (date(2026, 11, first), date(2026, 11, end))


def test_periods_across_month_and_year() -> None:
    """The week arithmetic crosses month and year ends."""
    periods = homework_periods(date(2026, 12, 31))
    assert periods["tomorrow"][0] == date(2027, 1, 1)
    assert periods["next_week"] == (date(2027, 1, 4), date(2027, 1, 11))


def test_next_week_fits() -> None:
    """Next week needs at least two weeks ahead."""
    assert [next_week_fits(w) for w in (1, 2, 3)] == [False, True, True]


def test_items_in_period_is_end_exclusive() -> None:
    """The day after the period does not belong to it."""
    items = extract_homework(
        [
            appointment(Id=1, Start="2026-11-15T10:00:00.0000000Z"),
            appointment(Id=2, Start="2026-11-16T10:00:00.0000000Z"),
        ],
        HOST,
        1,
    )
    period = (date(2026, 11, 9), date(2026, 11, 16))
    assert [i.appointment_id for i in items_in_period(items, period)] == [1]


def _items() -> list[HomeworkItem]:
    return extract_homework(
        [
            appointment(Id=1),
            appointment(Id=2, InfoType=2, Vakken=[{"Naam": "Duits"}]),
            appointment(Id=3, Vakken=[{"Naam": "duits"}]),
        ],
        HOST,
        1,
    )


def test_summary_empty_is_100() -> None:
    """Nothing due means nothing left to do."""
    result = summarize([], lambda _: 0, Weights())
    assert (result.value, result.items, result.completed) == (100.0, 0, 0)


def test_summary_unweighted_average() -> None:
    """Without weights it is the plain average, with counts."""
    progress = {"school.magister.net:1:1": 100, "school.magister.net:1:2": 50}
    result = summarize(_items(), lambda uid: progress.get(uid, 0), Weights())
    assert result.value == 50.0
    assert (result.items, result.completed, result.open, result.tests) == (3, 1, 2, 1)


def test_summary_weighted() -> None:
    """Sum(w x p) / Sum(w) with type weight x subject weight."""
    weights = Weights.from_options(
        {"types": {"test": 3}, "subjects": {"DUITS": 2, "wiskunde": 0.5}}
    )
    progress = {
        "school.magister.net:1:1": 100,  # w = 1 x 0.5
        "school.magister.net:1:2": 0,  # w = 3 x 2 (case-insensitive subject)
        "school.magister.net:1:3": 50,  # w = 1 x 2
    }
    result = summarize(_items(), lambda uid: progress[uid], weights)
    assert result.value == round((0.5 * 100 + 6 * 0 + 2 * 50) / 8.5, 1)


def test_summary_zero_weights_do_not_count() -> None:
    """A weight of 0 leaves the item out; all zero means 100 %."""
    weights = Weights.from_options({"types": {"homework": 0}})
    result = summarize(_items(), lambda _: 0, weights)
    assert result.value == 0.0 and result.items == 3
    only_zero = [i for i in _items() if not i.is_test]
    assert summarize(only_zero, lambda _: 0, weights).value == 100.0


def test_weights_parse_leniently() -> None:
    """Bad stored data is ignored, values are clamped to 0-10."""
    weights = Weights.from_options(
        {
            "types": {"test": 99, "nope": 2, "exam": "x", "homework": True},
            "subjects": {"a": -3, "": 2, "b": float("nan"), 5: 1},
        }
    )
    assert dict(weights.types) == {"test": 10.0}
    assert dict(weights.subjects) == {"a": 0.0}
    assert Weights.from_options("junk") == Weights()
    assert Weights.from_options({"types": 3, "subjects": []}) == Weights()


def test_effective_weights_lists_types_and_present_subjects() -> None:
    """All five types, the subjects in the items, sorted without case."""
    weights = Weights.from_options({"types": {"test": 2}, "subjects": {"Duits": 3}})
    result = effective_weights(_items(), weights)
    assert result["types"] == {
        "homework": 1.0,
        "test": 2.0,
        "exam": 1.0,
        "written_quiz": 1.0,
        "oral_quiz": 1.0,
    }
    assert result["subjects"] == {"Duits": 3.0, "wiskunde": 1.0}


def test_merge_subject_weights() -> None:
    """Present subjects replace matches, absent ones stay, defaults are dropped."""
    merged = merge_subject_weights(
        {"Duits": 2, "oud vak": 3, "wisB": 4}, {"duits": 1.0, "wisb": 0.5, "ak": 1.0}
    )
    assert merged == {"oud vak": 3, "wisb": 0.5}


def test_subjects_of_is_distinct_and_sorted() -> None:
    """Case-insensitive distinct subjects, first spelling kept."""
    assert subjects_of(_items()) == ["Duits", "wiskunde"]


@pytest.mark.parametrize("school", ["school_a", "school_b"])
def test_fixture_items(school: str) -> None:
    """Fixtures give items of types 1-5 only, sorted, with unique uids."""
    data = json.loads((FIXTURES / school / "appointments.json").read_text("utf-8"))
    appointments = [Appointment.from_json(i) for i in data["Items"]]
    items = extract_homework(appointments, HOST, 1001)
    assert items
    assert len({i.uid for i in items}) == len(items)
    assert all(1 <= i.info_type <= 5 for i in items)
    assert [i.start for i in items] == sorted(i.start for i in items)
    assert any(i.cancelled for i in items)
    assert datetime(2026, 11, 2, tzinfo=UTC) <= items[0].start
