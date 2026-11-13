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
  "progress": {
    "tomorrow":  {"value": 100.0, "items": 0, "completed": 0},
    "week":      {"value": 25.0,  "items": 18, "completed": 4},
    "next_week": null
  }
}}
```

`progress` (since 1.2.0) holds exactly the values of the three progress sensors (tomorrow, this week Mon–Sun,
next week Mon–Sun), using the weighted average and the same 100 % rule for empty periods.
- `value`: float 0–100.
- `items` and `completed`: counts of the items in that period.
- An entry is `null` when the corresponding sensor is unavailable, e.g. when next week falls outside the fetch window.
  It is also `null` for every period when `available` is false.
- Clients that predate 1.2.0 ignore the field.

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
| `info_type` | int | 1 Huiswerk, 2 Proefwerk, 3 Tentamen, 4 SO, 5 MO. **The card translates its own labels from this** |
| `label` | string | The Dutch label (Huiswerk/Proefwerk/Tentamen/SO/MO). For reference only |
| `is_test` | bool | `info_type` 2–5 |
| `text` | string | Homework text, plain text: newlines and `- ` bullets, may be empty |
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

## Equivalent service
`magister.set_homework_progress` (target: the homework to-do entity; fields `item`, `progress`) behaves
the same as `set_progress`, for automations.
