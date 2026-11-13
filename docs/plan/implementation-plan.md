# Magister for Home Assistant — Implementation Plan

| | |
|---|---|
| Status | **Approved by PM (2026-11-09)** |
| Date | 2026-11-09 |
| Based on | `docs/design/high-level-design.md` |

## Working method

1. For each milestone the Architect writes `docs/milestones/Mx-<name>.md` (scope,
   tasks, acceptance criteria). **The PM approves it before work starts.**
2. A **Developer session** (Sonnet 5.5, medium effort) implements it on a feature branch
   and reports back.
3. A fresh **Reviewer session** (Opus 5.5, medium effort) reviews against the milestone
   doc, the HLD and the quality bar. Findings go back to a Developer session until resolved.
4. The Architect summarizes the result. **The PM accepts the milestone** (for M1/M2/M4 this
   includes a hands-on check with a real account, because developers have no credentials).

## Milestones

### M0 — Repository foundation
Repo skeleton for a HACS custom integration: `custom_components/magister/` stub
(manifest, empty setup), `hacs.json`, `pyproject.toml` (ruff, pytest, mypy config),
`requirements_test.txt`, GitHub Actions (tests, ruff, hassfest, HACS validation),
README stub, LICENSE.
**Done when:** CI is green on an integration that loads but does nothing.

### M1 — Auth spike + API client *(highest risk, first)*
`api/` package: `auth.py` (full login incl. dynamic `authCode` scrape, TOTP, silent
renew, token expiry), `client.py` (account, children, appointments), `models.py`,
`errors.py`. `tools/magister_cli.py` for the PM: log in, list children, print a week,
optionally dump **anonymized** JSON. Unit tests with mocked HTTP.
**PM verifies:** the CLI works for each of their tenants/accounts (incl. 2FA if relevant).
Confirm the Status/InfoType codes and the `status=1` behaviour from the dumps.
**Go/no-go:** if unattended login turns out to be infeasible, we stop here and revisit R1.

### M2 — Config flow, coordinator, calendar (MVP)
Config flow (account → children), coordinator with the sync window, calendar entity
per child, event mapping incl. prefixes (`mapping.py`), devices, NL/EN translations.
**Done when:** the PM installs it via HACS (custom repo) on their HA and sees correct
calendars for all children, including cancelled lessons and tests.

### M3 — Robustness & options
Options flow (children, window, interval) with entity/device cleanup, reauth flow,
error handling/backoff, keeping last good data, diagnostics with redaction, logging
review (no secrets), test coverage targets met.
**Done when:** the reviewer signs off failure scenarios (wrong password, expired session,
Magister down, child removed) with tests.

### M4 — Release 1.0
README (NL + EN): installation, setup, TOTP secret how-to, troubleshooting, privacy note;
CHANGELOG, version tagging, GitHub release, HACS validation green.
**Done when:** v1.0.0 is tagged and installable via HACS custom repository.

## Backlog (post-v1, needs a new PM survey)
- Sensors: first lesson tomorrow, next lesson, cancelled lessons today/tomorrow.
- Homework/test sensors (open homework, tests this week).
- HA events on schedule changes (cancellation, new test) for automations.
- On-demand fetch for calendar ranges outside the sync window.
- Grades, absences; SSO login support; publishing `api/` as a PyPI library.
- **Passkey login** (discussed 2026-11-13, **not scheduled** by PM decision: no urgent need).
  Technical note for later: HA cannot use the user's own passkey. It could register its own
  software passkey via Magister's pairing step (`pair-fido`) and then sign logins instead of
  storing the password. This is undocumented and Magister may reject software authenticators,
  so it would need a spike first.

## Risks

| Risk | Impact | Mitigation |
|---|---|---|
| Magister changes the login flow / `authCode` | Integration stops working | Isolated `auth.py`, clear `MagisterAuthError` → reauth/repair message; quick-fix process |
| Login turns out infeasible for the PM's accounts (SSO, captcha) | Blocks v1 | M1 spike before any HA work; go/no-go |
| Developers cannot test against real Magister | Bugs only found at the PM | CLI harness, anonymized recorded fixtures, PM verification in M1/M2 |
| Rate limiting / account lockout by repeated failed logins | Account locked | No automatic retry after `invalid_auth`; go straight to reauth; backoff on 429 |
| Privacy (children's data in fixtures/logs) | Data leak | Anonymize fixtures, redaction in diagnostics, review checklist item |
