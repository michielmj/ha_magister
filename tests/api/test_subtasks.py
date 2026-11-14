"""Subtasks: rolling dates, derived progress and the entries of the periods (pure)."""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from custom_components.magister.api.homework import (
    MODE_DISABLE,
    HomeworkItem,
    Override,
    PeriodSummary,
    Subtask,
    Weights,
    derived_progress,
    entries_in_period,
    extract_homework,
    homework_entries,
    homework_periods,
    item_uid,
    skipped_days,
    split_subtask_uid,
    subtask_current_date,
    subtask_date_allowed,
    subtask_overdue,
    subtask_uid,
    summarize,
    summarize_entries,
)

from .test_homework import HOST, appointment

ITEM_DATE = date(2026, 11, 17)  # Tuesday: the test of the examples
FRIDAY = date(2026, 11, 13)
SATURDAY = date(2026, 11, 14)
SUNDAY = date(2026, 11, 15)
MONDAY = date(2026, 11, 16)


def sub(
    planned: date,
    progress: int = 0,
    completed_on: date | None = None,
    sub_id: str = "a",
) -> Subtask:
    """A subtask."""
    return Subtask(sub_id, "titel", planned, progress, 0, completed_on)


@pytest.mark.parametrize(
    ("planned", "today", "expected"),
    [
        (FRIDAY, FRIDAY, FRIDAY),  # on its day
        (FRIDAY, SATURDAY, SATURDAY),  # rolls into the weekend (calendar days)
        (FRIDAY, SUNDAY, SUNDAY),
        (FRIDAY, MONDAY, MONDAY),
        (FRIDAY, ITEM_DATE, ITEM_DATE),  # but never past the item
        (MONDAY, FRIDAY, MONDAY),  # planned in the future: stays planned
        (FRIDAY, date(2026, 11, 20), ITEM_DATE),  # the item date has passed: stays
        (ITEM_DATE, date(2026, 12, 1), ITEM_DATE),
    ],
)
def test_current_date_of_an_open_subtask(
    planned: date, today: date, expected: date
) -> None:
    """min(max(planned, today), item date)."""
    assert subtask_current_date(sub(planned), ITEM_DATE, today) == expected


def test_overdue_only_when_open_and_the_item_date_passed() -> None:
    """Overdue means: not done and the item date is before today."""
    open_sub, done = sub(FRIDAY), sub(FRIDAY, 100, FRIDAY)
    assert not subtask_overdue(open_sub, ITEM_DATE, ITEM_DATE)
    assert subtask_overdue(open_sub, ITEM_DATE, ITEM_DATE + timedelta(days=1))
    assert not subtask_overdue(done, ITEM_DATE, ITEM_DATE + timedelta(days=5))


def test_done_subtask_stays_where_it_was_completed() -> None:
    """A done subtask no longer moves, clamped to the item date."""
    done = sub(FRIDAY, 100, SATURDAY)
    for today in (SATURDAY, MONDAY, date(2026, 12, 24)):
        assert subtask_current_date(done, ITEM_DATE, today) == SATURDAY
    # completed after the item date (the item moved earlier): clamped
    late = sub(FRIDAY, 100, date(2026, 11, 20))
    assert subtask_current_date(late, ITEM_DATE, date(2026, 11, 25)) == ITEM_DATE
    # completed early (before its planned day) stays on the completion day
    early = sub(MONDAY, 100, FRIDAY)
    assert subtask_current_date(early, ITEM_DATE, MONDAY) == FRIDAY
    # a stored done subtask without a completion date falls back to its planned day
    assert subtask_current_date(sub(MONDAY, 100), ITEM_DATE, SUNDAY) == MONDAY


def test_derived_progress_is_the_rounded_mean() -> None:
    """Plain mean, rounded half up; 0 without subtasks."""
    assert derived_progress([]) == 0
    assert derived_progress([sub(FRIDAY, 100)]) == 100
    assert derived_progress([sub(FRIDAY, 25), sub(FRIDAY, 0), sub(FRIDAY, 0)]) == 8
    assert derived_progress([sub(FRIDAY, 50), sub(FRIDAY, 25)]) == 38  # 37.5
    assert derived_progress([sub(FRIDAY, 100), sub(FRIDAY, 100, sub_id="b")]) == 100
    assert derived_progress([sub(FRIDAY, 100), sub(FRIDAY, 50)]) == 75


@pytest.mark.parametrize(
    ("planned", "item_date", "today", "ok"),
    [
        (FRIDAY, ITEM_DATE, FRIDAY, True),  # today
        (ITEM_DATE, ITEM_DATE, FRIDAY, True),  # the item date
        (SUNDAY, ITEM_DATE, FRIDAY, True),
        (FRIDAY, ITEM_DATE, SATURDAY, False),  # in the past
        (date(2026, 11, 18), ITEM_DATE, FRIDAY, False),  # after the item
        (ITEM_DATE, ITEM_DATE, ITEM_DATE, True),  # item today: only today
        (FRIDAY, ITEM_DATE, ITEM_DATE, False),
        (ITEM_DATE, ITEM_DATE, date(2026, 11, 20), True),  # item past: exactly its date
        (date(2026, 11, 20), ITEM_DATE, date(2026, 11, 20), False),
        (date(2026, 11, 16), ITEM_DATE, date(2026, 11, 20), False),
    ],
)
def test_planned_date_rules(
    planned: date, item_date: date, today: date, ok: bool
) -> None:
    """today <= planned <= item date, or exactly the item date when it is past."""
    assert subtask_date_allowed(planned, item_date, today) is ok


def test_subtask_uid_round_trip() -> None:
    """``<item uid>:sub:<id>`` splits back; plain uids are not subtask uids."""
    uid = item_uid(HOST, 1001, 7)
    assert split_subtask_uid(subtask_uid(uid, "ab12cd34")) == (uid, "ab12cd34")
    assert split_subtask_uid(uid) is None
    assert split_subtask_uid(f"{uid}:sub:") is None


WEIGHTS = Weights(types={"test": 3.0})
TEST_UID = item_uid(HOST, 1, 7)


def make_items(
    subtasks: tuple[Subtask, ...], *, override: Override | None = None
) -> list[HomeworkItem]:
    """A test (weight 3) on Tuesday 17 Nov with subtasks, and a Monday homework."""
    return extract_homework(
        [
            appointment(Id=7, InfoType=2, Start="2026-11-17T08:00:00.0000000Z"),
            appointment(Id=8, InfoType=1, Start="2026-11-16T08:00:00.0000000Z"),
        ],
        HOST,
        1,
        None,
        {TEST_UID: override} if override else None,
        {TEST_UID: subtasks} if subtasks else None,
    )


def own(uid: str) -> int:
    """No own progress."""
    return 0


def summary_for(items: list[HomeworkItem], period: str, today: date) -> PeriodSummary:
    """The summary of a period through the entries."""
    entries = entries_in_period(
        homework_entries(items, own, WEIGHTS, today),
        homework_periods(today)[period],
        skipped_days(period, today),
    )
    return summarize_entries(entries)


SUBTASKS = (
    sub(FRIDAY, 100, FRIDAY, "a"),
    sub(FRIDAY, 0, None, "b"),
    sub(MONDAY, 0, None, "c"),
)


def test_item_with_subtasks_is_replaced_by_its_subtasks() -> None:
    """3 subtasks of a test with weight 3: three entries of weight 1."""
    items = make_items(SUBTASKS)
    entries = homework_entries(items, own, WEIGHTS, FRIDAY)
    mine = [e for e in entries if e.item_uid == TEST_UID]
    assert [e.uid for e in mine] == [subtask_uid(TEST_UID, x) for x in "abc"]
    assert [e.weight for e in mine] == [1.0, 1.0, 1.0]
    assert [e.day for e in mine] == [FRIDAY, FRIDAY, MONDAY]
    assert [e.progress for e in mine] == [100, 0, 0]
    assert all(e.is_test for e in mine)
    # the plain homework counts as before
    (plain,) = (e for e in entries if e.item_uid != TEST_UID)
    assert (plain.uid, plain.day, plain.weight) == (item_uid(HOST, 1, 8), MONDAY, 1.0)
    # the weights add up to the item's weight
    assert sum(e.weight for e in mine) == pytest.approx(3.0)


def test_period_summaries_count_entries() -> None:
    """Worked example, Friday 13 Nov: the entries land in the period of their day."""
    items = make_items(SUBTASKS)
    next_day = summary_for(items, "next_day", FRIDAY)  # Friday + Monday
    assert (next_day.items, next_day.completed, next_day.tests) == (4, 1, 3)
    assert next_day.value == 25.0  # (1x100) / 4 entries of weight 1
    week = summary_for(items, "week", FRIDAY)  # Sat 7 .. Fri 13
    assert (week.items, week.completed, week.value) == (2, 1, 50.0)
    next_week = summary_for(items, "next_week", FRIDAY)  # Sat 14 .. Fri 20
    assert (next_week.items, next_week.completed, next_week.value) == (2, 0, 0.0)


def test_open_subtask_rolls_into_the_next_period_with_the_day() -> None:
    """On Saturday the open subtask 'b' moved to Saturday: now in the new week."""
    items = make_items(SUBTASKS)
    week = summary_for(items, "week", SATURDAY)  # Sat 14 .. Fri 20
    # b (Sat), c (Mon), homework (Mon); the done subtask a stays on Friday
    assert (week.items, week.completed) == (3, 0)
    next_day = summary_for(items, "next_day", SATURDAY)  # Sat + Mon
    assert next_day.items == 3
    assert summary_for(items, "next_week", SATURDAY).items == 0
    # a done subtask is sticky: it is still in last week
    (done,) = (
        e
        for e in homework_entries(items, own, WEIGHTS, SATURDAY)
        if e.uid == subtask_uid(TEST_UID, "a")
    )
    assert done.day == FRIDAY


def test_all_entries_are_counted_exactly_once() -> None:
    """Across disjoint periods the weights add up to the item weight."""
    items = make_items(SUBTASKS)
    today = FRIDAY
    total = sum(
        e.weight
        for e in homework_entries(items, own, WEIGHTS, today)
        if e.item_uid == TEST_UID
    )
    week = homework_periods(today)["week"]
    nxt = homework_periods(today)["next_week"]
    covered = sum(
        e.weight
        for period in (week, nxt)
        for e in entries_in_period(homework_entries(items, own, WEIGHTS, today), period)
        if e.item_uid == TEST_UID
    )
    assert covered == pytest.approx(total) == pytest.approx(3.0)


def test_overdue_subtasks_stay_on_the_item_date() -> None:
    """After the item date an open subtask stays on it (and is counted there)."""
    items = make_items((sub(FRIDAY, 0, None, "a"),))
    today = date(2026, 11, 19)
    entries = [
        e
        for e in homework_entries(items, own, WEIGHTS, today)
        if e.item_uid == TEST_UID
    ]
    assert [e.day for e in entries] == [ITEM_DATE]
    assert summarize(items, own, WEIGHTS, today).items == 2


def test_disabled_item_contributes_nothing() -> None:
    """Disabled: no entries (the subtasks are hidden), as before for plain items."""
    items = make_items(SUBTASKS, override=Override(MODE_DISABLE))
    entries = homework_entries(items, own, WEIGHTS, FRIDAY)
    assert [e.item_uid for e in entries] == [item_uid(HOST, 1, 8)]
    assert summarize(items, own, WEIGHTS, FRIDAY).items == 1


def test_item_without_subtasks_is_unchanged() -> None:
    """An item without subtasks is one entry on its due date with its own progress."""
    items = make_items(())
    entries = homework_entries(items, lambda uid: 40, WEIGHTS, FRIDAY)
    assert [(e.uid, e.day, e.weight, e.progress) for e in entries] == [
        (item_uid(HOST, 1, 8), MONDAY, 1.0, 40),
        (TEST_UID, ITEM_DATE, 3.0, 40),
    ]
    summary = summarize(items, lambda uid: 40, WEIGHTS, FRIDAY)
    assert (summary.value, summary.items) == (40.0, 2)
    assert summarize([], own, WEIGHTS, FRIDAY).value == 100.0
