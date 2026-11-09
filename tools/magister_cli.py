#!/usr/bin/env python3
"""Verify the Magister login and agenda from the command line (PM verification tool).

See ``tools/README.md`` for step-by-step instructions. Short version, from the
repository root, in Terminal (macOS/Linux) or PowerShell / cmd (Windows; NOT Git Bash or
mintty, where the hidden password prompt does not work)::

    python3 -m venv .venv-magister
    .venv-magister/bin/pip install aiohttp pyotp
    .venv-magister/bin/python tools/magister_cli.py \\
        --tenant myschool --username me --dump dump1

(Windows: ``.venv-magister\\Scripts\\pip`` / ``...\\Scripts\\python``.)

Only ``aiohttp`` and ``pyotp`` are needed (Home Assistant is not). On Windows also run
``pip install tzdata``.

The password is always asked with hidden input (there is no password option). For a 2FA
account use ``--totp-prompt`` (hidden input) or ``--totp-secret-env VAR``.

Output, in four steps: (1) login, (2) account type and children, (3) this week's agenda
per child with the raw Status/InfoType/Type codes, (4) a second token fetch with the
cache bypassed: "Silent renew WORKED" or "did NOT work ... a full login was used".
``--dump DIR`` additionally writes anonymized JSON; skim it before sharing.
"""

from __future__ import annotations

import argparse
import asyncio
import getpass
import html
import importlib.util
import json
import logging
import os
import re
import sys
from datetime import date, datetime, timedelta
from datetime import time as dtime
from pathlib import Path
from types import ModuleType
from typing import TYPE_CHECKING, Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import aiohttp

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.anonymize import Anonymizer, count_codes  # noqa: E402


def _load_api() -> ModuleType:
    """Import ``custom_components/magister/api`` without importing Home Assistant.

    The parent package ``custom_components.magister`` imports Home Assistant, so the
    pure-Python ``api`` package is loaded on its own under the name ``magister_api``.
    """
    api_dir = REPO_ROOT / "custom_components" / "magister" / "api"
    spec = importlib.util.spec_from_file_location(
        "magister_api",
        api_dir / "__init__.py",
        submodule_search_locations=[str(api_dir)],
    )
    if spec is None or spec.loader is None:  # pragma: no cover
        raise RuntimeError("Cannot load the Magister api package")
    module = importlib.util.module_from_spec(spec)
    sys.modules["magister_api"] = module
    spec.loader.exec_module(module)
    return module


if TYPE_CHECKING:
    from custom_components.magister.api import (
        MagisterApiError,
        MagisterAuth,
        MagisterAuthError,
        MagisterClient,
        MagisterConnectionError,
        normalize_host,
    )
    from custom_components.magister.api.utils import format_api_timestamp
else:
    _api = _load_api()
    MagisterApiError = _api.MagisterApiError
    MagisterAuth = _api.MagisterAuth
    MagisterAuthError = _api.MagisterAuthError
    MagisterClient = _api.MagisterClient
    MagisterConnectionError = _api.MagisterConnectionError
    normalize_host = _api.normalize_host
    format_api_timestamp = _api.utils.format_api_timestamp

MAX_PASSWORD_SUBMISSIONS = 2
DAYS = ["ma", "di", "wo", "do", "vr", "za", "zo"]
AUTH_HINTS = {
    "invalid_auth": "Wrong username or password (or the account is blocked).",
    "totp_required": "This account needs a TOTP secret: use --totp-prompt "
    "or --totp-secret-env.",
    "invalid_totp": "The TOTP code or secret was rejected.",
    "unsupported_login": "This login method (SSO / passkey) is not supported.",
}


def local_tz() -> ZoneInfo:
    """Europe/Amsterdam, with a helpful error when tz data is missing."""
    try:
        return ZoneInfo("Europe/Amsterdam")
    except ZoneInfoNotFoundError:  # pragma: no cover
        raise SystemExit(
            "Time zone data is missing. Install it with: pip install tzdata"
        ) from None


def week_window(
    tz: ZoneInfo, today: date | None = None, offset_weeks: int = 0, weeks: int = 1
) -> tuple[datetime, datetime]:
    """[Monday 00:00, Monday + ``weeks`` weeks) local time, as aware datetimes."""
    today = today or datetime.now(tz).date()
    monday = today - timedelta(days=today.weekday()) + timedelta(weeks=offset_weeks)
    start = datetime.combine(monday, dtime.min, tzinfo=tz)
    return start, start + timedelta(weeks=weeks)


def html_to_text(src: str | None) -> str:
    """Very small HTML to text conversion for homework text."""
    if not src:
        return ""
    src = re.sub(r"(?i)<br\s*/?>|</p>|</li>|</div>", "\n", src)
    src = re.sub(r"<[^>]+>", "", src)
    src = html.unescape(src).replace("\xa0", " ")
    return "\n".join(line.strip() for line in src.splitlines()).strip()


def format_appointment(item: dict[str, Any], tz: ZoneInfo) -> str:
    """One agenda line, including the raw Status/InfoType/Type codes."""
    start = datetime.fromisoformat(
        str(item["Start"]).replace("Z", "+00:00")
    ).astimezone(tz)
    end = datetime.fromisoformat(str(item["Einde"]).replace("Z", "+00:00")).astimezone(
        tz
    )
    subjects = ", ".join(v["Naam"] for v in item.get("Vakken") or [] if v.get("Naam"))
    title = subjects or item.get("Omschrijving") or "Afspraak"
    when = "hele dag" if item.get("DuurtHeleDag") else f"{start:%H:%M}-{end:%H:%M}"
    hour = f" (uur {item['LesuurVan']})" if item.get("LesuurVan") else ""
    codes = (
        f"status={item.get('Status')} info={item.get('InfoType')} "
        f"type={item.get('Type')}"
    )
    line = f"  {when}{hour}  {title}  <{codes}>"
    notes = html_to_text(item.get("Inhoud"))
    if notes:
        line += "\n      " + notes.replace("\n", "\n      ")
    return line


def print_week(name: str, items: list[dict[str, Any]], tz: ZoneInfo) -> None:
    """Print the agenda of one person."""
    print(f"\n=== {name} ===")
    if not items:
        print("  (no appointments this week)")
        return
    current: date | None = None
    for item in sorted(items, key=lambda i: (i["Start"], i["Id"])):
        start = datetime.fromisoformat(str(item["Start"]).replace("Z", "+00:00"))
        day = start.astimezone(tz).date()
        if day != current:
            current = day
            print(f"\n  {DAYS[day.weekday()]} {day:%d-%m-%Y}")
        print(format_appointment(item, tz))


def person_name(person: dict[str, Any]) -> str:
    """Display name from a raw person object."""
    first = person.get("Roepnaam") or person.get("Voorletters") or ""
    parts = [first, person.get("Tussenvoegsel") or "", person.get("Achternaam") or ""]
    return " ".join(p for p in parts if p) or f"person {person.get('Id')}"


async def verify(
    client: Any,
    auth: Any,
    host: str,
    dump_dir: Path | None,
    tz: ZoneInfo,
    today: date | None = None,
) -> int:
    """Run the verification steps against a logged-in client."""
    print("[1/4] Logging in ...")
    await auth.async_get_token()
    print(f"      OK via {auth.last_token_source}")

    print("[2/4] Account and children ...")
    account = await client.async_get_raw("/api/account")
    me = account["Persoon"]
    groups = [g.get("Naam") for g in account.get("Groep") or []]
    is_parent = "Ouder" in groups
    group_text = ", ".join(map(str, groups)) or "-"
    print(f"      Account: {person_name(me)} - groups: {group_text}")
    if is_parent:
        kids = (await client.async_get_raw(f"/api/personen/{me['Id']}/kinderen")).get(
            "Items", []
        )
        print(f"      Parent account with {len(kids)} child(ren)")
        children_raw = {"Items": kids}
        targets = [(k["Id"], person_name(k)) for k in kids]
    else:
        print("      Not a parent account: showing your own agenda")
        children_raw = {"Items": []}
        targets = [(me["Id"], person_name(me))]
    for _, name in targets:
        print(f"        - {name}")

    print("[3/4] This week's agenda ...")
    week_start, week_end = week_window(tz, today)
    for person_id, name in targets:
        data = await client.async_get_raw(
            f"/api/personen/{person_id}/afspraken",
            {
                "status": "1",
                "van": format_api_timestamp(week_start),
                "tot": format_api_timestamp(week_end),
            },
        )
        print_week(name, data.get("Items", []), tz)

    print("\n[4/4] Second token fetch (cache bypassed) ...")
    if auth.password_submissions >= MAX_PASSWORD_SUBMISSIONS:
        print(
            f"      Skipped: the password was already sent "
            f"{auth.password_submissions} times in this run (never more than "
            f"{MAX_PASSWORD_SUBMISSIONS})."
        )
        return await _finish(
            client, dump_dir, host, account, children_raw, targets, tz, today
        )
    await auth.async_get_token(force_refresh=True)
    if auth.last_token_source == "silent":
        print("      Silent renew WORKED (no new login needed).")
    else:
        reason = auth.last_silent_failure or "n/a"
        print(
            f"      Silent renew did NOT work (reason: {reason}); "
            "a full login was used instead."
        )
    await client.async_get_raw("/api/account")
    print("      The new token works.")
    return await _finish(
        client, dump_dir, host, account, children_raw, targets, tz, today
    )


async def _finish(
    client: Any,
    dump_dir: Path | None,
    host: str,
    account: dict[str, Any],
    children_raw: dict[str, Any],
    targets: list[tuple[int, str]],
    tz: ZoneInfo,
    today: date | None,
) -> int:
    """Write the anonymized dump when requested."""
    if dump_dir is not None:
        files = await collect_dump(
            client, host, account, children_raw, targets, tz, today
        )
        write_dump(dump_dir, files)
    return 0


async def collect_dump(
    client: Any,
    host: str,
    account: dict[str, Any],
    children_raw: dict[str, Any],
    targets: list[tuple[int, str]],
    tz: ZoneInfo,
    today: date | None = None,
) -> dict[str, Any]:
    """Fetch -1..+3 weeks per child and return ``{file name: anonymized data}``."""
    anon = Anonymizer(host)
    start, end = week_window(tz, today, offset_weeks=-1, weeks=4)
    base = {"van": format_api_timestamp(start), "tot": format_api_timestamp(end)}
    raw: dict[int, tuple[dict[str, Any], dict[str, Any]]] = {}
    for person_id, _ in targets:
        path = f"/api/personen/{person_id}/afspraken"
        filtered = await client.async_get_raw(path, {**base, "status": "1"})
        unfiltered = await client.async_get_raw(path, base)
        raw[person_id] = (filtered, unfiltered)

    # Pass 1: learn every name and teacher code before anything is written.
    anon.collect(account)
    anon.collect(children_raw)
    for filtered, unfiltered in raw.values():
        anon.collect(filtered)
        anon.collect(unfiltered)

    # Pass 2: anonymize.
    files: dict[str, Any] = {
        "account.json": anon.account(account),
        "children.json": anon.children(children_raw),
    }
    summary: dict[str, Any] = {}
    for person_id, (filtered, unfiltered) in raw.items():
        label = anon.person_label(person_id)
        slug = label.lower().replace(" ", "-")
        files[f"appointments-{slug}.json"] = anon.appointments(filtered)
        files[f"appointments-{slug}-without-status-filter.json"] = anon.appointments(
            unfiltered
        )
        summary[label] = {
            "with_status_1": _code_counts(filtered),
            "without_status_filter": _code_counts(unfiltered),
        }
    files["observed-codes.json"] = summary
    return files


def write_dump(out_dir: Path, files: dict[str, Any]) -> None:
    """Write the dump files and tell the user what to do with them."""
    out_dir.mkdir(parents=True, exist_ok=True)
    print(f"\nAnonymized dump written to {out_dir}:")
    for name, data in files.items():
        (out_dir / name).write_text(
            json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(f"  - {name}")
    print("Counts of Status/InfoType/Type codes (with and without status filter):")
    print(json.dumps(files["observed-codes.json"], indent=2))
    print("Please skim the files for real names before sharing them.")


def _code_counts(data: dict[str, Any]) -> dict[str, Any]:
    items = data.get("Items", [])
    return {
        "items": len(items),
        "Status": count_codes(items, "Status"),
        "InfoType": count_codes(items, "InfoType"),
        "Type": count_codes(items, "Type"),
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse command-line arguments (there is deliberately no password option)."""
    parser = argparse.ArgumentParser(description="Check Magister login and agenda.")
    parser.add_argument(
        "--tenant",
        required=True,
        help="school, e.g. 'myschool' or 'myschool.magister.net'",
    )
    parser.add_argument("--username", required=True)
    parser.add_argument(
        "--totp-prompt",
        action="store_true",
        help="ask for the base32 TOTP secret with hidden input",
    )
    parser.add_argument(
        "--totp-secret-env",
        metavar="VAR",
        help="name of an environment variable holding the base32 TOTP secret",
    )
    parser.add_argument(
        "--dump", metavar="DIR", type=Path, help="write anonymized JSON to DIR"
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="debug logging (contains no secrets)",
    )
    return parser.parse_args(argv)


async def run(args: argparse.Namespace, password: str, totp_secret: str | None) -> int:
    """Log in and run the verification; map errors to exit codes."""
    try:
        host = normalize_host(args.tenant)
    except ValueError:
        print("The tenant must be a *.magister.net school name.", file=sys.stderr)
        return 2
    tz = local_tz()
    async with aiohttp.ClientSession(cookie_jar=aiohttp.CookieJar()) as session:
        auth = MagisterAuth(session, host, args.username, password, totp_secret)
        client = MagisterClient(session, auth, host)
        try:
            return await verify(client, auth, host, args.dump, tz)
        except MagisterAuthError as err:
            server = f" [server error: {err.server_error}]" if err.server_error else ""
            print(
                f"\nLOGIN FAILED ({err.code}){server}: {AUTH_HINTS.get(err.code, err)}",
                file=sys.stderr,
            )
            return 1
        except MagisterConnectionError as err:
            print(f"\nCONNECTION PROBLEM: {err}", file=sys.stderr)
            return 3
        except MagisterApiError as err:
            status = f" (HTTP {err.status})" if err.status else ""
            print(f"\nMAGISTER ERROR{status}: {err}", file=sys.stderr)
            return 4


def main(argv: list[str] | None = None) -> int:
    """Entry point."""
    args = parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.WARNING,
        format="%(levelname)s %(name)s: %(message)s",
    )
    totp_secret = None
    if args.totp_secret_env:
        totp_secret = os.environ.get(args.totp_secret_env)
        if not totp_secret:
            print(
                f"Environment variable {args.totp_secret_env} is empty or not set.",
                file=sys.stderr,
            )
            return 2
    if args.totp_prompt and not totp_secret:
        totp_secret = getpass.getpass("TOTP secret (base32, hidden): ").strip() or None
        if not totp_secret:
            print("No TOTP secret entered.", file=sys.stderr)
            return 2
    password = getpass.getpass(f"Magister password for {args.username}: ")
    if not password:
        print("No password entered.", file=sys.stderr)
        return 2
    return asyncio.run(run(args, password, totp_secret))


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
