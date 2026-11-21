# Homework planner — WebSocket contract

The contract between the integration (backend, M5 Phase A) and the Homework planner card
(M5 Phase B). Both sides must follow this document. Any change requires an update here and
a version note in the CHANGELOG.

All commands use HA's authenticated WebSocket API (`hass.connection` in the frontend).
`entity_id` must be a Magister homework to-do entity (`todo.*` created by this integration).
The user must have read permission on the entity (subscribe) or control permission (set_progress).

## `magister/homework/subscribe`

Request:
```json
{"id": 1, "type": "magister/homework/subscribe", "entity_id": "todo.kind_myschool_homework"}
```

Result (sent first):
```json
{"id": 1, "type": "result", "success": true, "result": null}
```

Then an **event** is sent immediately with the full state, and again on every change: progress, Magister
refresh, reload, availability or entity removal. Identical consecutive payloads for the same entity instance
are not repeated. After an entry reload the new entity pushes its list once to existing subscribers, so
**the card does not need to resubscribe**.

```json
{"id": 1, "type": "event", "event": {
  "available": true,
  "items": [ <item>, ... ],
  "labels": [ <label option>, ... ],
  "progress": {
    "next_day":  {"value": 100.0, "items": 0, "completed": 0},
    "week":      {"value": 25.0,  "items": 18, "completed": 4},
    "next_week": null
  },
  "daily_max_minutes": 90,
  "daily_max_weekdays": [90, 90, 90, 90, 90, 0, 0],
  "daily_max_overrides": {"2026-11-18": 30},
  "proposals": [ <proposal>, ... ],
  "timer": null,
  "timer_settings": {"prewarn_minutes": null, "extra_minutes": null}
}}
```

`timer` and `timer_settings` (since 1.10.0): see "Study timer" below. Both are in the final `available: false` event
too (the timer as it was in the last event), and in a payload with `available: false` because the Magister data is
stale: the timer is local data and is always included; clients that predate them ignore them.

`daily_max_weekdays` (since 1.9.0) is the child's normal daily maximum per weekday, **Monday first** (Monday to Sunday), seven
integers 0–480 in steps of 15, default 90 for every day; 0 means "no study planned that day" (any planned minutes are over
the maximum). Weekends count: every day can be a homework day. It is set in the options (Configure > Daily study maximum:
one field per weekday) or by accepting a proposal, and applies without a reload (a new event is pushed). It is present in
the final `available: false` event too. Clients that predate the field ignore it and use `daily_max_minutes`.

`proposals` (since 1.9.0) lists the proposals for the daily maximum of this child (see below): the open ones first, then the
ones answered or expired within the last 14 days, each group by creation time. It is `[]` when there are none, and it is in
the final `available: false` event too. Clients that predate the field ignore it.

`daily_max_overrides` (since 1.8.0) maps `YYYY-MM-DD` to the **effective** daily maximum, for every day of the sync window
(the same period as the calendar and the card: from the weeks back to the weeks ahead in the options, including past
days) on which a coach circumstance sets a maximum that differs from the normal maximum **of that weekday** (since 1.9.0:
`daily_max_weekdays[weekday]`; in 1.8.x it was `daily_max_minutes`). Days that are not listed use the weekday's value:
a day whose effective maximum equals it is left out, so a circumstance that changes
nothing (for example a hidden one) leaves no trace in the card. The effective maximum of a date is the lowest maximum of a
circumstance that covers it (a circumstance can also raise it), otherwise the weekday's value. When circumstances overlap, the lowest maximum wins. The map holds numbers only (no note text) and is present in the final `available: false`
event too. Clients that predate the field ignore it (and 1.7.x does not send it).

`daily_max_minutes` (since 1.7.0) was the child's daily maximum of study minutes per school day. Since 1.9.0 it is the
**Monday value** of `daily_max_weekdays`, kept for older cards (and stored as a mirror in the options so that a downgrade
keeps a sensible single value; 1.8.x uses it for every day and ignores proposals). It is also present in the final
`available: false` event. Clients that predate the weekday values use it for every day.

**Migration (1.9.0).** The weekday values are stored with the weights of the child as `daily_max_weekdays: [mon, ..., sun]`,
only when they differ from 90 for every day, next to the mirror `daily_max_minutes` (the Monday value, only when it is not 90).
An entry that only has the single `daily_max_minutes` of 1.7 or 1.8 reads it as the value of all seven days, and writes the
new keys the next time the maximums are saved.

`progress` holds exactly the values of the three progress sensors. Since 1.5.0 an item with n subtasks is
replaced by its n subtasks, each with weight item weight / n, counted in the period of the subtask's current `date`;
`items`/`completed` then count these entries. It holds using the weighted average and the
same 100 % rule for empty periods. The periods (since 1.3.0; the first public release with `progress`):
- `next_day`: today plus the next school day (Mon–Fri). On Fri, Sat and Sun the next school day is Monday.
  All of today's items count.
- `week`: the Saturday on or before today through the following Friday.
- `next_week`: the following Saturday through Friday.
- `value`: float 0–100.
- `items` and `completed`: counts of the items in that period. Since 1.4.0, **disabled** items are not counted and
  do not affect `value`.
- An entry is `null` when the corresponding sensor is unavailable, e.g. when next week falls outside the fetch window.
  It is also `null` for every period when `available` is false.
- Clients that predate the field ignore it.

`labels` (since 1.3.0) lists the label options configured for this child, in configured order:
`{"id": str, "name": str, "kind": "homework" | "test"}`. The card offers these in the add-label dialog.

`available: false` means that the data is older than 24 h, the entry is not loaded, or the entity was
removed. `items` then holds the last known list, which can be empty. The card shows a "not available" state.

Item (sorted by `due`, then `lesson_hour` (null sorts as 0, i.e. first), then `uid`):

| Field | Type | Meaning |
|---|---|---|
| `uid` | string | `<host>:<childId>:<appointmentId>`; stable key; used in `set_progress` |
| `due` | string | All-day item: a date `YYYY-MM-DD`. Otherwise a local ISO datetime with offset (Europe/Amsterdam), e.g. `2026-11-16T10:00:00+01:00` |
| `date` | string | Local due date `YYYY-MM-DD` (use this to group per day) |
| `all_day` | bool | |
| `lesson_hour` | int \| null | First lesson hour |
| `subject` | string | Subject as shown in titles (Vakken name or the first Omschrijving segment) |
| `info_type` | int \| null | Magister type: 1 Huiswerk, 2 Proefwerk, 3 Tentamen, 4 SO, 5 MO; `null` when the item is in the planner only because of manual labels. **The card translates its own labels from this** |
| `label` | string \| null | The Dutch Magister label. For reference only |
| `manual_labels` | array | Since 1.3.0: `[{"id": str, "name": str, "kind": "homework"\|"test", "note": str}]`, in the order they were added. Only these can be removed. A label whose option was renamed shows its current name. |
| `override` | object \| null | Since 1.4.0: an override of the Magister label: `{"mode": "replace", "label": {"id", "name", "kind"}}` or `{"mode": "disable"}`; `null` when there is none (always `null` when `info_type` is null) |
| `disabled` | bool | Since 1.4.0: no active labels left (the Magister label is disabled and there are no manual labels). The item counts as completed with weight 0 |
| `is_test` | bool | Any **active** label of kind test: the effective Magister label (the replacement's kind if replaced, `info_type` 2–5 if not overridden, none if disabled) or a manual label of kind `test` |
| `text` | string | Magister homework text, plain text: newlines and `- ` bullets, may be empty (manual notes are in `manual_labels`) |
| `cancelled` | bool | The lesson is cancelled (Status 4/5) |
| `has_attachments` | bool | Magister has attachments (not downloadable here) |
| `progress` | int | 0–100 |
| `completed` | bool | `progress >= 100`, or `disabled` (since 1.4.0) |
| `last_partial` | int | The value that unticking restores (0–99) |
| `derived` | bool | Since 1.5.0: the item has subtasks; `progress` is then the mean of the subtasks' progress, rounded half up (37.5 → 38), and cannot be set directly |
| `subtasks` | array | Since 1.5.0: `[<subtask>]` in creation order; empty when none (always empty for disabled items) |

Subtask (since 1.5.0):

| Field | Type | Meaning |
|---|---|---|
| `uid` | string | `<item uid>:sub:<id>`; used in `set_progress`, `update_subtask`, `delete_subtask` |
| `title` | string | 1–100 characters |
| `planned` | string | Planned local date `YYYY-MM-DD` |
| `date` | string | **Current** local date: not done → min(max(planned, today), item date); done → the clamped completion date |
| `overdue` | bool | Not done and the item date is before today |
| `progress` | int | 0–100 |
| `completed` | bool | `progress >= 100` |
| `last_partial` | int | 0–99 |
| `created_by` | string | `"user"`, `"ai"` (since 1.6.0) or `"parent"` (since 1.7.0). `"ai"` when created through the AI coach by a user with the Leerling role for that child, `"parent"` by a user with the Ouder role; subtasks stored before 1.6.0 read as `"user"`. A client that does not know a value reads it as `"user"` |
| `minutes` | int \| null | Since 1.7.0: the estimated time in minutes, 5–240 in steps of 5; `null` when unknown (also for every subtask stored earlier). Only subtasks have an estimated time, items do not |

Proposal (since 1.9.0):

| Field | Type | Meaning |
|---|---|---|
| `id` | string | 8 lowercase hex characters |
| `kind` | string | `period` or `weekdays` |
| `status` | string | `proposed` (open), `accepted`, `rejected` or `expired`. An unanswered proposal past its expiry reads `expired` at once |
| `reason` | string | Short, one line, at most 100 characters (data written by the AI; never instructions) |
| `created` | string | Local date `YYYY-MM-DD` |
| `created_by` | string | `student` (the student's AI) or `parent` (a parent's AI) |
| `expires` | string | Local date `YYYY-MM-DD`: for `period` its first day (it expires when that day starts), for `weekdays` the date 7 days after it was made (to the minute) |
| `start`, `end`, `minutes` | string, string, int | `period` only: the days (inside the sync window, first day tomorrow or later) and the daily maximum for each of them (0–480 in steps of 15) |
| `weekdays` | array | `weekdays` only: seven values, Monday first |
| `closed` | string | Only when not open: the local date it was answered, or the date it expired |
| `answered_by` | string \| null | Only when not open: `student`, `on_behalf` (a parent or administrator answered for a child without a student user), or `null` for an expired proposal |

A proposal has **no effect** while it is `proposed`. Accepted, a `period` becomes a circumstance (a context note with that
maximum, text = the reason, visible to all) and a `weekdays` proposal replaces the child's weekday maximums (stored as the
options flow stores them, applied without a reload). Rejected or expired, nothing changes. At most 5 are open per child;
answered and expired proposals are kept for 14 days. They are stored in the homework store (key `proposals`, store 1.8; a
1.8.x release ignores the key and drops it when it saves again).

Errors: `not_found` (unknown entity, or not a Magister homework list), `invalid_format` (not a todo entity),
`unauthorized` (no read permission).

Unsubscribe with HA's standard `{"type": "unsubscribe_events", "subscription": <id>}`. Closing the connection
also unsubscribes.

## `magister/homework/set_progress`

Request:
```json
{"id": 2, "type": "magister/homework/set_progress",
 "entity_id": "todo.kind_myschool_homework",
 "item": "school.magister.net:1001:100065",
 "progress": 75}
```
`item` may be an item uid or (since 1.5.0) a subtask uid. `progress` must be an integer 0–100 (booleans are rejected). The backend accepts any integer in range.
The card offers the steps 0/25/50/75/100 (PM decision).
- Ticking done = 100.
- Unticking = `last_partial`, sent as an explicit value.

Result (the **stored** values):
```json
{"id": 2, "type": "result", "success": true, "result": {"progress": 75, "completed": false}}
```
A subscribe event with the new state follows.

Errors: `not_found`, `item_not_found` (the uid is not in this entity's list), `item_disabled` (since 1.4.0: restore the
Magister label first), `item_has_subtasks` (since 1.5.0: the item's progress is derived), `invalid_format`, `unauthorized`
(no control permission). For a subtask uid: `item_disabled` when its item is disabled (checked first), otherwise
`item_not_found` when the subtask does not exist or is not visible.

## `magister/homework/appointments` (since 1.3.0)
Lists one day's appointments for the add-label dialog, **including appointments without any label**.

Request:
```json
{"id": 3, "type": "magister/homework/appointments", "entity_id": "todo.kind_myschool_homework", "date": "2026-11-16"}
```
`date` must fall within the fetch window. Otherwise the error is `invalid_date`.

Result:
```json
{"id": 3, "type": "result", "success": true, "result": {"appointments": [
  {"uid": "school.magister.net:1001:100070", "start": "2026-11-16T09:10:00+01:00", "end": "2026-11-16T10:00:00+01:00",
   "all_day": false, "lesson_hour": 3, "subject": "wisB", "cancelled": false,
   "info_type": null, "manual_labels": []}
]}}
```
The appointments are sorted like items. The `uid` format equals the item uid.

Errors: `not_found`, `invalid_format`, `invalid_date`, `unauthorized` (read permission).

## `magister/homework/add_label` (since 1.3.0)
```json
{"id": 4, "type": "magister/homework/add_label", "entity_id": "todo.kind_myschool_homework",
 "appointment": "school.magister.net:1001:100070", "label": "<label option id>", "note": "H3 + H4"}
```
- `note` is optional: a string of at most 200 characters, trimmed; empty means no note.
- Adding the same label twice to an appointment is an error (`label_exists`).
- On success the result is the updated item, in the item format above, and a subscribe event follows.

Errors: `not_found`, `invalid_format`, `appointment_not_found`, `label_not_found` (not in this child's options),
`label_exists`, `unauthorized` (control permission).

## `magister/homework/remove_label` (since 1.3.0)
```json
{"id": 5, "type": "magister/homework/remove_label", "entity_id": "todo.kind_myschool_homework",
 "appointment": "school.magister.net:1001:100070", "label": "<label option id>"}
```
- Removes a **manual** label only. Magister labels cannot be removed.
- Result: `{"item": <item> | null}`. It is `null` when the appointment left the planner because it has no labels any more.
- A subscribe event follows.

Errors: `not_found`, `invalid_format`, `appointment_not_found`, `label_not_found` (the id is not a label option of this child), `label_not_on_appointment`, `unauthorized`.

## `magister/homework/set_override` (since 1.4.0)
Replace, disable or restore the **Magister** label of an appointment.
```json
{"id": 6, "type": "magister/homework/set_override", "entity_id": "todo.kind_myschool_homework",
 "appointment": "school.magister.net:1001:100070", "mode": "replace", "label": "<label option id>"}
```
- `mode` is `replace` (requires `label`, one of this child's label options), `disable`, or `clear` (restore).
- `clear` without an override succeeds and changes nothing. `clear` also succeeds when an override is stored for an
  appointment that no longer has a Magister label: the override is removed. The result item is then `null` when the
  appointment is no longer in the planner.
- Result: `{"item": <item> | null}`; a subscribe event follows.
- In the `appointments` command result, each appointment also carries `override` (same shape as on items).

Errors: `not_found`, `invalid_format` (including `replace` without `label`, or replacing with the original's own default
label), `appointment_not_found`, `no_magister_label` (only for `replace`/`disable`: the appointment has no Magister InfoType 1–5),
`label_not_found`, `unauthorized` (control permission).

## Subtask commands (since 1.5.0)
Control permission. The result is the updated parent item, and a subscribe event follows.

`magister/homework/add_subtask`:
```json
{"id": 7, "type": "magister/homework/add_subtask", "entity_id": "todo.kind_myschool_homework",
 "item": "school.magister.net:1001:100070", "title": "H4 woordjes", "date": "2026-11-15"}
```
`date` is optional (default today). Rules: `today ≤ date ≤ item date`, or exactly the item date when that is not in the future.
`minutes` (since 1.7.0) is optional: an integer 5–240 in steps of 5, or `null` (unknown, the default).

`magister/homework/update_subtask`: `{"entity_id", "subtask": <subtask uid>, "title"?: str, "date"?: "YYYY-MM-DD", "minutes"?: int | null}`. At least one of `title`, `date` or `minutes` must be present; if all are missing the result is `invalid_format`. Since 1.7.0 `minutes` changes the estimate; `null` clears it; leaving it out keeps it. Clearing an estimate that is not set succeeds.

`magister/homework/delete_subtask`: `{"entity_id", "subtask": <subtask uid>}`.

Errors:
- `not_found`, `invalid_format` (the title is empty or longer than 100 characters, or the date format is wrong);
- `item_not_found` (the parent item is not, or no longer, in the list), `subtask_not_found` (an unknown subtask id, or a uid
  without `:sub:`);
- `invalid_date` (outside the allowed range);
- `invalid_minutes` (since 1.7.0: `minutes` is not an integer 5–240 in steps of 5, or `null`; booleans, text and fractions are refused too; nothing is stored);
- `item_disabled`;
- `too_many_subtasks` (at most 20 per item);
- `unauthorized`.

## `magister/homework/respond_proposal` (since 1.9.0)
Control permission, like the other write commands. The user of the connection answers a proposal for the daily maximum:
```json
{"id": 9, "type": "magister/homework/respond_proposal", "entity_id": "todo.kind_myschool_homework",
 "proposal": "a1b2c3d4", "answer": "accept"}
```
`answer` is `accept` or `reject`. (The field is `proposal` and not `id`: `id` is the message id of the WebSocket protocol.)
Result: `{"proposal": <proposal>}`, and a subscribe event follows with the new `proposals` (and, when accepted, the new
`daily_max_overrides` or `daily_max_weekdays`).

Who may answer (`connection.user`, checked on every call, before the proposal is looked up):
- a Home Assistant user linked as **Leerling** for the child;
- only when the child has **no active** Leerling user (none linked, or every linked user is deactivated, system-generated or
  deleted): a user linked as **Ouder** for the child, or an administrator. The
  logbook then says "namens het kind" and the proposal has `answered_by` `on_behalf`;
- nobody else. In particular a parent cannot answer while the child has an active Leerling user, and a user with a stored link as
  both Leerling and Ouder counts as Ouder.

Errors: `not_found` (unknown entity), `invalid_format` (bad `answer`), `not_allowed_for_role` (see above; nothing changes),
`proposal_not_found` (also for the proposal of another child), `proposal_closed` (already answered or expired),
`too_many_notes` (accepting a `period` needs room for one more circumstance: at most 50 notes; the proposal stays open),
`unauthorized` (no control permission).

Logbook (entity of the child's list; only the first name of the Home Assistant user): "Voorstel dagmaximum geaccepteerd
door Anna", "... afgewezen door Anna", with " namens het kind" when answered on behalf, and "voorstel dagmaximum verlopen
(Toetsweek)" when a proposal expires.

## Study timer (since 1.10.0)

A student starts a timer on a subtask that has `minutes`. The timer lives in the backend (per config entry and child, in
the homework store under `timer`), so it keeps running when the card is closed and survives a restart. One timer per
child. When it runs out the integration notifies the notify services (`notify.mobile_app_*`) the administrator chose for
that child (never a parent), creates a persistent notification and fires `magister_study_timer_finished`
(`{"child": <child id>, "subtask": <subtask uid>, "entity_id": <the child's homework to-do entity>}`).

### Payload

```json
"timer": {
  "subtask": "myschool.magister.net:1001:100065:sub:ab12cd34",
  "title": "Opgave 3", "subject": "wiskunde",
  "due": "2026-11-16", "label": "Huiswerk",
  "state": "running",
  "ends_at": "2026-11-13T10:00:00+00:00",
  "minutes": 30,
  "started_at": "2026-11-13T09:30:00+00:00"
}
```

* `timer` is `null` when there is none. `state` is `running` (`ends_at`), `paused` (`remaining`, whole seconds) or
  `finished` (`ends_at` is when it ran out). Compute the countdown from `ends_at` / `remaining`; the payload is not
  pushed every second.
* `minutes` is the length of the current countdown: the subtask's estimate, or the extra minutes after an extend. The
  ring is `remaining / (minutes * 60)`.
* The nonce of the notification buttons is never in the payload.
* `timer_settings`: `{"prewarn_minutes": null | 1..15, "extra_minutes": null | 1..30}` (null is off), always present.

### `magister/homework/timer`

`{"entity_id", "action", "subtask"?, "replace"?, "progress"?}` with `action`:

| action | meaning |
|---|---|
| `start` | needs `subtask` (the uid in the payload). The duration is the subtask's `minutes`. Another timer that runs or is paused gives `timer_running` unless `replace` is true (it is then stopped). A finished timer is replaced and logged as stopped ("Studietimer gestopt"). A subtask that is already at 100 % gives `subtask_completed`. |
| `pause` / `resume` | only from `running` / `paused`, else `timer_wrong_state`. |
| `stop` | removes the timer. With `progress` (0, 25, 50, 75 or 100) it first sets the subtask's progress: one call. |
| `extend` | only when the timer has **finished** (`timer_not_finished` otherwise, for running and paused alike): it runs again for `extra_minutes` (the setting at the moment of the extension, not the one at the start) and can be repeated; the pre-warning does not repeat. The end notification is cleared on every target and its buttons go stale. `extra_not_set` when the student has no extra minutes. |
| `done` | sets the subtask's progress to 100 and removes the timer. |

Result: `{"timer": <timer or null>}` (the timer after the action). Errors: `no_minutes`, `subtask_not_found` (also a
subtask of another child), `subtask_completed`, `no_timer`, `timer_running`, `timer_wrong_state`, `timer_not_finished`, `extra_not_set`,
`not_allowed_for_role`, `not_found`, `invalid_format` (unknown action, `start` without `subtask`, `progress` not one of
the five steps). Control permission on the entity is required, as for the other write commands.

Deleting the subtask, completing it (progress 100, by any route) or hiding its item stops the timer; changing its
`minutes` does not.

### `magister/homework/timer_settings`

`{"entity_id", "prewarn_minutes"?, "extra_minutes"?}`: `null` switches a setting off, a missing key leaves it as it is,
at least one key is required (`invalid_format` otherwise, and for values outside 1-15 / 1-30). Result:
`{"timer_settings": {...}}`.

### Rights

The same rule as `respond_proposal`: a user linked as an active **Leerling** of the child; only when the child has no
active Leerling user, a user linked as **Ouder** or an administrator on the child's behalf. Everyone else gets
`not_allowed_for_role`. Settings follow the same rule.

### Notifications

* Pre-warning: `Nog {n} minuten: {title} ({subject})` (`Nog 1 minuut` for one), no buttons; skipped when the timer is
  not longer than `prewarn_minutes`.
* End: `Tijd is om: {title} ({subject})`, buttons **Klaar** (done), **+x min** (extend, only when `extra_minutes` is
  set) and **Nog niet** (stop without progress change).
* iOS `push.interruption-level: time-sensitive`, `tag` `magister_study_timer_<child id>`, `ttl: 0`, `priority: high`.
  Button ids are `MAGISTER_TIMER|<verb>|<entry id>|<child id>|<appointment>:sub:<id>|<nonce>`; the nonce is random per
  timer, so buttons of an earlier timer are ignored. A stop, done or extend sends `clear_notification` for the tag to all targets, but only when a pre-warning or end notification was actually sent for that timer. An extend also gives the timer a new nonce.
* A persistent notification (`magister_study_timer_<entry id>_<child id>`, title "Studietimer <first name>: tijd is
  om") is created at the end and dismissed on restart, extend, stop, done and when the entry is unloaded or removed (a
  restart of Home Assistant re-creates it from the stored finished timer). **It is visible to every Home Assistant
  user**, unlike the phone notifications, which go only to the child's targets; it therefore carries the first name (or
  initials) only, never the full name.
* Setting the same values again changes, saves and logs nothing. Study timer targets of children that are no longer
  selected are dropped with the rest of the store.
* Button presses arrive as `mobile_app_notification_action`. When the event context has a user, that user needs the
  rights above; without a user the nonce and the configured target are the proof.

## Equivalent services
These target the homework to-do entity and behave the same as the WebSocket commands, for automations:
- `magister.set_homework_progress` (fields `item`, `progress`)
- `magister.add_homework_label` (fields `appointment`, `label` (id **or** name, case-insensitive), `note`), since 1.3.0
- `magister.remove_homework_label` (fields `appointment`, `label` (id or name)), since 1.3.0
- `magister.set_homework_override` (fields `appointment`, `mode` (`replace`|`disable`|`clear`), `label` (id or name, for replace)), since 1.4.0
- `magister.add_homework_subtask` (fields `item`, `title`, `date`?, `minutes`?), `magister.update_homework_subtask` (fields `subtask`, `title`?, `date`?, `minutes`? (null clears)),
  `magister.delete_homework_subtask` (field `subtask`), since 1.5.0; `minutes` since 1.7.0. A wrong `minutes` is a `ServiceValidationError` with translation key `homework_invalid_minutes`.

## AI coach (since 1.6.0, roles since 1.7.0)
The LLM API `magister_coach` (for HA's MCP Server) uses the same subtask rules and errors as the commands above; its
tool errors are `{"error": <code>, "message": ...}`. Changes in 1.7.0:
- Every child is linked to users in one of two roles: **Leerling** (`student`, option `students`) and **Ouder**
  (`parent`, option `parents`). A 1.6.0 `users` list is read as `students` while `students` is missing. One user
  cannot be in both lists of a child (the options flow refuses it; a stored overlap is treated as `parent`).
- `list_children` returns `{"id", "name", "role", "daily_max_minutes"}` per child.
- New read tool `get_overview(start, end)` (at most 31 days, inclusive; errors `invalid_format`, `not_linked`): for every
  accessible child `{"child", "name", "role", "daily_max_minutes", "days": [...]}`; a day is `{"date", "weekday", "tests",
  "assignments", "cancelled", "open_items", "planned_minutes", "daily_max_minutes", "over_daily_max"}`. `tests`,
  `assignments` and `cancelled` are the non-disabled items due that day (`{"id", "subject", "label", "cancelled",
  "manual_labels", "progress", "completed", "subtasks"}`, ids without the host, no text, no teacher data). `label` is
  the effective label (the replacement when the label is overridden). Items of a cancelled lesson are listed only
  under `cancelled` (their `cancelled` is `true`) and are not counted in `tests`, `assignments` or `open_items`;
  `open_items` is the number of the items in `tests` and `assignments` not completed; `planned_minutes` the sum
  of `minutes` of the subtasks whose current `date` is that day, done or not; this includes the subtasks of cancelled
  items.
- `list_homework`, `get_progress` and the write tools return subtasks with `minutes` and `created_by`. `add_subtask` and
  `update_subtask` accept `minutes` (error `invalid_minutes`; `null` clears on update). Subtasks made through the coach get
  `created_by` `"parent"` for the Ouder role and `"ai"` for the Leerling role.
- `set_progress` fails with `not_allowed_for_role` for a child where the caller has the Ouder role: nothing is written or
  logged. Parents read progress only; ticking in the card stays possible for any Home Assistant user.
- Logbook: writes by a parent read "Ouder via AI: …", by a student "AI-coach: …".

### Changes in 1.7.1
- `list_homework` without `start` lists the open overdue items (due before today, not completed, not disabled) of the
  last 7 days only: due date >= today - `overdue_days`. `overdue_days` is a new integer argument, 1 to 35, default 7;
  anything else (0, 36, a float, a string, a bool) is `invalid_format`. `include_overdue: false` still switches the
  overdue part off, and with a `start` there is no overdue part.
- Items with `cancelled: true` are never overdue. They are still listed, marked `cancelled: true`, when they fall
  inside the requested `start`-`end` window.
- New error `coach_not_enabled` for every tool (and `list_children`, as its `message`, and the prompt): the user is
  linked (as student or parent) to at least one child whose coach is not enabled and to no enabled child. The message
  is "You are linked, but the AI coach is not enabled for this child. An administrator can enable it in Settings >
  Devices & services > Magister > Configure > AI coach > Settings per child." It names no child and reveals nothing
  but the linking. `not_linked` stays for a user without any link (and for an unknown, inactive or system user).

## Time planning and proposals (since 1.9.0)
The student decides about their own study plan and time. The AI never sets a daily maximum itself: every change is a
**proposal** that the student accepts (on the card, or in the conversation after an explicit "yes"). A proposal made through a
parent's AI needs the student's acceptance too.

Changes to the coach tools:
- `list_children` also returns `daily_max_weekdays` (seven values, Monday first); `daily_max_minutes` is the Monday value.
- In `get_overview` the child-level `daily_max_minutes` is the Monday value only: use `daily_max_weekdays` (and the `daily_max_minutes` of each day, the effective maximum).
- `get_overview`: every child has `daily_max_weekdays`; a day's `daily_max_minutes` is the **effective** maximum of that
  date (the lowest circumstance, else that weekday's value); `daily_max_period` as before (no `text` for a student when the
  circumstance is `parents`-only); `proposal` is `null` or `{"id", "minutes"}`: the open `period` proposal that covers the
  day (the lowest `minutes`; not accepted yet, so without effect).
- `add_context` and `update_context` refuse a `daily_max_minutes` that is not `null` with `use_proposal`; nothing is stored.
  A circumstance that already has a maximum keeps it, and `update_context` with `null` still removes it. `update_context` also
  refuses with `use_proposal` (nothing changes) a change of `start`/`end` of a circumstance that has a maximum when the new
  days include a day outside the current days (moving or extending); shortening is allowed, and so is changing the days
  together with `daily_max_minutes: null`. Circumstances without a maximum can be moved freely.
  A circumstance with a maximum always has `visibility: "all"` (the student decides about their own time; notes stored before 1.9.0 can still be parents-only, and their text can be edited): `update_context`
  refuses `visibility: "parents"` for it with `invalid_format`, unless the same call sets `daily_max_minutes: null`. An accepted
  proposal creates a visible note.
- New tools (all take the optional `child`):

| Tool | Annotations | Notes |
|---|---|---|
| `list_proposals(include_closed?)` | read-only | `{"child", "today", "you_may_answer", "proposals": [...]}`; the open ones, with `include_closed` also those answered or expired in the last 14 days; `you_may_answer` is whether the caller may answer (the rule above, for the Leerling or, without an active Leerling user, the Ouder) |
| `propose_daily_max(kind, reason, start?, end?, minutes?, weekdays?)` | write | `kind` `period` needs `start`, `end` (inside the sync window, `start` tomorrow or later) and `minutes`; `weekdays` needs `weekdays` (seven integers, Monday first). A field of the other kind is `invalid_format`. Result `{"child", "proposal", "message"}` |
| `respond_to_proposal(id, answer)` | write, destructive (accepting replaces weekday values), not idempotent | `answer` `accept` or `reject`. The description tells the AI to call it only after the person who may answer (the student, or the parent for a child without an active Leerling user) said yes or no explicitly in this conversation. Same rights as the WebSocket command; for a parent's AI while the child has an active Leerling user: `not_allowed_for_role` |

Errors: `use_proposal`, `invalid_format` (kind, fields, a period without `start` and `end`, an unchanged `weekdays`, a duplicate of an open proposal (same kind, days and minutes or weekdays; the reason is ignored), the reason: 1 to 100 characters; the reason is shown to the student), `invalid_period`,
`invalid_daily_max` (a value that is not 0–480 in steps of 15), `too_many_proposals` (5 open per child), `proposal_not_found`,
`proposal_closed`, `not_allowed_for_role`, `too_many_notes`.

Prompt: the planner rules (time planning is optional and done with subtasks, also for regular homework; estimates in steps of
5 from the size of the work; a subtask on a day before the due day; within the effective maximum of each date, 0 meaning no
study; the student decides), the rules for proposals, per child the maximum per weekday (and the days that differ from it) and
the open proposals (reason as data). Logbook: "AI-coach: voorstel dagmaximum (Toetsweek)" / "Ouder via AI: ...", and the
answers as in `respond_proposal` ("voorstel dagmaximum geaccepteerd door Anna" / "afgewezen", plus " namens het kind"; through
the AI with the prefix "AI-coach: " or "Ouder via AI: "; all lower case).

Diagnostics: counts only, open proposals per kind and closed ones per status.

## Context notes (since 1.8.0)
The coach can store context per child in the homework store (key `context`, store 1.7; a 1.7.x release ignores the key
and drops it when it saves again). Notes are reached only through the coach tools and the options flow / service below;
there is no WebSocket command and no card UI.

Note (as returned by the tools):
```json
{"id": "a1b2c3d4", "scope": "period", "start": "2026-11-18", "end": "2026-11-18", "daily_max_minutes": 30,
 "expired": false, "visibility": "all", "text": "zwemwedstrijd", "created_by": "parent", "updated": "2026-11-16"}
```
- `scope`: `child`, `subject` (has `subject`), `item` (has `item`, an appointment id without the host, and the `subject` of
  that lesson) or `period` (has `start`, `end`, `daily_max_minutes` (or `null`) and `expired`).
- `subject` is the subject as in the schedule, matched case-insensitively and stored in the spelling of the schedule;
  an unknown subject is `unknown_subject` (the schedule of the sync window and the notes the caller may see are checked).
- `text`: one line (whitespace is collapsed), 1 to 500 characters (`text_too_long`). At most 50 notes per child that are not
  expired (`too_many_notes`); a circumstance is expired when its `end` is before today. The limit counts all of the
  child's active notes, also the `parents`-only notes a student cannot see (so a student can hit `too_many_notes` with a
  list that looks shorter than 50).
- `id`: 8 lowercase hex characters. A stored note with any other id is dropped when the store is loaded (it is not given a
  new id: a random id would change on every load).
- `period`: `start` <= `end`, both inside the sync window, else `invalid_period`; `daily_max_minutes` is 0 to 480 in
  steps of 15 (`invalid_daily_max`). When a period is changed, only the days that are given are held to the window
  (a new `start` is not before its first day, a new `end` not after its last day nor before its first day, a new `start`
  not after its last day) and `start` <= `end` always holds, with the stored day for the one that is not given; a circumstance that began before the window can still get a new text,
  end or maximum. `invalid_period` then says which given day is wrong. With neither `start` nor `end` the days are not
  checked. It applies to every day of the period, also after it has ended (past days stay
  visible in the card). A period is deleted when its `end` is before the first day of the sync window.
- Item notes are deleted 14 days after their appointment left the sync window, like the other planner data of the item.
  `item_not_found` when an appointment is not in the window.
- `visibility`: `all` or `parents`. Only the Ouder role can set `parents`; a Leerling gets `not_allowed_for_role`. A student
  never sees a `parents` note: it is not listed, and update or delete answers `context_not_found`.
- A student cannot change or delete a note whose `created_by` is `parent` (`not_allowed_for_role`). A change by a parent makes
  the note the parent's (`created_by` `parent`).
- `created_by`: `student` (the Leerling role) or `parent`. `updated` is the local date of the last change.

Tools (all take the optional `child`, as before):
| Tool | Annotations | Notes |
|---|---|---|
| `list_context(scope?, subject?, item?, include_expired?)` | read-only | Returns `{"child", "today", "notes": [...]}`; expired circumstances only with `include_expired` |
| `add_context(scope, text, subject?, item?, start?, end?, daily_max_minutes?, visibility?)` | write | Fields that do not belong to the scope are `invalid_format`; `daily_max_minutes: null` means "not given"; since 1.9.0 a number is refused with `use_proposal` |
| `update_context(id, text?, start?, end?, daily_max_minutes?, visibility?)` | write, idempotent | At least one field (`invalid_format` otherwise); `daily_max_minutes: null` removes the maximum; since 1.9.0 a number is refused with `use_proposal` |
| `delete_context(id)` | destructive | |
| `clear_context(subject?)` | destructive | Parents only (`not_allowed_for_role`); a subject takes its subject and item notes; returns `{"child", "deleted"}` |

Errors: `text_too_long`, `too_many_notes`, `unknown_subject`, `item_not_found`, `invalid_period`, `invalid_daily_max`,
`context_not_found` (also for the note of another child, another login, or a `parents` note for a student),
`not_allowed_for_role`, `invalid_format` (also a malformed id).

- `list_homework` items have `context`: the item's notes and its subject's notes the caller may see.
- `get_overview` days: `daily_max_minutes` is the **effective** maximum (the lowest `daily_max_minutes` of the periods that
  cover the day, else the child's daily maximum (since 1.9.0 that weekday's maximum); a period can also raise it). `daily_max_period` is `null` or
  `{"id", "text"?}`: the period that sets it (on equal maximums the one the caller may see), without `text` when it is
  `parents`-only and the caller is a student. It is `null` when the deciding period is `parents`-only, the caller is a
  student and its maximum equals the normal one. The child-level `daily_max_minutes` of the overview is the normal maximum.
- Prompt: first the rules for context (once, before the children), then per child the `child` notes, the periods that have
  not ended and the days with another maximum, only what the caller may see (the maximums of parents-only periods are
  shown as numbers, without text).
- Logbook (no note text): "AI-coach: context toegevoegd (Engelse taal)", "... gewijzigd", "... verwijderd", and "Ouder via AI:
  context gewist (Engelse taal)" / "alle context gewist"; the subject is named when the note has one, except for a `parents`-only note (also one that was `parents`-only before
  an update, and a clear that deleted only such notes). A write that changes
  nothing is not logged.

Outside the AI:
- Options flow: Configure > AI coach > Context wissen (child; all context or a subject that has notes; confirmation with the
  number of notes).
- Service `magister.clear_coach_context` (`config_entry_id`, `child` (id or name), `subject`?; administrators only) with a
  response `{"deleted": <number>}`. `ServiceValidationError` keys: `entry_not_loaded`, `child_not_found`, `child_ambiguous` (a name or id that matches
  more than one child).
- Removing a child from the integration, or the config entry, removes its notes. Diagnostics: counts per scope and the
  number of parents-only notes.
