"""Config flow tests."""

from __future__ import annotations

import logging
from typing import Any
from unittest.mock import patch

import pytest
from aioresponses import aioresponses
from homeassistant import config_entries
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers.aiohttp_client import async_create_clientsession

from custom_components.magister.api import (
    MagisterApiError,
    MagisterAuthError,
    MagisterClient,
    MagisterConnectionError,
)
from custom_components.magister.const import (
    CONF_CHILDREN,
    CONF_HOST,
    CONF_SCHOOL,
    CONF_TOTP_SECRET,
    DOMAIN,
)

from .api.helpers import PASSWORD, RETURN_URL, TOKEN, TOTP_SECRET, USERNAME
from .ha_helpers import CHILD_ID, UNIQUE_ID, FakeMagister, make_entry

TWO_CHILDREN = [
    {"Id": 1001, "Roepnaam": "Anna", "Achternaam": "", "Tussenvoegsel": ""},
    {"Id": 1002, "Roepnaam": "Bram", "Achternaam": "", "Tussenvoegsel": ""},
]

USER_INPUT = {
    CONF_SCHOOL: "school",
    CONF_USERNAME: USERNAME,
    CONF_PASSWORD: PASSWORD,
}


def _spy_sessions(sessions: list[Any]) -> Any:
    """A replacement for ``async_create_clientsession`` that records sessions."""

    def spy(hass: HomeAssistant, *args: Any, **kwargs: Any) -> Any:
        session = async_create_clientsession(hass, *args, **kwargs)
        sessions.append(session)
        return session

    return spy


async def _start(hass: HomeAssistant) -> str:
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    return result["flow_id"]


async def test_parent_flow_creates_entry(
    hass: HomeAssistant, mocked: aioresponses
) -> None:
    """User step, children step (all selected by default), entry set up."""
    fake = FakeMagister(mocked)
    flow_id = await _start(hass)

    result = await hass.config_entries.flow.async_configure(flow_id, USER_INPUT)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "children"
    schema = result["data_schema"].schema
    default = next(k for k in schema if k == CONF_CHILDREN).default()
    assert default == [str(CHILD_ID)]

    result = await hass.config_entries.flow.async_configure(
        flow_id, {CONF_CHILDREN: [str(CHILD_ID)]}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Magister school (Ouder)"
    assert result["data"] == {
        CONF_HOST: "school.magister.net",
        CONF_USERNAME: USERNAME,
        CONF_PASSWORD: PASSWORD,
        CONF_CHILDREN: [{"id": CHILD_ID, "name": "Kind A", "short_name": "Kind A"}],
    }
    entry = result["result"]
    assert entry.unique_id == UNIQUE_ID
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.LOADED
    # The login of the flow is reused: no second login at setup
    assert [name for name, *_ in fake.login.posts] == [
        "current",
        "username",
        "password",
    ]
    assert fake.account_requests == 1


@pytest.mark.parametrize(
    "school",
    ["school", " School ", "school.magister.net", "https://school.magister.net/app"],
)
async def test_school_is_normalized(
    hass: HomeAssistant, mocked: aioresponses, school: str
) -> None:
    """Short names, hosts and URLs all end up as the same host."""
    FakeMagister(mocked, student=True)
    flow_id = await _start(hass)
    result = await hass.config_entries.flow.async_configure(
        flow_id, {**USER_INPUT, CONF_SCHOOL: school}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_HOST] == "school.magister.net"


async def test_student_account_skips_children_step(
    hass: HomeAssistant, mocked: aioresponses
) -> None:
    """A student account is its own (only) child."""
    FakeMagister(mocked, student=True)
    flow_id = await _start(hass)
    result = await hass.config_entries.flow.async_configure(flow_id, USER_INPUT)
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_CHILDREN] == [
        {"id": CHILD_ID, "name": "Ouder", "short_name": "Ouder"}
    ]
    assert result["result"].unique_id == f"school.magister.net:{CHILD_ID}"


async def test_totp_flow(hass: HomeAssistant, mocked: aioresponses) -> None:
    """Without the secret the flow reports totp_required; then it works."""
    steps: list[dict[str, Any]] = [
        {"action": "username"},
        {"action": "password"},
        {"action": "soft-token"},
    ]
    fake = FakeMagister(
        mocked,
        student=True,
        challenges=[*steps, *steps, {"redirectURL": RETURN_URL}],
    )
    flow_id = await _start(hass)
    result = await hass.config_entries.flow.async_configure(flow_id, USER_INPUT)
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "totp_required"}

    result = await hass.config_entries.flow.async_configure(
        flow_id,
        {**USER_INPUT, CONF_TOTP_SECRET: f" {TOTP_SECRET[:8]} {TOTP_SECRET[8:]}"},
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_TOTP_SECRET] == TOTP_SECRET
    await hass.async_block_till_done()
    assert result["result"].state is ConfigEntryState.LOADED
    # soft-token was answered once; setup reused the validated login
    assert [name for name, *_ in fake.login.posts].count("soft-token") == 1


@pytest.mark.parametrize(
    ("error", "key"),
    [
        (
            MagisterAuthError("invalid_auth", server_error="InvalidChallenge"),
            "invalid_auth",
        ),
        (MagisterAuthError("totp_required"), "totp_required"),
        (MagisterAuthError("invalid_totp"), "invalid_totp"),
        (MagisterAuthError("unsupported_login"), "unsupported_login"),
        (MagisterAuthError("something_new"), "invalid_auth"),
        (MagisterConnectionError("down"), "cannot_connect"),
        (MagisterApiError("rate limit", status=429), "cannot_connect"),
        (MagisterApiError("odd", status=404), "unknown"),
        (RuntimeError("boom"), "unknown"),
    ],
)
async def test_error_paths_and_recovery(
    hass: HomeAssistant,
    mocked: aioresponses,
    error: Exception,
    key: str,
) -> None:
    """Every error shows on the form, and a retry can still succeed."""
    FakeMagister(mocked, student=True)
    flow_id = await _start(hass)
    with patch.object(MagisterClient, "async_get_account", side_effect=error):
        result = await hass.config_entries.flow.async_configure(flow_id, USER_INPUT)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": key}

    result = await hass.config_entries.flow.async_configure(flow_id, USER_INPUT)
    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_children_lookup_error(hass: HomeAssistant, mocked: aioresponses) -> None:
    """A failure while reading the children is reported like a login failure."""
    FakeMagister(mocked)
    flow_id = await _start(hass)
    with patch.object(
        MagisterClient, "async_get_children", side_effect=MagisterConnectionError("x")
    ):
        result = await hass.config_entries.flow.async_configure(flow_id, USER_INPUT)
    assert result["errors"] == {"base": "cannot_connect"}


async def test_real_login_failure_is_invalid_auth(
    hass: HomeAssistant, mocked: aioresponses
) -> None:
    """A rejected password from the (fake) login service maps to invalid_auth."""
    FakeMagister(
        mocked,
        challenges=[
            {"action": "username"},
            {"action": "password"},
            {"error": "InvalidChallenge"},
        ],
    )
    flow_id = await _start(hass)
    result = await hass.config_entries.flow.async_configure(flow_id, USER_INPUT)
    assert result["errors"] == {"base": "invalid_auth"}


@pytest.mark.parametrize("school", ["", "example.com", "evil.net/x", "accounts"])
async def test_invalid_school(hass: HomeAssistant, school: str) -> None:
    """Only *.magister.net schools are accepted; nothing is sent elsewhere."""
    flow_id = await _start(hass)
    result = await hass.config_entries.flow.async_configure(
        flow_id, {**USER_INPUT, CONF_SCHOOL: school}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {CONF_SCHOOL: "invalid_school"}


async def test_duplicate_account_aborts(
    hass: HomeAssistant, mocked: aioresponses
) -> None:
    """The same school account cannot be added twice."""
    FakeMagister(mocked)
    make_entry().add_to_hass(hass)
    flow_id = await _start(hass)
    result = await hass.config_entries.flow.async_configure(flow_id, USER_INPUT)
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_no_child_selected(hass: HomeAssistant, mocked: aioresponses) -> None:
    """At least one child is required."""
    FakeMagister(mocked)
    flow_id = await _start(hass)
    await hass.config_entries.flow.async_configure(flow_id, USER_INPUT)
    result = await hass.config_entries.flow.async_configure(
        flow_id, {CONF_CHILDREN: []}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "no_children_selected"}
    result = await hass.config_entries.flow.async_configure(
        flow_id, {CONF_CHILDREN: [str(CHILD_ID)]}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_parent_without_children_aborts(
    hass: HomeAssistant, mocked: aioresponses
) -> None:
    """A parent account without children has nothing to show."""
    FakeMagister(mocked, children=[])
    flow_id = await _start(hass)
    result = await hass.config_entries.flow.async_configure(flow_id, USER_INPUT)
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_children"


async def test_abandoned_flow_closes_its_session(
    hass: HomeAssistant, mocked: aioresponses
) -> None:
    """A login that never becomes an entry does not leak its session."""
    FakeMagister(mocked)
    sessions = []

    def spy(hass_: HomeAssistant, *args: Any, **kwargs: Any) -> Any:
        session = async_create_clientsession(hass_, *args, **kwargs)
        sessions.append(session)
        return session

    with patch(
        "custom_components.magister.config_flow.async_create_clientsession", spy
    ):
        flow_id = await _start(hass)
        result = await hass.config_entries.flow.async_configure(flow_id, USER_INPUT)
        assert result["step_id"] == "children"
        assert not sessions[0].closed
        hass.config_entries.flow.async_abort(flow_id)
        await hass.async_block_till_done()
    assert sessions[0].closed


async def test_failed_login_closes_its_session(
    hass: HomeAssistant, mocked: aioresponses
) -> None:
    """Sessions of failed attempts are closed, and a new one is made for a retry."""
    FakeMagister(mocked, student=True)
    sessions = []

    def spy(hass_: HomeAssistant, *args: Any, **kwargs: Any) -> Any:
        session = async_create_clientsession(hass_, *args, **kwargs)
        sessions.append(session)
        return session

    with (
        patch("custom_components.magister.config_flow.async_create_clientsession", spy),
        patch.object(
            MagisterClient, "async_get_account", side_effect=MagisterAuthError("x")
        ),
    ):
        flow_id = await _start(hass)
        await hass.config_entries.flow.async_configure(flow_id, USER_INPUT)
    assert sessions[0].closed


async def test_no_secrets_in_logs(
    hass: HomeAssistant, mocked: aioresponses, caplog: pytest.LogCaptureFixture
) -> None:
    """Config flow and setup never log the password, TOTP secret or token."""
    caplog.set_level(logging.DEBUG)
    steps: list[dict[str, Any]] = [
        {"action": "username"},
        {"action": "password"},
        {"action": "soft-token"},
        {"redirectURL": RETURN_URL},
    ]
    FakeMagister(mocked, challenges=steps)
    flow_id = await _start(hass)
    # failure path first (debug logging of auth errors)
    with patch.object(
        MagisterClient,
        "async_get_account",
        side_effect=MagisterAuthError("invalid_auth", server_error="InvalidChallenge"),
    ):
        await hass.config_entries.flow.async_configure(
            flow_id, {**USER_INPUT, CONF_TOTP_SECRET: TOTP_SECRET}
        )
    await hass.config_entries.flow.async_configure(
        flow_id, {**USER_INPUT, CONF_TOTP_SECRET: TOTP_SECRET}
    )
    result = await hass.config_entries.flow.async_configure(
        flow_id, {CONF_CHILDREN: [str(CHILD_ID)]}
    )
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert "InvalidChallenge" in caplog.text  # the server error name is logged
    for secret in (PASSWORD, TOTP_SECRET, TOKEN):
        assert secret not in caplog.text


async def test_child_of_another_login_is_not_offered(
    hass: HomeAssistant, mocked: aioresponses
) -> None:
    """A child already configured under another login of the school is hidden."""
    FakeMagister(mocked, children=TWO_CHILDREN)
    make_entry(unique_id="school.magister.net:2000").add_to_hass(hass)
    flow_id = await _start(hass)
    result = await hass.config_entries.flow.async_configure(flow_id, USER_INPUT)
    assert result["step_id"] == "children"
    schema = result["data_schema"].schema
    key = next(k for k in schema if k == CONF_CHILDREN)
    assert [o["value"] for o in schema[key].config["options"]] == ["1002"]

    # A stale or forged selection is rejected with a clear error
    flow = hass.config_entries.flow._progress[flow_id]
    assert flow._taken_children() == {CHILD_ID}
    result = await flow.async_step_children({CONF_CHILDREN: ["1001", "1002"]})
    assert result["errors"] == {"base": "child_already_configured"}


async def test_all_children_already_configured_aborts(
    hass: HomeAssistant, mocked: aioresponses
) -> None:
    """When every child already belongs to another login there is nothing to add."""
    FakeMagister(mocked)
    make_entry(unique_id="school.magister.net:2000").add_to_hass(hass)
    flow_id = await _start(hass)
    result = await hass.config_entries.flow.async_configure(flow_id, USER_INPUT)
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "all_children_configured"
