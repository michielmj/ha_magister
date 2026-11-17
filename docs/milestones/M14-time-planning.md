# M14 — Time planning with subtasks, a daily maximum per weekday and proposals (release 1.9.0)

| | |
|---|---|
| Status | **Approved by PM (2026-11-17)** |
| Branch | `claude/jolly-mayer-i2h3oo` |
| Refs | M9 (subtasks), M11 (minutes, daily maximum), M13 (circumstances) · `docs/reference/homework-websocket.md` |

## Background
The day total and the daily maximum only count the minutes of subtasks. Regular homework has no time, so in practice
the maximum only covers extra study time. The PM decided how time planning should work (2026-11-17).

## PM decisions (2026-11-17)
| # | Decision |
|---|---|
| 1 | Planning with time is **optional**: it is useful in some periods, e.g. preparing for a test week. Without subtasks nothing changes. |
| 2 | When you plan with time, you do it **with subtasks, also for regular homework**. The AI coach creates subtasks for regular homework too. |
| 3 | Homework is **not** done on the day it is due. A subtask is planned on the day the work is done. |
| 4 | The time of a subtask depends on the **size of the work**, not on a fixed time per subject. The AI estimates it from the homework text. |
| 5 | **Every day** can be a homework day, weekends included. The **daily maximum is set per weekday** (Monday to Sunday), per child. |
| 6 | Card: **subtasks get a different colour**, and an item that has subtasks gets a **marker** showing that subtasks exist. |
| 7 | **Basic rule: the student decides** about their own study plan and time. The parent and the coach support. |
| 8 | The coach may **propose** a change to the daily maximum, in consultation with the student or a parent, e.g. for a test week. **The student must accept it.** Until then it has no effect. This applies to a period (a circumstance) **and** to the weekday values. |
| 9 | The student accepts **on the card or in the conversation**; in the conversation only after an explicit "yes". A proposal made through a **parent's** AI also needs the student's acceptance. |
| 10 | A proposal that is not answered **expires** (a period proposal when the period starts; a weekday proposal after 7 days). |

## Design
### Daily maximum per weekday
- Per child, there are seven values (Mon–Sun), each 0–480 in steps of 15. **0 means "no study planned"**: any planned minutes on that day are over the maximum.
- **Migration:** the existing single `daily_max_minutes` becomes the value for all seven days.
  - Default: 90 for every day, as now.
  - Stored with the weights as `daily_max_weekdays: [mon, …, sun]`, and only when it differs from the default.
  - The store and options keep `daily_max_minutes` as a 1.8 mirror. This is the Monday value, so a downgrade keeps a sensible single value.
- **Options flow:** "Dagmaximum studietijd" now shows seven number fields (Maandag … Zondag), with the child choice as now.
- **Effective maximum for a date:** the lowest maximum of a circumstance on that date, otherwise the weekday value. It is still one function, used by:
  - `get_overview`;
  - the prompt;
  - the card payload.
- **Payload:** the card payload gains `daily_max_weekdays`. The top-level `daily_max_minutes` stays, holding the Monday value for older cards. `daily_max_overrides` now lists only dates where a circumstance gives a value different from **that weekday's** value.
- **Coach tools:**
  - `list_children` returns `daily_max_weekdays`;
  - `get_overview` days already carry `daily_max_minutes`, which is now the effective value for that date.

### Proposals for the daily maximum (PM decisions 7–10)
- **The AI never changes a daily maximum directly.** Every change through the AI is a **proposal**. This replaces M13's direct `daily_max_minutes` on circumstances: a circumstance written through the AI can still be added without a maximum. A maximum is always a proposal.
- **Two kinds of proposal:**
  - **period:** a date range inside the sync window, a maximum per day (one value for all days of the period), and a short reason ("Toetsweek"). Once accepted, it becomes a circumstance with that maximum, as in M13.
  - **weekdays:** seven new weekday values and a reason. Once accepted, they replace the child's weekday maximums.
- **States:** `proposed` → `accepted` | `rejected` | `expired`. A period proposal expires when its first day starts unanswered. A weekday proposal expires 7 days after it was made.
  - Each child has at most 5 open proposals.
  - Answered and expired proposals are kept for 14 days for the history, then pruned.
- **Who may accept or reject:**
  - a Home Assistant user linked as **Leerling** for that child, on the card or through their AI;
  - when the child has **no** Leerling user linked (a child who does not use the app), a user linked as **Ouder**, or an administrator, may answer on the child's behalf. The logbook says so.
  - A parent's AI can make a proposal, but cannot answer it while the child has a Leerling user.
- **Through the AI:**
  - `propose_daily_max(child?, kind, start?, end?, minutes? | weekdays?, reason)`;
  - `respond_to_proposal(child?, id, answer: accept|reject)`. Its description says: only call this after the student has said yes or no explicitly in this conversation;
  - `list_proposals(child?, include_closed?)`.
  - `get_overview` days show any open proposal that covers them (`proposal: {id, minutes}`).
  - The prompt lists the open proposals.
- **WebSocket and card:** a new command `magister/homework/respond_proposal` (`entity_id`, `id`, `answer`) with the same rights check, using `connection.user`. The payload gains `proposals` (open ones, plus those answered in the last 14 days).
- **Logbook:** "AI-coach: voorstel dagmaximum (Toetsweek)", "Voorstel dagmaximum geaccepteerd door <first name of the HA user>" / "afgewezen", "… namens het kind" and "verlopen". No other personal data.
- **Options flow:** the weekday maximums stay editable by an administrator under Configureer → Dagmaximum studietijd ("beheer"). The README explains that, following the basic rule, changes are best made with the student, through a proposal.

### Coaching guidelines and prompt
- The planner rules in the prompt and the tool descriptions say:
  - planning with time is optional, and done with subtasks;
  - when the user wants a time plan for a period, create subtasks **for every piece of homework and test preparation in that period**, regular homework included;
  - estimate each subtask's minutes from the size of the work in the homework text (number of exercises, pages, words to learn), in steps of 5, and say it is an estimate;
  - plan a subtask on the day the work is done: **before** the due day, normally the previous day or earlier. The due day only works for something planned before the lesson starts, which is not the default;
  - keep each day within that date's effective maximum, using `get_overview`;
  - a weekday maximum of 0 means no planned study that day.
- The **default coaching guidelines** (student and parent) replace the fixed "about 1.5 hours of extra work per school day" with "keep to the child's daily maximum for that day". Guidelines a parent has edited are not changed. The README says how to reset them to the new default.

### Card
- **Subtask rows** get a distinct colour: a left border and a light tint, using a theme colour (e.g. `--info-color`) with a fallback. They stay readable in light and dark, with sufficient contrast. The "AI" and "Ouder" chips stay.
- **Proposals:** at the top of the card, each open proposal shows as a block in the subtask colour: "Voorstel van de coach: Toetsweek 23–27 nov, max 2 u per dag", or the seven weekday values. It has **Accepteren** and **Afwijzen** buttons, with a confirm step for accepting.
  - The buttons are shown to everyone. The backend enforces who may answer and shows a translated message when someone is not allowed.
  - Days covered by an open period proposal show "voorstel: max 2 u" next to the day total.
  - Answered proposals are listed with the "Eerder" switch.
- **Items with subtasks** get a marker next to the title: an icon plus "3 deelstappen" / "3 subtasks", in the same colour as the subtasks. It has an accessible label ("heeft 3 deelstappen") and is visible on touch devices.
  - The existing "x van y deelstappen" progress line stays.
  - The marker is also shown on the item when it appears on a day other than its subtasks' days.
- **Day total** uses that weekday's maximum (or the circumstance's). "/ max …" and "(aangepast)" mean: different from **that weekday's** normal value.
- Screenshots: subtasks in the new colour, one item with the marker, and a weekend day with a different maximum.

### Small follow-ups from 1.8.0 (included)
- `get_overview` tool description: a circumstance can raise or lower the maximum, and `daily_max_period` has no text for a student when the note is parents-only.
- README tip: after an update that adds tools, reload the connector's tools in Claude, and start a new conversation if needed.

## Phases
- **A, backend:**
  - weekday maximums (store, migration, options flow, effective maximum, payload, tools);
  - proposals (store, states and expiry, rights, the AI tools, the WebSocket command, logbook);
  - prompt, rules and default guidelines;
  - contract, translations, tests.
- **B, card and docs:**
  - subtask colour, the item marker, the day total per weekday, proposals with accept/reject;
  - Vitest tests, bundle, screenshots;
  - README NL/EN: time planning, the weekday maximum, an example ("plan de toetsweek met tijd").
  - Then release **1.9.0**.

## Acceptance criteria
- [ ] Both phases reviewed; CI green; version 1.9.0; CHANGELOG (with a downgrade note: 1.8.x uses the Monday value for every day); README NL/EN.
- [ ] **PM test:**
  - set different maximums for weekdays and the weekend;
  - ask the AI for a time plan for a test week, and check that regular homework gets subtasks with estimated times on the days before it is due;
  - check the colours and markers on the card, and the day totals against each weekday's maximum;
  - let the parent's AI propose a test-week maximum, check that it has no effect until the student accepts it (on the card, or with an explicit "yes" in the student's conversation), and check the logbook;
  - let the coach propose new weekday values, reject them, and check that nothing changed;
  - leave a proposal unanswered until its period starts, and check that it expires.
