"""Shared test fixtures."""

import inspect
from collections.abc import AsyncGenerator, Generator
from typing import Any
from unittest.mock import Mock

import aiohttp
import pytest
from aioresponses import aioresponses, core


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(
    enable_custom_integrations: None,
) -> Generator[None]:
    """Enable loading of custom integrations in all tests."""
    yield


class _CompatClientResponse(aiohttp.ClientResponse):
    """ClientResponse that tolerates aioresponses 0.7.9 on aiohttp >= 3.14.

    aiohttp 3.14 added a required ``stream_writer`` argument that aioresponses
    0.7.9 does not pass yet. Upstream: https://github.com/pnuckowski/aioresponses
    (no release with the fix at the time of writing). The shim is only applied
    when ``ClientResponse`` actually requires ``stream_writer``; remove it once
    aioresponses supports aiohttp 3.14.
    """

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        writer = Mock()
        writer.output_size = 0
        kwargs.setdefault("stream_writer", writer)
        super().__init__(*args, **kwargs)


@pytest.fixture(autouse=True)
def _patch_aioresponses(monkeypatch: pytest.MonkeyPatch) -> None:
    """Apply the aioresponses/aiohttp compatibility shim."""
    if "stream_writer" in inspect.signature(aiohttp.ClientResponse.__init__).parameters:
        monkeypatch.setattr(core, "ClientResponse", _CompatClientResponse)


@pytest.fixture
def mocked() -> Generator[aioresponses]:
    """Mock aiohttp requests."""
    with aioresponses() as m:
        yield m


@pytest.fixture
async def session() -> AsyncGenerator[aiohttp.ClientSession]:
    """A client session with its own cookie jar."""
    async with aiohttp.ClientSession() as client_session:
        yield client_session
