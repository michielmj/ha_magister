# Magister for Home Assistant

[Nederlands](README.nl.md) | English

Show your child's school agenda from [Magister](https://www.magister.nl/) in Home Assistant:
one calendar per child, plus optional sensors with the start time of the first appointment of
a day (handy for a wake-up alarm).

> **Unofficial.** This project is not affiliated with, endorsed by or supported by Iddink or
> Magister. It signs in the way a browser does, so it may stop working when Magister changes its
> login. Use it at your own risk.

## What you get

- A calendar **Agenda** for every child (device `Kind (myschool)`), with lessons, homework,
  tests, cancelled lessons and school events. By default from one week back to three weeks
  ahead, refreshed every 30 minutes (both adjustable).
- Optional **first-appointment sensors** (a timestamp) for automations.
- Event titles come from Magister (in Dutch) with these labels:

| Title | Meaning |
|---|---|
| `[Vervallen] wiskunde` | cancelled lesson |
| `[Huiswerk] wiskunde` | lesson with homework |
| `[Proefwerk]`, `[Tentamen]`, `[SO]`, `[MO]`, `[Informatie]` | test, exam, written/oral quiz, information |

Labels combine, for example `[Vervallen] [Huiswerk] scheikunde`. When Magister gives no subject, the first part of the appointment's description is used as the
title (and `Afspraak` if that is empty). The event description shows the lesson hour, a note
for moved or cancelled lessons, the teachers and the homework text.

## Requirements

- Home Assistant **2026.10.4** or newer.
- A Magister account of a parent or student with a **username and password**. Accounts that
  can only sign in through school SSO (Entree, Microsoft, Google) or a passkey are not supported.
- Only if the account uses two-step verification (an authenticator app): the **authenticator
  secret**. This is the base32 text (letters and digits) that Magister shows next to the QR code
  when you set up the authenticator app. Magister shows it only during setup, so you probably
  have to set up the authenticator again (a new QR code and secret) and note the secret. The
  new secret replaces the old pairing: also add it to your own authenticator app.

## Installation

### With HACS (recommended)

1. Install HACS first if you have not done so: follow the official guide,
   <https://hacs.xyz/docs/use/download/download/> (in Home Assistant 2026.2 and later add-ons are
   called *apps*).
2. In HACS open the three-dot menu and choose **Custom repositories**.
3. Enter `https://github.com/michielmj/ha_magister` and choose type **Integration**, then **Add**.
4. Search for **Magister** in HACS, choose **Download** and restart Home Assistant.
5. Refresh your browser (a hard refresh) so the new integration and its icon show up.

### Manually

Copy the folder `custom_components/magister` from this repository to
`config/custom_components/magister` in Home Assistant, restart Home Assistant and refresh the browser.

## Setup

1. Go to **Settings > Devices & services > Add integration** and choose **Magister**.
2. Enter the school (`myschool`, `myschool.magister.net` or the web address), the username and
   the password. With two-step verification also enter the authenticator secret.
3. For a parent account choose the children that should get a calendar.

Each Magister login is one entry. You can add several logins, also for the same school (for
example both parents), and logins for different schools. The same account cannot be added twice.

### Options

**Configure** on the integration page changes the children (also adds or removes their
calendars and sensors), the weeks back (0 to 8), the weeks ahead (1 to 12) and the refresh
interval (15 to 360 minutes). Saving reloads the integration without logging in again.

## First-appointment sensors

Nothing is created automatically. On the integration page choose **Add first-appointment
sensor** (next to **Configure**):

1. Choose the child and the day offset (0 = today, 1 = tomorrow, ...). The day must lie
   inside the fetched window: at most `7 x weeks ahead - 1` days ahead (20 with the default of 3
   weeks).
2. Choose the subjects that do not count, for example `Franse taal`. The list shows subjects in
   the child's current agenda and you can type other names. A subject matches when the whole name
   is equal, ignoring upper and lower case.

The sensor (device class `timestamp`, on the child's device, for example
`sensor.kind_myschool_eerste_afspraak_vandaag`) shows the start of the first timed appointment of
that day that is not cancelled and not excluded. Lessons, school exams and school events count;
all-day items do not. Attributes: `date`, `end`, `subject`, `summary`, `location`,
`lesson_hours` and `skipped` (the number of cancelled or excluded items before it).

The state is **`unknown`** when there is no such appointment (weekend, holiday, everything
cancelled or excluded) or when the offset no longer fits the window (a repair notice then explains
this). The offset counts calendar days, so on Friday offset 1 is Saturday. The sensor updates with
each refresh and at midnight, without extra requests to Magister. Every sensor can be edited
(reconfigure) and deleted separately.

### Automation examples

The sensor is a timestamp, so the **Time** trigger can fire relative to it. An alarm 1 h 30 min
before the first lesson of today (sensor with offset 0):

```yaml
triggers:
  - trigger: time
    at:
      entity_id: sensor.kind_myschool_eerste_afspraak_vandaag
      offset: "-01:30:00"
actions:
  - action: script.wake_up
```

For an early lesson you may want the alarm the evening before: use the "tomorrow" sensor (offset
1) with a large negative offset, for example `"-14:00:00"` (14 hours before the first lesson of
tomorrow).

Rule of thumb: pick the sensor whose day is the target day at the moment the trigger fires. A
"today" sensor rolls over to the next day at midnight, so an alarm at 06:45 for today's lesson
belongs on the offset 0 sensor and an alarm the evening before on the offset 1 sensor.

**Add a fallback for important alarms.** The sensors and calendars keep the last good data for up
to 24 hours when Magister or your internet connection is down, so a short outage does not cancel a
scheduled alarm. After 24 hours without a successful refresh they become unavailable. For a first
lesson you must not miss, also add a fixed-time alarm as a fallback.

## How it behaves

- Refresh every 30 minutes by default; the whole window is fetched in one go.
- During an outage the data stays available for up to 24 hours, then it becomes unavailable.
- Cancelled lessons stay visible with `[Vervallen]` and are skipped by the sensors.
- Moved lessons get a note in the description.
- Only the school agenda is read. Nothing is written to Magister.

## Troubleshooting

- **Re-authentication required** (card on the integration page): the login stopped working,
  usually after a password change. Enter the new password (and a new authenticator secret only if
  it changed). The integration then logs in exactly once. To change the username or secret on
  purpose, use **Reconfigure** in the three-dot menu of the entry. Both only accept the same
  Magister account.
- **Login blocked / "Logging in to Magister is blocked after repeated failures"**: to avoid
  locking your account, the integration stops trying after repeated failures. Fix the cause
  (password, network), then **reload** the integration (three-dot menu): that tries one more
  time. If the password is wrong, use Reconfigure or the re-login card instead.
- **Repair "Magister changed its login page"**: Magister changed its sign-in pages. Update the
  integration in HACS; if it persists, open an issue.
- **Repair "First-appointment sensor outside the window"**: a sensor looks further ahead than the
  weeks ahead allow. Increase **Weeks ahead** or edit the sensor.
- **Logs**: Settings > System > Logs, filter on `magister`. For more detail add this to
  `configuration.yaml` and restart:

  ```yaml
  logger:
    logs:
      custom_components.magister: debug
  ```

- **Diagnostics**: on the integration page, three-dot menu, **Download diagnostics**. The file
  contains options, counts and the login state; usernames, passwords, secrets, tokens, names, ids
  and the school host are removed.

**Never post names, screenshots that show names, or passwords in an issue.** Attach the
diagnostics file instead and replace anything personal in logs by hand.

### Command-line check

[`tools/magister_cli.py`](tools/README.md) tests the login and agenda from your own computer,
without Home Assistant, and can write an anonymized dump. Read [`tools/README.md`](tools/README.md)
first; the password is asked with hidden input.

## Privacy and security

- Your username, password and authenticator secret are stored in Home Assistant's config entry
  (`config/.storage`), like other integrations. Protect your backups.
- They are never written to logs; diagnostics redact them.
- Data goes only between your Home Assistant and Magister (your school's Magister server and
  login service). There is no other server, no analytics.
- Lockout protection: after a failed login or repeated server errors the integration waits and
  does not retry with the password; it stops completely when it could count towards a lockout,
  until you reload the integration or re-authenticate.

Report security problems privately, see [SECURITY.md](SECURITY.md).

## Development

Design and planning documents are in [`docs/`](docs/). Maintainer: `michielmj`. License: MIT.
