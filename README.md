# Magister for Home Assistant

A Home Assistant custom integration that brings the school agenda from
[Magister](https://www.magister.nl/) into Home Assistant as calendars: one calendar per
child and school, with lessons, homework, tests, cancelled lessons and school events from
one week back to three weeks ahead (adjustable), refreshed every 30 minutes (adjustable).

## Installation (HACS)

1. In HACS, open the menu and choose **Custom repositories**.
2. Add `https://github.com/michielmj/ha_magister` with category **Integration**.
3. Install **Magister** and restart Home Assistant.

## Setup

1. Go to **Settings > Devices & services > Add integration** and choose **Magister**.
2. Enter the school (`myschool`, `myschool.magister.net` or the web address), the username
   and the password of a parent or student account. For an account with two-step
   verification, also enter the authenticator secret (the base32 text shown when the
   authenticator app was set up).
3. For a parent account, choose the children that should get a calendar.

Add the integration again for another school or another login. Accounts that sign in
through school SSO (Entree, Microsoft, Google) or with a passkey are not supported.

## What you get

For every child a device `<name> (<school>)` with a calendar entity **Agenda**.
Event titles come from Magister (in Dutch) and use Magister's own labels:

| Title | Meaning |
|---|---|
| `[Vervallen] wiskunde` | cancelled lesson |
| `[Huiswerk] wiskunde` | lesson with homework |
| `[Proefwerk]`, `[Tentamen]`, `[SO]`, `[MO]`, `[Informatie]` | test, exam, written/oral quiz, information |

Labels combine, for example `[Vervallen] [Huiswerk] scheikunde`. The description shows the
lesson hour, a note for changed or cancelled lessons, the teachers and the homework text.

## First-appointment sensors

For automations such as a wake-up alarm, add a sensor with the start time of the first
appointment of a day:

1. Open the integration page and choose **Add first-appointment sensor** (next to
   **Configure**). Nothing is created automatically.
2. Choose the child and the day offset (0 = today, 1 = tomorrow, ...). The day must lie
   inside the fetched window: at most `7 x weeks ahead - 1` days ahead (20 with the
   default of 3 weeks).
3. Choose the subjects that do not count (for example `Franse taal`). The list shows the
   subjects in the child's current agenda and you can type other names. A subject matches
   when the whole name is equal, ignoring upper and lower case.

The sensor (device class `timestamp`, on the child's device) shows the start of the first
timed appointment on that day that is not cancelled and not excluded. Lessons, school
exams and school events all count; all-day items do not. When there is no such item
(weekend, holiday, everything cancelled or excluded) the state is `unknown`. The offset
counts calendar days, so on Friday offset 1 is Saturday. Attributes: `date`, `end`,
`subject`, `summary`, `location`, `lesson_hours` and `skipped` (the number of cancelled or
excluded items before it). The sensor updates with every refresh and at midnight, without
extra requests to Magister. Each sensor is a sub-entry on the integration page that can be edited
(reconfigure) and deleted separately.

If you later shrink **Weeks ahead** so that a sensor's offset no longer fits, the sensor
becomes `unknown` and a repair notice explains why.

## Options

**Configure** on the integration page changes the children (add or remove, which also adds
or removes their calendars, devices and sensors), the weeks back (0 to 8), the weeks ahead
(1 to 12) and the refresh interval (15 to 360 minutes). Saving reloads the integration
without logging in again.

## Password changed

When the login stops working (for example after a password change), Home Assistant shows
**Re-authentication required**. Enter the new password (and a new authenticator secret
only when that changed); the school and username are shown and cannot be changed. The
integration logs in exactly once with the new password. To change the username or the
authenticator secret on purpose, use **Reconfigure** in the three-dot menu of the
integration entry. Both only accept the same Magister account.

If Magister changes its login page, a repair notice asks you to update the integration.

## Diagnostics

**Download diagnostics** (integration page, three-dot menu) gives the options, the number of
children, per child the number of events and the counts per status, info type and type,
the state of the last refresh, and the login state (token source, backoff, failure flag,
number of password submissions). Usernames, passwords, secrets, tokens, names, ids and the
school host are redacted or left out.

## Documentation

Design and planning documents are in [`docs/`](docs/).
