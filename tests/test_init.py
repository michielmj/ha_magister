"""Config entry lifecycle tests."""

from __future__ import annotations

from datetime import timedelta
from functools import partial
from unittest.mock import Mock, patch

from aioresponses import aioresponses
from freezegun.api import FrozenDateTimeFactory
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_PASSWORD, EVENT_HOMEASSISTANT_CLOSE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.setup import async_setup_component
from pytest_homeassistant_custom_component.common import async_fire_time_changed

from custom_components.magister import _child_of_unique_id
from custom_components.magister.api import MagisterAuth, MagisterClient
from custom_components.magister.const import DOMAIN
from custom_components.magister.pending import (
    PendingLogin,
    retain_login,
    store_pending_login,
    take_pending_login,
)

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


def _password_posts(fake: FakeMagister) -> int:
    return [name for name, *_ in fake.login.posts].count("password")


async def test_setup_retry_does_not_resend_the_password(
    hass: HomeAssistant, mocked: aioresponses, freezer: FrozenDateTimeFactory
) -> None:
    """A 503 after the password step: the retry waits instead of posting again."""
    fake = FakeMagister(
        mocked,
        challenges=[{"action": "username"}, {"action": "password"}, {"_status": 503}],
    )
    entry = make_entry()
    entry.add_to_hass(hass)
    assert not await hass.config_entries.async_setup(entry.entry_id)
    assert entry.state is ConfigEntryState.SETUP_RETRY
    assert _password_posts(fake) == 1

    for _ in range(3):
        freezer.tick(timedelta(seconds=70))
        async_fire_time_changed(hass)
        await hass.async_block_till_done()
        assert entry.state is ConfigEntryState.SETUP_RETRY
    assert _password_posts(fake) == 1


async def test_final_failure_then_reload_tries_exactly_one_login(
    hass: HomeAssistant, mocked: aioresponses
) -> None:
    """A reported final failure ends in SETUP_ERROR; a reload tries one new login."""
    bad = [
        {"action": "username"},
        {"action": "password"},
        {"error": "InvalidChallenge"},
    ]
    fake = FakeMagister(mocked, challenges=[*bad, *bad])
    entry = make_entry()
    entry.add_to_hass(hass)
    assert not await hass.config_entries.async_setup(entry.entry_id)
    assert entry.state is ConfigEntryState.SETUP_ERROR
    assert _password_posts(fake) == 1

    await hass.config_entries.async_reload(entry.entry_id)
    assert entry.state is ConfigEntryState.SETUP_ERROR
    assert _password_posts(fake) == 2


async def test_outage_after_password_gives_three_posts_then_setup_error(
    hass: HomeAssistant, mocked: aioresponses, freezer: FrozenDateTimeFactory
) -> None:
    """A long outage: 3 password POSTs (300 s apart), then a blocked login."""
    clock = [0.0]
    down = [{"action": "username"}, {"action": "password"}, {"_status": 503}]
    ok = [{"action": "username"}, {"action": "password"}, {"redirectURL": RETURN_URL}]
    fake = FakeMagister(mocked, challenges=[*down, *down, *down, *ok])
    entry = make_entry()
    entry.add_to_hass(hass)
    with patch(
        "custom_components.magister.MagisterAuth",
        partial(MagisterAuth, clock=lambda: clock[0]),
    ):
        assert not await hass.config_entries.async_setup(entry.entry_id)
        assert entry.state is ConfigEntryState.SETUP_RETRY
        for expected in (1, 2, 3):
            # Before the 300 s backoff ends nothing is posted
            freezer.tick(timedelta(seconds=400))
            async_fire_time_changed(hass)
            await hass.async_block_till_done()
            if expected < 3:
                assert _password_posts(fake) == expected
                clock[0] += 301
                freezer.tick(timedelta(seconds=400))
                async_fire_time_changed(hass)
                await hass.async_block_till_done()
        # an automatic retry never clears the block
        assert _password_posts(fake) == 3
        assert entry.state is ConfigEntryState.SETUP_ERROR
        assert "blocked" in (entry.reason or "")
        clock[0] += 1000
        freezer.tick(timedelta(hours=1))
        async_fire_time_changed(hass)
        await hass.async_block_till_done()
        assert _password_posts(fake) == 3

        # a user-initiated reload may try once more
        await hass.config_entries.async_reload(entry.entry_id)
        assert _password_posts(fake) == 4
        assert entry.state is ConfigEntryState.LOADED


def test_pending_login_repr_hides_secrets() -> None:
    """The repr of a stored login never shows credentials."""
    login = PendingLogin(
        session=object(),  # type: ignore[arg-type]
        auth=object(),  # type: ignore[arg-type]
        client=object(),  # type: ignore[arg-type]
        credentials=("h", "user", "s3cret-pw", "TOTPSECRET"),
    )
    text = repr(login)
    assert "s3cret-pw" not in text
    assert "TOTPSECRET" not in text


async def test_login_is_kept_across_reload_and_dropped_on_new_credentials(
    hass: HomeAssistant, mocked: aioresponses
) -> None:
    """Reload reuses the auth helper; changed credentials and removal release it."""
    steps = [
        {"action": "username"},
        {"action": "password"},
        {"redirectURL": RETURN_URL},
    ]
    FakeMagister(mocked, challenges=[*steps, *steps])
    entry = make_entry()
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    first = entry.runtime_data
    assert not first.session.closed

    assert await hass.config_entries.async_reload(entry.entry_id)
    assert entry.runtime_data.auth is first.auth
    assert not first.session.closed

    hass.config_entries.async_update_entry(
        entry, data={**entry.data, CONF_PASSWORD: "new-password"}
    )
    assert await hass.config_entries.async_reload(entry.entry_id)
    second = entry.runtime_data
    assert second.auth is not first.auth
    assert first.session.closed
    assert not second.session.closed

    assert await hass.config_entries.async_remove(entry.entry_id)
    assert second.session.closed


async def test_shutdown_and_replacement_release_pending_sessions(
    hass: HomeAssistant,
) -> None:
    """Replaced and left-over pending logins are detached."""
    assert await async_setup_component(hass, DOMAIN, {})
    sessions = [Mock(), Mock(), Mock()]
    first, second, retained = (PendingLogin(s, Mock(), Mock()) for s in sessions)
    store_pending_login(hass, "a", first)
    store_pending_login(hass, "a", second)
    first.session.detach.assert_called_once()
    retain_login(hass, "entry", retained)

    hass.bus.async_fire(EVENT_HOMEASSISTANT_CLOSE)
    await hass.async_block_till_done()
    second.session.detach.assert_called_once()
    retained.session.detach.assert_called_once()
    assert take_pending_login(hass, "a") is None


def test_child_of_unique_id() -> None:
    """The child id is the second part of the unique id; odd ids give None."""
    assert _child_of_unique_id("school.magister.net:1001") == 1001
    assert _child_of_unique_id("school.magister.net:1001:first:abc") == 1001
    assert _child_of_unique_id("school.magister.net") is None
    assert _child_of_unique_id("school.magister.net:abc") is None
