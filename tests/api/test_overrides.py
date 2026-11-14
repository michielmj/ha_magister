"""Overrides of the Magister label: the effective state of an item (pure logic)."""

from __future__ import annotations

from dataclasses import replace
from typing import Any

import pytest

from custom_components.magister.api.homework import (
    MODE_DISABLE,
    MODE_REPLACE,
    HomeworkItem,
    LabelOption,
    ManualLabel,
    Override,
    Weights,
    effective_state,
    effective_weights,
    extract_homework,
    item_uid,
    magister_label_text,
    summarize,
)
from custom_components.magister.api.mapping import build_summary

from .test_homework import HOST, appointment

HOMEWORK = LabelOption("default_homework", "Huiswerk", "homework")
TEST = LabelOption("default_test", "Proefwerk", "test")
EXTRA = LabelOption("ex", "Extra", "homework")
TOETS = LabelOption("tw", "Toetsweek", "test")
WEIGHTS = Weights(
    types={"homework": 1.5, "test": 3.0},
    labels={"ex": 2.0, "tw": 5.0},
    subjects={"wiskunde": 2.0},
)


def manual(option: LabelOption) -> ManualLabel:
    """A manual label of an option."""
    return ManualLabel(option.id, option.name, option.kind, "", "")


def item(
    info_type: int | None,
    override: Override | None = None,
    labels: tuple[LabelOption, ...] = (),
    subject: str = "Frans",
) -> HomeworkItem:
    """One item through ``extract_homework``."""
    data: dict[str, Any] = {"Id": 1, "InfoType": info_type or 0}
    data["Vakken"] = [{"Naam": subject}]
    uid = item_uid(HOST, 1, 1)
    (result,) = extract_homework(
        [appointment(**data)],
        HOST,
        1,
        {uid: tuple(manual(o) for o in labels)} if labels else None,
        {uid: override} if override else None,
    )
    return result


@pytest.mark.parametrize(
    ("info_type", "override", "labels", "active", "disabled", "is_test", "weight"),
    [
        # no override: the original label
        (1, None, (), ["default_homework"], False, False, 1.5),
        (2, None, (), ["default_test"], False, True, 3.0),
        # replaced: weights, kind and test highlight follow the replacement
        (
            2,
            Override(MODE_REPLACE, HOMEWORK),
            (),
            ["default_homework"],
            False,
            False,
            1.5,
        ),
        (1, Override(MODE_REPLACE, TOETS), (), ["tw"], False, True, 5.0),
        # replacement plus manual labels: the maximum
        (
            2,
            Override(MODE_REPLACE, HOMEWORK),
            (EXTRA,),
            ["default_homework", "ex"],
            False,
            False,
            2.0,
        ),
        # disabled alone: nothing active, weight 0
        (2, Override(MODE_DISABLE), (), [], True, False, 0.0),
        # disabled with a manual label: the item stays active, weight from the label
        (2, Override(MODE_DISABLE), (EXTRA,), ["ex"], False, False, 2.0),
        (2, Override(MODE_DISABLE), (TOETS,), ["tw"], False, True, 5.0),
        # manual labels only (no Magister label)
        (None, None, (EXTRA,), ["ex"], False, False, 2.0),
        # an override on an appointment without a Magister label is ignored
        (None, Override(MODE_DISABLE), (EXTRA,), ["ex"], False, False, 2.0),
    ],
)
def test_effective_state_truth_table(
    info_type: int | None,
    override: Override | None,
    labels: tuple[LabelOption, ...],
    active: list[str],
    disabled: bool,
    is_test: bool,
    weight: float,
) -> None:
    """The one function that decides label, test, disabled and weight."""
    state = effective_state(item(info_type, override, labels), WEIGHTS)
    assert [label.id for label in state.active_labels] == active
    assert (state.disabled, state.is_test, state.weight) == (disabled, is_test, weight)


def test_subject_weight_multiplies_and_disabled_is_zero() -> None:
    """max(active label weights) x subject weight; 0 when disabled."""
    assert effective_state(item(2, subject="wiskunde"), WEIGHTS).weight == 6.0
    disabled = item(2, Override(MODE_DISABLE), subject="wiskunde")
    assert effective_state(disabled, WEIGHTS).weight == 0.0


def test_effective_label() -> None:
    """The original, the replacement, or none."""
    assert effective_state(item(2), WEIGHTS).effective_label == TEST
    replaced = item(2, Override(MODE_REPLACE, HOMEWORK))
    assert effective_state(replaced, WEIGHTS).effective_label == HOMEWORK
    assert (
        effective_state(item(2, Override(MODE_DISABLE)), WEIGHTS).effective_label
        is None
    )
    assert effective_state(item(None, None, (EXTRA,)), WEIGHTS).effective_label is None


def test_label_text_for_titles() -> None:
    """``None`` original, ``""`` disabled, ``Proefwerk->Huiswerk`` replaced."""
    assert magister_label_text(item(2)) is None
    assert magister_label_text(item(2, Override(MODE_DISABLE))) == ""
    assert (
        magister_label_text(item(2, Override(MODE_REPLACE, HOMEWORK)))
        == "Proefwerk→Huiswerk"
    )
    assert magister_label_text(item(None, None, (EXTRA,))) is None


def test_build_summary_with_label_text() -> None:
    """The Magister label in a title: original, replaced or omitted."""
    appt = appointment(InfoType=2)
    assert build_summary(appt, ["Extra"]) == "[Proefwerk] [Extra] wiskunde"
    assert (
        build_summary(appt, ["Extra"], "Proefwerk→Huiswerk")
        == "[Proefwerk→Huiswerk] [Extra] wiskunde"
    )
    assert build_summary(appt, ["Extra"], "") == "[Extra] wiskunde"
    assert build_summary(appt, (), "") == "wiskunde"


def test_summarize_ignores_disabled_items() -> None:
    """Disabled items have no weight and are not counted; replacements follow."""
    items = [
        item(1),
        item(2, Override(MODE_DISABLE)),
        item(2, Override(MODE_REPLACE, HOMEWORK)),
    ]
    items = [replace(i, uid=f"{i.uid}-{n}") for n, i in enumerate(items)]
    result = summarize(items, lambda uid: 50 if uid.endswith("-0") else 0, WEIGHTS)
    assert (result.items, result.open, result.tests) == (2, 2, 0)
    assert result.value == 25.0
    only_disabled = [item(2, Override(MODE_DISABLE))]
    assert summarize(only_disabled, lambda _: 0, WEIGHTS).value == 100.0
    assert summarize(only_disabled, lambda _: 0, WEIGHTS).items == 0


def test_effective_weights_list_the_replacement() -> None:
    """A replacement option shows up in the weights in use, by name."""
    result = effective_weights([item(1, Override(MODE_REPLACE, TOETS))], WEIGHTS)
    assert result["labels"] == {"Toetsweek": 5.0}


def test_extract_ignores_overrides_without_magister_label() -> None:
    """Only appointments with a Magister label take an override."""
    assert item(None, Override(MODE_DISABLE), (EXTRA,)).override is None
    assert item(2, Override(MODE_DISABLE)).override == Override(MODE_DISABLE)
