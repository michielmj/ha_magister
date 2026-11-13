# Changelog

## Unreleased

- Homework planner card (`custom:magister-homework-card`, NL/EN, visual editor) shipped with the
  integration and loaded automatically. The integration now depends on `frontend` and `http`.
- Homework planner backend: a to-do list per child with the homework and test items,
  progress in percent stored in Home Assistant, the service `magister.set_homework_progress`,
  a WebSocket API for the upcoming card, weighted progress sensors (tomorrow, this week, next
  week) and an options menu with homework weights.
- Every child gets new entities after upgrading: a Homework to-do list and three progress
  sensors. With `weeks_ahead` set to 1, a repair notice appears because the next-week sensor
  needs at least 2 weeks ahead (that sensor stays unavailable until you raise it).

## 1.0.0

First stable release. Summary of 0.1 to 0.3:

- Calendars per child and school with Magister's labels (`[Vervallen]`, `[Huiswerk]`,
  `[Proefwerk]`, ...), fetched from one week back to three weeks ahead every 30 minutes
  (adjustable in the options).
- Config flow with school, username, password, optional authenticator secret and a choice of
  children; several logins per school are supported. Re-authentication, reconfigure and
  options flows (saving reloads without a new login).
- First-appointment sensors (config sub-entries) with a day offset and excluded subjects,
  for example for a wake-up alarm.
- Calendars and sensors stay available on the last good data for up to 24 hours when a
  refresh fails.
- Lockout protection for the login, diagnostics with redaction, and repair messages when
  Magister changes its login page or a sensor falls outside the fetched window.
- Dutch and English translations and README; `tools/magister_cli.py` for troubleshooting.
- A child that another login of the same school already has is no longer offered (config
  flow and options), and a login whose children are all taken is rejected with a clear
  message. This prevents two calendars with the same unique id.
- Dutch translation fixes.
- Repair message when a child is configured under more than one login of a school (installs
  from before this check); the options form always offers the children an entry already has.
- New in 1.0: project icon (shipped in `custom_components/magister/brand/`), user
  documentation in English and Dutch, release workflow, issue templates, security policy and
  Dependabot.

## 0.3.1

- Status 3 appointments are shown as normal lessons: the "Gewijzigd" line is gone from
  the description (Magister itself shows no changed marker). "Verplaatst" for Status 9
  and 10 stays.
- An entity that is still available when its data-age timer fires now schedules the
  timer again.
- Test for an outage that spans midnight: the sensor shows the next day's first
  lesson from cached data.

## 0.3.0

Summary of M2, M3 and the follow-up since 0.0.1:

- Calendars per child (M2) and the options, re-authentication, reconfigure, diagnostics,
  repair and first-appointment sensor features (M3), listed below.
- Calendars and sensors now stay available on the last good data for up to 24 hours
  when a refresh fails, so Time triggers on the sensor are not cancelled by an outage.
  Diagnostics show the age of the last successful refresh.
- The version in the manifest is now 0.3.0 (it was still 0.0.1).
- README: a section on using the sensor in automations.

Details:

- Repository foundation: integration stub, tooling, tests and CI workflows.
- Test baseline: Home Assistant 2026.10.4 on Python 3.14.
- M1: Home-Assistant-independent API package (`custom_components/magister/api/`:
  login with optional TOTP, silent token renew, client, models) and the
  `tools/magister_cli.py` verification tool with anonymized dumps.
- M2: config flow (school, credentials, optional TOTP secret, choice of children),
  a coordinator that fetches 1 week back to 3 weeks ahead every 30 minutes, and one
  calendar entity per child with Magister's labels (`[Vervallen]`, `[Huiswerk]`,
  `[Proefwerk]`, ...). Login backoff after server errors (auth carry-overs from M1).
  NL and EN translations.
- M3: options flow (children, weeks back/ahead, refresh interval; saving reloads
  without a new login), re-authentication and reconfigure flows (one validating login,
  handed over to the entry so the reload does not log in again), diagnostics with
  redaction, a repair issue when Magister changes its login page, and first-appointment
  sensors (config sub-entries) with a day offset and excluded subjects.
