# M15 — Study timer with notifications (release 1.10.0)

| | |
|---|---|
| Status | **Draft — awaiting PM approval** |
| Branch | `claude/jolly-mayer-i2h3oo` |
| Refs | M9 (subtasks), M11 (minutes), M14 (the student decides) · `docs/reference/homework-websocket.md` |

## Goal
A student can start a **timer on a subtask** from the card. When it runs out, the student gets a push notification on
their phone (the HA companion app) and a notification in Home Assistant (the bell, visible on the website). The
notification on the phone lets the student mark the subtask as done.

## PM decisions (2026-11-21)
| # | Decision |
|---|---|
| 1 | Option b: the timer is built into the integration (no helpers or automations needed). |
| 2 | The duration is the subtask's **estimated time**. |
| 3 | The timer can be **paused** and resumed. |
| 4 | Only **activities with a time**: subtasks that have `minutes`. |
| 5 | **No notifications to parents** (the student decides). |
| 6 | An optional **pre-warning** "nog x minuten", configurable **by the student**. |
| 7 | An optional **"nog x extra minuten"** after the timer runs out, configurable by the student. |

## Design
### Timer
- **One timer per child at a time.** Starting a timer on another subtask while one is running asks for confirmation on the card, then stops the running one.
- **States:** `running` (with its end time), `paused` (with the remaining seconds), then `finished` or `stopped`.
- **The timer lives in the backend, per config entry and child,** in the homework store under `timer`. Because of that it:
  - keeps running when the card or app is closed;
  - survives a restart: on start-up a running timer is restored, and if its end has already passed, it finishes at once and notifies;
  - is scheduled with `async_track_point_in_time`.
- **Ending the timer:**
  - Deleting or completing the subtask stops it.
  - Changing the subtask's minutes does not change a running timer.
- **Rights:** start, pause, resume, stop and extend follow the M14 answer rule:
  - a user linked as an active **Leerling** of the child;
  - or, when the child has no active student user, an **Ouder** or administrator on the child's behalf.

  The control permission on the to-do entity is also required, as for the other write commands.

### Student settings (PM decisions 6–7)
- **Per child,** stored in the homework store, set by the student (same rights as above):
  - `prewarn_minutes`: off, or 1–15. "Nog x minuten" is sent x minutes before the end. If the timer is shorter than x, the pre-warning is skipped.
  - `extra_minutes`: off, or 1–30. When the timer runs out, the notification offers **"+x min"**. Choosing it extends the timer by x minutes, and the pre-warning does not repeat. It can be chosen again each time the timer runs out.
- **Where they are set:**
  - on the card: a small ⚙ "Timerinstellingen" panel near the timer, visible to everyone, but only saved for users who may change it, as enforced by the backend;
  - through the coach's AI: a tool `set_timer_settings(child?, prewarn_minutes?, extra_minutes?)`, called only after the student asks for it.
- The administrator's options do not contain these settings.

### Notifications
- **Phone:**
  - **Target:** the administrator chooses per child the companion-app notify service(s), e.g. `notify.mobile_app_iphone_x`, under Configure → AI coach (or a new menu item "Studietimer"). The list shows only `notify.mobile_app_*` services.
  - **When it fires:**
    - **Pre-warning:** "Nog 5 minuten: <subtask title> (<subject>)".
    - **End:** "Tijd is om: <subtask title> (<subject>)", with actionable buttons **Klaar** (sets the subtask to 100), **+x min** (only when `extra_minutes` is set) and **Stop**.
  - **Notification options:** iOS `interruption-level: time-sensitive` and a `tag` per child, so a new message replaces the old one.
  - **Handling the buttons:** button presses arrive as the `mobile_app_notification_action` event. The integration handles them using the action id, which holds the entry, child and subtask, plus a random nonce so old buttons cannot act on a new timer.
- **Home Assistant (website and app):** a persistent notification for the end, removed when the timer is restarted, stopped or completed. HA cannot pop up a browser notification without the page open; the README says so.
- **To parents:** nothing. Notification targets are only the ones chosen for that child.
- **Privacy:** the texts contain only the subtask title and subject, no teacher data. The README warns that lock-screen notifications are visible to anyone holding the phone.

### Card
- **Subtask rows with `minutes`** get a ▶ button (start). While running they show a countdown and ⏸ / ▶ (pause/resume) and ■ (stop). When the timer has finished they show "Tijd is om" with **Klaar**, **+x min** (when set) and **Stop**.
- **The timer must be visible** even when the subtask is on another day: a timer bar at the top of the card for the child, with the subtask title and the countdown.
- **Accessibility:**
  - an `aria-live` region announces the pre-warning and the end (politely, not on every second);
  - keyboard operable;
  - NL/EN.
- **Countdown:** computed from the end time in the payload, so it is correct even if the card was closed.

### API
- **WebSocket commands** (contract updated):
  - `magister/homework/timer` (`entity_id`, `action`: start|pause|resume|stop|extend|done, `subtask` for start);
  - `magister/homework/timer_settings` (`entity_id`, `prewarn_minutes`, `extra_minutes`).
- **Payload:**
  - `timer: null | {subtask, state, ends_at | remaining, minutes}`;
  - `timer_settings: {prewarn_minutes, extra_minutes}`.
- **Services:** `magister.start_study_timer` and `magister.stop_study_timer`, for automations.
- **Event:** `magister_study_timer_finished` (`child` id, `subtask`) for your own automations, e.g. a light that blinks.
- **Coach tools:**
  - `set_timer_settings` (above);
  - `get_progress` / `list_homework` show a running timer;
  - the AI cannot start or stop a timer.
- **Logbook:** "Studietimer gestart / gepauzeerd / gestopt / afgelopen" with the subtask title, and "deelstap afgerond via melding".

## Phases
- **A, backend:**
  - timer store, scheduling, restore after restart;
  - rights, student settings, notify targets in the options flow;
  - notifications and action handling, persistent notification;
  - WebSocket commands, services, event, coach tool, logbook;
  - translations, contract, tests (frozen time and the restore path).
- **B, card and docs:**
  - timer controls on subtask rows, the timer bar, the ⚙ settings panel, countdown, `aria-live`, tests, bundle, screenshots;
  - README NL/EN: setting up the companion app and the notify target, what the student can configure, privacy on the lock screen.
  - Then release **1.10.0**.

## Acceptance criteria
- [ ] Both phases reviewed; CI green; version 1.10.0; CHANGELOG (with a downgrade note: 1.9.x ignores the timer); README NL/EN.
- [ ] **PM test:**
  - choose an iPhone as target for a child;
  - as the student, set the pre-warning to 2 and the extra time to 5;
  - start a timer on a 5-minute subtask and pause/resume it;
  - receive "nog 2 minuten";
  - at the end, tap "+5 min", then "Klaar", and see the subtask ticked on the card and in the logbook;
  - restart HA while a timer runs and check that it still ends and notifies.
