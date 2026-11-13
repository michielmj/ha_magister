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
    CONF_WEEKS_AHEAD,
    CONF_WEEKS_BACK,
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


async def _init(hass: HomeAssistant, entry: Any) -> Any:
    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"
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
        result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == reason


async def test_no_kept_login_aborts(hass: HomeAssistant, mocked: aioresponses) -> None:
    """Without a kept login (entry not set up) the form cannot read the children."""
    _, entry = await _setup(hass, mocked)
    drop_login(hass, entry.entry_id)
    result = await hass.config_entries.options.async_init(entry.entry_id)
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
    result = await flow.async_step_init(
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
