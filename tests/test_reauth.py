"""Reauth and reconfigure flow tests."""

from __future__ import annotations

from datetime import timedelta
from functools import partial
from typing import Any
from unittest.mock import patch

import pytest
from aioresponses import aioresponses
from freezegun.api import FrozenDateTimeFactory
from homeassistant.config_entries import SOURCE_REAUTH, ConfigEntryState
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_fire_time_changed,
)

from custom_components.magister.api import MagisterAuth
from custom_components.magister.const import CONF_TOTP_SECRET, DOMAIN

from .api.helpers import PASSWORD, RETURN_URL, TOTP_SECRET, USERNAME
from .ha_helpers import NOW, FakeMagister, make_entry

LOGIN_OK: list[dict[str, Any]] = [
    {"action": "username"},
    {"action": "password"},
    {"redirectURL": RETURN_URL},
]
LOGIN_TOTP_OK: list[dict[str, Any]] = [
    {"action": "username"},
    {"action": "password"},
    {"action": "soft-token"},
    {"redirectURL": RETURN_URL},
]
LOGIN_BAD: list[dict[str, Any]] = [
    {"action": "username"},
    {"action": "password"},
    {"error": "InvalidChallenge"},
]
NEW_PASSWORD = "n3w-Passw0rd!"
NEW_TOTP = "KRSXG5CTMVRXEZLU"


@pytest.fixture(autouse=True)
def frozen_now(freezer: FrozenDateTimeFactory) -> FrozenDateTimeFactory:
    """Freeze time on Friday 13 November 2026."""
    freezer.move_to(NOW)
    return freezer


def _posts(fake: FakeMagister, name: str) -> list[dict[str, Any]]:
    return [body for step, body, _ in fake.login.posts if step == name]


async def _setup(
    hass: HomeAssistant, entry: MockConfigEntry | None = None
) -> MockConfigEntry:
    entry = entry or make_entry()
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.LOADED
    return entry


async def _start_reauth(hass: HomeAssistant, entry: MockConfigEntry) -> Any:
    result = await entry.start_reauth_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"
    return result


async def test_reauth_success_logs_in_once_and_hands_over(
    hass: HomeAssistant, mocked: aioresponses
) -> None:
    """New password: one login in the flow, none during the reload."""
    fake = FakeMagister(mocked, challenges=[*LOGIN_OK, *LOGIN_OK])
    entry = await _setup(hass)
    old = entry.runtime_data
    result = await _start_reauth(hass, entry)
    # username and school are shown, not editable
    assert result["description_placeholders"]["username"] == USERNAME
    assert result["description_placeholders"]["school"] == "school"
    assert CONF_USERNAME not in {str(k) for k in result["data_schema"].schema}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_PASSWORD: NEW_PASSWORD}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.LOADED
    assert entry.data[CONF_PASSWORD] == NEW_PASSWORD
    assert entry.data[CONF_USERNAME] == USERNAME
    assert [p["password"] for p in _posts(fake, "password")] == [
        PASSWORD,
        NEW_PASSWORD,
    ]
    new = entry.runtime_data
    assert new.auth is not old.auth
    assert old.session.closed
    assert not new.session.closed
    assert new.auth.password_submissions == 1


async def test_reauth_wrong_password_can_be_retried(
    hass: HomeAssistant, mocked: aioresponses
) -> None:
    """A rejected password shows an error; each attempt is exactly one login."""
    fake = FakeMagister(mocked, challenges=[*LOGIN_OK, *LOGIN_BAD, *LOGIN_OK])
    entry = await _setup(hass)
    result = await _start_reauth(hass, entry)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_PASSWORD: "wrong"}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_auth"}
    assert entry.data[CONF_PASSWORD] == PASSWORD
    assert len(_posts(fake, "password")) == 2

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_PASSWORD: NEW_PASSWORD}
    )
    assert result["reason"] == "reauth_successful"
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.LOADED
    assert len(_posts(fake, "password")) == 3


async def test_reauth_wrong_account_aborts(
    hass: HomeAssistant, mocked: aioresponses
) -> None:
    """Credentials of a different person are refused and nothing changes."""
    fake = FakeMagister(mocked, challenges=[*LOGIN_OK, *LOGIN_OK])
    entry = await _setup(hass)
    old = entry.runtime_data
    fake.account["Persoon"]["Id"] = 2000
    result = await _start_reauth(hass, entry)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_PASSWORD: NEW_PASSWORD}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "wrong_account"
    await hass.async_block_till_done()
    assert entry.data[CONF_PASSWORD] == PASSWORD
    assert entry.runtime_data is old
    assert len(_posts(fake, "password")) == 2


async def test_reauth_with_new_totp_secret(
    hass: HomeAssistant, mocked: aioresponses
) -> None:
    """A new authenticator secret replaces the old one (spaces are ignored)."""
    fake = FakeMagister(mocked, challenges=[*LOGIN_TOTP_OK, *LOGIN_TOTP_OK])
    entry = await _setup(hass, make_entry(totp=True))
    result = await _start_reauth(hass, entry)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_PASSWORD: NEW_PASSWORD, CONF_TOTP_SECRET: "KRSX G5CT MVRX EZLU"},
    )
    assert result["reason"] == "reauth_successful"
    await hass.async_block_till_done()
    assert entry.data[CONF_TOTP_SECRET] == NEW_TOTP
    assert entry.state is ConfigEntryState.LOADED
    assert len(_posts(fake, "soft-token")) == 2
    assert entry.runtime_data.auth.password_submissions == 1


async def test_reauth_keeps_the_saved_totp_secret_when_left_empty(
    hass: HomeAssistant, mocked: aioresponses
) -> None:
    """Only the password changes: the saved secret is used for the check."""
    FakeMagister(mocked, challenges=[*LOGIN_TOTP_OK, *LOGIN_TOTP_OK])
    entry = await _setup(hass, make_entry(totp=True))
    result = await _start_reauth(hass, entry)
    await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_PASSWORD: NEW_PASSWORD}
    )
    await hass.async_block_till_done()
    assert entry.data[CONF_TOTP_SECRET] == TOTP_SECRET
    assert entry.data[CONF_PASSWORD] == NEW_PASSWORD


async def test_setup_failure_starts_reauth_and_reauth_recovers(
    hass: HomeAssistant, mocked: aioresponses
) -> None:
    """A rejected password at setup shows HA's re-authentication card."""
    fake = FakeMagister(mocked, challenges=[*LOGIN_BAD, *LOGIN_OK])
    entry = make_entry()
    entry.add_to_hass(hass)
    assert not await hass.config_entries.async_setup(entry.entry_id)
    assert entry.state is ConfigEntryState.SETUP_ERROR
    flows = hass.config_entries.flow.async_progress_by_handler(DOMAIN)
    assert [f["context"]["source"] for f in flows] == [SOURCE_REAUTH]
    assert len(_posts(fake, "password")) == 1

    result = await hass.config_entries.flow.async_configure(
        flows[0]["flow_id"], {CONF_PASSWORD: NEW_PASSWORD}
    )
    assert result["reason"] == "reauth_successful"
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.LOADED
    assert len(_posts(fake, "password")) == 2
    assert not hass.config_entries.flow.async_progress_by_handler(DOMAIN)


async def test_reauth_never_causes_more_than_one_password_submission(
    hass: HomeAssistant, mocked: aioresponses, frozen_now: FrozenDateTimeFactory
) -> None:
    """Regression: from the failing poll to the finished reauth, one submission.

    The password was changed at Magister. The next login after the token ran out
    is rejected (one submission). Polling must not retry it, and the reauth form
    makes exactly one more login that the reload then reuses.
    """
    fake = FakeMagister(
        mocked, challenges=[*LOGIN_OK, *LOGIN_BAD, *LOGIN_OK], student=False
    )
    clock = [0.0]
    with patch(
        "custom_components.magister.MagisterAuth",
        partial(MagisterAuth, clock=lambda: clock[0]),
    ):
        entry = await _setup(hass)
    assert len(_posts(fake, "password")) == 1

    # The token (1 h) runs out; the silent renew finds no session; the login fails.
    clock[0] += 4000
    frozen_now.tick(timedelta(minutes=65))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)
    assert len(_posts(fake, "password")) == 2
    flows = hass.config_entries.flow.async_progress_by_handler(DOMAIN)
    assert [f["context"]["source"] for f in flows] == [SOURCE_REAUTH]

    # More polls while the card is open send nothing.
    for _ in range(4):
        frozen_now.tick(timedelta(minutes=35))
        async_fire_time_changed(hass)
        await hass.async_block_till_done(wait_background_tasks=True)
    assert len(_posts(fake, "password")) == 2

    result = await hass.config_entries.flow.async_configure(
        flows[0]["flow_id"], {CONF_PASSWORD: NEW_PASSWORD}
    )
    assert result["reason"] == "reauth_successful"
    await hass.async_block_till_done(wait_background_tasks=True)
    assert entry.state is ConfigEntryState.LOADED
    assert len(_posts(fake, "password")) == 3
    assert [p["password"] for p in _posts(fake, "password")][-1] == NEW_PASSWORD

    # The reload used the handed-over login, and polling goes on without a login.
    for _ in range(3):
        frozen_now.tick(timedelta(minutes=35))
        async_fire_time_changed(hass)
        await hass.async_block_till_done(wait_background_tasks=True)
    assert len(_posts(fake, "password")) == 3
    assert entry.state is ConfigEntryState.LOADED


async def test_reconfigure_username_and_secret(
    hass: HomeAssistant, mocked: aioresponses
) -> None:
    """Reconfigure: other username, same person; one login and a reload."""
    fake = FakeMagister(mocked, challenges=[*LOGIN_OK, *LOGIN_OK])
    entry = await _setup(hass)
    old = entry.runtime_data
    result = await entry.start_reconfigure_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"
    suggested = {
        str(k): k.description["suggested_value"]
        for k in result["data_schema"].schema
        if k.description and "suggested_value" in k.description
    }
    assert suggested[CONF_USERNAME] == USERNAME

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_USERNAME: "other-user"}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    await hass.async_block_till_done()
    assert entry.data[CONF_USERNAME] == "other-user"
    assert entry.data[CONF_PASSWORD] == PASSWORD  # left empty: kept
    assert entry.state is ConfigEntryState.LOADED
    assert [p["username"] for p in _posts(fake, "username")] == [
        USERNAME,
        "other-user",
    ]
    assert len(_posts(fake, "password")) == 2
    assert entry.runtime_data.auth is not old.auth


async def test_reconfigure_wrong_account_and_wrong_password(
    hass: HomeAssistant, mocked: aioresponses
) -> None:
    """Reconfigure shows login errors and refuses another person."""
    fake = FakeMagister(mocked, challenges=[*LOGIN_OK, *LOGIN_BAD, *LOGIN_OK])
    entry = await _setup(hass)
    result = await entry.start_reconfigure_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_USERNAME: "other-user", CONF_PASSWORD: "wrong"}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_auth"}
    fake.account["Persoon"]["Id"] = 2000
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_USERNAME: "other-user", CONF_PASSWORD: NEW_PASSWORD}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "wrong_account"
    assert entry.data[CONF_USERNAME] == USERNAME
    assert entry.state is ConfigEntryState.LOADED


async def test_login_page_changed_is_a_form_error(
    hass: HomeAssistant, mocked: aioresponses, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A changed login page is reported as such in reauth and reconfigure."""
    from . import api as _api  # noqa: F401
    from .api import helpers

    FakeMagister(mocked, challenges=[*LOGIN_OK, *LOGIN_OK, *LOGIN_OK])
    entry = await _setup(hass)
    original = helpers.read_fixture
    monkeypatch.setattr(
        helpers,
        "read_fixture",
        lambda name: "x" if name == "login_bundle_excerpt.js" else original(name),
    )
    result = await _start_reauth(hass, entry)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_PASSWORD: NEW_PASSWORD}
    )
    assert result["errors"] == {"base": "login_page_changed"}
    monkeypatch.setattr(helpers, "read_fixture", original)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_PASSWORD: NEW_PASSWORD}
    )
    assert result["reason"] == "reauth_successful"


async def test_reconfigure_can_remove_the_totp_secret(
    hass: HomeAssistant, mocked: aioresponses
) -> None:
    """The checkbox removes the saved authenticator secret."""
    FakeMagister(mocked, challenges=[*LOGIN_TOTP_OK, *LOGIN_OK])
    entry = await _setup(hass, make_entry(totp=True))
    result = await entry.start_reconfigure_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_USERNAME: USERNAME, "remove_totp": True}
    )
    assert result["reason"] == "reconfigure_successful"
    await hass.async_block_till_done()
    assert CONF_TOTP_SECRET not in entry.data
    assert entry.state is ConfigEntryState.LOADED
