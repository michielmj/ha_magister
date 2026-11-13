"""Helpers to fake a whole Magister school (login plus data API) for HA tests."""

from __future__ import annotations

import copy
import json
import re
from pathlib import Path
from typing import Any

from aioresponses import CallbackResult, aioresponses
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.magister.const import (
    CONF_CHILDREN,
    CONF_HOST,
    CONF_TOTP_SECRET,
    DOMAIN,
)

from .api.helpers import HOST, PASSWORD, TOTP_SECRET, USERNAME, FakeLogin

FIXTURES = Path(__file__).parent / "fixtures"
PARENT_ID = 1000
CHILD_ID = 1001
UNIQUE_ID = f"{HOST}:{PARENT_ID}"
# The frozen "now" for tests: Friday 13 Nov 2026 (the fixtures cover 2-30 Nov).
NOW = "2026-11-13 09:30:00+00:00"

_APPOINTMENTS_RE = re.compile(
    rf"^https://{re.escape(HOST)}/api/personen/(\d+)/afspraken(\?.*)?$"
)


def load_fixture(school: str, name: str) -> dict[str, Any]:
    """Load an anonymized real response."""
    data: dict[str, Any] = json.loads(
        (FIXTURES / school / name).read_text(encoding="utf-8")
    )
    return data


class FakeMagister:
    """Login service plus data API for one school, on an ``aioresponses`` mock."""

    def __init__(
        self,
        mocked: aioresponses,
        school: str = "school_a",
        *,
        student: bool = False,
        challenges: list[dict[str, Any]] | None = None,
        children: list[dict[str, Any]] | None = None,
    ) -> None:
        """Register the endpoints. ``student`` makes a non-parent account."""
        self.login = FakeLogin(mocked, challenges=challenges)
        self.account = copy.deepcopy(load_fixture(school, "account.json"))
        if student:
            self.account["Groep"] = [{"Naam": "Leerling"}]
            self.account["Persoon"]["Id"] = CHILD_ID
        self.children = (
            children
            if children is not None
            else copy.deepcopy(load_fixture(school, "children.json"))["Items"]
        )
        items = load_fixture(school, "appointments.json")["Items"]
        self.appointments: dict[int, list[dict[str, Any]]] = {
            int(child["Id"]): copy.deepcopy(items) for child in self.children
        }
        if student:
            self.appointments[CHILD_ID] = copy.deepcopy(items)
        self.appointment_status = 200
        self.appointment_requests: list[tuple[int, dict[str, str]]] = []
        self.account_requests = 0
        self.max_parallel = 0
        self._running = 0
        mocked.get(f"https://{HOST}/api/account", callback=self._account, repeat=True)
        mocked.get(
            re.compile(rf"^https://{re.escape(HOST)}/api/personen/\d+/kinderen$"),
            callback=self._children,
            repeat=True,
        )
        mocked.get(_APPOINTMENTS_RE, callback=self._appointments, repeat=True)

    def _account(self, url: Any, **kwargs: Any) -> CallbackResult:
        self.account_requests += 1
        return CallbackResult(payload=self.account)

    def _children(self, url: Any, **kwargs: Any) -> CallbackResult:
        return CallbackResult(payload={"Items": self.children})

    def _appointments(self, url: Any, **kwargs: Any) -> CallbackResult:
        match = _APPOINTMENTS_RE.match(str(url))
        assert match is not None
        person_id = int(match.group(1))
        self.appointment_requests.append((person_id, dict(url.query)))
        if self.appointment_status != 200:
            return CallbackResult(status=self.appointment_status, body="")
        return CallbackResult(payload={"Items": self.appointments.get(person_id, [])})


def make_entry(
    *,
    children: list[tuple[int, str]] | None = None,
    unique_id: str = UNIQUE_ID,
    totp: bool = False,
) -> MockConfigEntry:
    """A config entry like the config flow creates it."""
    children = children if children is not None else [(CHILD_ID, "Kind A")]
    data: dict[str, Any] = {
        CONF_HOST: HOST,
        CONF_USERNAME: USERNAME,
        CONF_PASSWORD: PASSWORD,
        CONF_CHILDREN: [
            {"id": child_id, "name": name, "short_name": name.split()[0]}
            for child_id, name in children
        ],
    }
    if totp:
        data[CONF_TOTP_SECRET] = TOTP_SECRET
    return MockConfigEntry(
        domain=DOMAIN,
        title="Magister school (Ouder)",
        unique_id=unique_id,
        data=data,
    )
