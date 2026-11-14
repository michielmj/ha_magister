# M11 — Parent study planner via MCP (release 1.7.0)

| | |
|---|---|
| Status | **Draft — awaiting PM approval of the parent guidelines (§4) and the scope** |
| Branch | `claude/jolly-mayer-i2h3oo` |
| Refs | M10 · `docs/reference/homework-websocket.md` · `custom_components/magister/coach.py` |

## Goal
Let a parent build a study plan for each child with their own AI assistant. The plan consists of subtasks with an
**estimated time**, spread over the days before tests and assignments, and within a daily maximum. The parent can also
get an **overview across all their children**.

## PM decisions (2026-11-14)
| # | Decision |
|---|---|
| 1 | The same tools as the student coach, with **parent guidelines** and an **overview across all children** (no changes to settings, label options or weights). |
| 2 | The parent connects **the same way as students**: their HA user is linked to each child under AI-coach, with the role **Ouder**. It uses the same MCP Server setup (main endpoint `/api/mcp`). |
| 3 | Subtasks get an **estimated time**. The plan respects a **daily maximum**, and the card shows the planned time per day. |
| 4 | Subtasks made through a parent's AI are marked **"Ouder"** instead of "AI". The child can still edit and tick them. |
| 5 | The parent assistant sees the **same data** as the student coach: no teacher names or codes. |
| 6 | 1.6.0 (student coach) is released first; this is 1.7.0. |

## Roles and linking (options flow "AI-coach", per child)
- The single "linked HA users" list is replaced by two lists:
  - **Leerling** (student users);
  - **Ouder** (parent users).
- A user may not be in both lists for the same child. The flow refuses that with a translated error.
- **Migration:** users linked in 1.6.0 become Leerling. There is no config-entry version change. The old `users` key
  is read as `students` when `students` is missing.
- **Guidelines:**
  - the per-child **student** guidelines stay as in 1.6.0;
  - new: one **parent guidelines** text per config entry, under AI-coach, then "Ouder-richtlijnen". Empty means the default in §4, and it has a reset option.
- **Daily maximum** per child (new): **study minutes per school day**, default 90, range 15–480, step 15. It is
  stored with the child's homework settings, because the card uses it as well as the AI.
- Access rule as in 1.6.0: the coach must be enabled, and the user active, not a system user and linked in either role.

## Estimated time on subtasks
- New optional subtask field `minutes`: an integer from 5 to 240 in steps of 5, or null (unknown).
  - It is stored with the subtask. The store minor version goes up (major stays 1); 1.6.0 ignores the field, so
    downgrade is safe.
  - It is shown in the payload.
- `add_subtask` and `update_subtask` accept `minutes`, in the WebSocket API, the services and the coach tools. On update,
  `null` clears it. A new error `invalid_minutes` is added.
- Only subtasks have an estimated time (PM decision 3); items do not.

## `created_by`
- The values become `"user" | "ai" | "parent"`:
  - `"ai"` for a subtask created through the coach by a user with the Leerling role for that child;
  - `"parent"` for a subtask created by a user with the Ouder role.
- 1.6.0 reads an unknown value as "user", so the downgrade is safe.

## Tools (additions to `magister_coach`; all tools stay scoped to the linked children)
- **`get_overview(start, end)`** (read-only, max 31 days): for every accessible child and every day, the tests and
  assignments due, the open homework count, the planned subtask minutes, and the daily maximum. It replaces
  calling `list_homework` once per child for "how busy is everyone next week".
- **`list_children`** additionally returns the caller's **role** for each child and the child's **daily maximum**.
- **`list_homework` and `get_progress`:** subtasks include `minutes` and `created_by`.
- **`add_subtask` and `update_subtask`:** accept `minutes`.
- **The prompt**, for each accessible child, contains:
  - the role;
  - the daily maximum;
  - the matching guidelines: student guidelines for Leerling, parent guidelines for Ouder.
  
  It also tells the AI to keep each day's planned minutes within the maximum, using `get_overview`.
- **Logbook:** writes by a parent are logged as "Ouder via AI: deelstap … toegevoegd aan …". Writes by a student stay "AI-coach: …".

## Card
- **Subtask rows:**
  - show the estimated time (e.g. "30 min") when it is set;
  - the "AI" chip stays for `"ai"`, and a new **"Ouder"** chip appears for `"parent"`, with an accessible label (NL "Aangemaakt door ouder via AI", EN "Created by parent via AI").
- **Day headers** show the planned time: "± 1 u 15 min gepland", the sum of the open and completed subtask minutes with that current date.
  - If the sum exceeds the child's daily maximum, it is shown in a warning style with an accessible text such as "boven dagmaximum (1 u 30 min)".
- **The add and edit subtask forms** get an optional "Geschatte tijd" field: a select with —, 15, 30, 45, 60, 90, 120, 180 and 240 minutes.
  - When an existing value is not in the list, it is kept and shown.
- The payload provides the daily maximum per child, so the card needs no extra configuration.

## 4. Default parent guidelines (for PM review; editable)
> Je helpt een ouder om voor een kind een haalbare studieplanning te maken. Je praat met de ouder, niet met het kind.
> - Geef eerst een overzicht van toetsen, grote opdrachten en huiswerk in de gevraagde periode, en wijs op drukke dagen.
> - Stel een planning voor met deelstappen van 15–45 minuten, elk met een geschatte tijd, verspreid over de dagen vóór de deadline.
> - Houd je aan het dagmaximum van het kind en laat de dag vóór een toets ruimte voor herhalen.
> - Leg de planning eerst voor en voer wijzigingen pas door als de ouder akkoord geeft.
> - Pas voortgang alleen aan als de ouder zegt dat het kind iets af heeft.
> - Maak geen huiswerk of opdrachten; de planning is bedoeld om het kind zelfstandig te laten werken.
> - Spreek Nederlands, tenzij de ouder een andere taal gebruikt.

## Contract changes (`docs/reference/homework-websocket.md`)
- Subtask fields:
  - `minutes` (int | null);
  - `created_by` gains `"parent"`.
- `add_subtask` and `update_subtask` take an optional `minutes`, with the error `invalid_minutes`.
- The subscribe payload gains `daily_max_minutes` per child list.

## Phases
- **A, backend:**
  - roles and migration, parent guidelines, the daily maximum, `minutes`;
  - `created_by: "parent"`, `get_overview`, the prompt, the logbook;
  - the WebSocket API, services, translations and tests (including security: a parent linked to children A and B
    cannot reach child C; a student linked to A sees no overview of B).
- **B, card and docs:**
  - the time on subtasks, the day total with the maximum warning, the time field in the forms, the "Ouder" chip;
  - README NL/EN: parent setup, roles and the daily maximum, an example conversation;
  - screenshots.
  - Then release **1.7.0**.

## Acceptance criteria
- [ ] Both phases reviewed; CI green; version 1.7.0; CHANGELOG (with a downgrade note); README NL/EN.
- [ ] **PM test:**
  - link your own HA user as Ouder to two children;
  - ask your AI for "overzicht volgende week" and a study plan for a test;
  - check the subtasks with times and the "Ouder" chip on the card;
  - check the day totals and the warning above the maximum;
  - check that a student user only sees their own child and gets "AI" chips.
