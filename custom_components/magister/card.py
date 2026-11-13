"""Serve and register the Homework planner card (a bundled Lovelace module)."""

from __future__ import annotations

import hashlib
import logging
from pathlib import Path
from typing import Final

from homeassistant.components.frontend import add_extra_js_url
from homeassistant.components.http import StaticPathConfig  # type: ignore[attr-defined]
from homeassistant.core import HomeAssistant

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

CARD_FILE: Final = "magister-homework-card.js"
CARD_PATH: Final = Path(__file__).parent / "frontend" / CARD_FILE
CARD_URL_PATH: Final = f"/{DOMAIN}_frontend/{CARD_FILE}"
_REGISTERED: Final = f"{DOMAIN}_card_registered"


def _bundle_hash() -> str | None:
    """A short content hash of the bundle, ``None`` when the file is missing."""
    try:
        return hashlib.sha256(CARD_PATH.read_bytes()).hexdigest()[:12]
    except OSError:
        return None


async def async_register_card(hass: HomeAssistant) -> None:
    """Serve the card bundle and load it in every dashboard (once per HA run).

    The URL carries a short hash of the bundle, so a changed bundle is never served
    from a cached older one.
    """
    if hass.data.get(_REGISTERED):
        return
    digest = await hass.async_add_executor_job(_bundle_hash)
    if digest is None:
        _LOGGER.warning("The Homework planner card bundle is missing: %s", CARD_PATH)
        return
    hass.data[_REGISTERED] = True
    await hass.http.async_register_static_paths(
        [StaticPathConfig(CARD_URL_PATH, str(CARD_PATH), cache_headers=True)]
    )
    add_extra_js_url(hass, f"{CARD_URL_PATH}?v={digest}")
