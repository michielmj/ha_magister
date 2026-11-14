# Changelog

## Unreleased

## 1.4.0

Replace or disable Magister labels.

- **Overrides.** The Magister label of a lesson can be **replaced** by one of the child's label
  options or **disabled**, and always **restored**. Nothing is written to Magister. A replacement
  decides the weight, the test highlight and the sensors' `tests` count; the calendar title shows
  `[Proefwerk→Huiswerk]`. A disabled label counts as completed: the item is completed in the
  payload and in Home Assistant's to-do list, is left out of the to-do count, has weight 0 and is
  ignored by the bars and sensors; its progress is kept. If the lesson also has an active manual
  label the item stays active. An item's weight is the highest weight of its active labels times
  the subject weight. A label option used as a replacement on a lesson cannot be deleted; a
  replacement whose option is gone falls back to the original label.
- **API.** New WebSocket command `magister/homework/set_override` and service
  `magister.set_homework_override`; items carry `override` and `disabled`, `completed` is true for
  disabled items, `set_progress` on a disabled item returns `item_disabled`, and appointments
  carry `override` (`docs/reference/homework-websocket.md`). Ticking a disabled item in Home
  Assistant's to-do view gives a translated error. Diagnostics count overrides per mode.
- **Homework planner card.** The Magister chip is a menu button (replace, disable, restore; with
  keyboard support and on a phone). Changed chips are struck through, followed by the replacement;
  disabled items appear with the completed ones.
- **Store.** The progress store moves to schema 1.3 (adds the optional `override` per item).
  Upgrading needs no action. Downgrading to 1.3.0 keeps progress and labels but ignores (and on its
  next save drops) the overrides.

## 1.3.0

Next school day, manual labels and card switches.

- **Periods.** School days are Monday to Friday. The "tomorrow" sensor is now **next school day**:
  all of today's items plus the next school day's (on Friday, Saturday and Sunday that is Monday).
  **This week** is Saturday to Friday (on a Saturday it is the coming school week) and **next
  week** the following Saturday to Friday. Existing unique ids are kept, so entity ids and history
  stay; only the display name changed. The WebSocket `progress` key `tomorrow` is now `next_day`.
- **Manual labels.** Per child, under *Configure > Labels*, you manage label options (name and kind
  homework or test; the list starts with the five Magister names; a label in use cannot be
  deleted). Labels can be put on any lesson in the fetched window with an optional note and
  removed again (only manual labels). They count in the progress (weights per label, the highest
  label weight of an item is used), make a test-kind item a test, and appear in calendar titles
  after the Magister label. New services `magister.add_homework_label` and
  `magister.remove_homework_label`; new WebSocket commands `appointments`, `add_label` and
  `remove_label` (`docs/reference/homework-websocket.md`).
- **Homework planner card.** Header switches for *Done* and *Earlier* (remembered per browser), a
  `language` option (`auto`, `nl`, `en`), a **+** button with a dialog to add a label to a lesson,
  manual label chips with a note and a confirmed **×** to remove them, and the editor label
  "Show next school day progress" (the `show_progress_tomorrow` key is unchanged).
- **Store migration.** The progress store moves to schema v2 (manual labels). Upgrading migrates it
  automatically. Downgrading to 1.2.0 keeps the progress but loses the manual labels.

## 1.2.0

Progress bars on the card and a to-do count that ignores past homework.

- The **number shown for the Homework to-do list** now counts only the open items due **today or
  later** (Europe/Amsterdam). Past homework stays in the list and on the card but is no longer
  counted. The count moves on at midnight. Automations and conditions on the list's state use this
  count (overdue items are not counted).
- The **Homework planner card** can show the progress sensors as horizontal bars above the
  homework: tomorrow, this week and next week, each with its own option
  (`show_progress_tomorrow`, `show_progress_week`, `show_progress_next_week`, all off by default;
  also in the visual editor, Dutch and English).
- WebSocket API: the `magister/homework/subscribe` event gains a `progress` object with the
  values of the three progress sensors (`docs/reference/homework-websocket.md`). Older clients
  ignore it.

## 1.1.0

Homework planner.

- A **Homework to-do list per child** with the homework and test items (Huiswerk, Proefwerk,
  Tentamen, SO, MO), cancelled lessons marked. Progress in percent is stored in Home Assistant
  only (nothing is written back to Magister); the service `magister.set_homework_progress` and
  a WebSocket API (`docs/reference/homework-websocket.md`) change it.
- **Three progress sensors per child**: tomorrow, this week and next week, as a weighted average,
  with an options menu **Homework weights** (per type and per subject).
- The **Homework planner card** (`custom:magister-homework-card`, Dutch and English, with a
  visual editor) is shipped with the integration and loaded automatically; no resource to add.
  Add it via the dashboard editor (search "Magister"). See the README.
- The integration now declares the dependencies `frontend` and `http` in its manifest (it
  serves and registers the card).
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
