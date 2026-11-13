# M6 — Progress bars on the card, to-do count from today (release 1.2.0)

| | |
|---|---|
| Status | **Approved by PM (2026-11-13)**: scope as requested by the PM; start immediately |
| Branch | `claude/jolly-mayer-i2h3oo` |
| Refs | M5 · `docs/reference/homework-websocket.md` |

## PM decisions (2026-11-13)
1. The homework to-do list **counts only homework due today or later**. Past homework stays in the list and on the card,
   but does not count.
2. The card can show the **progress sensor values as horizontal bars** above the homework: **tomorrow, this week,
   next week** (option a: the same periods as the sensors), each toggled on or off separately.

## Tasks

### 1. To-do count from today (backend)
- The homework to-do entity's state, i.e. the number HA shows, counts the `needs_action` items with a local due
  date ≥ today (Europe/Amsterdam). Verify in the HA 2026.10 source how `TodoListEntity.state` is computed, and
  override it in the cleanest supported way.
- It recomputes at Amsterdam midnight, using the existing midnight handling, and on every data or progress change.
- The items themselves are unchanged: past items remain visible in HA's to-do view and on the card.
- Tests: past open items are not counted; an item due today is counted; midnight rollover; completed items are not counted.

### 2. Progress values in the WebSocket payload (backend; contract update)
- The subscribe event gains a `progress` object with the **same values as the three progress sensors**:
  `{"tomorrow": {...}, "week": {...}, "next_week": {...}}`. Each entry is `{"value": float 0–100, "items": int, "completed": int}`,
  or `null` when the sensor is unavailable (e.g. next week outside the window).
- These are pushed on every change that affects the sensors (progress, weights, data, midnight).
  The deduplication still applies.
- One implementation must feed both the sensors and the payload, so the numbers can never differ.
- The contract document `docs/reference/homework-websocket.md` is updated by the Architect (done) and is binding.

### 3. Progress bars on the card (frontend)
- New card options: `show_progress_tomorrow`, `show_progress_week`, `show_progress_next_week` (all default `false`).
  They are added to the visual editor as three toggles (NL/EN labels).
- When enabled, a compact block above the homework list shows one horizontal bar per enabled period:
  - the label ("Morgen / Tomorrow", "Deze week / This week", "Volgende week / Next week");
  - a bar filled to the value;
  - the value in % (rounded to whole numbers);
  - the number of items as secondary text ("3 van 5 klaar" / "3 of 5 done"). With 0 items: "geen huiswerk / no homework" at 100 %.
- `null`: the bar shows "niet beschikbaar / not available".
- Colours come from HA CSS variables (light/dark).
- Accessibility: `role="progressbar"` with `aria-valuenow`, `aria-valuemin` and `aria-valuemax`, plus a label.
- The editor keeps unknown config keys (as now).
- The bundle is rebuilt and committed; the README screenshots are updated (placeholder data).

### 4. Housekeeping
- Dependabot: ignore TypeScript major updates (7.x) for now, because typescript-eslint does not support them yet.
- Version 1.2.0 (manifest, pyproject, USER_AGENT, frontend/package.json + lock) and the CHANGELOG `## 1.2.0`.
- README NL/EN: the count rule and the bar options.

## Acceptance criteria
- [ ] Reviewed and approved; CI green (Python + frontend).
- [ ] **PM test on HAOS (1.2.0):**
  - the to-do count ignores past homework;
  - with the bar toggles on, the bars match the three sensors;
  - ticking an item updates the bars immediately;
  - toggles off hide the bars.
