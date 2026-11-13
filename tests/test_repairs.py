"""Repair issue and hygiene tests."""

from __future__ import annotations

from datetime import timedelta
from functools import partial
from unittest.mock import patch

import pytest
from aioresponses import aioresponses
from freezegun.api import FrozenDateTimeFactory
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.aiohttp_client import async_create_clientsession
from pytest_homeassistant_custom_component.common import async_fire_time_changed

from custom_components.magister import async_sync_duplicate_issues
from custom_components.magister.api import (
    MagisterApiError,
    MagisterAuth,
    MagisterClient,
)
from custom_components.magister.const import DOMAIN
from custom_components.magister.pending import PendingLogin, retain_login

from .api import helpers
from .ha_helpers import NOW, FakeMagister, make_entry


@pytest.fixture(autouse=True)
def frozen_now(freezer: FrozenDateTimeFactory) -> FrozenDateTimeFactory:
    """Freeze time on Friday 13 November 2026."""
    freezer.move_to(NOW)
    return freezer


async def test_changed_login_page_creates_and_clears_a_repair_issue(
    hass: HomeAssistant,
    mocked: aioresponses,
    monkeypatch: pytest.MonkeyPatch,
    frozen_now: FrozenDateTimeFactory,
) -> None:
    """No authCode in the login script: a repair issue, cleared by a good login."""
    FakeMagister(mocked)
    original = helpers.read_fixture
    monkeypatch.setattr(
        helpers,
        "read_fixture",
        lambda name: (
            "var nothing=1;" if name == "login_bundle_excerpt.js" else original(name)
        ),
    )
    clock = [0.0]
    entry = make_entry()
    entry.add_to_hass(hass)
    issue_id = f"login_page_changed_{entry.entry_id}"
    registry = ir.async_get(hass)
    with patch(
        "custom_components.magister.MagisterAuth",
        partial(MagisterAuth, clock=lambda: clock[0]),
    ):
        assert not await hass.config_entries.async_setup(entry.entry_id)
        assert entry.state is ConfigEntryState.SETUP_RETRY
        issue = registry.async_get_issue(DOMAIN, issue_id)
        assert issue is not None
        assert issue.translation_key == "login_page_changed"
        assert issue.severity is ir.IssueSeverity.ERROR
        assert not issue.is_fixable

        # Magister (or the integration) is fixed: the next retry logs in
        monkeypatch.setattr(helpers, "read_fixture", original)
        clock[0] += 60
        frozen_now.tick(timedelta(minutes=10))
        async_fire_time_changed(hass)
        await hass.async_block_till_done(wait_background_tasks=True)
    assert entry.state is ConfigEntryState.LOADED
    assert registry.async_get_issue(DOMAIN, issue_id) is None


async def test_issue_is_removed_with_the_entry(
    hass: HomeAssistant, mocked: aioresponses, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Removing the entry removes its repair issue."""
    FakeMagister(mocked)
    original = helpers.read_fixture
    monkeypatch.setattr(
        helpers,
        "read_fixture",
        lambda name: "x" if name == "login_bundle_excerpt.js" else original(name),
    )
    entry = make_entry()
    entry.add_to_hass(hass)
    assert not await hass.config_entries.async_setup(entry.entry_id)
    registry = ir.async_get(hass)
    assert registry.async_get_issue(DOMAIN, f"login_page_changed_{entry.entry_id}")
    await hass.config_entries.async_remove(entry.entry_id)
    assert (
        registry.async_get_issue(DOMAIN, f"login_page_changed_{entry.entry_id}") is None
    )


async def test_other_errors_do_not_create_the_issue(
    hass: HomeAssistant, mocked: aioresponses
) -> None:
    """A plain API error is a retry, not a "login page changed" repair."""
    FakeMagister(mocked)
    entry = make_entry()
    entry.add_to_hass(hass)
    with patch.object(
        MagisterAuth, "async_get_token", side_effect=MagisterApiError("odd")
    ):
        assert not await hass.config_entries.async_setup(entry.entry_id)
    assert entry.state is ConfigEntryState.SETUP_RETRY
    assert not ir.async_get(hass).issues


async def test_unreported_final_failure_blocks_setup(
    hass: HomeAssistant, mocked: aioresponses
) -> None:
    """A remembered failure that was never reported is not retried."""
    fake = FakeMagister(mocked)
    entry = make_entry()
    entry.add_to_hass(hass)
    http = async_create_clientsession(hass, auto_cleanup=False)
    auth = MagisterAuth(http, helpers.HOST, helpers.USERNAME, helpers.PASSWORD)
    auth._failure = MagisterApiError("remembered")
    login = PendingLogin(
        http,
        auth,
        MagisterClient(http, auth, helpers.HOST),
        credentials=(
            helpers.HOST,
            helpers.USERNAME,
            helpers.PASSWORD,
            None,
        ),
    )
    retain_login(hass, entry.entry_id, login)
    assert not await hass.config_entries.async_setup(entry.entry_id)
    assert entry.state is ConfigEntryState.SETUP_ERROR
    assert auth.final_failure_reported
    assert fake.login.posts == []


async def test_child_in_two_logins_creates_and_clears_a_repair_issue(
    hass: HomeAssistant, mocked: aioresponses, caplog: pytest.LogCaptureFixture
) -> None:
    """A child shared by two logins of a school is reported, without names."""
    FakeMagister(mocked)
    entry = make_entry()
    entry.add_to_hass(hass)
    other = make_entry(unique_id="school.magister.net:2000")
    other.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    registry = ir.async_get(hass)
    issue_id = f"child_in_multiple_entries_{entry.entry_id}"
    issue = registry.async_get_issue(DOMAIN, issue_id)
    assert issue is not None
    assert not issue.is_fixable
    assert issue.translation_key == "child_in_multiple_entries"
    assert "more than one Magister login" in caplog.text
    assert "Kind A" not in caplog.text

    await hass.config_entries.async_remove(other.entry_id)
    await hass.async_block_till_done()
    assert registry.async_get_issue(DOMAIN, issue_id) is None


async def test_duplicate_issue_cleared_when_child_is_removed_via_options(
    hass: HomeAssistant, mocked: aioresponses
) -> None:
    """Fixing the duplicate in one login clears the issue of the other."""
    FakeMagister(mocked)
    entry = make_entry()
    entry.add_to_hass(hass)
    other = make_entry(unique_id="school.magister.net:2000")
    other.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    registry = ir.async_get(hass)
    assert registry.async_get_issue(
        DOMAIN, f"child_in_multiple_entries_{entry.entry_id}"
    )
    # In real life the other login changes through its own options flow, whose update
    # listener runs the same sync.
    hass.config_entries.async_update_entry(
        other,
        data={**other.data, "children": [{"id": 9, "name": "X", "short_name": "X"}]},
    )
    async_sync_duplicate_issues(hass)
    assert (
        registry.async_get_issue(DOMAIN, f"child_in_multiple_entries_{entry.entry_id}")
        is None
    )
