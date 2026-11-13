# M1 — Auth spike + API client

| | |
|---|---|
| Status | **Accepted by PM (2026-11-13)** — GO at both test schools |
| Branch | `claude/jolly-mayer-i2h3oo` |
| Refs | `docs/design/high-level-design.md` §3, §4, §7, §8 · `docs/reference/magister_agenda.py` |

## Goal

Prove that unattended login to Magister works with plain HTTP, and deliver the
HA-independent `api/` package that M2 builds on. This is the **go/no-go milestone**
for requirement R1 (username + password + optional TOTP).

## Out of scope

Anything importing `homeassistant` (config flow, coordinator, calendar: M2). The
`api/` package must not import HA. `manifest.json` gets only the `pyotp` requirement.

## Tasks

### 1. Discovery (live, without credentials)
The unauthenticated part of the login flow is publicly reachable. Explore it with real
HTTP requests against a public tenant (e.g. `<tenant>.magister.net`, any school):
- where the OIDC client settings come from (client_id, redirect_uri, scopes, authority)
- the `/connect/authorize` → `/account/login?sessionId=…&returnUrl=…` redirect, and the `XSRF-TOKEN` cookie
- how to locate the login JS bundle and extract the current `authCode`. Write a
  robust extractor and document the pattern used.
- the challenge endpoints and request/response shapes, as far as they can be seen without valid
  credentials (`/challenges/current`, `/challenges/username` with a dummy user)

Write findings to `docs/reference/magister-auth-flow.md`, including the exact request sequence.
Never send real-looking credentials. Keep request volume low (a handful of requests).

### 2. `custom_components/magister/api/`
Follow HLD §4:
- `errors.py`: `MagisterError` base; `MagisterAuthError` (subtypes or codes:
  `invalid_auth`, `totp_required`, `invalid_totp`, `unsupported_login` for SSO/passkey),
  `MagisterConnectionError`, `MagisterApiError` (with HTTP status).
- `auth.py`: `MagisterAuth(session: aiohttp.ClientSession, host, username, password, totp_secret=None)`
  - `async_get_token()` returns a valid access token: the cached one if not about to expire
    (60 s margin), else silent renew (`prompt=none` with session cookies), else full login.
  - Full login: authorize → challenges (username, password, TOTP via `pyotp` when Magister
    asks for it) → follow `returnUrl` → parse `access_token`/`expires_in` from the fragment.
  - Detect SSO/external-IdP redirects and raise `unsupported_login`.
  - A lock prevents concurrent logins. `invalid_auth` is never retried automatically.
  - Secrets (password, TOTP secret, tokens, cookies, authCode) never appear in logs,
    exception messages or `repr()`.
- `client.py`: `MagisterClient(session, auth, host)` with `async_get_account()`,
  `async_get_children(parent_id)`, `async_get_appointments(person_id, start, end)`.
  Bearer header from `auth`; one automatic re-auth retry on 401; 429/5xx →
  `MagisterApiError`/`MagisterConnectionError`; request timeout 30 s.
- `models.py`: frozen dataclasses `Account`, `Person`, `Appointment` (fields per HLD §7 plus
  `status`, `info_type`, `type`, `afgerond`), with parsing from API JSON (UTC-aware datetimes).
  Unknown enum codes must not crash parsing.
- `mapping.py` is **not** part of M1 (M2), but record the observed `Status`/`InfoType`/`Type`
  codes in `docs/reference/magister-api.md`.

### 3. PM verification CLI: `tools/magister_cli.py`
- `python tools/magister_cli.py --tenant <tenant> --username <user>` prompts for the password
  with `getpass` (optional `--totp-secret-env VAR`). It never takes a password as an argument
  and never prints secrets.
- Logs in, prints the account type and children, and for each child prints this week's
  agenda (like the reference script) **and** runs a second token fetch, which should be a silent renew,
  reporting which path was used.
- `--dump DIR` writes **anonymized** JSON (account, children, appointments for `-1..+3` weeks):
  names → `Kind A`/`Ouder`, person/appointment IDs → stable fake numbers,
  teacher names/codes → `Docent N`, tenant host → `school.example`, free text (`Inhoud`) kept but
  e-mail addresses and URLs scrubbed. The anonymizer lives in `tools/anonymize.py` with tests.
- Runs with only `aiohttp` and `pyotp` installed (document this in the script's docstring).

### 4. Tests (`tests/api/`)
`aioresponses`-based tests for: full login happy path, login with TOTP challenge, wrong
password, missing TOTP, SSO detection, authCode extraction (from a saved, trimmed bundle
fixture), silent renew success and fallback to full login, token expiry margin, concurrent
`async_get_token` calls → one login, 401 → re-auth retry, 429/5xx mapping, model parsing
incl. all-day and unknown codes, anonymizer. Coverage ≥ 90 % for `api/`. mypy strict
for `custom_components/magister/api/`.

## Acceptance criteria

- [ ] Discovery doc written; authCode extraction works against the live bundle at time of delivery.
- [ ] `api/` has no `homeassistant` imports; mypy strict clean; ruff clean; coverage ≥ 90 %.
- [ ] No secrets in logs/reprs (a test asserts that password/token never appear in caplog output).
- [ ] CI green (except the HACS topics check, if still unset).
- [ ] **PM verification:** the CLI logs in and shows a correct week for both test schools,
      the second token fetch uses silent renew (or fallback is reported clearly), and the
      anonymized dumps contain no real names/IDs (PM checks before sharing).
- [ ] The PM shares the anonymized dumps. They are committed as fixtures under `tests/fixtures/`
      and the Status/InfoType table in `docs/reference/magister-api.md` is confirmed from them,
      including whether `status=1` hides cancelled lessons.

## Go / no-go

If login fails for the PM's accounts in a way we cannot fix (captcha, mandatory SSO,
bot protection), the Architect brings options back to the PM before M2 starts.

## Carried over to M2 (from M1 reviews)

1. **Backoff after the password was sent** (`auth.py`): on a 5xx/connection error after the
   password POST, start the backoff at 300 s; after 3 such failures in a row, block until
   reload or `update_credentials`. Add a test.
2. **Backoff before the password step**: `MagisterApiError` (429, login page 404, authCode
   rejected twice) must honour `retry_after` or the same backoff, so coordinator polls don't
   re-run the login flow immediately.
3. **Git history hygiene**: an early commit contains an expired, anonymous pre-login
   `XSRF-TOKEN` value in a test fixture. Merge the branch to `main` with a **squash merge**.

## PM verification results

**School 1 (2026-11-13): GO.** Parent account, no 2FA.
- Full login OK; week matches the Magister website; **silent renew worked**.
- Anonymized dumps shared (1 child) and checked by the Architect: no person names found.
- **`status=1` hides cancelled lessons:** 140 items without the filter vs 130 with it. The 10
  missing items are all Status 5 (vervallen automatisch). Decision recorded in HLD §7: fetch
  without a status filter.

**School 2 (2026-11-13): GO.** Parent account, no 2FA. Login OK, silent renew worked.
Dumps shared and checked: no person names. `status=1` again hid exactly the cancelled
(Status 5) items (94 vs 89). New: `Vakken` is empty at this school, so the title falls back to the
first `Omschrijving` segment; Magister's label words are used as prefixes (HLD §7).

**M1 result: GO** — unattended login with username + password works at both schools.
