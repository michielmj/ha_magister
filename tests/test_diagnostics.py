"""Diagnostics tests."""

from __future__ import annotations

import json

import pytest
from aioresponses import aioresponses
from freezegun.api import FrozenDateTimeFactory
from homeassistant.core import HomeAssistant

from custom_components.magister.const import (
    CONF_INTERVAL,
    CONF_WEEKS_AHEAD,
    CONF_WEEKS_BACK,
)
from custom_components.magister.diagnostics import async_get_config_entry_diagnostics

from .api.helpers import HOST, PASSWORD, RETURN_URL, TOKEN, TOTP_SECRET, USERNAME
from .ha_helpers import CHILD_ID, NOW, PARENT_ID, FakeMagister, make_entry
from .test_sensor import add_sensor


@pytest.fixture(autouse=True)
async def frozen_now(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> FrozenDateTimeFactory:
    """Friday 13 November 2026."""
    await hass.config.async_set_time_zone("Europe/Amsterdam")
    freezer.move_to(NOW)
    return freezer


async def test_diagnostics_content_and_redaction(
    hass: HomeAssistant, mocked: aioresponses
) -> None:
    """Useful counts, and no secret, name, id or host anywhere."""
    FakeMagister(
        mocked,
        challenges=[
            {"action": "username"},
            {"action": "password"},
            {"action": "soft-token"},
            {"redirectURL": RETURN_URL},
        ],
    )
    entry = make_entry(
        totp=True,
        options={CONF_WEEKS_BACK: 1, CONF_WEEKS_AHEAD: 3, CONF_INTERVAL: 45},
    )
    add_sensor(entry, 0, ["Franse taal"])
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    diagnostics = await async_get_config_entry_diagnostics(hass, entry)
    assert diagnostics["entry"]["account_type"] == "parent"
    assert diagnostics["entry"]["number_of_children"] == 1
    assert diagnostics["entry"]["options"] == {
        CONF_WEEKS_BACK: 1,
        CONF_WEEKS_AHEAD: 3,
        CONF_INTERVAL: 45,
    }
    (child,) = diagnostics["children"]
    assert child["events_in_window"] == 140
    assert sum(child["status"].values()) == 140
    assert sum(child["info_type"].values()) == 140
    assert sum(child["type"].values()) == 140
    assert diagnostics["sensors"] == [{"offset": 0, "excluded_subjects": 1}]
    assert diagnostics["coordinator"]["last_update_success"] is True
    assert diagnostics["coordinator"]["last_error"] is None
    assert diagnostics["coordinator"]["last_success"] is not None
    auth = diagnostics["auth"]
    assert auth["token_source"] == "login"
    assert auth["final_failure"] is False
    assert auth["password_submissions"] == 1
    assert auth["backoff_remaining_seconds"] == 0

    text = json.dumps(diagnostics, default=str)
    for secret in (
        PASSWORD,
        USERNAME,
        TOTP_SECRET,
        TOKEN,
        HOST,
        "school",
        "Kind",
        str(CHILD_ID),
        str(PARENT_ID),
        "Franse taal",
    ):
        assert secret not in text, secret
    assert entry.title not in text


async def test_diagnostics_student_account_and_failure(
    hass: HomeAssistant, mocked: aioresponses
) -> None:
    """A student account is recognised; a failed refresh shows the error class."""
    fake = FakeMagister(mocked, student=True)
    entry = make_entry(unique_id=f"{HOST}:{CHILD_ID}")
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    fake.appointment_status = 503
    await entry.runtime_data.coordinator.async_refresh()
    diagnostics = await async_get_config_entry_diagnostics(hass, entry)
    assert diagnostics["entry"]["account_type"] == "student"
    assert diagnostics["coordinator"]["last_update_success"] is False
    assert diagnostics["coordinator"]["last_error"] == "UpdateFailed"
