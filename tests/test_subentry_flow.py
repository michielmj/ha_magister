"""Sub-entry flow tests (first-appointment sensors)."""

from __future__ import annotations

from typing import Any

import pytest
from aioresponses import aioresponses
from freezegun.api import FrozenDateTimeFactory
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.magister.const import (
    CONF_CHILD_ID,
    CONF_EXCLUDED,
    CONF_INTERVAL,
    CONF_OFFSET,
    CONF_WEEKS_AHEAD,
    CONF_WEEKS_BACK,
    DOMAIN,
    SUBENTRY_FIRST,
)
from custom_components.magister.subentry_flow import default_title

from .ha_helpers import CHILD_ID, NOW, FakeMagister, make_entry
from .test_sensor import add_sensor


@pytest.fixture(autouse=True)
async def frozen_now(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> FrozenDateTimeFactory:
    """Friday 13 November 2026."""
    await hass.config.async_set_time_zone("Europe/Amsterdam")
    freezer.move_to(NOW)
    return freezer


async def _setup(
    hass: HomeAssistant, mocked: aioresponses, entry: MockConfigEntry | None = None
) -> MockConfigEntry:
    FakeMagister(mocked)
    entry = entry or make_entry()
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


async def _start_add(hass: HomeAssistant, entry: MockConfigEntry) -> Any:
    result = await hass.config_entries.subentries.async_init(
        (entry.entry_id, SUBENTRY_FIRST), context={"source": "user"}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    return result


def test_default_titles() -> None:
    """Default names follow the offset, in Dutch and English."""
    assert default_title(0, "nl") == "Eerste afspraak vandaag"
    assert default_title(1, "nl-NL") == "Eerste afspraak morgen"
    assert default_title(5, "nl") == "Eerste afspraak over 5 dagen"
    assert default_title(0, "en") == "First appointment today"
    assert default_title(1, "en-GB") == "First appointment tomorrow"
    assert default_title(5, "en") == "First appointment in 5 days"


async def test_supported_and_reconfigurable(
    hass: HomeAssistant, mocked: aioresponses
) -> None:
    """The entry offers the sub-entry type, with reconfigure."""
    entry = await _setup(hass, mocked)
    assert entry.supported_subentry_types == {
        SUBENTRY_FIRST: {"supports_reconfigure": True}
    }


async def test_add_sensor(hass: HomeAssistant, mocked: aioresponses) -> None:
    """Child and day, then the excluded subjects; the sensor appears."""
    entry = await _setup(hass, mocked)
    result = await _start_add(hass, entry)
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {CONF_CHILD_ID: str(CHILD_ID), CONF_OFFSET: 6}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "excluded"
    schema = result["data_schema"].schema
    key = next(k for k in schema if k == CONF_EXCLUDED)
    options = [o["value"] for o in schema[key].config["options"]]
    assert "Franse taal" in options
    assert "studieles" in options
    assert schema[key].config["custom_value"] is True

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {CONF_EXCLUDED: ["Franse taal", " Eigen vak ", ""]}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.LOADED
    (subentry,) = entry.subentries.values()
    assert subentry.subentry_type == SUBENTRY_FIRST
    assert subentry.title == "First appointment in 6 days"
    assert dict(subentry.data) == {
        CONF_CHILD_ID: CHILD_ID,
        CONF_OFFSET: 6,
        CONF_EXCLUDED: ["Franse taal", "Eigen vak"],
    }
    state = hass.states.get("sensor.kind_school_first_appointment_in_6_days")
    assert state is not None
    assert state.state == "2026-11-19T08:15:00+00:00"


async def test_add_sensor_dutch_title_and_custom_name(
    hass: HomeAssistant, mocked: aioresponses
) -> None:
    """The default name follows the language; a given name wins."""
    entry = await _setup(hass, mocked)
    hass.config.language = "nl"
    for offset, name, title in (
        (1, "", "Eerste afspraak morgen"),
        (0, "Wekker", "Wekker"),
    ):
        result = await _start_add(hass, entry)
        result = await hass.config_entries.subentries.async_configure(
            result["flow_id"],
            {
                CONF_CHILD_ID: str(CHILD_ID),
                CONF_OFFSET: offset,
                "name": name,
            },
        )
        result = await hass.config_entries.subentries.async_configure(
            result["flow_id"], {}
        )
        assert result["type"] is FlowResultType.CREATE_ENTRY
        assert result["title"] == title
        await hass.async_block_till_done()


async def test_offset_must_fit_the_window(
    hass: HomeAssistant, mocked: aioresponses
) -> None:
    """Weeks ahead 3: 20 days is the last one that fits."""
    entry = await _setup(hass, mocked)
    result = await _start_add(hass, entry)
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {CONF_CHILD_ID: str(CHILD_ID), CONF_OFFSET: 21}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {CONF_OFFSET: "offset_outside_window"}
    assert result["description_placeholders"] == {"max_offset": "20"}
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {CONF_CHILD_ID: str(CHILD_ID), CONF_OFFSET: 20}
    )
    assert result["step_id"] == "excluded"


async def test_offset_limit_follows_the_options(
    hass: HomeAssistant, mocked: aioresponses
) -> None:
    """With weeks ahead 1 only 6 days fit."""
    entry = make_entry(
        options={CONF_WEEKS_BACK: 1, CONF_WEEKS_AHEAD: 1, CONF_INTERVAL: 30}
    )
    entry = await _setup(hass, mocked, entry)
    result = await _start_add(hass, entry)
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {CONF_CHILD_ID: str(CHILD_ID), CONF_OFFSET: 7}
    )
    assert result["errors"] == {CONF_OFFSET: "offset_outside_window"}
    assert result["description_placeholders"] == {"max_offset": "6"}


async def test_subjects_are_empty_while_the_entry_is_down(
    hass: HomeAssistant, mocked: aioresponses
) -> None:
    """Without data the subject list is empty; typing a subject still works."""
    entry = await _setup(hass, mocked)
    await hass.config_entries.async_unload(entry.entry_id)
    result = await _start_add(hass, entry)
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {CONF_CHILD_ID: str(CHILD_ID), CONF_OFFSET: 0}
    )
    schema = result["data_schema"].schema
    key = next(k for k in schema if k == CONF_EXCLUDED)
    assert schema[key].config["options"] == []
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {CONF_EXCLUDED: ["Typed"]}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_reconfigure_sensor(hass: HomeAssistant, mocked: aioresponses) -> None:
    """Edit day, name and exclusions; the sensor follows."""
    entry = make_entry()
    add_sensor(entry, 6, ["Franse taal"], title="Eerste les")
    entry = await _setup(hass, mocked, entry)
    state = hass.states.get("sensor.kind_school_eerste_les")
    assert state is not None
    assert state.state == "2026-11-19T08:15:00+00:00"

    result = await hass.config_entries.subentries.async_init(
        (entry.entry_id, SUBENTRY_FIRST),
        context={"source": "reconfigure", "subentry_id": "sub1"},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"
    assert CONF_CHILD_ID not in {str(k) for k in result["data_schema"].schema}
    suggested = {
        str(k): k.description["suggested_value"]
        for k in result["data_schema"].schema
        if k.description and "suggested_value" in k.description
    }
    assert suggested == {CONF_OFFSET: 6, "name": "Eerste les"}

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {CONF_OFFSET: 4, "name": "Wekker"}
    )
    assert result["step_id"] == "excluded"
    # the current exclusions are offered and preselected
    schema = result["data_schema"].schema
    key = next(k for k in schema if k == CONF_EXCLUDED)
    assert key.default() == ["Franse taal"]
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {CONF_EXCLUDED: []}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    await hass.async_block_till_done()
    subentry = entry.subentries["sub1"]
    assert subentry.title == "Wekker"
    assert dict(subentry.data) == {
        CONF_CHILD_ID: CHILD_ID,
        CONF_OFFSET: 4,
        CONF_EXCLUDED: [],
    }
    # the entity id stays, the name follows the title
    state = hass.states.get("sensor.kind_school_eerste_les")
    assert state is not None
    assert state.attributes["friendly_name"] == "Kind (school) Wekker"
    assert state.state == "2026-11-17T07:30:00+00:00"


async def test_reconfigure_keeps_title_when_name_is_empty(
    hass: HomeAssistant, mocked: aioresponses
) -> None:
    """An empty name keeps the current title; the offset limit applies."""
    entry = make_entry()
    add_sensor(entry, 2, title="Mijn sensor")
    entry = await _setup(hass, mocked, entry)
    result = await hass.config_entries.subentries.async_init(
        (entry.entry_id, SUBENTRY_FIRST),
        context={"source": "reconfigure", "subentry_id": "sub1"},
    )
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {CONF_OFFSET: 50, "name": ""}
    )
    assert result["errors"] == {CONF_OFFSET: "offset_outside_window"}
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {CONF_OFFSET: 3, "name": ""}
    )
    result = await hass.config_entries.subentries.async_configure(result["flow_id"], {})
    assert result["type"] is FlowResultType.ABORT
    assert entry.subentries["sub1"].title == "Mijn sensor"
    assert entry.subentries["sub1"].data[CONF_OFFSET] == 3


async def test_delete_sensor(hass: HomeAssistant, mocked: aioresponses) -> None:
    """Deleting a sub-entry removes its sensor and nothing else."""
    entry = make_entry()
    add_sensor(entry, 0, subentry_id="one", title="One")
    add_sensor(entry, 1, subentry_id="two", title="Two")
    entry = await _setup(hass, mocked, entry)
    assert hass.states.get("sensor.kind_school_one") is not None
    assert hass.states.get("sensor.kind_school_two") is not None
    hass.config_entries.async_remove_subentry(entry, "one")
    await hass.async_block_till_done()
    assert hass.states.get("sensor.kind_school_one") is None
    assert hass.states.get("sensor.kind_school_two") is not None
    assert hass.states.get("calendar.kind_school_agenda") is not None
    assert entry.state is ConfigEntryState.LOADED
    assert DOMAIN in hass.config.components


async def test_default_title_follows_a_new_offset(
    hass: HomeAssistant, mocked: aioresponses
) -> None:
    """A default title is renewed for the new offset; a custom one is kept."""
    entry = make_entry()
    add_sensor(entry, 1, subentry_id="d", title="First appointment tomorrow")
    add_sensor(entry, 1, subentry_id="c", title="My own")
    entry = await _setup(hass, mocked, entry)
    for sub_id, expected in (("d", "First appointment in 3 days"), ("c", "My own")):
        result = await hass.config_entries.subentries.async_init(
            (entry.entry_id, SUBENTRY_FIRST),
            context={"source": "reconfigure", "subentry_id": sub_id},
        )
        title = entry.subentries[sub_id].title
        result = await hass.config_entries.subentries.async_configure(
            result["flow_id"], {CONF_OFFSET: 3, "name": title}
        )
        result = await hass.config_entries.subentries.async_configure(
            result["flow_id"], {}
        )
        assert result["type"] is FlowResultType.ABORT
        assert entry.subentries[sub_id].title == expected
        await hass.async_block_till_done()
