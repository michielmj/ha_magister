"""Pure homework planner logic: extraction, periods, weights and averages."""

from __future__ import annotations

import json
from datetime import UTC, date, datetime, time, timedelta
from pathlib import Path
from typing import Any

import pytest

from custom_components.magister.api import Appointment
from custom_components.magister.api.homework import (
    HomeworkItem,
    LabelOption,
    ManualLabel,
    Weights,
    default_label_options,
    effective_weights,
    extract_homework,
    homework_periods,
    item_uid,
    items_in_period,
    merge_subject_weights,
    next_week_fits,
    parse_label_options,
    skipped_days,
    subjects_of,
    summarize,
)
from custom_components.magister.api.mapping import LOCAL_TZ
from custom_components.magister.coordinator import fetch_window

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
    ("today", "next_day", "week", "next_week"),
    [
        # Monday 9 to Sunday 15 November 2026: (first day, last day inclusive).
        (date(2026, 11, 9), (9, 10), (7, 13), (14, 20)),
        (date(2026, 11, 10), (10, 11), (7, 13), (14, 20)),
        (date(2026, 11, 11), (11, 12), (7, 13), (14, 20)),
        (date(2026, 11, 12), (12, 13), (7, 13), (14, 20)),
        # Friday: Monday is the next school day; the week ends today
        (date(2026, 11, 13), (13, 16), (7, 13), (14, 20)),
        # Saturday: the week starts today
        (date(2026, 11, 14), (14, 16), (14, 20), (21, 27)),
        (date(2026, 11, 15), (15, 16), (14, 20), (21, 27)),
    ],
)
def test_periods(
    today: date,
    next_day: tuple[int, int],
    week: tuple[int, int],
    next_week: tuple[int, int],
) -> None:
    """Next school day, Saturday-Friday this week and the following week."""
    periods = homework_periods(today)
    for name, (first, last) in (
        ("next_day", next_day),
        ("week", week),
        ("next_week", next_week),
    ):
        assert periods[name] == (date(2026, 11, first), date(2026, 11, last + 1))


@pytest.mark.parametrize(
    "start", [date(2026, 3, 16), date(2026, 10, 19), date(2026, 12, 28)]
)
def test_periods_every_weekday_incl_dst_weeks(start: date) -> None:
    """The invariants hold for every weekday, also in the weeks the clocks change."""
    for offset in range(7):
        today = start + timedelta(days=offset)
        periods = homework_periods(today)
        first, end = periods["week"]
        assert first.weekday() == 5 and first <= today < end  # Saturday..Friday
        assert (end - first).days == 7
        assert periods["next_week"] == (end, end + timedelta(days=7))
        next_first, next_end = periods["next_day"]
        assert next_first == today
        last = next_end - timedelta(days=1)
        assert last.weekday() < 5 and last > today  # a school day after today
        assert (last - today).days <= 3
        # no school day lies between today and the next school day
        skipped = skipped_days("next_day", today)
        assert all(day.weekday() >= 5 for day in skipped)
        assert len(skipped) == (last - today).days - 1


@pytest.mark.parametrize("weeks_ahead", [1, 2, 3, 12])
def test_next_week_fits_the_fetch_window(weeks_ahead: int) -> None:
    """Next week lies in the window on every weekday exactly when it is said to fit."""
    fits = []
    for offset in range(7):
        today = date(2026, 11, 9) + timedelta(days=offset)
        window = fetch_window(
            datetime.combine(today, time(12), LOCAL_TZ), 1, weeks_ahead
        )
        fits.append(homework_periods(today)["next_week"][1] <= window[1].date())
    assert all(fits) == next_week_fits(weeks_ahead)


def test_next_day_skips_the_free_days() -> None:
    """On Friday the weekend items are not part of the next-day period."""
    items = extract_homework(
        [
            appointment(Id=1, Start="2026-11-13T08:00:00.0000000Z"),  # Friday
            appointment(Id=2, Start="2026-11-14T08:00:00.0000000Z"),  # Saturday
            appointment(Id=3, Start="2026-11-16T08:00:00.0000000Z"),  # Monday
            appointment(Id=4, Start="2026-11-17T08:00:00.0000000Z"),  # Tuesday
        ],
        HOST,
        1,
    )
    today = date(2026, 11, 13)
    got = items_in_period(
        items, homework_periods(today)["next_day"], skipped_days("next_day", today)
    )
    assert [i.appointment_id for i in got] == [1, 3]
    assert skipped_days("week", today) == frozenset()


def test_periods_across_month_and_year() -> None:
    """The arithmetic crosses month and year ends."""
    periods = homework_periods(date(2026, 12, 31))  # Thursday
    assert periods["next_day"] == (date(2026, 12, 31), date(2027, 1, 2))
    assert periods["week"] == (date(2026, 12, 26), date(2027, 1, 2))
    assert periods["next_week"] == (date(2027, 1, 2), date(2027, 1, 9))


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


def _label(label_id: str, kind: str = "test", note: str = "") -> ManualLabel:
    return ManualLabel(
        label_id, label_id.title(), kind, note, "2026-11-13T10:00:00+00:00"
    )


def test_item_set_is_magister_type_or_manual_label() -> None:
    """Untyped appointments only appear with a manual label; info_type stays None."""
    appointments = [
        appointment(Id=1, InfoType=0),
        appointment(Id=2, InfoType=0),
        appointment(Id=3, InfoType=6),
        appointment(Id=4, InfoType=2),
    ]
    manual = {item_uid(HOST, 1, 2): (_label("a", "homework"),)}
    manual[item_uid(HOST, 1, 3)] = (_label("b"),)
    manual[item_uid(HOST, 1, 4)] = (_label("c", "homework"),)
    items = {
        i.appointment_id: i for i in extract_homework(appointments, HOST, 1, manual)
    }
    assert set(items) == {2, 3, 4}
    assert (items[2].info_type, items[2].label, items[2].is_test) == (None, None, False)
    assert items[3].info_type is None and items[3].is_test  # a test label
    assert items[4].info_type == 2 and items[4].label == "Proefwerk"
    assert items[4].is_test  # Magister type 2


def test_is_test_rule() -> None:
    """Type 2-5 or any manual test label; homework labels do not make a test."""
    plain, homework, test = extract_homework(
        [appointment(Id=1), appointment(Id=2), appointment(Id=3)],
        HOST,
        1,
        {
            item_uid(HOST, 1, 2): (_label("a", "homework"),),
            item_uid(HOST, 1, 3): (_label("a", "homework"), _label("b", "test")),
        },
    )
    assert (plain.is_test, homework.is_test, test.is_test) == (False, False, True)


def test_weight_is_the_max_of_the_labels_times_the_subject() -> None:
    """Magister type and manual labels: highest weight; subject weight multiplies."""
    weights = Weights(
        types={"test": 3.0}, subjects={"wiskunde": 2.0}, labels={"a": 5.0, "b": 0.5}
    )
    items = {
        i.appointment_id: i
        for i in extract_homework(
            [
                appointment(Id=1, InfoType=2),  # type only
                appointment(Id=2, InfoType=2),  # type 3, label 5 -> 5
                appointment(Id=3, InfoType=2),  # type 3, label 0.5 -> 3
                appointment(Id=4, InfoType=0),  # two labels -> 5
                appointment(Id=5, InfoType=0),  # label without weight -> 1
            ],
            HOST,
            1,
            {
                item_uid(HOST, 1, 2): (_label("a"),),
                item_uid(HOST, 1, 3): (_label("b"),),
                item_uid(HOST, 1, 4): (_label("b"), _label("a")),
                item_uid(HOST, 1, 5): (_label("zzz"),),
            },
        )
    }
    got = {i: weights.item_weight(item) for i, item in items.items()}
    assert got == {1: 6.0, 2: 10.0, 3: 6.0, 4: 10.0, 5: 2.0}


def test_effective_weights_lists_the_labels_in_use() -> None:
    """Manual labels present in the period appear by name."""
    items = extract_homework(
        [appointment(Id=1, InfoType=0)],
        HOST,
        1,
        {item_uid(HOST, 1, 1): (_label("a"),)},
    )
    result = effective_weights(items, Weights(labels={"a": 4.0}))
    assert result["labels"] == {"A": 4.0}


def test_weights_parse_labels_leniently() -> None:
    """Bad label weights are ignored, good ones clamped."""
    weights = Weights.from_options({"labels": {"a": 99, "b": "x", "": 1, 3: 1}})
    assert dict(weights.labels) == {"a": 10.0}


def test_label_options_parse_and_defaults() -> None:
    """Defaults are the five Magister names; stored options are parsed leniently."""
    defaults = default_label_options()
    assert [(o.name, o.kind) for o in defaults] == [
        ("Huiswerk", "homework"),
        ("Proefwerk", "test"),
        ("Tentamen", "test"),
        ("SO", "test"),
        ("MO", "test"),
    ]
    assert len({o.id for o in defaults}) == 5
    assert parse_label_options(None) is None
    assert parse_label_options([]) == []
    raw = [
        {"id": "a", "name": " Toetsweek ", "kind": "test"},
        {"id": "a", "name": "dup", "kind": "test"},
        {"id": "b", "name": "X", "kind": "weird"},
        {"id": "", "name": "no id"},
        {"id": "c", "name": "  "},
        "junk",
    ]
    assert parse_label_options(raw) == [
        LabelOption("a", "Toetsweek", "test"),
        LabelOption("b", "X", "homework"),
    ]
