"""Options flow tests."""

from __future__ import annotations

from datetime import timedelta
from typing import Any
from unittest.mock import patch

import pytest
from aioresponses import aioresponses
from freezegun.api import FrozenDateTimeFactory
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType, InvalidData
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er

from custom_components.magister.api import (
    MagisterApiError,
    MagisterAuthError,
    MagisterClient,
    MagisterConnectionError,
)
from custom_components.magister.const import (
    CONF_CHILDREN,
    CONF_INTERVAL,
    CONF_LABELS,
    CONF_WEEKS_AHEAD,
    CONF_WEEKS_BACK,
    CONF_WEIGHTS,
    DOMAIN,
)
from custom_components.magister.pending import drop_login

from .ha_helpers import CHILD_ID, NOW, FakeMagister, make_entry
from .test_sensor import add_sensor

TWO_CHILDREN = [
    {"Id": 1001, "Roepnaam": "Anna", "Achternaam": "", "Tussenvoegsel": ""},
    {"Id": 1002, "Roepnaam": "Bram", "Achternaam": "", "Tussenvoegsel": ""},
]


@pytest.fixture(autouse=True)
async def frozen_now(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> FrozenDateTimeFactory:
    """Friday 13 November 2026."""
    await hass.config.async_set_time_zone("Europe/Amsterdam")
    freezer.move_to(NOW)
    return freezer


def _password_posts(fake: FakeMagister) -> int:
    return [name for name, *_ in fake.login.posts].count("password")


async def _setup(
    hass: HomeAssistant,
    mocked: aioresponses,
    *,
    children: list[tuple[int, str]] | None = None,
    magister_children: list[dict[str, Any]] | None = None,
    student: bool = False,
) -> tuple[FakeMagister, Any]:
    fake = FakeMagister(mocked, children=magister_children, student=student)
    entry = make_entry(children=children)
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return fake, entry


async def _open_general(hass: HomeAssistant, entry: Any) -> Any:
    """Open the options menu and choose the general settings."""
    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] is FlowResultType.MENU
    assert result["step_id"] == "init"
    assert result["menu_options"] == ["general", "weights", "labels"]
    return await hass.config_entries.options.async_configure(
        result["flow_id"], {"next_step_id": "general"}
    )


async def _init(hass: HomeAssistant, entry: Any) -> Any:
    result = await _open_general(hass, entry)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "general"
    return result


async def test_form_defaults_and_no_extra_password(
    hass: HomeAssistant, mocked: aioresponses
) -> None:
    """The form shows the current values and reuses the kept login."""
    fake, entry = await _setup(hass, mocked, magister_children=TWO_CHILDREN)
    result = await _init(hass, entry)
    assert _password_posts(fake) == 1
    assert fake.account_requests == 1
    keys = {str(k): k for k in result["data_schema"].schema}
    assert keys[CONF_CHILDREN].description["suggested_value"] == [str(CHILD_ID)]
    assert keys[CONF_WEEKS_BACK].description["suggested_value"] == 1
    assert keys[CONF_WEEKS_AHEAD].description["suggested_value"] == 3
    assert keys[CONF_INTERVAL].description["suggested_value"] == 30
    options = result["data_schema"].schema[keys[CONF_CHILDREN]].config["options"]
    assert [o["label"] for o in options] == ["Anna", "Bram"]


async def test_save_options_reloads_without_new_login(
    hass: HomeAssistant, mocked: aioresponses
) -> None:
    """Each field is saved, used by the coordinator, and no login is repeated."""
    fake, entry = await _setup(hass, mocked)
    first = entry.runtime_data
    result = await _init(hass, entry)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            CONF_CHILDREN: [str(CHILD_ID)],
            CONF_WEEKS_BACK: 0,
            CONF_WEEKS_AHEAD: 2,
            CONF_INTERVAL: 60,
        },
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()
    assert entry.options == {
        CONF_WEEKS_BACK: 0,
        CONF_WEEKS_AHEAD: 2,
        CONF_INTERVAL: 60,
    }
    assert entry.state is ConfigEntryState.LOADED
    coordinator = entry.runtime_data.coordinator
    assert coordinator is not first.coordinator
    assert coordinator.update_interval == timedelta(minutes=60)
    # window: from Sunday 8 Nov 23:00 UTC up to today + 15 days
    query = fake.appointment_requests[-1][1]
    assert query["van"].startswith("2026-11-08T23:00")
    assert query["tot"].startswith("2026-11-27T23:00")
    # one reload only, with the kept login: still one password
    assert len(fake.appointment_requests) == 2
    assert _password_posts(fake) == 1
    assert entry.runtime_data.auth is first.auth


async def test_saving_unchanged_values_does_not_reload(
    hass: HomeAssistant, mocked: aioresponses
) -> None:
    """Saving the same values again leaves the running entry alone."""
    fake, entry = await _setup(hass, mocked)
    user_input = {
        CONF_CHILDREN: [str(CHILD_ID)],
        CONF_WEEKS_BACK: 1,
        CONF_WEEKS_AHEAD: 3,
        CONF_INTERVAL: 45,
    }
    for _ in range(2):
        result = await _init(hass, entry)
        await hass.config_entries.options.async_configure(result["flow_id"], user_input)
        await hass.async_block_till_done()
        if _ == 0:
            requests = len(fake.appointment_requests)
            assert requests == 2
    assert len(fake.appointment_requests) == requests


@pytest.mark.parametrize(
    ("field", "value"),
    [
        (CONF_WEEKS_BACK, 9),
        (CONF_WEEKS_BACK, -1),
        (CONF_WEEKS_AHEAD, 0),
        (CONF_WEEKS_AHEAD, 13),
        (CONF_INTERVAL, 14),
        (CONF_INTERVAL, 361),
    ],
)
async def test_values_outside_the_range_are_rejected(
    hass: HomeAssistant, mocked: aioresponses, field: str, value: int
) -> None:
    """Weeks back 0-8, weeks ahead 1-12, interval 15-360 minutes."""
    _, entry = await _setup(hass, mocked)
    result = await _init(hass, entry)
    user_input = {
        CONF_CHILDREN: [str(CHILD_ID)],
        CONF_WEEKS_BACK: 1,
        CONF_WEEKS_AHEAD: 3,
        CONF_INTERVAL: 30,
        field: value,
    }
    with pytest.raises(InvalidData):
        await hass.config_entries.options.async_configure(result["flow_id"], user_input)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        (CONF_WEEKS_BACK, 0),
        (CONF_WEEKS_BACK, 8),
        (CONF_WEEKS_AHEAD, 1),
        (CONF_WEEKS_AHEAD, 12),
        (CONF_INTERVAL, 15),
        (CONF_INTERVAL, 360),
    ],
)
async def test_boundary_values_are_accepted(
    hass: HomeAssistant, mocked: aioresponses, field: str, value: int
) -> None:
    """The limits themselves are valid."""
    _, entry = await _setup(hass, mocked)
    result = await _init(hass, entry)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            CONF_CHILDREN: [str(CHILD_ID)],
            CONF_WEEKS_BACK: 1,
            CONF_WEEKS_AHEAD: 3,
            CONF_INTERVAL: 30,
            field: value,
        },
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()
    assert entry.options[field] == value


async def test_at_least_one_child(hass: HomeAssistant, mocked: aioresponses) -> None:
    """An empty selection is an error on the form."""
    _, entry = await _setup(hass, mocked)
    result = await _init(hass, entry)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            CONF_CHILDREN: [],
            CONF_WEEKS_BACK: 1,
            CONF_WEEKS_AHEAD: 3,
            CONF_INTERVAL: 30,
        },
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "no_children_selected"}


async def test_add_and_remove_child_updates_registries(
    hass: HomeAssistant, mocked: aioresponses
) -> None:
    """A new child gets a calendar and device; a removed one loses all of them."""
    _, entry = await _setup(
        hass, mocked, children=[(1001, "Anna")], magister_children=TWO_CHILDREN
    )
    entities = er.async_get(hass)
    devices = dr.async_get(hass)
    assert hass.states.get("calendar.bram_school_agenda") is None

    async def save(selected: list[int]) -> None:
        result = await _init(hass, entry)
        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            {
                CONF_CHILDREN: [str(child) for child in selected],
                CONF_WEEKS_BACK: 1,
                CONF_WEEKS_AHEAD: 3,
                CONF_INTERVAL: 30,
            },
        )
        assert result["type"] is FlowResultType.CREATE_ENTRY
        await hass.async_block_till_done()

    await save([1001, 1002])
    assert [c["id"] for c in entry.data[CONF_CHILDREN]] == [1001, 1002]
    assert hass.states.get("calendar.bram_school_agenda") is not None
    assert devices.async_get_device_by_identifier(
        (DOMAIN, "school.magister.net:1002"), entry.entry_id
    )

    await save([1001])
    assert [c["id"] for c in entry.data[CONF_CHILDREN]] == [1001]
    assert hass.states.get("calendar.bram_school_agenda") is None
    assert entities.async_get("calendar.bram_school_agenda") is None
    assert (
        devices.async_get_device_by_identifier(
            (DOMAIN, "school.magister.net:1002"), entry.entry_id
        )
        is None
    )
    assert hass.states.get("calendar.anna_school_agenda") is not None


async def test_removing_a_child_removes_its_sensors(
    hass: HomeAssistant, mocked: aioresponses
) -> None:
    """The sensor sub-entries of a removed child go away with it."""
    fake = FakeMagister(mocked, children=TWO_CHILDREN)
    entry = make_entry(children=[(1001, "Anna"), (1002, "Bram")])
    add_sensor(entry, 0, subentry_id="a", title="Sensor A", child_id=1001)
    add_sensor(entry, 0, subentry_id="b", title="Sensor B", child_id=1002)
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert hass.states.get("sensor.bram_school_sensor_b") is not None

    result = await _init(hass, entry)
    await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            CONF_CHILDREN: ["1001"],
            CONF_WEEKS_BACK: 1,
            CONF_WEEKS_AHEAD: 3,
            CONF_INTERVAL: 30,
        },
    )
    await hass.async_block_till_done()
    assert set(entry.subentries) == {"a"}
    assert hass.states.get("sensor.bram_school_sensor_b") is None
    assert er.async_get(hass).async_get("sensor.bram_school_sensor_b") is None
    assert hass.states.get("sensor.anna_school_sensor_a") is not None
    assert _password_posts(fake) == 1


async def test_child_missing_at_magister_can_still_be_removed(
    hass: HomeAssistant, mocked: aioresponses
) -> None:
    """A child Magister no longer lists stays selectable so it can be unticked."""
    _, entry = await _setup(
        hass,
        mocked,
        children=[(1001, "Anna"), (1002, "Bram")],
    )
    result = await _init(hass, entry)
    schema = result["data_schema"].schema
    key = next(k for k in schema if k == CONF_CHILDREN)
    assert [o["value"] for o in schema[key].config["options"]] == ["1001", "1002"]


async def test_student_account(hass: HomeAssistant, mocked: aioresponses) -> None:
    """A student account lists only itself."""
    _, entry = await _setup(hass, mocked, student=True)
    result = await _init(hass, entry)
    schema = result["data_schema"].schema
    key = next(k for k in schema if k == CONF_CHILDREN)
    assert [o["value"] for o in schema[key].config["options"]] == ["1001"]


@pytest.mark.parametrize(
    ("error", "reason"),
    [
        (MagisterAuthError("invalid_auth"), "auth_failed"),
        (MagisterConnectionError("down"), "cannot_connect"),
        (MagisterApiError("odd"), "cannot_connect"),
    ],
)
async def test_fetch_errors_abort(
    hass: HomeAssistant, mocked: aioresponses, error: Exception, reason: str
) -> None:
    """Problems while reading the children list abort the flow."""
    _, entry = await _setup(hass, mocked)
    with patch.object(MagisterClient, "async_get_account", side_effect=error):
        result = await _open_general(hass, entry)
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == reason


async def test_no_kept_login_aborts(hass: HomeAssistant, mocked: aioresponses) -> None:
    """Without a kept login (entry not set up) the form cannot read the children."""
    _, entry = await _setup(hass, mocked)
    drop_login(hass, entry.entry_id)
    result = await _open_general(hass, entry)
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "cannot_connect"


async def test_child_of_another_login_is_not_offered(
    hass: HomeAssistant, mocked: aioresponses
) -> None:
    """Children that another login of the school has are hidden and rejected."""
    _, entry = await _setup(
        hass, mocked, children=[(1001, "Anna")], magister_children=TWO_CHILDREN
    )
    other = make_entry(children=[(1002, "Bram")], unique_id="school.magister.net:2000")
    other.add_to_hass(hass)
    result = await _init(hass, entry)
    keys = {str(k): k for k in result["data_schema"].schema}
    options = result["data_schema"].schema[keys[CONF_CHILDREN]].config["options"]
    assert [o["value"] for o in options] == ["1001"]
    flow = hass.config_entries.options._progress[result["flow_id"]]
    result = await flow.async_step_general(
        {
            CONF_CHILDREN: ["1001", "1002"],
            CONF_WEEKS_BACK: 1,
            CONF_WEEKS_AHEAD: 3,
            CONF_INTERVAL: 30,
        }
    )
    assert result["errors"] == {"base": "child_already_configured"}


async def test_existing_duplicate_child_stays_offered_and_saveable(
    hass: HomeAssistant, mocked: aioresponses
) -> None:
    """A child this entry already has stays in the form even if another login has it."""
    _, entry = await _setup(
        hass,
        mocked,
        children=[(1001, "Anna"), (1002, "Bram")],
        magister_children=TWO_CHILDREN,
    )
    make_entry(
        children=[(1002, "Bram")], unique_id="school.magister.net:2000"
    ).add_to_hass(hass)
    result = await _init(hass, entry)
    keys = {str(k): k for k in result["data_schema"].schema}
    options = result["data_schema"].schema[keys[CONF_CHILDREN]].config["options"]
    assert [o["value"] for o in options] == ["1001", "1002"]
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            CONF_CHILDREN: ["1001", "1002"],
            CONF_WEEKS_BACK: 1,
            CONF_WEEKS_AHEAD: 3,
            CONF_INTERVAL: 30,
        },
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert [c["id"] for c in entry.data[CONF_CHILDREN]] == [1001, 1002]


# -- homework weights ---------------------------------------------------------------


async def _open_weights(hass: HomeAssistant, entry: Any) -> Any:
    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] is FlowResultType.MENU
    return await hass.config_entries.options.async_configure(
        result["flow_id"], {"next_step_id": "weights"}
    )


async def _submit_types(
    hass: HomeAssistant, result: Any, values: dict[str, Any]
) -> Any:
    """Submit the type weights and leave the labels step at its defaults."""
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], values
    )
    assert result["step_id"] == "weights_labels"
    return await hass.config_entries.options.async_configure(
        result["flow_id"], {str(k): 1 for k in result["data_schema"].schema}
    )


async def test_weights_flow_saves_only_non_default_values(
    hass: HomeAssistant, mocked: aioresponses
) -> None:
    """Types, then subjects; stored sparsely; no reload and no Magister request."""
    fake, entry = await _setup(hass, mocked)
    runtime = entry.runtime_data
    requests = len(fake.appointment_requests)
    result = await _open_weights(hass, entry)  # one child: no child selection
    assert result["step_id"] == "weights_types"
    keys = {str(k): k for k in result["data_schema"].schema}
    assert list(keys) == ["homework", "test", "exam", "written_quiz", "oral_quiz"]
    assert keys["test"].description["suggested_value"] == 1.0
    selector = result["data_schema"].schema[keys["test"]]
    assert (selector.config["min"], selector.config["max"]) == (0, 10)
    assert selector.config["step"] == 0.5
    assert result["description_placeholders"] == {"child": "Kind A"}

    result = await _submit_types(
        hass,
        result,
        {
            "homework": 1,
            "test": 3,
            "exam": 2.5,
            "written_quiz": 1,
            "oral_quiz": 1,
        },
    )
    assert result["step_id"] == "weights_subjects"
    names = [str(k) for k in result["data_schema"].schema]
    assert names[0] == "aardrijkskunde"
    assert "Duitse taal" in names and "wiskunde" in names
    assert len(names) == len({n.casefold() for n in names})
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {name: (0.5 if name == "Duitse taal" else 1) for name in names},
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()
    assert entry.options[CONF_WEIGHTS] == {
        str(CHILD_ID): {
            "types": {"test": 3.0, "exam": 2.5},
            "subjects": {"Duitse taal": 0.5},
        }
    }
    assert entry.runtime_data is runtime
    assert len(fake.appointment_requests) == requests
    weights = hass.states.get("sensor.kind_school_homework_next_week").attributes[
        "weights"
    ]
    assert weights["types"]["test"] == 3.0 and weights["types"]["exam"] == 2.5
    assert weights["subjects"]["Duitse taal"] == 0.5


async def test_weights_flow_keeps_absent_subjects_and_resets_to_default(
    hass: HomeAssistant, mocked: aioresponses
) -> None:
    """Saved weights of subjects not in the data stay; 1 removes a stored weight."""
    fake = FakeMagister(mocked)
    entry = make_entry(
        options={
            CONF_WEIGHTS: {
                str(CHILD_ID): {
                    "types": {"test": 4},
                    "subjects": {"oud vak": 3, "DUITSE TAAL": 2},
                },
                "9999": {"types": {"exam": 2}},
            }
        }
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    result = await _open_weights(hass, entry)
    keys = {str(k): k for k in result["data_schema"].schema}
    assert keys["test"].description["suggested_value"] == 4.0
    result = await _submit_types(
        hass,
        result,
        {"homework": 1, "test": 1, "exam": 1, "written_quiz": 1, "oral_quiz": 1},
    )
    keys = {str(k): k for k in result["data_schema"].schema}
    # the stored weight shows under the subject as it is written in the data
    assert keys["Duitse taal"].description["suggested_value"] == 2.0
    assert "oud vak" not in keys
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {name: 1 for name in keys}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert entry.options[CONF_WEIGHTS] == {
        str(CHILD_ID): {"types": {}, "subjects": {"oud vak": 3}},
        "9999": {"types": {"exam": 2}},
    }
    assert fake.appointment_requests


async def test_weights_flow_removes_empty_weights(
    hass: HomeAssistant, mocked: aioresponses
) -> None:
    """With everything back at 1 the weights option disappears."""
    _, entry = await _setup(hass, mocked)
    hass.config_entries.async_update_entry(
        entry,
        options={CONF_WEIGHTS: {str(CHILD_ID): {"types": {"test": 4}}}},
    )
    await hass.async_block_till_done()
    result = await _open_weights(hass, entry)
    result = await _submit_types(
        hass,
        result,
        {"homework": 1, "test": 1, "exam": 1, "written_quiz": 1, "oral_quiz": 1},
    )
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {str(k): 1 for k in result["data_schema"].schema}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert CONF_WEIGHTS not in entry.options


async def test_weights_flow_without_subjects_skips_that_step(
    hass: HomeAssistant, mocked: aioresponses
) -> None:
    """A child without homework data only gets the type weights."""
    fake = FakeMagister(mocked)
    fake.appointments[CHILD_ID] = []
    entry = make_entry()
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    result = await _open_weights(hass, entry)
    result = await _submit_types(
        hass,
        result,
        {"homework": 2, "test": 1, "exam": 1, "written_quiz": 1, "oral_quiz": 1},
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert entry.options[CONF_WEIGHTS] == {
        str(CHILD_ID): {"types": {"homework": 2.0}, "subjects": {}}
    }


async def test_weights_flow_asks_for_the_child(
    hass: HomeAssistant, mocked: aioresponses
) -> None:
    """With several children the first step selects the child."""
    _, entry = await _setup(
        hass,
        mocked,
        children=[(1001, "Anna"), (1002, "Bram")],
        magister_children=TWO_CHILDREN,
    )
    result = await _open_weights(hass, entry)
    assert result["step_id"] == "weights"
    options = next(iter(result["data_schema"].schema.values())).config["options"]
    assert [(o["value"], o["label"]) for o in options] == [
        ("1001", "Anna"),
        ("1002", "Bram"),
    ]
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"child": "1002"}
    )
    assert result["step_id"] == "weights_types"
    assert result["description_placeholders"] == {"child": "Bram"}
    result = await _submit_types(
        hass,
        result,
        {"homework": 1, "test": 5, "exam": 1, "written_quiz": 1, "oral_quiz": 1},
    )
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {str(k): 1 for k in result["data_schema"].schema}
    )
    assert entry.options[CONF_WEIGHTS]["1002"]["types"] == {"test": 5.0}
    assert "1001" not in entry.options[CONF_WEIGHTS]


async def test_weights_need_a_loaded_entry(
    hass: HomeAssistant, mocked: aioresponses
) -> None:
    """The subject list comes from the loaded data."""
    _, entry = await _setup(hass, mocked)
    assert await hass.config_entries.async_unload(entry.entry_id)
    result = await _open_weights(hass, entry)
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "not_loaded"


async def test_general_settings_keep_the_weights(
    hass: HomeAssistant, mocked: aioresponses
) -> None:
    """Saving the general options does not drop the stored weights."""
    _, entry = await _setup(hass, mocked)
    weights = {str(CHILD_ID): {"types": {"test": 4.0}}}
    hass.config_entries.async_update_entry(entry, options={CONF_WEIGHTS: weights})
    await hass.async_block_till_done()
    result = await _init(hass, entry)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            CONF_CHILDREN: [str(CHILD_ID)],
            CONF_WEEKS_BACK: 2,
            CONF_WEEKS_AHEAD: 3,
            CONF_INTERVAL: 30,
        },
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert entry.options[CONF_WEIGHTS] == weights
    assert entry.options[CONF_WEEKS_BACK] == 2


# -- labels -------------------------------------------------------------------------


async def _open_labels(hass: HomeAssistant, entry: Any) -> Any:
    result = await hass.config_entries.options.async_init(entry.entry_id)
    return await hass.config_entries.options.async_configure(
        result["flow_id"], {"next_step_id": "labels"}
    )


async def _labels_action(hass: HomeAssistant, result: Any, action: str) -> Any:
    assert result["step_id"] == "labels_menu"
    return await hass.config_entries.options.async_configure(
        result["flow_id"], {"next_step_id": action}
    )


async def test_labels_flow_add_rename_kind_and_delete(
    hass: HomeAssistant, mocked: aioresponses
) -> None:
    """Add, rename, change the kind and delete; no reload, no Magister request."""
    fake, entry = await _setup(hass, mocked)
    runtime = entry.runtime_data
    requests = len(fake.appointment_requests)
    result = await _open_labels(hass, entry)  # one child: no child selection
    assert result["step_id"] == "labels_menu"
    assert result["menu_options"] == ["label_add", "label_edit", "label_delete"]
    assert result["description_placeholders"] == {"child": "Kind A"}

    # add: the defaults are stored with their ids, plus the new label
    result = await _labels_action(hass, result, "label_add")
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"name": " Toetsweek ", "kind": "test"}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()
    stored = entry.options[CONF_LABELS][str(CHILD_ID)]
    assert [(o["name"], o["kind"]) for o in stored] == [
        ("Huiswerk", "homework"),
        ("Proefwerk", "test"),
        ("Tentamen", "test"),
        ("SO", "test"),
        ("MO", "test"),
        ("Toetsweek", "test"),
    ]
    new_id = stored[-1]["id"]
    assert new_id and new_id not in {o["id"] for o in stored[:-1]}
    assert entry.state is ConfigEntryState.LOADED
    assert entry.runtime_data is runtime
    assert len(fake.appointment_requests) == requests

    # rename and change the kind (the id stays)
    result = await _open_labels(hass, entry)
    result = await _labels_action(hass, result, "label_edit")
    assert result["step_id"] == "label_edit"
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"label": new_id}
    )
    assert result["step_id"] == "label_edit_details"
    assert result["description_placeholders"] == {"label": "Toetsweek"}
    keys = {str(k): k for k in result["data_schema"].schema}
    assert keys["name"].description["suggested_value"] == "Toetsweek"
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"name": "Extra", "kind": "homework"}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()
    assert entry.options[CONF_LABELS][str(CHILD_ID)][-1] == {
        "id": new_id,
        "name": "Extra",
        "kind": "homework",
    }
    assert entry.runtime_data is runtime

    # delete
    result = await _open_labels(hass, entry)
    result = await _labels_action(hass, result, "label_delete")
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"label": new_id}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()
    assert [o["name"] for o in entry.options[CONF_LABELS][str(CHILD_ID)]] == [
        "Huiswerk",
        "Proefwerk",
        "Tentamen",
        "SO",
        "MO",
    ]
    assert entry.runtime_data is runtime


async def test_labels_flow_name_errors(
    hass: HomeAssistant, mocked: aioresponses
) -> None:
    """Empty, too long and duplicate names are refused (case-insensitive)."""
    _, entry = await _setup(hass, mocked)
    result = await _labels_action(hass, await _open_labels(hass, entry), "label_add")
    for name, error in (
        ("   ", "name_required"),
        ("x" * 41, "name_too_long"),
        ("proefWERK", "name_exists"),
    ):
        result = await hass.config_entries.options.async_configure(
            result["flow_id"], {"name": name, "kind": "test"}
        )
        assert result["type"] is FlowResultType.FORM
        assert result["errors"] == {"name": error}
    # renaming a label to its own name (another case) is fine, to another's is not
    result = await _labels_action(hass, await _open_labels(hass, entry), "label_edit")
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"label": "default_test"}
    )
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"name": "so", "kind": "test"}
    )
    assert result["errors"] == {"name": "name_exists"}
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"name": "PROEFWERK", "kind": "homework"}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    stored = entry.options[CONF_LABELS][str(CHILD_ID)]
    assert stored[1] == {"id": "default_test", "name": "PROEFWERK", "kind": "homework"}


async def test_deleting_a_label_in_use_is_refused(
    hass: HomeAssistant, mocked: aioresponses
) -> None:
    """A label that is on a lesson cannot be deleted; after removing it, it can."""
    _, entry = await _setup(hass, mocked)
    manager = entry.runtime_data.homework
    uid = f"school.magister.net:{CHILD_ID}:100067"
    await hass.services.async_call(
        DOMAIN,
        "add_homework_label",
        {
            "entity_id": "todo.kind_school_homework",
            "appointment": uid,
            "label": "Proefwerk",
        },
        blocking=True,
    )
    assert manager.label_in_use(CHILD_ID, "default_test")
    result = await _labels_action(hass, await _open_labels(hass, entry), "label_delete")
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"label": "default_test"}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "label_delete"
    assert result["errors"] == {"base": "label_in_use"}
    assert CONF_LABELS not in entry.options
    # another label can still be deleted from the same form
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"label": "default_oral_quiz"}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    names = [o["name"] for o in entry.options[CONF_LABELS][str(CHILD_ID)]]
    assert "MO" not in names and "Proefwerk" in names

    manager.remove_label(
        CHILD_ID,
        uid,
        next(o for o in manager.label_options(CHILD_ID) if o.name == "Proefwerk"),
    )
    result = await _labels_action(hass, await _open_labels(hass, entry), "label_delete")
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"label": "default_test"}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_labels_menu_without_labels_and_edge_cases(
    hass: HomeAssistant, mocked: aioresponses
) -> None:
    """With no labels only 'add' is offered; a vanished label aborts the edit."""
    _, entry = await _setup(hass, mocked)
    hass.config_entries.async_update_entry(
        entry, options={CONF_LABELS: {str(CHILD_ID): []}}
    )
    await hass.async_block_till_done()
    result = await _open_labels(hass, entry)
    assert result["menu_options"] == ["label_add"]

    hass.config_entries.async_update_entry(
        entry,
        options={
            CONF_LABELS: {str(CHILD_ID): [{"id": "a", "name": "A", "kind": "test"}]}
        },
    )
    await hass.async_block_till_done()
    result = await _labels_action(hass, await _open_labels(hass, entry), "label_edit")
    hass.config_entries.async_update_entry(
        entry, options={CONF_LABELS: {str(CHILD_ID): []}}
    )
    await hass.async_block_till_done()
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"label": "a"}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "label_gone"


async def test_labels_need_a_loaded_entry_and_ask_for_the_child(
    hass: HomeAssistant, mocked: aioresponses
) -> None:
    """Not loaded aborts; with several children the first step selects the child."""
    _, entry = await _setup(
        hass,
        mocked,
        children=[(1001, "Anna"), (1002, "Bram")],
        magister_children=TWO_CHILDREN,
    )
    result = await _open_labels(hass, entry)
    assert result["step_id"] == "labels"
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"child": "1002"}
    )
    assert result["description_placeholders"] == {"child": "Bram"}
    result = await _labels_action(hass, result, "label_add")
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"name": "Extra", "kind": "homework"}
    )
    assert "1001" not in entry.options[CONF_LABELS]
    assert entry.options[CONF_LABELS]["1002"][-1]["name"] == "Extra"

    assert await hass.config_entries.async_unload(entry.entry_id)
    result = await _open_labels(hass, entry)
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "not_loaded"


async def test_weights_flow_lists_and_stores_label_weights(
    hass: HomeAssistant, mocked: aioresponses
) -> None:
    """The labels step lists the child's labels by name; weights are stored by id."""
    fake = FakeMagister(mocked)
    entry = make_entry(
        options={
            CONF_LABELS: {
                str(CHILD_ID): [
                    {"id": "tw", "name": "Toetsweek", "kind": "test"},
                    {"id": "ex", "name": "Extra", "kind": "homework"},
                ]
            },
            CONF_WEIGHTS: {str(CHILD_ID): {"labels": {"tw": 3, "gone": 2}}},
        }
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    result = await _open_weights(hass, entry)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {"homework": 1, "test": 1, "exam": 1, "written_quiz": 1, "oral_quiz": 1},
    )
    assert result["step_id"] == "weights_labels"
    keys = {str(k): k for k in result["data_schema"].schema}
    assert list(keys) == ["Toetsweek", "Extra"]
    assert keys["Toetsweek"].description["suggested_value"] == 3.0
    assert result["description_placeholders"] == {"child": "Kind A"}
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"Toetsweek": 4, "Extra": 1}
    )
    assert result["step_id"] == "weights_subjects"
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {str(k): 1 for k in result["data_schema"].schema}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert entry.options[CONF_WEIGHTS] == {
        str(CHILD_ID): {"types": {}, "subjects": {}, "labels": {"tw": 4.0}}
    }
    assert fake.appointment_requests


async def test_weights_flow_skips_the_labels_step_without_labels(
    hass: HomeAssistant, mocked: aioresponses
) -> None:
    """A child whose labels were all deleted goes straight to the subjects."""
    FakeMagister(mocked)
    entry = make_entry(options={CONF_LABELS: {str(CHILD_ID): []}})
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    result = await _open_weights(hass, entry)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {"homework": 1, "test": 1, "exam": 1, "written_quiz": 1, "oral_quiz": 1},
    )
    assert result["step_id"] == "weights_subjects"
