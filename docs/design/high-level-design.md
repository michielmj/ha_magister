# Magister for Home Assistant — High-Level Design

| | |
|---|---|
| Status | **Approved by PM (2026-11-09)** |
| Date | 2026-11-09 |
| Owner | Architect (Claude) · Product: PM |

## 1. Goal

A Home Assistant (HA) custom integration that downloads the agenda of one or more
children, from one or more schools (Magister *tenants*), and keeps **one HA calendar
per tenant–child combination** up to date.

## 2. Requirements (outcome of the PM survey, 2026-11-09)

| # | Topic | Decision |
|---|---|---|
| R1 | Login | Unattended login with **username + password**, plus an **optional TOTP secret** for 2FA accounts. Plain HTTP, no browser. |
| R2 | Setup model | **UI config flow, one config entry per Magister login** (tenant + account). Children are discovered automatically; the user selects which get a calendar. Several logins/schools = several entries. |
| R3 | Content | All agenda items: **lessons**, **homework & tests**, **cancelled/changed lessons**, **personal & school events**. |
| R4 | Scope v1 | **Calendars**, plus (added 2026-11-13) user-defined **first-appointment sensors** per child: day offset, excluded subjects, created as config sub-entries (M3). Other sensors and change events go to the backlog. |
| R5 | Sync | Window **1 week back to 3 weeks ahead**, refreshed **every 30 min**. Both can be changed in the options. |
| R6 | Cancelled lessons | **Kept in the calendar, title prefixed** (e.g. `[Vervallen] Wiskunde`). |
| R7 | Distribution | **HACS custom repository**, UI translations **NL + EN**. Event texts come from Magister (Dutch). |
| R8 | Quality | **pytest + pytest-homeassistant-custom-component**, mocked Magister API, GitHub Actions running tests, ruff, hassfest and HACS validation. |

Non-goals for v1: grades, absences, messages, sensors, notifications, writing back to
Magister (e.g. marking homework done), student and teacher accounts beyond "self".

## 3. Context and key risk: authentication

The reference script (`docs/reference/magister_agenda.py`) shows the data API, which is
simple and Bearer-token based:

```
GET /api/account                                   -> Persoon.Id, Groep[] ("Ouder"?)
GET /api/personen/{ouderId}/kinderen               -> Items[] (children)
GET /api/personen/{persoonId}/afspraken?van=<UTC>&tot=<UTC>      (NO status filter, see §7)
```

The **hard part is getting the token**. Magister uses OpenID Connect at
`accounts.magister.net` with client `M6-<tenant>.magister.net` and an implicit-style
flow (`response_type=id_token token`). Access tokens last about 1 hour and **no refresh
token** is issued to this client. The integration therefore replays the web login with
HTTP requests, the way community libraries do (magister.js, Magister-Python ports):

1. Read the tenant's OIDC settings, then start `/connect/authorize`. This leads to
   `/account/login?sessionId=…&returnUrl=…` and sets an `XSRF-TOKEN` cookie.
2. Run the challenge sequence: `POST /challenges/current` → `/challenges/username`
   → `/challenges/password` → (TOTP challenge if 2FA). Requests carry `sessionId`,
   `returnUrl` and an **`authCode`**, which Magister embeds in its login JavaScript
   bundle. That value changes over time and must be scraped dynamically.
3. Follow `returnUrl`. The redirect fragment contains `access_token` and `expires_in`.
4. **Silent renew:** with the `accounts.magister.net` session cookies kept,
   `/connect/authorize?prompt=none` returns a fresh token without re-entering
   credentials. If that fails, do a full login (step 1).

Consequences:
- The flow is **undocumented and may change**. It is isolated in one module (`auth.py`)
  with clear error types, so a Magister change means one targeted fix.
- **Milestone 1 is a feasibility spike** against the PM's real account(s). Developers
  have no Magister credentials, so the PM verifies with a CLI harness.
- Login methods we do **not** support in v1: school SSO (Entree/Microsoft/Google
  federated login) and passkeys. A tenant/account that requires these fails setup with
  a clear message. *(Flagged in §10.)*

## 4. Architecture

```
custom_components/magister/
├── __init__.py          setup/unload entry, create coordinator, forward to calendar
├── manifest.json        domain "magister", iot_class cloud_polling, config_flow true
├── const.py             domain, defaults (window -1/+3 weeks, 30 min), option keys
├── config_flow.py       user step → children step; options flow; reauth flow
├── coordinator.py       DataUpdateCoordinator per config entry
├── calendar.py          MagisterCalendarEntity per selected child
├── entity.py            shared device info (device per child)
├── diagnostics.py       config-entry diagnostics with redaction
├── strings.json / translations/en.json / translations/nl.json
└── api/                 ← pure Python, NO homeassistant imports
    ├── __init__.py
    ├── auth.py          MagisterAuth: login, TOTP, silent renew, token cache
    ├── client.py        MagisterClient: account, children, appointments
    ├── models.py        Person, Appointment (dataclasses) + parsing
    ├── mapping.py       Appointment → calendar fields (title/prefix/description)
    └── errors.py        MagisterAuthError, MagisterConnectionError, MagisterApiError
tests/                   pytest-homeassistant-custom-component + aioresponses
tools/magister_cli.py    dev harness: log in, list children, dump a week (PM verification)
```

Design rules:
- **`api/` has no HA dependency.** It uses `aiohttp` and receives the session from HA
  (`async_create_clientsession` with its own cookie jar per entry). Unit-testable on its
  own, and could later be published to PyPI.
- **Async only.** No `requests`, no Playwright, no blocking I/O in the event loop.
- TOTP codes are generated with `pyotp` (the only extra requirement in the manifest).

### 4.1 Data flow

```
Config entry (tenant, username, password, totp_secret?)
   │  options: children[], weeks_back, weeks_ahead, scan_interval
   ▼
MagisterCoordinator (every 30 min)
   ├─ auth.ensure_token()        silent renew → full login → MagisterAuthError
   ├─ client.get_appointments(child, van, tot)   for each selected child, sequential
   └─ data = {child_id: [Appointment…]}          (whole window, sorted)
   ▼
MagisterCalendarEntity (one per child)
   ├─ event                → current or next event from coordinator data
   └─ async_get_events()   → events in [start, end] from coordinator data
```

Ranges the calendar card asks for outside the sync window return only the cached data
(no on-demand fetch in v1). This keeps API load predictable. It can be added later if needed.

## 5. Configuration UX

**Step 1 — Account:** school (`myschool`, `myschool.magister.net` or a URL; normalized to a host),
username, password, TOTP secret (optional; base32 secret from the authenticator setup).
Credentials are validated with a real login. Errors: `invalid_auth`, `totp_required`,
`invalid_totp`, `cannot_connect`, `unsupported_login` (SSO), `unknown`.

**Step 2 — Children:** multi-select of the children found (`Roepnaam Achternaam`),
all selected by default. For a non-parent (student) account, step 2 is skipped and
the account holder is the only "child".

**Entry:** title `Magister <tenant> (<account name>)`, `unique_id = "<host>:<accountPersonId>"`
(prevents duplicates).

**Options flow:** children selection, weeks back (0–8, default 1), weeks ahead
(1–12, default 3), refresh interval in minutes (15–360, default 30).

**Reauth flow:** triggered by `ConfigEntryAuthFailed` (password changed, TOTP
invalid). Asks for password (+ TOTP secret) again.

## 6. Entities

| Item | Value |
|---|---|
| Device | one per child: name `<Roepnaam> (<school prefix>)`, manufacturer "Magister", entry_type service |
| Entity | `calendar.<roepnaam>_<school prefix>_agenda` (has_entity_name with translation key; name "Agenda"). `event`/state skips cancelled items (Architect decision, M2 review); `async_get_events` includes them |
| unique_id | `<host>:<childPersonId>` — stable across renames and re-setup |

Removing a child in the options removes its entity/device (registry cleanup).

## 7. Event mapping

| Calendar field | Source |
|---|---|
| uid | `magister-<Id>@<host>` (same scheme as the reference script) |
| start/end | `Start`/`Einde` (UTC). All-day when `DuurtHeleDag` → date-only event (end exclusive) |
| summary | `<prefix><subject>` where subject = `Vakken[].Naam` → first `" - "` segment of `Omschrijving` (e.g. `wisB`, `SE NAT`, `Schoolfotograaf`) → "Afspraak". Some schools leave `Vakken` empty (PM decision 2026-11-13) |
| location | `Lokatie` → `Lokalen[].Naam` |
| description | `Lesuur n` (or `n–m`), full Omschrijving, teachers, a status line ("Vervallen"/"Verplaatst"), homework/test text (`Inhoud`, HTML → text) |

Title prefixes, using **Magister's own label words** (PM decision 2026-11-13; multiple combine, e.g. `[Vervallen] [Proefwerk] biologie`):

| Condition | Prefix |
|---|---|
| Status 4 / 5 (vervallen handmatig / automatisch) | `[Vervallen]` |
| InfoType 2 / 3 | `[Proefwerk]` / `[Tentamen]` |
| InfoType 4 / 5 (schriftelijke / mondelinge overhoring) | `[SO]` / `[MO]` |
| InfoType 6 | `[Informatie]` |
| InfoType 1 | `[Huiswerk]` |
| Status 9 / 10 (verplaatst; community codes, not yet seen) | no prefix; "Verplaatst" note in the description |
| Status 3 | **no note**: PM confirmed 2026-11-13 that Magister shows these as normal lessons |

Prefix texts are Dutch constants in `mapping.py` (the event text comes from Dutch data anyway).
**Confirmed in M1 (PM run, 2026-11-13):** the `status=1` query parameter **hides cancelled
lessons** (Status 5 items only appear without it). The integration therefore fetches
appointments **without** a status filter. Observed codes: Status 1, 3, 5, 7; InfoType 0, 1, 2, 4;
Type 13 (lesuur) and 7 (keuzewerktijd-like, e.g. NT2). A cancelled lesson keeps its homework
(`InfoType` 1 + `Inhoud`), and a replacement item (e.g. a z-uur) can appear in the same slot;
both are shown. A second school confirmed Status 5 = cancelled (5 items) and showed Type 2
(school events, e.g. school photographer), empty `Vakken`, and school exams as `SE <VAK>` items
with InfoType 0 (recognizable by title only). Codes not seen yet (4, 9, 10; InfoType 3, 5, 6) follow community knowledge.

## 8. Reliability, security and privacy

- **Errors:** auth failure → `ConfigEntryAuthFailed` (reauth). Network/5xx/429 →
  `UpdateFailed`. The coordinator keeps the last good data, so the calendar stays
  populated during outages. HTTP 429 is respected with backoff.
- **Load:** per refresh, one `/api/account` call (cached per entry) plus one call
  per child. Children are fetched sequentially. The 30 min default is 48×/day per child.
- **Secrets:** password and TOTP secret are stored in the config entry (HA standard).
  Tokens stay in memory only. Tokens, passwords, TOTP secrets, cookies and
  `authCode` are **never logged**. Diagnostics redact credentials and person names.
- **Test fixtures:** recorded responses must be **anonymized** before they are committed
  (no real names, IDs or school data of the children).

## 9. Quality and tooling

- Python ≥ 3.14 (required by HA since 2026.3), targeting the newest HA release supported by `pytest-homeassistant-custom-component` (minimum version set in `hacs.json`).
- `ruff` (lint + format), `mypy` on `api/` (strict-ish), pytest with
  `pytest-homeassistant-custom-component`, `aioresponses` for HTTP mocks, coverage
  target ≥ 90 % for `api/` and config flow.
- GitHub Actions: tests + ruff, `hassfest`, `hacs/action`.
- Every milestone: Developer session → Reviewer session → PM acceptance.

## 10. PM decisions on open points (2026-11-09)

1. SSO/passkey accounts are out of scope for v1 (setup fails with a clear message). **Approved.**
2. License: **MIT.**
3. Prefix texts in §7: approved, then changed on 2026-11-13 to Magister's own label words.
4. Test accounts for Milestone 1: **parent accounts without 2FA** at two school tenants (details shared privately with the Architect). TOTP is covered by mocked tests only (not verified against a real account).
