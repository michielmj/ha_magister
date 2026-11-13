# M3 — Robustness & options

| | |
|---|---|
| Status | **Draft — awaiting PM approval** |
| Branch | `claude/jolly-mayer-i2h3oo` |
| Refs | HLD §5 (options, reauth), §8 (reliability, privacy) · M2 review notes |

## Goal

Make the integration pleasant to live with: change settings without re-adding it, recover from
a password change through a re-login form, and give useful diagnostics when something breaks,
all without weakening the lockout protection built in M1/M2.

## Out of scope

Passkey login (backlog, not scheduled). New entities (sensors, events). Release packaging (M4).

## Tasks

### 1. Options flow
- Fields: children (multi-select from a fresh children list, at least one), weeks back (0–8, default 1),
  weeks ahead (1–12, default 3), refresh interval in minutes (15–360, default 30).
- Fetching the children list in the options flow reuses the entry's retained login (no extra
  password submission when a valid token or silent renew is available).
- Saving reloads the entry (update listener). The coordinator uses the window and interval from the options.
- Removing a child removes its entity and device from the registries. Adding a child creates them.

### 2. Reauth flow (re-login form)
- `async_step_reauth` / `reauth_confirm`: asks for the password (and optionally a new TOTP secret)
  for the same account; the school and username are shown, not editable.
- Validates with one login. On success: update the entry data, call `update_credentials` on the
  retained auth (clears the remembered failure), then reload. Wrong account (different person id) → abort
  `wrong_account`.
- `ConfigEntryAuthFailed` (setup or polling) now leads to HA's "Re-authentication required" card.
  Keep `login_blocked` (ConfigEntryError) for non-credential final failures (outage after the password step).
- Update the README: the "remove and re-add after a password change" note is replaced by the reauth flow.

### 3. Reconfigure flow (optional but recommended)
`async_step_reconfigure` to change the username or TOTP secret for the same account, with the same
validation and `wrong_account` guard as reauth.

### 4. Diagnostics (`diagnostics.py`)
Config-entry diagnostics: options, host prefix, account type, number of children, per child the
number of events in the window and the counts per Status/InfoType/Type, the coordinator's last success/error,
the auth state (token source, backoff remaining, final-failure flag, password submission count).
**Redact**: username, password, TOTP secret, tokens, cookies, person names, ids and the host.
A test asserts that no secret or name appears.

### 5. Repairs / user messages
- When the authCode can no longer be extracted (Magister changed its login page), create a repair
  issue "Magister changed its login page; update the integration" instead of a generic error.
- Clear the issue on the next successful login.

### 6. Hygiene from M2 reviews
- Cover or mark the defensive guard in `__init__.py` (lines ~61-63).
- Reset `final_failure_reported` after a successful login and in `update_credentials`.
- Confirm the "Gewijzigd" note for Status 3 against the PM's observations. Until it is confirmed, keep it.

### 7. Tests & quality
Options flow (each field, child add/remove with registry cleanup), reauth (success, wrong password,
wrong account, TOTP), reconfigure, diagnostics redaction, the repair issue lifecycle, and a regression
test that reauth never causes more than one password submission. Coverage ≥ 90 %; all CI green.

## Acceptance criteria

- [ ] All tasks done; reviewer approved; CI green.
- [ ] **PM test on HAOS:** update via HACS, change an option (e.g. weeks ahead, or untick a child)
      and see the calendar follow, then download diagnostics and confirm they contain no names or secrets.
- [ ] Optional PM test: the next time you change your Magister password, the re-login card should
      appear in HA; entering the new password restores the calendars (the reauth paths are
      covered by automated tests either way).
