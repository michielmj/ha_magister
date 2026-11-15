# Changelog

## Unreleased

## 1.7.1

AI coach fixes from the live test. Released 2026-11-15.

- **Shorter overdue list.** `list_homework` without `start` lists the open overdue items of the last 7 days only. The
  new argument `overdue_days` (1 to 35, default 7) widens the window; `include_overdue: false` still switches it off.
- **Cancelled lessons are never overdue.** They are still listed, marked `cancelled: true`, inside a requested
  `start`-`end` window.
- **`coach_not_enabled`.** A user who is linked to a child whose coach is not enabled (and to no enabled child) now
  gets this error, with a message that says where an administrator can enable it. The message and the prompt name no
  child. `not_linked` stays for users without any link.
- **README (NL/EN).** "Connecting Claude" now starts with the remote connector (verified): URL, "Sign in now",
  Claude's published identity or the fallback client ID, the required `use_x_forwarded_for` / `trusted_proxies`
  settings behind a reverse proxy, user and MCP Server settings, and a troubleshooting list. The local bridge is the
  alternative.
## 1.7.0

Parent study planner. Released 2026-11-14.

- **Roles.** Under Configure > AI coach, each child now has two user lists: students (Leerling) and parents (Ouder).
  The same user cannot be in both lists of a child. Users linked in 1.6.0 are read as students; there is no
  migration step. Parents use the same MCP Server setup as students.
- **Parent guidelines.** One text per config entry (Configure > AI coach > Parent guidelines, "Ouder-richtlijnen"),
  with a default and a reset option.
- **Daily maximum.** Study minutes per school day for each child (Configure > Daily study maximum): default 90,
  15 to 480 in steps of 15. Stored with the child's homework settings, applied without a reload, and sent to the
  card as `daily_max_minutes`.
- **Estimated time on subtasks.** Optional `minutes` (5 to 240 in steps of 5, or empty) in the WebSocket API, the
  services (`add_homework_subtask`, `update_homework_subtask`) and the coach tools; the new error is `invalid_minutes`.
  The store is now 1.6.
- **Coach.** New tool `get_overview(start, end)` for all linked children (tests, assignments, cancelled items, open
  items, planned minutes and the daily maximum per day). `list_children` returns the role and the daily maximum. The
  prompt names the role, the daily maximum and the matching guidelines per child. Subtasks made by a parent are marked
  `created_by: "parent"`; the parent's AI cannot set progress (`not_allowed_for_role`, nothing written or logged).
  Parent writes show as "Ouder via AI: …" in the logbook.
- **Homework planner card.** Subtasks show their estimated time ("30 min"). Subtasks created by a parent's AI show an
  **Ouder** marker (tooltip and screen reader text "Aangemaakt door ouder via AI" / "Created by parent via AI"), next
  to the "AI" marker for the student coach. Each day heading shows the planned time ("± 1 u 15 min gepland"), the sum
  of the estimates of all subtasks of that day, with a warning, the visible text "/ max 1 u 30 min" and "boven dagmaximum (1 u 30 min)" for screen readers
  when it is above the child's daily maximum. The add and edit forms have an optional "Geschatte tijd" select (15 to
  240 minutes); a value outside the list is kept and choosing "—" clears it. A card older than 1.7.0 ignores the new
  fields.
- **README.** The AI coach section covers parents (Ouder): linking, what the parent's AI can do, the parent
  guidelines, the daily maximum, an example conversation and the card's time display. The screenshots show times,
  a day over the maximum and the Ouder marker.
- Downgrading to 1.6.0 drops the estimated times and shows parent subtasks as added by the user. 1.6.0 keeps the
  student links; parents have no access in 1.6.0, and saving a child's coach settings in 1.6.0 removes its parents.
  Saving a child's weights in 1.6.0 drops its daily maximum, so the default of 90 applies after upgrading again.

## 1.6.0

AI homework coach. Released 2026-11-14.

- **AI homework coach (backend).** LLM API `magister_coach` ("Magister huiswerkcoach") with read tools (children,
  schedule, homework, progress, label options) and write tools (subtasks, progress, labels, label overrides) for
  HA's MCP Server and conversation agents. Opt-in per child, linked to HA users under Configure > AI-coach, with
  editable coaching guidelines. Writes are logged in the logbook. No teacher data is shared.
- Downgrading to an earlier version drops the AI marker (`created_by`): subtasks added by the coach then read as
  added by the user.
- **Subtasks** carry `created_by` (`"user"` or `"ai"`); the store is now 1.5 (older files read as `"user"`).
- **Homework planner card.** Subtasks created by the AI coach show a small "AI" marker with a tooltip and screen
  reader text ("Aangemaakt door AI-coach" / "Created by AI coach"). A missing `created_by` counts as `"user"`.
- **README.** New section "AI homework coach" / "AI-huiswerkcoach": what it can and cannot do, setup, connecting
  the Claude desktop app (local bridge first, remote connector for HTTPS), privacy and age notes, and the coaching
  guidelines. The connection steps are not yet verified with a real Claude desktop app.

## 1.5.0

Subtasks ("deelstappen") for homework, especially for tests.

- **Subtasks.** A homework item, usually a Proefwerk, can be split into subtasks with a title (1 to 100
  characters) and a planned day. A new subtask defaults to today; the latest allowed day is the lesson's
  day (or exactly that day when it is today or past), at most 20 per item, not on disabled items. A
  subtask that is not done moves forward day by day (weekends included) but never past the lesson; a
  done subtask stays on the day it was completed. A subtask uses the same 0/25/50/75/100 steps as an item.
- **Derived progress.** An item with subtasks shows the mean of its subtasks' progress (rounded half
  up) and is completed when all are done. Its own progress setting is not used while it has subtasks
  and applies again when the last subtask is deleted.
- **Bars and sensors.** An item with n subtasks is not counted itself. Each subtask counts with weight
  item weight / n in the period of its current day, so the weights still add up to the item's weight.
  The `items` and `completed` counts and the to-do count count these entries.
- **Home Assistant to-do list.** Each subtask is listed as `↳ <subject>: <title>` with its current day
  as due date. Ticking a subtask sets 100 or restores its last partial value; ticking an item that
  has subtasks gives a translated error.
- **API.** Items carry `derived` and `subtasks`; `set_progress` accepts a subtask uid (and returns
  `item_has_subtasks` for an item with subtasks); new WebSocket commands `add_subtask`,
  `update_subtask` and `delete_subtask`; new services `magister.add_homework_subtask`,
  `magister.update_homework_subtask` and `magister.delete_homework_subtask`
  (`docs/reference/homework-websocket.md`).
- **Homework planner card.** "+ deelstap" on an item opens an inline form (title, day). Subtasks are
  indented "↳" rows on their current day with a reference to the item ("voor Proefwerk Engels (di 17
  nov)"), their own checkbox and progress steps, and edit and delete (with confirmation). Overdue
  subtasks (the lesson has passed) are always shown in a group "Achterstallig" at the top. Completed
  subtasks follow the "Afgerond" switch, other past days the "Eerder" switch. An item with subtasks shows
  "x van y deelstappen" and the derived percentage, read-only. Everything works with the keyboard and
  screen readers, and changes are optimistic with rollback (adding waits for the answer).
- **Store.** The progress store moves to schema 1.4 (adds the optional `subtasks` per item). Upgrading
  needs no action. Downgrading to 1.4.0 keeps your progress, labels and overrides; 1.4.0
  ignores subtasks (an item with subtasks shows its own progress again) and deletes them the next
  time it saves.

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
