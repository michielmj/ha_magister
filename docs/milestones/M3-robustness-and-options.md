# M3 — Robustness & options

| | |
|---|---|
| Status | **Accepted by PM (2026-11-13)** — options, repair message, diagnostics and sensors tested on HAOS (0.3.1) |
| Branch | `claude/jolly-mayer-i2h3oo` |
| Refs | HLD §5 (options, reauth), §8 (reliability, privacy) · M2 review notes |

## Goal

Add user-defined **first-appointment sensors** (PM request 2026-11-13), and make the integration pleasant to live with: change settings without re-adding it, recover from
a password change through a re-login form, and give useful diagnostics when something breaks,
all without weakening the lockout protection built in M1/M2.

## Out of scope

Passkey login (backlog, not scheduled). Other new entities (homework/test sensors, change events). Release packaging (M4).

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
- ~~Confirm the "Gewijzigd" note for Status 3~~ **Resolved 2026-11-13:** the PM confirmed Magister shows Status 3 as a normal lesson, so the note was removed in 0.3.1.

### 8. First-appointment sensors (PM request 2026-11-13)
Purpose: e.g. wake-up automations ("what time does the first lesson of child X start tomorrow?").
- **Creation via config sub-entries** (HA's sub-entry feature): on the integration page an
  "Add first-appointment sensor" button opens a flow with:
  - child (one of the entry's selected children)
  - day offset (integer ≥ 0; 0 = today, 1 = tomorrow, …). It must fall inside the fetch window: at most
    7 × weeks-ahead − 1. Validate this, and show a clear error.
  - excluded subjects: multi-select of the subjects in that child's current data (as shown in the title:
    `Appointment.subject`, e.g. "Franse taal", "wisB"), with free-text entries allowed. Matching is exact
    and case-insensitive.
  - Each sensor can be edited (reconfigure sub-entry) and deleted individually. Nothing is created automatically.
- **Entity**: one `sensor` per sub-entry, device class `timestamp`, attached to the child's device.
  The default name comes from the offset ("Eerste afspraak vandaag" / "morgen" / "over N dagen"; EN equivalents);
  the sub-entry title is editable.
  `unique_id = <host>:<childId>:first:<subentry_id>`.
- **Value**: the start of the first appointment on local date (today + offset, Europe/Amsterdam) that
  - is timed (not all-day),
  - is not cancelled (Status 4/5),
  - and whose subject is not excluded.
  All types count: lessons, school exams ("SE …") and school events. No such item → state `unknown` (weekend, holiday,
  everything cancelled/excluded). The offset counts calendar days (Friday + 1 = Saturday → unknown).
- **Attributes**: date, end, subject, summary (with labels), location, lesson hour(s), and the number of excluded
  or cancelled items skipped before it.
- **Updates**: recompute on every coordinator refresh **and** at local midnight (the day rolls over),
  without extra API calls. If options later shrink the window so the offset no longer fits,
  the sensor becomes `unknown` and a repair issue explains it.
- Removing a child in the options also removes its sensor sub-entries (or the flow warns first).
- Translations NL/EN for the sub-entry flow, errors and entity names.
- Tests: fixture-based (school A: excluding "Franse taal" picks the next item; a cancelled first lesson
  is skipped; weekend → unknown); midnight rollover with frozen time; DST day; sub-entry
  add/edit/delete; offset validation; window shrink → unknown + repair issue.

### 7. Tests & quality
Options flow (each field, child add/remove with registry cleanup), reauth (success, wrong password,
wrong account, TOTP), reconfigure, diagnostics redaction, the repair issue lifecycle, and a regression
test that reauth never causes more than one password submission. Coverage ≥ 90 %; all CI green.

## Acceptance criteria

- [ ] All tasks done; reviewer approved; CI green.
- [ ] **PM test on HAOS:** add first-appointment sensors (e.g. offset 0 and 1, and one excluding a subject) and
      check them against the calendar; update via HACS, change an option (e.g. weeks ahead, or untick a child)
      and see the calendar follow, then download diagnostics and confirm they contain no names or secrets.
- [ ] Optional PM test: the next time you change your Magister password, the re-login card should
      appear in HA; entering the new password restores the calendars (the reauth paths are
      covered by automated tests either way).
