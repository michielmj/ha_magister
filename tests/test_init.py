"""Config entry lifecycle tests."""

from __future__ import annotations

from aioresponses import aioresponses
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.setup import async_setup_component

from custom_components.magister.api import MagisterAuth, MagisterClient
from custom_components.magister.const import DOMAIN
from custom_components.magister.pending import take_pending_login

from .api.helpers import RETURN_URL
from .ha_helpers import CHILD_ID, FakeMagister, make_entry


async def test_async_setup(hass: HomeAssistant) -> None:
    """The integration can be set up from YAML-less config."""
    assert await async_setup_component(hass, DOMAIN, {})


async def test_entry_lifecycle(hass: HomeAssistant, mocked: aioresponses) -> None:
    """Setup -> loaded with runtime data -> unload -> remove."""
    fake = FakeMagister(mocked)
    entry = make_entry()
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.LOADED
    runtime = entry.runtime_data
    assert isinstance(runtime.auth, MagisterAuth)
    assert isinstance(runtime.client, MagisterClient)
    assert set(runtime.coordinator.data) == {CHILD_ID}
    assert len(runtime.coordinator.data[CHILD_ID]) == 140
    # one login, one appointments call, and no status filter (it hides cancellations)
    assert len(fake.appointment_requests) == 1
    assert "status" not in fake.appointment_requests[0][1]
    assert fake.login.posts[0][0] == "current"

    entity_registry = er.async_get(hass)
    entities = er.async_entries_for_config_entry(entity_registry, entry.entry_id)
    assert [e.unique_id for e in entities] == [f"school.magister.net:{CHILD_ID}"]

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.NOT_LOADED
    assert hass.states.get(entities[0].entity_id).state == "unavailable"

    assert await hass.config_entries.async_remove(entry.entry_id)
    await hass.async_block_till_done()
    assert hass.config_entries.async_get_entry(entry.entry_id) is None
    assert not er.async_entries_for_config_entry(entity_registry, entry.entry_id)
    assert not dr.async_entries_for_config_entry(dr.async_get(hass), entry.entry_id)


async def test_entries_have_separate_cookie_jars(
    hass: HomeAssistant, mocked: aioresponses
) -> None:
    """Each entry gets its own session and cookie jar."""
    steps = [
        {"action": "username"},
        {"action": "password"},
        {"redirectURL": RETURN_URL},
    ]
    FakeMagister(mocked, challenges=[*steps, *steps])
    first = make_entry(unique_id="school.magister.net:1")
    second = make_entry(unique_id="school.magister.net:2")
    for entry in (first, second):
        entry.add_to_hass(hass)
        assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    jar_1 = first.runtime_data.session.cookie_jar
    jar_2 = second.runtime_data.session.cookie_jar
    assert jar_1 is not jar_2
    assert first.runtime_data.session is not second.runtime_data.session


async def test_setup_with_wrong_password_needs_reauth(
    hass: HomeAssistant, mocked: aioresponses
) -> None:
    """A final login failure ends in a setup error (reauth form arrives in M3)."""
    FakeMagister(
        mocked,
        challenges=[
            {"action": "username"},
            {"action": "password"},
            {"error": "InvalidChallenge"},
        ],
    )
    entry = make_entry()
    entry.add_to_hass(hass)
    assert not await hass.config_entries.async_setup(entry.entry_id)
    assert entry.state is ConfigEntryState.SETUP_ERROR


async def test_setup_retries_when_magister_is_down(
    hass: HomeAssistant, mocked: aioresponses
) -> None:
    """Server errors make HA retry the setup later."""
    fake = FakeMagister(mocked)
    fake.appointment_status = 503
    entry = make_entry()
    entry.add_to_hass(hass)
    assert not await hass.config_entries.async_setup(entry.entry_id)
    assert entry.state is ConfigEntryState.SETUP_RETRY


def test_no_pending_login_without_unique_id(hass: HomeAssistant) -> None:
    """An entry without unique id never receives a pending login."""
    assert take_pending_login(hass, None) is None
