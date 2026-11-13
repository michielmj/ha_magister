# M5 — Homework planner (release 1.1)

| | |
|---|---|
| Status | **Approved by PM (2026-11-13)**, with the open points answered |
| Branch | `claude/jolly-mayer-i2h3oo` |
| Refs | HLD §4–§8 · PM survey 2026-11-13 |

## Goal

A homework planner per child: all homework and test items from Magister as a to-do list that
parents and children can work through. Progress is tracked in percent, shown on our own
**Homework planner card**, and summarised by progress sensors for automations.

## PM decisions (survey 2026-11-13)

| # | Decision |
|---|---|
| 1 | Progress and done status are stored **in Home Assistant only**. Nothing is written back to Magister. |
| 2 | Items are **Huiswerk and tests**: InfoType 1 Huiswerk, 2 Proefwerk, 3 Tentamen, 4 SO, 5 MO. Not InfoType 6 Informatie. |
| 3 | Homework on **cancelled lessons is shown**, marked "lesson cancelled". |
| 4 | Past homework is what lies in the fetch window ("weeks back" option). It is not archived beyond that. |
| 5 | **One card per child.** |
| 6 | Ships after 1.0, as **1.1**. |
| 7 | **Progress in percent** (0–100) per item. Marking an item done sets it to 100 %. |
| 8 | **Progress sensors per child**: average completion for **tomorrow**, **this week** and **next week**. |
| 9 | Empty period → **100 %** (attribute `items: 0`). |
| 10 | Progress control in **steps of 0/25/50/75/100**. |
| 11 | **Weighted average**, with weights configurable **per child per type** (Huiswerk, Proefwerk, Tentamen, SO, MO) **and per subject**. The default is 1. |

## Out of scope

Writing to Magister, archiving older homework, editing homework text, adding custom (non-Magister) items, notifications
(automations can be built on the sensors and the to-do list). More card features follow in later milestones.

## Design

### Data model and storage
- **Homework item** = one Magister appointment with InfoType 1–5. Key: `<host>:<childId>:<appointmentId>`.
  Fields from Magister: due (appointment start), all-day flag, subject (`Appointment.subject`), label
  (`Huiswerk`/`Proefwerk`/`Tentamen`/`SO`/`MO`), text (`Inhoud` → plain text), cancelled flag (Status 4/5),
  lesson hour, has-attachments.
- **Progress store** (`homeassistant.helpers.storage.Store`, one per config entry): `{item_key: {"progress": 0–100,
  "last_partial": 0–99, "updated": iso}}`.
  - Progress 100 = done.
  - Unticking restores `last_partial`, the last value below 100 (default 0).
  - Entries for items that have left the fetch window for more than 14 days are pruned.
  - The store survives restarts and Magister refreshes. If Magister changes the homework text,
    the progress is kept.
- An item that disappears from Magister disappears from the planner. Its stored progress is pruned later.

### Backend (integration)
- **To-do entity per child** (`todo` platform, HA native), named "Huiswerk"/"Homework":
  - The items are the homework items in the fetch window. `summary` = `[Label] subject`, `due` = date (or datetime),
    `description` = the text plus "Les vervallen" for cancelled items plus the progress "(40 %)" when it is between 0 and 100.
  - Status `completed` when progress = 100, otherwise `needs_action`.
  - Supported features: `UPDATE_TODO_ITEM` (status only). Completing an item sets 100; reopening restores
    `last_partial`. No create/delete/move (the items come from Magister).
  - This makes the planner usable in HA's own to-do view, the mobile app, voice and automations.
- **Service** `magister.set_homework_progress` (`entity_id` of the to-do entity, `item` uid, `progress` 0–100) for
  automations and the card.
- **WebSocket API** for the card:
  - `magister/homework/subscribe` (entity_id). It sends the full item list (all fields above plus
    progress) and pushes updates on changes.
  - `magister/homework/set_progress`.
  - Both require an authenticated HA user. They are read/write only for the entry's own items.
- **Progress sensors per child** (3, created automatically with the to-do entity): "Huiswerk morgen",
  "Huiswerk deze week", "Huiswerk volgende week".
  - Unit %, state class measurement.
  - Value = the **weighted** average of the progress of the items due in that period:
    Σ(w·p)/Σ(w), with w(item) = type_weight(child, type) × subject_weight(child, subject).
    The default weight is 1. A weight of 0 excludes the item from the average (it is still shown on the card).
    If every item in the period has weight 0, the value is 100 % (same as an empty period). Tomorrow = the local date + 1.
    This week = Mon–Sun of the current week, including the days already past. Next week = the following Mon–Sun.
  - No items in the period → **100 %** (nothing left to do). The attribute `items: 0` tells "nothing to do" apart from "all done". *(Open point 1.)*
  - Attributes: `items`, `completed`, `open`, `tests` (count of InfoType 2–5).
  - Recalculated on progress changes, on coordinator updates and at Amsterdam midnight.
  - Next week must fit in the fetch window: weeks ahead ≥ 2 (the default is 3). If it doesn't, the sensor is unavailable and a repair issue is raised.
- Both the to-do entity and the sensors follow the 24 h availability rule.

### Weights (options flow)
- A new options-menu step **"Huiswerkgewichten / Homework weights"**: choose a child, then
  - **per type**: 5 number fields (Huiswerk, Proefwerk, Tentamen, SO, MO), 0–10 in steps of 0.5, default 1;
  - **per subject**: one number field per subject currently in that child's homework data (`Appointment.subject`,
    e.g. "Duitse taal", "wisB"), 0–10 in steps of 0.5, default 1. Weights saved for subjects that are no longer in the data
    are kept, so they reappear when the subject comes back.
- Only values ≠ 1 are stored, in the entry options under `weights[child_id] = {"types": {...}, "subjects": {...}}`.
  Subject matching is exact and case-insensitive (like the sensor exclusions).
- Changing weights recomputes the sensors **without a reload or an API call** (no extra Magister traffic).
- The sensor attributes show the effective weights used (types and the subjects present in the period).
- The options flow becomes a menu: "General settings" (the existing options) and "Homework weights".

### Homework planner card (frontend)
- **Tech**: TypeScript + Lit (the HA standard), built with Vite into one ES module
  `custom_components/magister/frontend/magister-homework-card.js`.
  - The integration serves it through a static path and registers it automatically as a frontend module
    (`add_extra_js_url`), so no manual resource step and still **one HACS install**.
  - **Delivery:** the built bundle is committed. CI rebuilds it and fails if it differs, so source and bundle cannot drift.
- **Card** `custom:magister-homework-card`, config: `entity` (the child's to-do entity, required), `show_completed`
  (default false), `show_past` (default false), `days_ahead` (default 7), `title` (optional).
  - A visual card editor with an entity picker restricted to Magister homework to-do entities, and toggles.
- **Layout**: grouped per day ("Vandaag", "Morgen", weekday + date). Per item:
  - a checkbox
  - the label chip (Huiswerk / Proefwerk / …, tests visually emphasised)
  - the subject
  - the homework text (collapsed after 2 lines, tap to expand)
  - a "les vervallen" marker
  - an attachment hint
  - a **progress control**: a slider or 0/25/50/75/100 steps. Done = 100 %. Unticking restores the previous value.
- Completed items are hidden unless `show_completed`, and then shown with an untick option.
  Past days are hidden unless `show_past`.
- Card texts in NL/EN following `hass.language`. Light/dark theme via HA CSS variables. Mobile-friendly.
  Accessible (keyboard, labels).
- Live updates through the WebSocket subscription.

## Phases (each phase: Developer → Reviewer)
- **Phase A, backend**: store, to-do entity, service, WebSocket API, progress sensors, repair, translations, tests.
- **Phase B, card**: the Lit card plus editor, the build pipeline (Vite, TypeScript, ESLint, Vitest), CI checks for the bundle,
  auto-registration, README section (NL+EN) with screenshots made from fixture data only.
- Then a **release 1.1.0**: PR, merge, tag.

## Acceptance criteria
- [ ] Both phases reviewed and approved; CI green (Python and frontend jobs).
- [ ] **PM test on HAOS:** for each child a Homework to-do list and 3 progress sensors appear.
      Add the Homework planner card per child via the dashboard editor. Then:
  - tick an item off and untick it
  - set 50 % on a Proefwerk item
  - check that the progress sensors follow
  - check the same items in HA's own to-do view
  - check that cancelled-lesson homework is marked
  - check the progress survives an HA restart

## Open points for the PM (answered 2026-11-13, see decisions 9–11)
1. **Empty period**: with no homework tomorrow, should the progress sensor show **100 %** (proposed: nothing left to do;
   the attribute says 0 items) or **unknown**?
2. **Progress control**: a free **slider** (0–100) or **steps** of 0/25/50/75/100 (proposed: steps, easier on a phone)?
3. **Weighting**: count every item equally in the average (proposed), or count tests more heavily?
