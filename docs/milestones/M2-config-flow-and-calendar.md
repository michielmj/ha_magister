# M2 — Config flow, coordinator and calendars (MVP)

| | |
|---|---|
| Status | **Approved by PM (2026-11-13)** |
| Branch | `claude/jolly-mayer-i2h3oo` |
| Refs | HLD §4–§8 · `docs/reference/magister-api.md` · fixtures in `tests/fixtures/school_a`, `school_b` |

## Goal

The first usable version: install via HACS, add a Magister login in the HA UI, pick the
children, and get **one calendar per tenant–child** showing lessons, homework, tests,
cancelled lessons and school events from 1 week back to 3 weeks ahead, refreshed every 30 minutes.

## Out of scope (M3)

Options flow (changing children/window/interval after setup), reauth flow UI, diagnostics,
repairs. M2 uses the default window and interval as constants. Auth failures must still raise
`ConfigEntryAuthFailed` so HA shows "re-authentication required"; the reauth *form* comes in M3.

## Tasks

### 1. Carry-overs from M1 (`api/auth.py`)
- After the password has been sent, a 5xx/connection error starts the backoff at 300 s.
  After 3 such failures in a row, block (remembered failure) until reload or `update_credentials`.
- Before the password step, a `MagisterApiError` (429, login page 404, authCode rejected twice)
  honours `retry_after`, or the same backoff, so coordinator polls don't re-run the flow immediately.
- Tests for both.

### 2. `api/mapping.py`: appointment → calendar fields (HLD §7)
- `summary`: `[Vervallen] ` for Status 4/5, then the label word for the InfoType:
  1 `[Huiswerk]`, 2 `[Proefwerk]`, 3 `[Tentamen]`, 4 `[SO]`, 5 `[MO]`, 6 `[Informatie]`;
  then `Appointment.subject` (Vakken name, else the first Omschrijving segment, else "Afspraak").
- `description` (plain text): `Lesuur n` or `Lesuur n–m`; a status line for cancelled
  ("Vervallen") or changed/moved (Status 3/9/10: "Gewijzigd"/"Verplaatst"); the full Omschrijving;
  teachers; then `Inhoud` converted from HTML to text (lists, `<br>`, `&nbsp;`, entities);
  "Bijlagen in Magister" when `HeeftBijlagen` is true.
- `location`: `Lokatie`, else the `Lokalen` names.
- All-day (`DuurtHeleDag`): date-only event with exclusive end date, as in the reference script.
  Not seen in real data yet, so test it with a synthetic item.
- `uid`: `magister-<Id>@<host>`.
- Pure functions, no HA imports. Snapshot-style tests over **every** item of both fixtures,
  plus targeted cases (cancelled + homework, Type 2 event, multi-hour, empty Vakken, SE item).

### 3. Config flow (`config_flow.py`, `manifest.json`: `config_flow: true`)
- Step `user`: school (any of `myschool`, `myschool.magister.net` or a URL → normalized host,
  `*.magister.net` only), username, password, optional TOTP secret. Validate with a real login
  and `async_get_account()`. Errors: `invalid_auth`, `totp_required`, `invalid_totp`,
  `unsupported_login`, `cannot_connect`, `unknown` (and the server error name in the log at
  debug level, never secrets).
- Step `children` (parent accounts): multi-select of the children (`Roepnaam Achternaam`),
  all selected by default; at least one required. Student accounts skip this step (self only).
- `unique_id = "<host>:<accountPersonId>"`; abort `already_configured`.
- Entry title `Magister <host-prefix> (<account Roepnaam>)`.
- Data: host, username, password, totp_secret (optional), selected child ids and names.
- Full config-entry lifecycle tests (setup → unload → remove), replacing the M0 direct-call test.

### 4. Coordinator (`coordinator.py`)
- One `DataUpdateCoordinator` per entry, `update_interval` 30 min. The window is computed in
  Europe/Amsterdam: Monday of last week 00:00 to Monday +3 weeks 00:00 (as the CLI dump does).
- Children are fetched **sequentially** with **no status filter**. Data:
  `{child_id: list[Appointment]}` sorted by start.
- `MagisterAuthError` with a final code → `ConfigEntryAuthFailed`. Connection/API errors →
  `UpdateFailed` (HA keeps the last good data). One HA-managed aiohttp session per entry
  (`async_create_clientsession`, own cookie jar).
- `MagisterAuth` and `MagisterClient` are created once per entry and kept in `entry.runtime_data`.

### 5. Calendar entities (`calendar.py`, `entity.py`)
- One `CalendarEntity` per selected child: `has_entity_name`, translated entity name
  "Agenda" ("Agenda"/"Calendar"), `unique_id = "<host>:<childId>"`.
- Device per child: name `<Roepnaam> (<host-prefix>)`, manufacturer "Magister",
  `entry_type` service, identifiers `(DOMAIN, "<host>:<childId>")`.
- `event`: the current or next event. `async_get_events(start, end)` returns events from coordinator
  data overlapping the range (no extra API calls).
- Timezone-correct (UTC from the API, HA converts). Tests with frozen time.

### 6. Translations
`strings.json`, `translations/en.json`, `translations/nl.json` for all config-flow steps,
fields, errors, aborts and the entity name. Hassfest must pass.

### 7. Tests & quality
pytest-homeassistant-custom-component tests for the config flow (every error path,
duplicates, student account), the coordinator (success, auth failure → reauth state, connection
failure keeps data), and the calendar (event ranges, all-day, cancelled). Coverage ≥ 90 % overall.
ruff, mypy (strict for `api/`), hassfest and HACS green.

## Acceptance criteria

- [ ] All tasks done; CI green.
- [ ] No secrets in logs (a test covers config-flow and coordinator logging).
- [ ] **PM test on their own HA:** install the M2 build through HACS as a custom repository,
      add both schools, and see a correct calendar per child, including cancelled lessons
      (`[Vervallen]`), homework/tests with Magister's labels, and titles like `wisB` at school 2.
- [ ] README updated with install and setup steps (short; full docs in M4).

## PM actions

Install via HACS as a custom repository (`https://github.com/michielmj/ha_magister`, category
Integration). HACS installs from releases or the default branch, so the Architect will publish
an M2 pre-release (or merge to `main`, by squash merge) and send exact steps when M2 is ready.
