# M12 — AI coach: fixes from the live test (release 1.7.1)

| | |
|---|---|
| Status | **Approved by PM (2026-11-15)** |
| Branch | `claude/jolly-mayer-i2h3oo` |
| Refs | M10, M11 · `docs/plan/implementation-plan.md` (follow-ups 2026-11-15) · `custom_components/magister/coach.py` |

## Background
On 2026-11-15 the PM connected Claude to the coach through a remote connector, and the Architect ran a read and write
test as a parent. Everything worked. The test also showed three rough edges and several setup steps the README is missing.

## Scope
1. **Shorter overdue list.** `list_homework` with no `start` lists the open overdue items of the **last 7 days** only
   (due date ≥ today − 7).
   - A new argument `overdue_days` (1–35, default 7) widens the window.
   - `include_overdue: false` still switches it off.
   - The tool description says what the default is and how to ask for more.
   - Reason: a child who never ticks items got about 35 old items, which was noise for the AI.
2. **Cancelled lessons are never overdue.** Exclude items with `cancelled: true` from the overdue part of
   `list_homework`. They are still listed when they fall inside the requested `start`–`end` window, marked
   `cancelled: true`, as now.
3. **A clearer message when the coach is linked but not enabled.**
   - When the calling user is linked to one or more children whose coach is **not enabled**, and to no enabled child,
     the tools return the new error `coach_not_enabled`. Its message is "You are linked, but the AI coach is not
     enabled for this child. An administrator can enable it in Settings > Devices & services > Magister > Configure >
     AI coach > Settings per child."
   - The message names no children.
   - The prompt says the same.
   - Otherwise `not_linked` stays as it is.
   - Security: this reveals only that the user is linked, which the user's administrator set up; no data.
4. **README NL/EN: connecting Claude, as verified by the PM.**
   - Make the **remote connector** the first method, and the local bridge the alternative for setups without HTTPS
     from the internet.
   - Connector URL: `https://<your HA>/api/mcp`.
   - In Claude:
     - Authentication "Sign in now";
     - OAuth client **"Use Claude's published identity"** (the default), no headers. Verified by the PM once the
       reverse-proxy settings below were correct; before that it failed with "couldn't register", because HA built
       its login metadata from the wrong (internal) address.
     - Fallback: "Use your own OAuth client" with Client ID `https://claude.ai/` and no secret. HA accepts a client ID
       on the same host as the return address.
   - HA must be reachable from the internet on port 443.
   - Behind a reverse proxy (e.g. the NGINX add-on), `use_x_forwarded_for: true` and `trusted_proxies` are **required**,
     with the example for the add-on network `172.30.33.0/24` and a short explanation.
   - Settings for the student's or parent's HA user:
     - "Can only log in from the local network" must be **off**;
     - "Require an administrator account" off in the MCP Server, saved with the **last** Submit.
   - With several Magister logins, enable and link the coach in **each** of them.
   - Troubleshooting:
     - "Couldn't reload tools from the server" (check the admin requirement and local-only login);
     - "not linked" / "coach not enabled";
     - "Couldn't register": check the reverse-proxy settings first (open `https://<your HA>/.well-known/oauth-authorization-server`
       from outside; the addresses must start with your public `https://` address), then try the fallback client ID.
   - Don't include the PM's address or any names.
5. **Spike doc** `docs/design/mcp-claude-desktop-spike.md`: record the outcome of the live test (which option worked, which failed).

## Out of scope / unchanged
- A parent's AI may still disable labels (M11 decision 1; confirmed by the live test that restoring works).

## Phases
One phase (backend + README) with Developer → Reviewer, followed by a verification round. No card changes. Release **1.7.1**.

## Acceptance criteria
- [ ] Reviewed; CI green; version 1.7.1; CHANGELOG; README NL/EN.
- [ ] Tests:
  - the overdue window (default 7, `overdue_days`, the bounds);
  - cancelled items are not overdue;
  - `coach_not_enabled` versus `not_linked`, with no child names in either.
- [ ] **PM check:**
  - ask the AI for a child's homework and see only last week's overdue items;
  - temporarily disable a child's coach and see the new message.
