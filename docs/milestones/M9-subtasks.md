# M9 — Subtasks for homework (release 1.5.0)

| | |
|---|---|
| Status | **Approved by PM (2026-11-14)**, via the survey answers below |
| Branch | `claude/jolly-mayer-i2h3oo` |
| Refs | M5–M8 · `docs/reference/homework-websocket.md` (binding, updated for 1.5.0) |

## Goal
Let a parent or child split homework, especially a test, into **subtasks** ("deelstappen") planned on earlier days.
Unfinished subtasks roll forward day by day, but never past the lesson.

## PM decisions (survey 2026-11-14)
| # | Decision |
|---|---|
| 1 | A subtask has a **title** and a **planned date**, and uses the same **0/25/50/75/100 progress steps** as items (done = 100, untick restores the last partial value). |
| 2 | Subtasks appear on the card on their **current date**, with a reference to the item ("↳ voor Proefwerk Engels (di 17 nov)"). The item shows "x van y deelstappen" on its due day. |
| 3 | Subtasks count in the progress bars and sensors in the period of their **current date** (rule below). |
| 4 | Subtasks also appear in **HA's to-do list** as separate items with their current date. |
| 5 | A new subtask's date defaults to **today**. It can be changed; the latest allowed date is the lesson's date. |
| 6 | Subtasks are allowed on **all** homework items. |
| — | An item with subtasks gets a **derived** progress: the plain mean of its subtasks' progress. Its own progress setting is not used while it has subtasks; it applies again when all subtasks are deleted. |
| — | On a **disabled** item (M8), subtasks are hidden and not counted until the item is restored. |

## Rules (one implementation in `api/homework.py`, used by sensors, payload, to-do, count)
- **Current date** of a subtask, all in local Europe/Amsterdam dates:
  - not done: `min(max(planned, today), item_date)`. If the item date has passed, the subtask stays on the item date, overdue;
  - done: the date it was completed, stored as `completed_on` and clamped the same way. A done subtask no longer moves.
  - Rolling uses **calendar days** (weekends included).
- **Derived item progress** = mean(subtask progress), rounded half up. The item is completed when every subtask is 100.
- **Periods / weights:** an item with n > 0 subtasks is not counted itself. Instead each subtask is an entry with
  weight `w_item / n` and its own progress, counted in the period of its **current date**. The weights in a period
  therefore still add up to the item's weight across all periods. Items without subtasks count as before.
  `items`/`completed` in the period summaries count **entries** (items without subtasks + subtasks).
- **To-do count:** open entries with a current date ≥ today: items without subtasks + subtasks.
- **HA to-do list:** the item stays listed (status completed when derived progress is 100). Each subtask is listed as
  `↳ <subject>: <title>` (Architect decision: the subject, e.g. "↳ Engels: H4 woordjes") with its current date as due. Ticking a subtask in HA sets 100 / restores its last partial value.
  Ticking an item that has subtasks in HA is refused with a translated error ("has subtasks").
- **Validation:**
  - title: 1–100 characters, trimmed;
  - planned date: `today ≤ planned ≤ item_date`, or exactly `item_date` when that is already today or in the past;
  - at most 20 subtasks per item;
  - not allowed on disabled items.
- **Storage:** `items[uid].subtasks = [{"id", "title", "planned", "progress", "last_partial", "completed_on"}]`.
  - The store minor version goes to 4 (major stays 1).
  - Subtasks are pruned together with their item entry.
  - The item entry is kept while it has subtasks.
- **Subtask uid:** `<item uid>:sub:<id>`. It is used in `set_progress` and in HA's to-do list.

## API (contract updated in `docs/reference/homework-websocket.md`)
- Payload items gain `subtasks` (with current date, overdue flag and progress) and `derived` (bool).
- `set_progress` accepts a subtask uid. For an item with subtasks it returns `item_has_subtasks`.
- New commands `add_subtask`, `update_subtask` (title and/or planned date) and `delete_subtask`.
- New services with the same validation: `magister.add_homework_subtask`, `magister.update_homework_subtask`, `magister.delete_homework_subtask`.

## Card
- On an item: a "+ deelstap" action opens a small inline form (title, date with min today / max item date, default today) to add a subtask.
- Subtask rows on their current day:
  - an indented "↳" row with title, a reference to the item (label, subject, due date) and an overdue marker;
  - the checkbox and progress steps;
  - edit (title/date) and delete (with confirm).
- The item row (on its due day) shows "x van y deelstappen" plus the derived percentage as a read-only bar or segments.
  Its own progress controls are hidden while it has subtasks.
- Completed subtasks follow the "Afgerond" switch; past days follow "Eerder" (overdue subtasks are always shown, on today).
- NL/EN texts, keyboard and screen-reader accessible, optimistic UI with rollback.

## Phases
- **A, backend:** rules, store, API, services, to-do, tests.
- **B, card:** UI, tests, bundle, screenshots, README.
- Then release **1.5.0**.

## Acceptance criteria
- [ ] Both phases reviewed; CI green; version 1.5.0; CHANGELOG (incl. downgrade note: 1.4.0 ignores subtasks and keeps its own progress); README NL/EN.
- [ ] **PM test on HAOS:**
  - add 3 subtasks to a Proefwerk (today, tomorrow, the day before the test);
  - leave one undone overnight and check that it moves to the next day;
  - check the derived percentage and the bars;
  - check the subtasks in HA's to-do list;
  - delete all subtasks and check that the item's own progress returns.
