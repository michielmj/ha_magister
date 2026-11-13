"""Registration of the Homework planner card."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

from homeassistant.components.frontend import DATA_EXTRA_MODULE_URL
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component
from pytest_homeassistant_custom_component.typing import ClientSessionGenerator

from custom_components.magister import card
from custom_components.magister.const import DOMAIN

MANIFEST = Path(card.__file__).parent / "manifest.json"
URL = "/magister_frontend/magister-homework-card.js"


async def test_card_is_served_and_registered(
    hass: HomeAssistant, hass_client_no_auth: ClientSessionGenerator
) -> None:
    """Integration setup serves the bundle and adds the versioned module URL."""
    assert await async_setup_component(hass, DOMAIN, {})
    version = json.loads(MANIFEST.read_text())["version"]
    assert hass.data[DATA_EXTRA_MODULE_URL].urls == {f"{URL}?v={version}"}

    client = await hass_client_no_auth()
    response = await client.get(URL)
    assert response.status == 200
    assert await response.read() == card.CARD_PATH.read_bytes()
    assert "max-age" in response.headers["Cache-Control"]


async def test_registration_happens_once(hass: HomeAssistant) -> None:
    """A second call of the setup (another entry) does not register again."""
    assert await async_setup_component(hass, DOMAIN, {})
    assert await async_setup_component(hass, DOMAIN, {})
    assert len(hass.data[DATA_EXTRA_MODULE_URL].urls) == 1


async def test_missing_bundle_is_not_fatal(hass: HomeAssistant, tmp_path: Path) -> None:
    """Without the bundle the integration still loads (and logs a warning)."""
    with patch.object(card, "CARD_PATH", tmp_path / "nope.js"):
        assert await async_setup_component(hass, DOMAIN, {})
    assert not hass.data[DATA_EXTRA_MODULE_URL].urls


def test_manifest_declares_the_dependencies() -> None:
    """hassfest: http is only allowed as a declared dependency; frontend is needed."""
    dependencies = json.loads(MANIFEST.read_text())["dependencies"]
    assert {"http", "frontend"} <= set(dependencies)
