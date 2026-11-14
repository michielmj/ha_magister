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
  }
}}
```

`progress` holds exactly the values of the three progress sensors, using the weighted average and the
same 100 % rule for empty periods. The periods (since 1.3.0; the first public release with `progress`):
- `next_day`: today plus the next school day (Mon–Fri). On Fri, Sat and Sun the next school day is Monday.
  All of today's items count.
- `week`: the Saturday on or before today through the following Friday.
- `next_week`: the following Saturday through Friday.
- `value`: float 0–100.
- `items` and `completed`: counts of the items in that period.
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
| `is_test` | bool | `info_type` 2–5, or any manual label of kind `test` |
| `text` | string | Magister homework text, plain text: newlines and `- ` bullets, may be empty (manual notes are in `manual_labels`) |
| `cancelled` | bool | The lesson is cancelled (Status 4/5) |
| `has_attachments` | bool | Magister has attachments (not downloadable here) |
| `progress` | int | 0–100 |
| `completed` | bool | `progress >= 100` |
| `last_partial` | int | The value that unticking restores (0–99) |

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
`progress` must be an integer 0–100 (booleans are rejected). The backend accepts any integer in range.
The card offers the steps 0/25/50/75/100 (PM decision).
- Ticking done = 100.
- Unticking = `last_partial`, sent as an explicit value.

Result (the **stored** values):
```json
{"id": 2, "type": "result", "success": true, "result": {"progress": 75, "completed": false}}
```
A subscribe event with the new state follows.

Errors: `not_found`, `item_not_found` (the uid is not in this entity's list), `invalid_format`, `unauthorized`
(no control permission).

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

## Equivalent services
These target the homework to-do entity and behave the same as the WebSocket commands, for automations:
- `magister.set_homework_progress` (fields `item`, `progress`)
- `magister.add_homework_label` (fields `appointment`, `label` (id **or** name, case-insensitive), `note`), since 1.3.0
- `magister.remove_homework_label` (fields `appointment`, `label` (id or name)), since 1.3.0
