"""Tests for the PM verification CLI."""

from __future__ import annotations

import json
import re
from datetime import date
from pathlib import Path

import aiohttp
import pytest
from aioresponses import aioresponses

from tests.api.helpers import (
    PASSWORD,
    RETURN_URL,
    TOKEN,
    FakeLogin,
    callback_url,
)
from tools import magister_cli as cli

HOST = "school.magister.net"
BASE = f"https://{HOST}"
TZ = cli.local_tz()
ITEMS = [
    {
        "Id": 1,
        "Start": "2026-11-09T07:30:00.0000000Z",
        "Einde": "2026-11-09T08:20:00.0000000Z",
        "Vakken": [{"Naam": "Wiskunde"}],
        "Docenten": [{"Id": 3, "Naam": "A. Docent", "Docentcode": "ADO"}],
        "LesuurVan": 1,
        "Status": 1,
        "InfoType": 1,
        "Type": 13,
        "Inhoud": "<p>Maak <b>opgave</b> 3&nbsp;a</p><br>Tot ziens",
    },
    {
        "Id": 2,
        "Start": "2026-11-10T00:00:00.0000000Z",
        "Einde": "2026-11-11T00:00:00.0000000Z",
        "DuurtHeleDag": True,
        "Omschrijving": "Studiedag",
        "Status": 5,
        "Type": 1,
    },
]


def mock_data(mocked: aioresponses, parent: bool = True) -> None:
    """Register the data API responses."""
    groups = [{"Naam": "Ouder"}] if parent else [{"Naam": "Leerling"}]
    mocked.get(
        f"{BASE}/api/account",
        payload={
            "Persoon": {"Id": 7, "Roepnaam": "Pieter", "Achternaam": "Echt"},
            "Groep": groups,
        },
        repeat=True,
    )
    mocked.get(
        f"{BASE}/api/personen/7/kinderen",
        payload={"Items": [{"Id": 11, "Roepnaam": "Anna", "Achternaam": "Echt"}]},
    )
    mocked.get(
        re.compile(rf"^{re.escape(BASE)}/api/personen/(11|7)/afspraken\?.*$"),
        payload={"Items": ITEMS},
        repeat=True,
    )


def test_parse_args_has_no_password_option() -> None:
    """The password can only be entered interactively."""
    args = cli.parse_args(["--tenant", "x", "--username", "u", "--dump", "out"])
    assert args.tenant == "x"
    assert args.dump == Path("out")
    assert not hasattr(args, "password")
    with pytest.raises(SystemExit):
        cli.parse_args(["--tenant", "x", "--username", "u", "--password", "p"])


def test_week_window_and_formatting() -> None:
    """The window starts on Monday local time; lines show raw codes."""
    start, end = cli.week_window(TZ, date(2026, 11, 11))
    assert start.isoformat() == "2026-11-09T00:00:00+01:00"
    assert (end - start).days == 7
    start, _ = cli.week_window(TZ, date(2026, 11, 11), offset_weeks=-1, weeks=4)
    assert start.date() == date(2026, 11, 2)

    line = cli.format_appointment(ITEMS[0], TZ)
    assert "08:30-09:20" in line
    assert "(uur 1)" in line
    assert "<status=1 info=1 type=13>" in line
    assert "Maak opgave 3 a" in line
    assert "hele dag" in cli.format_appointment(ITEMS[1], TZ)
    assert cli.html_to_text(None) == ""
    assert cli.person_name({"Id": 3}) == "person 3"


async def test_run_full_verification(
    mocked: aioresponses,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    """Login, agenda, silent renew and anonymized dump work end to end."""
    fake = FakeLogin(mocked)
    fake.silent_locations = [callback_url("renewed", 3600)]
    mock_data(mocked)
    args = cli.parse_args(
        ["--tenant", "school", "--username", "u", "--dump", str(tmp_path / "dump")]
    )

    assert await cli.run(args, PASSWORD, None) == 0
    out = capsys.readouterr().out
    assert "Parent account with 1 child(ren)" in out
    assert "Anna Echt" in out
    assert "Silent renew WORKED" in out
    assert TOKEN not in out
    assert PASSWORD not in out
    assert "renewed" not in out

    files = sorted(p.name for p in (tmp_path / "dump").iterdir())
    assert files == [
        "account.json",
        "appointments-kind-a-without-status-filter.json",
        "appointments-kind-a.json",
        "children.json",
        "observed-codes.json",
    ]
    dumped = "".join(p.read_text() for p in (tmp_path / "dump").iterdir())
    for secret in ("Anna", "Pieter", "Echt", "A. Docent", "ADO", HOST):
        assert secret not in dumped
    codes = json.loads((tmp_path / "dump" / "observed-codes.json").read_text())
    assert codes["Kind A"]["with_status_1"]["Status"] == {"1": 1, "5": 1}


async def test_run_student_and_silent_fallback(
    mocked: aioresponses, capsys: pytest.CaptureFixture[str]
) -> None:
    """A student account shows its own agenda; a failed silent renew is reported."""
    fake = FakeLogin(
        mocked,
        challenges=[
            {"action": "username"},
            {"action": "password"},
            {"redirectURL": RETURN_URL},
        ]
        * 2,
    )
    mock_data(mocked, parent=False)
    args = cli.parse_args(["--tenant", HOST, "--username", "u"])
    assert await cli.run(args, PASSWORD, None) == 0
    out = capsys.readouterr().out
    assert "Not a parent account" in out
    assert "Silent renew did NOT work (reason: login_required)" in out
    assert [step for step, _, _ in fake.posts].count("password") <= 2


async def test_run_empty_week(
    mocked: aioresponses, capsys: pytest.CaptureFixture[str]
) -> None:
    """An empty agenda is reported."""
    fake = FakeLogin(mocked)
    fake.silent_locations = [callback_url("renewed", 3600)]
    mocked.get(
        f"{BASE}/api/account",
        payload={"Persoon": {"Id": 7}, "Groep": [{"Naam": "Leerling"}]},
        repeat=True,
    )
    mocked.get(
        re.compile(rf"^{re.escape(BASE)}/api/personen/7/afspraken\?.*$"),
        payload={"Items": []},
    )
    args = cli.parse_args(["--tenant", HOST, "--username", "u"])
    assert await cli.run(args, PASSWORD, None) == 0
    assert "no appointments this week" in capsys.readouterr().out


async def test_run_error_exit_codes(
    mocked: aioresponses, capsys: pytest.CaptureFixture[str]
) -> None:
    """Auth, API and connection errors give distinct exit codes and messages."""
    FakeLogin(
        mocked,
        challenges=[
            {"action": "username"},
            {"action": "password"},
            {"error": "InvalidPassword"},
        ],
    )
    args = cli.parse_args(["--tenant", HOST, "--username", "u"])
    assert await cli.run(args, PASSWORD, None) == 1
    err_text = capsys.readouterr().err
    assert "LOGIN FAILED (invalid_auth)" in err_text
    assert "server error: InvalidPassword" in err_text

    assert (
        await cli.run(
            cli.parse_args(["--tenant", "evil.example.com", "--username", "u"]),
            "p",
            None,
        )
        == 2
    )

    mocked.clear()
    mocked.get(f"{BASE}/oidc_config.js", status=500)
    assert await cli.run(args, PASSWORD, None) == 3
    assert "CONNECTION PROBLEM" in capsys.readouterr().err

    mocked.clear()
    mocked.get(f"{BASE}/oidc_config.js", status=404)
    assert await cli.run(args, PASSWORD, None) == 4
    assert "HTTP 404" in capsys.readouterr().err


def test_main_reads_password_and_totp_env(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """main() prompts via getpass and validates the TOTP env var."""
    calls: dict[str, object] = {}

    async def fake_run(args: object, password: str, totp: str | None) -> int:
        calls["password"] = password
        calls["totp"] = totp
        return 0

    monkeypatch.setattr(cli, "run", fake_run)
    monkeypatch.setattr(cli.getpass, "getpass", lambda prompt: "typed-secret")
    monkeypatch.setenv("MY_TOTP", "JBSWY3DPEHPK3PXP")
    argv = ["--tenant", "s", "--username", "u", "--totp-secret-env", "MY_TOTP"]
    assert cli.main(argv) == 0
    assert calls == {"password": "typed-secret", "totp": "JBSWY3DPEHPK3PXP"}

    monkeypatch.delenv("MY_TOTP")
    assert cli.main(argv) == 2
    assert "MY_TOTP" in capsys.readouterr().err

    monkeypatch.setattr(cli.getpass, "getpass", lambda prompt: "")
    assert cli.main(["--tenant", "s", "--username", "u"]) == 2

    answers = iter(["jbsw y3dp", "typed-secret"])
    monkeypatch.setattr(cli.getpass, "getpass", lambda prompt: next(answers))
    assert cli.main(["--tenant", "s", "--username", "u", "--totp-prompt"]) == 0
    assert calls["totp"] == "jbsw y3dp"
    monkeypatch.setattr(cli.getpass, "getpass", lambda prompt: "")
    assert cli.main(["--tenant", "s", "--username", "u", "--totp-prompt"]) == 2


def test_api_loads_without_homeassistant() -> None:
    """The CLI loads the api package standalone (no custom_components.magister)."""
    assert cli._api.__name__ == "magister_api"
    assert aiohttp  # imported


async def test_forced_refresh_skipped_after_two_password_submissions(
    mocked: aioresponses, capsys: pytest.CaptureFixture[str]
) -> None:
    """If a 401 already cost a second login, step 4 does not log in a third time."""
    login = [
        {"action": "username"},
        {"action": "password"},
        {"redirectURL": RETURN_URL},
    ]
    fake = FakeLogin(mocked, challenges=login * 3)
    mocked.get(f"{BASE}/api/account", status=401)
    mocked.get(
        f"{BASE}/api/account",
        payload={"Persoon": {"Id": 7}, "Groep": [{"Naam": "Leerling"}]},
        repeat=True,
    )
    mocked.get(
        re.compile(rf"^{re.escape(BASE)}/api/personen/7/afspraken\?.*$"),
        payload={"Items": []},
    )
    args = cli.parse_args(["--tenant", HOST, "--username", "u"])
    assert await cli.run(args, PASSWORD, None) == 0
    out = capsys.readouterr().out
    assert "Skipped" in out
    assert [s for s, _, _ in fake.posts].count("password") == 2
