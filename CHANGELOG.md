# Changelog

## Unreleased

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
