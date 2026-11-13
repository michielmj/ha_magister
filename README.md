# Magister for Home Assistant

A Home Assistant custom integration that brings the school agenda from
[Magister](https://www.magister.nl/) into Home Assistant as calendars: one calendar per
child and school, with lessons, homework, tests, cancelled lessons and school events from
one week back to three weeks ahead, refreshed every 30 minutes.

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

Changing the children, the time window or the refresh interval after setup, and a re-login
form after a password change, follow in a later version.

## Documentation

Design and planning documents are in [`docs/`](docs/).
