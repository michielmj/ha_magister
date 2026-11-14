# M7 — Homework planner enhancements (release 1.3.0)

| | |
|---|---|
| Status | **Approved by PM (2026-11-14)**, via the survey answers below |
| Branch | `claude/jolly-mayer-i2h3oo` (a new PR for 1.3.0; 1.2.0 was merged and installed on 2026-11-14) |
| Refs | M5, M6 · `docs/reference/homework-websocket.md` (binding, updated for 1.3.0) |

## PM decisions (survey 2026-11-14)
| # | Decision |
|---|---|
| 1 | "Show completed" and "Show past" become **switches on the card**. The card config sets the start position, and changes on the card are **remembered per browser** (localStorage, per card). |
| 2 | **School days = Monday–Friday.** |
| 3 | The **"next day"** period replaces "tomorrow": **all of today's homework** (done and not done) **plus the next school day's homework**. The next school day is Mon–Fri after today, so on Friday, Saturday and Sunday it is Monday. |
| 4 | **This week = Saturday–Friday**, and **next week = the following Saturday–Friday**. On a Saturday "this week" already means the coming school week. |
| 5 | **Manual labels** are added **in the card**: pick a day, then a lesson, then a label, plus an optional note. |
| 6 | The labels you can choose from are **configured per child** under Configure → Labels. Each label has a name and a kind (**homework** or **test**). Its weight is set under Homework weights. The list starts with the five Magister names. A label that is in use cannot be deleted. |
| 7 | A manual label may be added to a lesson that **already has a Magister label**. **Only manual labels can be removed.** |
| 8 | A manual label has an optional **note** (short free text), shown like Magister's homework text. |
| 9 | Manual labels also appear in **calendar titles**, after the Magister label: `[Proefwerk] [Toetsweek] wisB`. |
| 10 | A **card language** setting: Automatic (follows HA), Nederlands, English. |
| 11 | All of this ships as **1.3.0**. 1.2.0 was already merged and installed. |

## Design

### Periods (backend; one implementation for the sensors and the payload, as in M6)
- `next_day` covers the local dates from today up to and including the next school day:
  - Mon–Thu: today + tomorrow.
  - Fri: Friday + Monday (Sat and Sun are not included).
  - Sat/Sun: today (normally without homework) + Monday.

  **All** of today's items count, done and not done, so the percentage shows how much of today's and the next
  school day's work is finished.
- `week` covers the Saturday on or before today through the following Friday.
- `next_week` covers the Saturday after that through its Friday.
- `next_week` must fit in the fetch window: weeks ahead ≥ 2, as now, with the repair kept.
- Sensors and bars: "Huiswerk volgende schooldag", "deze week", "volgende week" (EN: "next school day", "this week",
  "next week").
- The existing **unique ids stay the same**, so the old `:homework:tomorrow` id is reused for next_day. Users keep
  their entity ids and history; only the display name changes. The README says so.
- The WebSocket `progress` key is renamed from `tomorrow` (1.2.0) to `next_day`. The card ships in the same bundle, so no compatibility shim is needed.

### Manual labels (backend)
- **Label configuration** per child, stored in the entry options as
  `labels[child_id] = [{"id": str (stable, generated), "name": str, "kind": "homework"|"test"}]`.
  - Default (when not configured): the five Magister names with their kinds (Huiswerk = homework, the rest = test).
  - Options flow: a new menu item **"Labels"** to choose a child, then add, rename or delete labels and set their kind.
    Deleting a label that is still in use is refused with an error.
  - A label change triggers **no reload and no Magister call**; the change is recomputed locally, as with the weights.
- **Weights:** the weights step lists the labels per child: the 5 Magister types plus the configured manual labels
  (by id). The weight of an item with several labels is the **maximum** of its label weights, times the subject weight.
- **Storage:** the progress store moves to schema **v2**, with `items[uid].labels = [{"id": label_id, "note": str, "added": iso}]`.
  - A migration from v1 is needed.
  - Pruning follows the same rules as progress: kept while the appointment exists, deleted 14 days after it has gone.
- **Item set:** a homework item is any appointment in the window that has a Magister InfoType 1–5 **or** at least
  one manual label. Removing the last manual label from an appointment without a Magister label takes it out of the
  planner. Its progress is kept in the store under the normal pruning rules.
- `is_test` is true when the Magister type is 2–5 **or** any manual label is of kind test.
- **Calendar titles** get the manual label names as extra `[Name]` prefixes after the Magister ones. The calendar entity
  updates when labels change.
- **Services** (for automations, with the same validation as the WebSocket commands): `magister.add_homework_label`
  (entity_id, appointment, label, note) and `magister.remove_homework_label` (entity_id, appointment, label).

### Card
- **Header switches** for show completed and show past (an icon toggle with tooltip, or chips). The start position comes
  from the config; changes are stored in localStorage under a key per card (entity + a card id). Saving the card
  config resets them.
- **Language** option `language: auto | nl | en` (default auto), in the visual editor.
- **Add label:** a "+" button in the header opens a dialog.
  - Pick a date: today by default, restricted to the dates in the window.
  - The dialog then lists that day's lessons, with subject, lesson hour, time and any existing labels.
  - Choose a label (from the child's configured list), type an optional note, and save.
  - A lesson that already has the same manual label cannot get it a second time.
  - The dialog works on a phone and with the keyboard.
- **Label chips:** Magister labels as now; manual labels get a distinct style (e.g. outlined) and an **×** to remove
  them, with confirmation. The note is shown as text, under any Magister text.
- **Bars** use the new period names.
- README screenshots updated (placeholder data), NL/EN docs.

## Phases (each: Developer → Reviewer)
- **Phase A, backend:**
  - periods
  - the label configuration and options flow
  - the store v2 migration
  - manual labels in items, sensors, calendar titles and services
  - the WebSocket commands per the contract
  - translations and tests
- **Phase B, card:**
  - header switches with persistence
  - the language option
  - the add-label dialog and removable chips
  - bars renamed
  - tests, bundle, screenshots, README
- Then **release 1.3.0**: a new PR, squash-merge, publish `v1.3.0`.

## Acceptance criteria
- [ ] Both phases reviewed; CI green.
- [ ] **PM test on HAOS:**
  - the card switches work and are remembered;
  - the card language can be forced to NL;
  - on Fri/Sat/Sun the next-day bar and sensor cover Monday;
  - on Saturday "this week" shows the coming school week;
  - configure a "Toetsweek" label of kind test;
  - add it with a note to a lesson in the card;
  - check that it appears on the card, in the calendar title and in the progress;
  - remove it again (Magister labels have no ×);
  - try to delete a label that is in use (refused).
