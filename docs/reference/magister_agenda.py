#!/usr/bin/env python3
"""Haal de Magister-agenda van de huidige week op en exporteer die naar .ics (en optioneel .json).

Werking (zie README-regels onderaan voor wat wel/niet geverifieerd is):

1. Inloggen: een echte Chromium-browser (Playwright) opent https://<tenant>.magister.net/magister/.
   Jij logt zelf in (wachtwoord, wachtwoordsleutel, 2FA: alles wat Magister aanbiedt). De sessie
   wordt bewaard in een eigen browserprofiel, zodat volgende runs headless en zonder login werken.
   Het script leest daarna het access-token uit sessionStorage, precies zoals de Magister-webapp
   het zelf bewaart (sleutel ``oidc.user:https://accounts.magister.net:M6-<tenant>``).
   Het token wordt nooit geprint of naar schijf geschreven. Wachtwoorden komen niet in dit script.
2. Agenda: GET /api/account -> bij een ouderaccount GET /api/personen/<ouderId>/kinderen ->
   GET /api/personen/<persoonId>/afspraken?status=1&van=<UTC>&tot=<UTC>
3. Export: een .ics per persoon (stabiele UID's, dus opnieuw importeren werkt bij i.p.v. dupliceert).
"""
from __future__ import annotations

import argparse
import html
import json
import os
import re
import sys
import time
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from datetime import time as dtime
from pathlib import Path
from zoneinfo import ZoneInfo

import requests

TZ = ZoneInfo("Europe/Amsterdam")
PROFILE_DIR = Path.home() / ".cache" / "magister-agenda" / "profile"
DAGEN = ["ma", "di", "wo", "do", "vr", "za", "zo"]


# --------------------------------------------------------------------------- inloggen
def normalize_host(tenant: str) -> str:
    """'myschool' -> 'myschool.magister.net'; volledige hostnaam of URL wordt ook geaccepteerd."""
    tenant = tenant.strip().lower()
    tenant = re.sub(r"^https?://", "", tenant).split("/")[0]
    return tenant if "." in tenant else f"{tenant}.magister.net"


def token_storage_key(host: str) -> str:
    return f"oidc.user:https://accounts.magister.net:M6-{host}"


def parse_stored_token(raw: str | None, now: float | None = None) -> str | None:
    """Geef het access_token uit de oidc-user JSON terug, of None als het ontbreekt/verlopen is."""
    if not raw:
        return None
    try:
        data = json.loads(raw)
        token = data["access_token"]
        expires_at = float(data.get("expires_at", 0))
    except (ValueError, KeyError, TypeError):
        return None
    if expires_at <= (now if now is not None else time.time()) + 30:
        return None
    return token


def _wait_for_token(host: str, headless: bool, timeout: float) -> str | None:
    from playwright.sync_api import Error as PlaywrightError
    from playwright.sync_api import sync_playwright

    PROFILE_DIR.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        ctx = p.chromium.launch_persistent_context(str(PROFILE_DIR), headless=headless)
        try:
            page = ctx.pages[0] if ctx.pages else ctx.new_page()
            page.goto(f"https://{host}/magister/")
            key = token_storage_key(host)
            deadline = time.monotonic() + timeout
            while time.monotonic() < deadline:
                try:
                    raw = page.evaluate("k => window.sessionStorage.getItem(k)", key)
                except PlaywrightError:  # pagina is net aan het navigeren
                    raw = None
                token = parse_stored_token(raw)
                if token:
                    return token
                page.wait_for_timeout(500)
            return None
        finally:
            ctx.close()


def get_token(host: str, show_browser: bool = False) -> str:
    """Eerst stil (headless) met de bewaarde sessie; lukt dat niet, dan een zichtbaar venster."""
    if not show_browser:
        token = _wait_for_token(host, headless=True, timeout=20)
        if token:
            return token
    print("Log in in het browservenster dat opent (je hebt 5 minuten)...", file=sys.stderr)
    token = _wait_for_token(host, headless=False, timeout=300)
    if not token:
        raise SystemExit("Geen geldige Magister-sessie gevonden (time-out bij inloggen).")
    return token


# --------------------------------------------------------------------------- API
class MagisterClient:
    def __init__(self, host: str, token: str, base_url: str | None = None):
        self.base = base_url or f"https://{host}"
        self.session = requests.Session()
        self.session.headers.update(
            {
                "Authorization": f"Bearer {token}",
                "Accept": "application/json",
                "User-Agent": "magister-agenda/1.0",
            }
        )

    def get(self, path: str, **params):
        resp = self.session.get(self.base + path, params=params or None, timeout=30)
        resp.raise_for_status()
        return resp.json()


def person_name(p: dict) -> str:
    first = p.get("Roepnaam") or p.get("Voorletters") or ""
    parts = [first, p.get("Tussenvoegsel") or "", p.get("Achternaam") or ""]
    return " ".join(x for x in parts if x).strip() or f"persoon {p.get('Id')}"


def list_targets(client: MagisterClient) -> list[tuple[int, str]]:
    """Personen waarvan de agenda opgehaald wordt: de kinderen bij een ouderaccount, anders jezelf."""
    account = client.get("/api/account")
    me = account["Persoon"]
    groups = [g.get("Naam") for g in account.get("Groep", [])]
    if "Ouder" in groups:
        kids = client.get(f"/api/personen/{me['Id']}/kinderen").get("Items", [])
        return [(k["Id"], person_name(k)) for k in kids]
    return [(me["Id"], person_name(me))]


def week_window(today: date | None = None, offset: int = 0, days: int = 5) -> tuple[datetime, datetime]:
    """[ma 00:00, za 00:00) lokale tijd (Europe/Amsterdam), teruggegeven als UTC-datetimes."""
    today = today or datetime.now(TZ).date()
    monday = today - timedelta(days=today.weekday()) + timedelta(weeks=offset)
    start = datetime.combine(monday, dtime.min, tzinfo=TZ)
    end = start + timedelta(days=days)  # wandkloktijd-rekenen: klopt ook rond zomer/wintertijd
    return start.astimezone(timezone.utc), end.astimezone(timezone.utc)


def api_ts(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")


def fetch_appointments(client: MagisterClient, person_id: int, van: datetime, tot: datetime) -> list[dict]:
    data = client.get(f"/api/personen/{person_id}/afspraken", status=1, van=api_ts(van), tot=api_ts(tot))
    return data.get("Items", [])


# --------------------------------------------------------------------------- model
_TS = re.compile(r"^(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})(?:\.\d+)?Z$")


def parse_dt(value: str) -> datetime:
    m = _TS.match(value)
    if not m:
        raise ValueError(f"Onverwacht tijdformaat: {value!r}")
    return datetime.strptime(m.group(1), "%Y-%m-%dT%H:%M:%S").replace(tzinfo=timezone.utc)


def html_to_text(src: str | None) -> str:
    if not src:
        return ""
    src = re.sub(r"(?i)<br\s*/?>|</p>|</li>|</div>", "\n", src)
    src = re.sub(r"<[^>]+>", "", src)
    src = html.unescape(src).replace("\xa0", " ")
    return "\n".join(line.strip() for line in src.splitlines()).strip()


@dataclass
class Event:
    id: int
    start: datetime
    end: datetime
    all_day: bool
    title: str
    location: str
    teachers: list[str]
    period: int | None
    status: int | None
    omschrijving: str
    notes: str = ""
    raw: dict = field(default_factory=dict, repr=False)


def to_event(item: dict) -> Event:
    vakken = ", ".join(v["Naam"] for v in item.get("Vakken") or [] if v.get("Naam"))
    omschrijving = item.get("Omschrijving") or ""
    return Event(
        id=item["Id"],
        start=parse_dt(item["Start"]),
        end=parse_dt(item["Einde"]),
        all_day=bool(item.get("DuurtHeleDag")),
        title=vakken or omschrijving or "Afspraak",
        location=item.get("Lokatie") or ", ".join(l["Naam"] for l in item.get("Lokalen") or []),
        teachers=[d["Naam"] for d in item.get("Docenten") or [] if d.get("Naam")],
        period=item.get("LesuurVan"),
        status=item.get("Status"),
        omschrijving=omschrijving,
        notes=html_to_text(item.get("Inhoud")),
        raw=item,
    )


# --------------------------------------------------------------------------- export
def ics_escape(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    return text.replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\n", "\\n")


def fold(line: str) -> str:
    """Vouw regels op 75 octets (RFC 5545), zonder UTF-8-tekens te splitsen."""
    b = line.encode("utf-8")
    out = []
    while len(b) > 75:
        cut = 75
        while (b[cut] & 0xC0) == 0x80:
            cut -= 1
        out.append(b[:cut].decode("utf-8"))
        b = b" " + b[cut:]
    out.append(b.decode("utf-8"))
    return "\r\n".join(out)


def _utc_stamp(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def build_ics(events: list[Event], host: str, calname: str, now: datetime | None = None) -> str:
    stamp = _utc_stamp(now or datetime.now(timezone.utc))
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//magister-agenda//NL",
        "CALSCALE:GREGORIAN",
        f"X-WR-CALNAME:{ics_escape(calname)}",
    ]
    for ev in events:
        desc = []
        if ev.period:
            desc.append(f"Lesuur {ev.period}")
        if ev.omschrijving:
            desc.append(ev.omschrijving)
        if ev.teachers:
            desc.append("Docent(en): " + ", ".join(ev.teachers))
        if ev.notes:
            desc.append("")
            desc.append(ev.notes)
        lines += ["BEGIN:VEVENT", f"UID:magister-{ev.id}@{host}", f"DTSTAMP:{stamp}"]
        if ev.all_day:
            s = ev.start.astimezone(TZ)
            e = ev.end.astimezone(TZ)
            end_date = e.date() if e.time() == dtime.min else e.date() + timedelta(days=1)
            if end_date <= s.date():
                end_date = s.date() + timedelta(days=1)
            lines += [f"DTSTART;VALUE=DATE:{s:%Y%m%d}", f"DTEND;VALUE=DATE:{end_date:%Y%m%d}"]
        else:
            lines += [f"DTSTART:{_utc_stamp(ev.start)}", f"DTEND:{_utc_stamp(ev.end)}"]
        lines.append(f"SUMMARY:{ics_escape(ev.title)}")
        if ev.location:
            lines.append(f"LOCATION:{ics_escape(ev.location)}")
        if desc:
            lines.append(f"DESCRIPTION:{ics_escape(chr(10).join(desc))}")
        lines.append("END:VEVENT")
    lines.append("END:VCALENDAR")
    return "\r\n".join(fold(l) for l in lines) + "\r\n"


def print_week(name: str, events: list[Event]) -> None:
    print(f"\n=== {name} ===")
    if not events:
        print("(geen afspraken in deze periode)")
        return
    current = None
    for ev in events:
        s, e = ev.start.astimezone(TZ), ev.end.astimezone(TZ)
        if s.date() != current:
            current = s.date()
            print(f"\n{DAGEN[s.weekday()]} {s:%d-%m-%Y}")
        when = "hele dag" if ev.all_day else f"{s:%H:%M}-{e:%H:%M}"
        uur = f" (uur {ev.period})" if ev.period else ""
        extra = " · ".join(x for x in [ev.location, ", ".join(ev.teachers)] if x)
        print(f"  {when}{uur}  {ev.title}" + (f"  [{extra}]" if extra else ""))
        if ev.notes:
            print("      " + ev.notes.replace("\n", "\n      "))


def slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-") or "agenda"


# --------------------------------------------------------------------------- main
def parse_args(argv=None):
    ap = argparse.ArgumentParser(description="Importeer de Magister-agenda van de huidige week.")
    ap.add_argument("--tenant", default=os.environ.get("MAGISTER_TENANT"), help="bijv. 'myschool' of 'myschool.magister.net' (of env MAGISTER_TENANT)")
    ap.add_argument("--week-offset", type=int, default=0, help="0 = deze week, 1 = volgende week, -1 = vorige week")
    ap.add_argument("--days", type=int, default=5, help="aantal dagen vanaf maandag (5 = schoolweek, 7 = hele week)")
    ap.add_argument("--child", help="filter op (deel van de) naam van een kind (ouderaccount)")
    ap.add_argument("--out-dir", type=Path, default=Path("."), help="map voor .ics/.json bestanden")
    ap.add_argument("--json", action="store_true", help="schrijf ook de ruwe API-respons als .json")
    ap.add_argument("--show-browser", action="store_true", help="forceer een zichtbaar browservenster voor het inloggen")
    args = ap.parse_args(argv)
    if not args.tenant:
        ap.error("--tenant ontbreekt (of zet MAGISTER_TENANT)")
    return args


def main(argv=None) -> int:
    args = parse_args(argv)
    host = normalize_host(args.tenant)
    van, tot = week_window(offset=args.week_offset, days=args.days)
    token = get_token(host, args.show_browser)
    client = MagisterClient(host, token)

    try:
        targets = list_targets(client)
        if args.child:
            targets = [t for t in targets if args.child.lower() in t[1].lower()]
        if not targets:
            print("Geen passende personen gevonden.", file=sys.stderr)
            return 1
        args.out_dir.mkdir(parents=True, exist_ok=True)
        monday = van.astimezone(TZ).date()
        for pid, name in targets:
            items = fetch_appointments(client, pid, van, tot)
            events = sorted((to_event(i) for i in items), key=lambda e: (e.start, e.id))
            print_week(name, events)
            base = args.out_dir / f"magister-{slug(name)}-{monday:%Y-%m-%d}"
            base.with_suffix(".ics").write_text(build_ics(events, host, f"Magister {name}"), encoding="utf-8", newline="")
            written = [base.with_suffix(".ics")]
            if args.json:
                base.with_suffix(".json").write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")
                written.append(base.with_suffix(".json"))
            print("\nGeschreven: " + ", ".join(str(w) for w in written))
    except requests.HTTPError as exc:
        print(f"Magister gaf HTTP {exc.response.status_code} op {exc.request.url.split('?')[0]}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
