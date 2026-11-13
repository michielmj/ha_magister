"""Serve and register the Homework planner card (a bundled Lovelace module)."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Final

from homeassistant.components.frontend import add_extra_js_url
from homeassistant.components.http import StaticPathConfig  # type: ignore[attr-defined]
from homeassistant.core import HomeAssistant
from homeassistant.loader import async_get_integration

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

CARD_FILE: Final = "magister-homework-card.js"
CARD_PATH: Final = Path(__file__).parent / "frontend" / CARD_FILE
CARD_URL_PATH: Final = f"/{DOMAIN}_frontend/{CARD_FILE}"


async def async_register_card(hass: HomeAssistant) -> None:
    """Serve the card bundle and load it in every dashboard (once per HA run).

    The URL carries the integration version, so a new release is never served from
    a cached older bundle.
    """
    if not await hass.async_add_executor_job(CARD_PATH.is_file):
        _LOGGER.warning("The Homework planner card bundle is missing: %s", CARD_PATH)
        return
    integration = await async_get_integration(hass, DOMAIN)
    await hass.http.async_register_static_paths(
        [StaticPathConfig(CARD_URL_PATH, str(CARD_PATH), cache_headers=True)]
    )
    add_extra_js_url(hass, f"{CARD_URL_PATH}?v={integration.version}")
