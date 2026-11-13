"""Registration of the Homework planner card."""

from __future__ import annotations

import hashlib
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
    digest = hashlib.sha256(card.CARD_PATH.read_bytes()).hexdigest()[:12]
    assert hass.data[DATA_EXTRA_MODULE_URL].urls == {f"{URL}?v={digest}"}

    client = await hass_client_no_auth()
    response = await client.get(URL)
    assert response.status == 200
    assert await response.read() == card.CARD_PATH.read_bytes()
    assert "max-age" in response.headers["Cache-Control"]


async def test_registering_twice_serves_one_path(hass: HomeAssistant) -> None:
    """Registering again serves no second static path and adds no second URL."""
    assert await async_setup_component(hass, "http", {})
    with patch.object(
        hass.http,
        "async_register_static_paths",
        wraps=hass.http.async_register_static_paths,
    ) as register:
        await card.async_register_card(hass)
        await card.async_register_card(hass)
    register.assert_awaited_once()
    assert len(hass.data[DATA_EXTRA_MODULE_URL].urls) == 1


async def test_url_changes_with_the_bundle(hass: HomeAssistant, tmp_path: Path) -> None:
    """A different bundle gets a different cache-busting hash."""
    first = tmp_path / "a.js"
    first.write_text("one")
    with patch.object(card, "CARD_PATH", first):
        digest_one = card._bundle_hash()
        first.write_text("two")
        digest_two = card._bundle_hash()
    assert digest_one != digest_two
    assert len(digest_one or "") == 12


async def test_missing_bundle_is_not_fatal(hass: HomeAssistant, tmp_path: Path) -> None:
    """Without the bundle the integration still loads (and logs a warning)."""
    with patch.object(card, "CARD_PATH", tmp_path / "nope.js"):
        assert await async_setup_component(hass, DOMAIN, {})
    assert not hass.data[DATA_EXTRA_MODULE_URL].urls


def test_manifest_declares_the_dependencies() -> None:
    """hassfest: http is only allowed as a declared dependency; frontend is needed."""
    dependencies = json.loads(MANIFEST.read_text())["dependencies"]
    assert {"http", "frontend"} <= set(dependencies)
