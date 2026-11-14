# M10 — AI homework coach via MCP (release 1.6.0)

| | |
|---|---|
| Status | **Approved by PM (2026-11-14)** |
| Branch | `claude/jolly-mayer-i2h3oo` |
| Refs | M5–M9 · `docs/reference/homework-websocket.md` · HA 2026.10 `mcp_server` + `helpers/llm.py` |

## Goal
Let a student link an AI assistant to **their own** schedule and homework planner, so the AI can coach and help plan:
read the schedule and homework, create and adjust subtasks, set progress, and manage labels.

## PM decisions (2026-11-14)
| # | Decision |
|---|---|
| 1 | A student may use **their own AI account**, but only where the AI provider's terms allow it (age limits). The README states this responsibility clearly. Access is **opt-in per child**. |
| 2 | **Linking:** each student gets their own **non-admin HA user**, linked to their child under Configure → "AI-coach". A parent user may be linked to several children. |
| 3 | **Write scope:** subtasks, progress, **and labels**: manual labels add/remove, Magister label overrides replace/disable/clear. Nothing is written to Magister, and settings and weights cannot be changed. |
| 4 | **Coaching guidelines:** a default set (below, for PM review), **editable per child** in the options. |
| 5 | **Homework texts are always shared** with the AI (needed for coaching). Teacher names/codes and other children are never shared. |
| 6 | First test client: **Claude desktop app**. |

## Architecture (verified against the HA 2026.10 source)
- The integration registers an **LLM API** `magister_coach` ("Magister huiswerkcoach") with `homeassistant.helpers.llm.async_register_api`.
- HA's built-in **Model Context Protocol Server** integration (`mcp_server`) serves it to MCP clients. Its main endpoint
  `/api/mcp` serves the LLM APIs chosen in its settings. The setup is: select **only** "Magister huiswerkcoach",
  and set "require admin" **off**, so non-admin student users may connect.
  - The per-API endpoint `/api/mcp/<api_id>` requires admin for non-Assist APIs, so students use the main endpoint.
  - Assist stays reachable for anyone at `/api/mcp/assist`, but only with entities exposed to Assist; the README explains this.
- Every tool call receives `llm_context.context.user_id`. The tools resolve **which children this HA user is linked to**,
  and refuse anything else. An unlinked user sees no data, and the tools explain how to get linked.
- The same API also works with HA's own conversation agents (Assist with an AI model).
- **Connection from the Claude desktop app** (to be verified in Phase A as a spike; the result goes in the README). Two options:
  - (a) a remote MCP connector to `https://<ha>/api/mcp` with HA's OAuth login, which needs HA reachable over HTTPS;
  - (b) a local bridge (e.g. `mcp-proxy`) with a long-lived access token of the student's HA user, which works on the home network.

  The supported method(s) are documented step by step.

## Linking and settings (options flow, new menu item "AI-coach")
- Per child:
  - **enabled** (default off);
  - **linked HA users** (a multi-select of non-system HA users);
  - **coaching guidelines** (multiline text; empty = the default text below; a "reset to default" option).
- A user linked to several children (a parent) must pass `child` in tools. A user linked to exactly one child may omit it.
- Changes take effect without a reload.

## Tools (LLM API; English names and descriptions; data in Dutch as in Magister)
Each tool is properly annotated (read-only / writes), validates input, and only touches the linked children.

Read (read-only):
- `list_children`: the children this user may access (name = first name only, id).
- `get_schedule(child?, start, end)`: lessons and appointments in the window (date, time, lesson hour, subject, location,
  cancelled, labels incl. overrides). No teacher names or codes.
- `list_homework(child?, start?, end?, include_completed?)`: homework items with labels, text, due, progress, derived,
  and subtasks (incl. current date, overdue).
- `get_progress(child?)`: the next school day / this week / next week values (as the sensors).
- `list_label_options(child?)`.

Write (reversible; each writes a **logbook** entry such as "AI-coach: deelstap 'H4 woordjes' toegevoegd aan Proefwerk Engels"):
- `add_subtask`, `update_subtask`, `delete_subtask`
- `set_progress` (item or subtask)
- `add_label`, `remove_label`
- `set_label_override` (replace / disable / clear)

These reuse the same validation and errors as the WebSocket API (`docs/reference/homework-websocket.md`).

Marker: subtasks created through the AI get `created_by: "ai"` (contract addition). The card shows a small "AI" marker on them.

The **API prompt** (sent to the AI with the tools) contains:
- today's date and time zone;
- the rules of the planner (rolling subtasks, derived progress, periods);
- the child's **coaching guidelines**.

## 4. Default coaching guidelines (for PM review; editable per child)
> Je bent een huiswerkcoach voor een middelbare scholier. Je helpt plannen, niet het werk overnemen.
> - Maak geen huiswerk, opdrachten of toetsen voor de leerling; leg uit, stel vragen en geef hints.
> - Help toetsen en grote opdrachten op te knippen in kleine deelstappen (15–45 minuten), verspreid over de dagen vóór de deadline, en houd rekening met andere toetsen en huiswerk in dezelfde periode.
> - Plan realistisch: niet meer dan ongeveer 1,5 uur extra werk per schooldag, en laat de dag vóór een toets ruimte voor herhalen.
> - Vraag eerst wat de leerling al af heeft voordat je voortgang aanpast; pas voortgang alleen aan als de leerling dat bevestigt.
> - Wees positief en concreet. Benoem wat goed gaat. Geen druk of schuldgevoel.
> - Spreek Nederlands, tenzij de leerling een andere taal gebruikt.
> - Leg kort uit wat je in de planner verandert, en vraag toestemming voor het verwijderen van deelstappen of labels.

## Contract additions
- The subtask field `created_by: "user" | "ai"` (default `"user"` for existing subtasks).
- No other changes.

## Phases
- **A, backend:**
  - the LLM API, tools, linking, guidelines, logbook, `created_by`, translations and tests;
  - a spike: the Claude desktop connection (documented outcome).
- **B, card and docs:**
  - the AI marker on subtasks;
  - README NL/EN: "AI homework coach" covering setup (an HA user per student, linking, MCP Server settings, Claude desktop steps), privacy and age notes, and what the AI can and cannot do.
    The privacy notes must state (see `docs/design/mcp-claude-desktop-spike.md`):
    - the isolation holds only for the coach: a student's HA user, and the token on their computer, can still read all
      entity states in HA, including the other children's calendars with teacher names;
    - the token is stored in plain text; use HTTPS where possible, because `http://` sends it unencrypted on the network.
  - Then release **1.6.0**.

## Acceptance criteria
- [ ] Both phases reviewed; CI green; version 1.6.0; CHANGELOG; README NL/EN.
- [ ] Security tests:
  - an unlinked user gets nothing;
  - a user linked to child A cannot read or write child B;
  - no teacher names or codes in tool output;
  - writes are logged;
  - an admin-only per-API endpoint is not needed for students.
- [ ] **PM test:**
  - create a student HA user and link it;
  - connect the Claude desktop app with that user;
  - ask it to plan a Proefwerk;
  - check the subtasks (with the AI marker) on the card and in the logbook;
  - check that the AI cannot see the other children.
