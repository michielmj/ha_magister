"""Fixtures for the API tests."""

from __future__ import annotations

from collections.abc import AsyncGenerator, Generator
from typing import Any
from unittest.mock import Mock

import aiohttp
import pytest
from aioresponses import aioresponses, core


class _CompatClientResponse(aiohttp.ClientResponse):
    """ClientResponse that tolerates aioresponses 0.7.9 on aiohttp >= 3.14.

    aiohttp 3.14 added a required ``stream_writer`` argument that aioresponses
    0.7.9 does not pass yet. Remove this shim once aioresponses supports it.
    """

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        writer = Mock()
        writer.output_size = 0
        kwargs.setdefault("stream_writer", writer)
        super().__init__(*args, **kwargs)


@pytest.fixture(autouse=True)
def _patch_aioresponses(monkeypatch: pytest.MonkeyPatch) -> None:
    """Apply the aioresponses/aiohttp compatibility shim."""
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
