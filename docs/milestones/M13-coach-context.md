# M13 — Context notes for the AI coach (release 1.8.0)

| | |
|---|---|
| Status | **Draft — awaiting PM approval** |
| Branch | `claude/jolly-mayer-i2h3oo` |
| Refs | M10–M12 · `custom_components/magister/coach.py` · `docs/reference/homework-websocket.md` |

## Goal
Let the AI assistants of a student and a parent **store and retrieve context** per child, subject and homework item.
Examples are the books and tools in use ("Engels: Stepping Stones, woordjes in WRTS"). Also let them store
**circumstances for a period** ("wo 18 nov: zwemwedstrijd") that can lower the daily study maximum.

## PM decisions (2026-11-16)
| # | Decision |
|---|---|
| 1 | Context at four levels: **child**, **subject**, **homework item**, and **circumstance** (a period with start and end date). A circumstance expires after its end date. |
| 2 | A circumstance can set a **daily maximum for its days**. The card's day total and warning, `get_overview` and the prompt use the effective maximum. |
| 3 | Both the student's and the parent's AI can write and read context. A parent can mark a note **"alleen ouders"**; the student's AI never sees it. |
| 4 | Context is reached **only through the AI**, with no card UI in this version. There is also a **function to delete all context of a subject or a child**. |
| 5 | Privacy: the AI gets clear **instructions on what must not be stored** (below). Item notes are removed with their item, circumstances after their end date, and child and subject notes when someone deletes them. |
| 6 | Limits: **500 characters** per note, **50 notes** per child. Expired circumstances don't count. |

## Data model
- Context is stored per config entry and child, in the existing homework store under a new `context` key. The store minor
  version goes up; the major version stays 1, so a downgrade ignores the key.
- A note has these fields:

  ```
  {id, scope: "child"|"subject"|"item"|"period", subject?, item?, start?, end?, daily_max_minutes?,
   visibility: "all"|"parents", text, created_by: "student"|"parent", updated (ISO date)}
  ```
- How each field works:
  - `subject` is the subject name as Magister shows it in the schedule, compared case-insensitively. The tools refuse a
    subject the child doesn't have (`unknown_subject`). They check against the subjects in the fetched window and in
    existing notes.
  - `item` is an appointment id. Item notes are pruned together with the item's other planner data.
  - `period`: `start` ≤ `end`, each a local date; it can last at most 92 days.
    - It is pruned when `end` is before today.
    - An optional `daily_max_minutes` (0–480, step 15) applies to every day in the period.
    - When several periods overlap, the lowest maximum wins.
  - `visibility: "parents"` can only be set by a user with the Ouder role.
- The **effective daily maximum** for a date is the lowest period maximum for that date, otherwise the child's daily
  maximum. One function, used by `get_overview`, the prompt and the card payload.

## Tools (additions to `magister_coach`)
All tools stay scoped to the caller's accessible children, as in M10–M12.

| Tool | Description |
|---|---|
| `list_context(child?, scope?, subject?, item?, include_expired?)` | Read-only. The notes the caller may see; a student never gets `visibility: "parents"` notes. |
| `add_context(child?, scope, text, subject?, item?, start?, end?, daily_max_minutes?, visibility?)` | Adds a note. |
| `update_context(child?, id, text?, start?, end?, daily_max_minutes?, visibility?)` | Changes a note. |
| `delete_context(child?, id)` | Deletes one note. |
| `clear_context(child?, subject?)` | Deletes all notes of a subject, or of the whole child. **Parents only** (`not_allowed_for_role` for students). Destructive annotation; the description says to ask for confirmation first. |

- **Rights:**
  - A student can add, change and delete only notes with `visibility: "all"`.
  - A student cannot change a parent's notes (`not_allowed_for_role`).
  - A parent can do everything.
- **Validation errors:** `text_too_long`, `too_many_notes`, `unknown_subject`, `item_not_found`, `invalid_period`, `invalid_daily_max`,
  `context_not_found`, `not_allowed_for_role`, `invalid_format`.
- **Other tools:**
  - `list_homework` items gain `context`: the item's own notes and the subject's notes that the caller may see.
  - `get_overview` days use the effective maximum and show which period lowered it, as an id, without text for a student
    when the period is parents-only.
- **Logbook** for every successful write, without the note text:
  - "AI-coach: context toegevoegd (Engelse taal)";
  - "Ouder via AI: context gewist (Engelse taal)".

  No-op writes are not logged.

## Prompt
- For each accessible child, the prompt includes:
  - the child-level notes;
  - the circumstances from today to today + 14 days;
  - the effective maximum per day where it differs from the normal one.

  It includes only what the caller may see. Subject and item notes are read through the tools, which keeps the prompt short.
- **Rules for context** (also in the tool descriptions):
  - Store only what helps planning and coaching: books and tools, the way of learning, agreements, and the time
    available (circumstances).
  - **Never store:**
    - medical or health information, diagnoses or medication;
    - religion, beliefs or ethnicity;
    - family problems or conflicts;
    - grades or personal information of other people (classmates, siblings, teachers);
    - passwords, login data or contact details.
  - If the user wants to store something like that, don't store it; explain briefly why, and suggest a neutral wording such
    as "weinig tijd" or "rustige week".
  - Keep notes short and factual. Say what you store, and ask before storing anything about the student's circumstances.
  - Don't put "alleen ouders" notes in conversation with a student; a student's AI never receives them.

## Deleting context outside the AI (PM decision 4)
- **Options flow:** a new item under AI-coach, "Context wissen" / "Clear context".
  - Choose the child, then "alle context" or one subject (a list of the subjects that have notes), then confirm.
  - It shows the number of notes that will be deleted.
- **Service:** `magister.clear_coach_context` with `config_entry_id`, `child` and an optional `subject`. It returns the number deleted.
- Removing a child from the integration, or deleting the config entry, removes its context too.

## Card
- No UI for the notes themselves.
- The payload gains `daily_max_overrides: {"YYYY-MM-DD": minutes}` for dates in the shown window. The day total and warning
  use the effective maximum.
- The contract is updated; the card change is small.

## Diagnostics
Counts only: notes per scope and how many are parents-only. No text, subjects or ids.

## Phases
- **A, backend:**
  - the data model and store, the effective maximum, and the tools;
  - the rights and visibility, the prompt and its rules, the logbook;
  - the options flow "Context wissen", the service, pruning, the contract, translations and tests.
  - The security tests check that:
    - a student never sees parents-only notes, in any tool, the prompt or the overview text;
    - nothing crosses between children;
    - the limits hold.
- **B, card and docs:**
  - the card uses `daily_max_overrides`;
  - README NL/EN: a section on context, with what to store and what not, deleting, and privacy;
  - screenshots if the card changes visibly.
  - Then release **1.8.0**.

## Acceptance criteria
- [ ] Both phases reviewed; CI green; version 1.8.0; CHANGELOG (with the downgrade note: 1.7.x ignores context and overrides); README NL/EN.
- [ ] **PM test:**
  - As a parent, store the books for one subject and a circumstance with a lower maximum on one day.
  - As a student, ask what the AI knows. A parents-only note must not appear.
  - Check that the card shows the lower maximum that day.
  - Delete a subject's context through Configure → AI-coach → Context wissen.
  - Try to store something medical. The AI should refuse and suggest a neutral wording.
