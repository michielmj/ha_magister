"""The coach through Home Assistant's own MCP server (main endpoint, non-admin user)."""

from __future__ import annotations

import json
from typing import Any

import pytest
from aioresponses import aioresponses
from freezegun.api import FrozenDateTimeFactory
from homeassistant.auth.const import GROUP_ID_ADMIN
from homeassistant.const import CONF_LLM_HASS_API
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.typing import ClientSessionGenerator

from custom_components.magister.coach import COACH_API_ID

from .ha_helpers import NOW
from .test_coach import coach_options, make_user, setup_coach

CLIENT_ID = "https://example.com/app"
HEADERS = {"Content-Type": "application/json", "Accept": "application/json"}


@pytest.fixture(autouse=True)
async def frozen_now(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> FrozenDateTimeFactory:
    """Friday 13 November 2026."""
    await hass.config.async_set_time_zone("Europe/Amsterdam")
    freezer.move_to(NOW)
    return freezer


async def token_of(hass: HomeAssistant, user: Any) -> str:
    """An access token of a user."""
    refresh = await hass.auth.async_create_refresh_token(user, CLIENT_ID)
    return hass.auth.async_create_access_token(refresh)


async def mcp(
    client: Any, token: str, method: str, params: dict[str, Any] | None = None
) -> dict[str, Any]:
    """One JSON-RPC request to the main MCP endpoint."""
    response = await client.post(
        "/api/mcp",
        headers={**HEADERS, "Authorization": f"Bearer {token}"},
        json={"jsonrpc": "2.0", "id": 1, "method": method, "params": params or {}},
    )
    assert response.status == 200, await response.text()
    body: dict[str, Any] = await response.json()
    return body


async def setup_mcp(
    hass: HomeAssistant, *, require_admin: bool, apis: list[str] | None = None
) -> None:
    """The MCP Server integration serving only the coach."""
    entry = MockConfigEntry(
        domain="mcp_server",
        title="Magister huiswerkcoach",
        version=1,
        minor_version=3,
        data={
            "all_llm_apis": False,
            CONF_LLM_HASS_API: apis or [COACH_API_ID],
            "require_admin": require_admin,
        },
    )
    entry.add_to_hass(hass)
    assert await async_setup_component(hass, "homeassistant", {})
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()


async def test_student_uses_the_tools_without_admin(
    hass: HomeAssistant,
    mocked: aioresponses,
    hass_client_no_auth: ClientSessionGenerator,
) -> None:
    """A non-admin linked user lists tools, reads and writes (``require_admin`` off)."""
    await make_user(hass, "Eigenaar")  # the first user is the owner
    student = await make_user(hass, "Leerling")
    other = await make_user(hass, "Anders")
    await setup_coach(
        hass,
        mocked,
        coach_options(**{"1001": {"enabled": True, "users": [student.id]}}),
    )
    await setup_mcp(hass, require_admin=False)
    client = await hass_client_no_auth()
    token = await token_of(hass, student)
    assert not student.is_admin

    listed = await mcp(client, token, "tools/list")
    tools = {t["name"]: t for t in listed["result"]["tools"]}
    assert "add_subtask" in tools
    assert tools["list_homework"]["annotations"]["readOnlyHint"] is True
    assert tools["delete_subtask"]["annotations"]["destructiveHint"] is True
    assert "child" in tools["list_homework"]["inputSchema"]["properties"]
    minutes = tools["update_subtask"]["inputSchema"]["properties"]["minutes"]
    assert "null" in json.dumps(minutes)
    assert "get_overview" in tools
    assert tools["get_overview"]["annotations"]["readOnlyHint"] is True

    called = await mcp(
        client,
        token,
        "tools/call",
        {
            "name": "add_subtask",
            "arguments": {
                "item": "100084",
                "title": "H4 woordjes",
                "date": "2026-11-16",
            },
        },
    )
    assert called["result"]["isError"] is False
    data = json.loads(called["result"]["content"][0]["text"])
    assert data["item"]["subtasks"][0]["created_by"] == "ai"

    prompt = await mcp(client, token, "prompts/get", {"name": "Magister huiswerkcoach"})
    text = prompt["result"]["messages"][0]["content"]["text"]
    assert "Kind (id 1001)" in text

    # An unlinked user is served, but gets nothing.
    stranger = await mcp(
        client,
        await token_of(hass, other),
        "tools/call",
        {"name": "list_homework", "arguments": {}},
    )
    assert stranger["result"]["isError"] is True
    assert json.loads(stranger["result"]["content"][0]["text"])["error"] == "not_linked"


async def test_per_api_endpoint_needs_admin_main_endpoint_does_not(
    hass: HomeAssistant,
    mocked: aioresponses,
    hass_client_no_auth: ClientSessionGenerator,
) -> None:
    """HA's `/api/mcp/<api>` is admin-only for our API; students use `/api/mcp`."""
    await make_user(hass, "Eigenaar")
    student = await make_user(hass, "Leerling")
    await setup_coach(
        hass,
        mocked,
        coach_options(**{"1001": {"enabled": True, "users": [student.id]}}),
    )
    await setup_mcp(hass, require_admin=True)
    client = await hass_client_no_auth()
    token = await token_of(hass, student)
    body = {"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}}
    headers = {**HEADERS, "Authorization": f"Bearer {token}"}
    assert (
        await client.post(f"/api/mcp/{COACH_API_ID}", headers=headers, json=body)
    ).status == 401
    # With "require admin" on, the main endpoint is closed to the student as well.
    assert (await client.post("/api/mcp", headers=headers, json=body)).status == 401
    # An administrator can use both.
    admin = await hass.auth.async_create_user("Beheer", group_ids=[GROUP_ID_ADMIN])
    admin_headers = {
        **HEADERS,
        "Authorization": f"Bearer {await token_of(hass, admin)}",
    }
    for url in ("/api/mcp", f"/api/mcp/{COACH_API_ID}"):
        assert (await client.post(url, headers=admin_headers, json=body)).status == 200
